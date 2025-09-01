from typing import List, Dict, Any, TYPE_CHECKING
from blarify.graph.node.commit_node import CommitNode
from blarify.graph.node.documentation_node import DocumentationNode
from blarify.graph.relationship import Relationship, WorkflowStepRelationship, RelationshipType
from blarify.graph.node import NodeLabels
from blarify.repositories.graph_db_manager.dtos.code_node_dto import CodeNodeDto
from blarify.repositories.version_control.dtos.blame_line_range_dto import BlameLineRangeDto

if TYPE_CHECKING:
    from blarify.graph.graph import Graph
    from blarify.graph.node import Node
    from blarify.code_hierarchy import TreeSitterHelper
    from blarify.code_references.types import Reference


class RelationshipCreator:
    @staticmethod
    def create_relationships_from_paths_where_node_is_referenced(
        references: list["Reference"], node: "Node", graph: "Graph", tree_sitter_helper: "TreeSitterHelper"
    ) -> List[Relationship]:
        relationships = []
        for reference in references:
            file_node_reference = graph.get_file_node_by_path(path=reference.uri)
            if file_node_reference is None:
                continue

            node_referenced = file_node_reference.reference_search(reference=reference)
            if node_referenced is None or node.id == node_referenced.id:
                continue

            found_relationship_scope = tree_sitter_helper.get_reference_type(
                original_node=node, reference=reference, node_referenced=node_referenced
            )

            if found_relationship_scope.node_in_scope is None:
                scope_text = ""
            else:
                scope_text = found_relationship_scope.node_in_scope.text.decode("utf-8") if found_relationship_scope.node_in_scope.text else ""

            # Extract start_line and reference_character for CALL relationships
            start_line = None
            reference_character = None
            if found_relationship_scope.relationship_type == RelationshipType.CALLS:
                start_line = reference.range.start.line
                reference_character = reference.range.start.character

            relationship = Relationship(
                start_node=node_referenced,
                end_node=node,
                rel_type=found_relationship_scope.relationship_type,
                scope_text=scope_text,
                start_line=start_line,
                reference_character=reference_character,
            )

            relationships.append(relationship)
        return relationships

    @staticmethod
    def _get_relationship_type(defined_node: "Node") -> RelationshipType:
        if defined_node.label == NodeLabels.FUNCTION:
            return RelationshipType.FUNCTION_DEFINITION
        elif defined_node.label == NodeLabels.CLASS:
            return RelationshipType.CLASS_DEFINITION
        else:
            raise ValueError(f"Node {defined_node.label} is not a valid definition node")

    @staticmethod
    def create_defines_relationship(node: "Node", defined_node: "Node") -> Relationship:
        rel_type = RelationshipCreator._get_relationship_type(defined_node)
        return Relationship(
            node,
            defined_node,
            rel_type,
        )

    @staticmethod
    def create_contains_relationship(folder_node: "Node", contained_node: "Node") -> Relationship:
        return Relationship(
            folder_node,
            contained_node,
            RelationshipType.CONTAINS,
        )

    @staticmethod
    def create_belongs_to_workflow_relationship(documentation_node: "Node", workflow_node: "Node") -> Relationship:
        return Relationship(
            documentation_node,
            workflow_node,
            RelationshipType.BELONGS_TO_WORKFLOW,
        )

    @staticmethod
    def create_workflow_step_relationship(
        current_step_node: "Node", next_step_node: "Node", step_order: int = None
    ) -> WorkflowStepRelationship:
        scope_text = ""  # Keep scope_text empty for workflow metadata
        return WorkflowStepRelationship(
            current_step_node,
            next_step_node,
            RelationshipType.WORKFLOW_STEP,
            scope_text,
            step_order=step_order or 0,
        )

    @staticmethod
    def create_belongs_to_workflow_relationships_for_workflow_nodes(
        workflow_node: "Node", workflow_node_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Create BELONGS_TO_WORKFLOW relationships from workflow participant nodes to workflow node.

        Args:
            workflow_node: The workflow InformationNode
            workflow_node_ids: List of workflow participant node IDs

        Returns:
            List of relationship dicts suitable for database insertion via create_edges()
        """
        relationships = []

        for node_id in workflow_node_ids:
            if node_id:  # Ensure valid ID
                relationships.append(
                    {
                        "sourceId": node_id,  # Participant node
                        "targetId": workflow_node.hashed_id,  # Workflow node
                        "type": RelationshipType.BELONGS_TO_WORKFLOW.name,
                        "scopeText": "",
                    }
                )

        return relationships

    @staticmethod
    def create_describes_relationships(documentation_nodes: List[DocumentationNode]) -> List[Dict[str, Any]]:
        """
        Create DESCRIBES relationships from documentation nodes to their source code nodes.

        Args:
            documentation_nodes: List of DocumentationNode objects
            source_nodes: List of source code Node objects that the documentation describes

        Returns:
            List of DESCRIBES relationship dicts suitable for database insertion via create_edges()
        """
        describes_relationships = []
        for doc_node in documentation_nodes:
            describes_relationships.append(
                {
                    "sourceId": doc_node.hashed_id,  # Documentation node
                    "targetId": doc_node.source_id,  # Target code node
                    "type": "DESCRIBES",
                    "scopeText": "semantic_documentation",
                }
            )

        return describes_relationships

    @staticmethod
    def create_workflow_step_relationships_from_execution_edges(
        workflow_node: "Node", execution_edges: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Create WORKFLOW_STEP relationships between documentation nodes based on execution edges.

        Args:
            workflow_node: The workflow InformationNode
            execution_edges: List of execution edge dicts with caller_id, callee_id as doc IDs

        Returns:
            List of relationship dicts suitable for database insertion via create_edges()
        """
        if not execution_edges:
            return []

        relationships = []

        # Sort edges by depth to ensure proper sequencing (depth represents execution order)
        sorted_edges = sorted(execution_edges, key=lambda x: x.get("depth", 0))

        for edge in sorted_edges:
            source_doc_id = edge.get("caller_id")  # Already documentation node ID
            target_doc_id = edge.get("callee_id")  # Already documentation node ID
            step_order = edge.get("step_order", edge.get("depth", 0))  # Use step_order if available, fallback to depth

            if not source_doc_id or not target_doc_id:
                continue

            scope_text = f"workflow_id:{workflow_node.hashed_id},edge_based:true"

            # Only include call_line and call_character if they are not None
            relationship_dict = {
                "sourceId": source_doc_id,  # Source documentation node
                "targetId": target_doc_id,  # Target documentation node
                "type": RelationshipType.WORKFLOW_STEP.name,
                "scopeText": scope_text,
                "step_order": step_order,  # Store step_order as individual property
                "depth": edge.get("depth", 0),  # Store depth as individual property
            }

            # Only add call_line and call_character if they have non-null values
            call_line = edge.get("call_line")
            call_character = edge.get("call_character")

            if call_line is not None:
                relationship_dict["call_line"] = call_line
            if call_character is not None:
                relationship_dict["call_character"] = call_character

            relationships.append(relationship_dict)

        return relationships

    @staticmethod
    def create_integration_sequence_relationships(pr_node: "Node", commit_nodes: List["Node"]) -> List[Relationship]:
        """Create PR → INTEGRATION_SEQUENCE → Commit relationships.

        Args:
            pr_node: Pull request IntegrationNode
            commit_nodes: List of commit IntegrationNodes

        Returns:
            List of Relationship objects
        """
        relationships = []

        for idx, commit_node in enumerate(commit_nodes):
            rel = Relationship(
                start_node=pr_node,
                end_node=commit_node,
                rel_type=RelationshipType.INTEGRATION_SEQUENCE,
                scope_text=f"pr_{pr_node.external_id}" if hasattr(pr_node, "external_id") else "",
                attributes={"order": idx},
            )
            relationships.append(rel)

        return relationships

    @staticmethod
    def create_modified_by_relationships(
        commit_node: "Node", code_nodes: List["Node"], file_changes: List[Dict[str, Any]]
    ) -> List[Relationship]:
        """Create Code ← MODIFIED_BY ← Commit relationships.

        Args:
            commit_node: Commit IntegrationNode
            code_nodes: List of code nodes affected
            file_changes: List of file change data from GitHub

        Returns:
            List of Relationship objects
        """
        import json

        relationships = []

        for code_node in code_nodes:
            # Find the corresponding file change
            file_change = None
            for change in file_changes:
                if change.get("filename") in code_node.path:
                    file_change = change
                    break

            if not file_change:
                continue

            # Determine node specificity level
            node_type = getattr(code_node, "label", "UNKNOWN")
            if node_type == "FUNCTION":
                specificity_level = 1
            elif node_type == "CLASS":
                specificity_level = 2
            elif node_type == "FILE":
                specificity_level = 3
            else:
                specificity_level = 4

            # Build relationship attributes
            attributes = {
                "lines_added": file_change.get("additions", 0),
                "lines_deleted": file_change.get("deletions", 0),
                "change_type": file_change.get("status", "modified"),
                "file_path": file_change.get("filename", ""),
                "node_type": node_type,
                "node_specificity_level": specificity_level,
                "commit_sha": commit_node.external_id if hasattr(commit_node, "external_id") else "",
                "commit_timestamp": commit_node.timestamp if hasattr(commit_node, "timestamp") else "",
            }
            # Only add pr_number if it's not None
            if hasattr(commit_node, "metadata") and commit_node.metadata.get("pr_number") is not None:
                attributes["pr_number"] = commit_node.metadata.get("pr_number")

            # Add line ranges if available
            if "line_ranges" in file_change:
                attributes["line_ranges"] = json.dumps(file_change["line_ranges"])

            # Add patch summary if available
            if "patch" in file_change:
                attributes["patch_summary"] = file_change["patch"][:500]

            rel = Relationship(
                start_node=code_node,
                end_node=commit_node,
                rel_type=RelationshipType.MODIFIED_BY,
                scope_text="",
                attributes=attributes,
            )
            relationships.append(rel)

        # Return only the most specific relationship if multiple nodes
        if len(relationships) > 1:
            # Sort by specificity level and return the most specific (lowest level)
            relationships.sort(key=lambda r: r.attributes.get("node_specificity_level", 999))
            return [relationships[0]]

        return relationships

    @staticmethod
    def create_modified_by_with_blame(
        commit_node: CommitNode, 
        code_node: CodeNodeDto, 
        line_ranges: List[BlameLineRangeDto],
        relevant_patch: str = ""
    ) -> Dict[str, Any]:
        """Create MODIFIED_BY relationship with exact blame attribution.

        Args:
            commit_node: The commit that modified the code
            code_node: The code node that was modified (as DTO)
            line_ranges: Exact line ranges from blame (as DTOs)
            relevant_patch: The patch hunks relevant to this specific node

        Returns:
            Relationship dictionary with blame attribution
        """
        import json

        # Convert DTOs to dictionaries for JSON serialization
        line_ranges_dict = [{"start": lr.start, "end": lr.end} for lr in line_ranges]

        # Calculate total lines affected
        total_lines = sum(lr.end - lr.start + 1 for lr in line_ranges)

        # Build relationship attributes with exact blame information
        attributes = {
            # Exact line attribution from blame
            "blamed_lines": json.dumps(line_ranges_dict),
            "total_lines_affected": total_lines,
            # Node context
            "node_type": code_node.label,
            "node_path": code_node.path,
            "node_name": code_node.name,
            # Commit context
            "commit_sha": commit_node.external_id,
            "commit_timestamp": commit_node.timestamp,
            "commit_message": commit_node.title,
            "commit_author": commit_node.author,
            # Attribution metadata
            "attribution_method": "blame",
            "attribution_accuracy": "exact",
        }
        # Only add pr_number if it's not None
        if commit_node.metadata.get("pr_number") is not None:
            attributes["pr_number"] = commit_node.metadata.get("pr_number")
        # Only add relevant_patch if it's not None or empty
        if relevant_patch:
            attributes["relevant_patch"] = relevant_patch

        # Return as dictionary format for database
        # Use sourceId/targetId to match Neo4j manager expectations
        return {
            "sourceId": code_node.id,
            "targetId": commit_node.hashed_id,
            "type": "MODIFIED_BY",
            **attributes,  # Spread attributes directly into the edge object
        }

    @staticmethod
    def create_affects_relationships(commit_nodes: List["Node"], workflow_nodes: List["Node"]) -> List[Relationship]:
        """Create Commit → AFFECTS → Workflow relationships.

        Args:
            commit_nodes: List of commit IntegrationNodes
            workflow_nodes: List of workflow nodes

        Returns:
            List of Relationship objects
        """
        relationships = []

        for commit_node in commit_nodes:
            for workflow_node in workflow_nodes:
                rel = Relationship(
                    start_node=commit_node,
                    end_node=workflow_node,
                    rel_type=RelationshipType.AFFECTS,
                    scope_text="",
                    attributes={},
                )
                relationships.append(rel)

        return relationships
