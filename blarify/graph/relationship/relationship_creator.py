from typing import List, Dict, Any, TYPE_CHECKING
from blarify.graph.node.documentation_node import DocumentationNode
from blarify.graph.relationship import Relationship, WorkflowStepRelationship, RelationshipType
from blarify.graph.node import NodeLabels

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
                scope_text = found_relationship_scope.node_in_scope.text.decode("utf-8")

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
    def create_belongs_to_spec_relationship(workflow_node: "Node", spec_node: "Node") -> Relationship:
        return Relationship(
            workflow_node,
            spec_node,
            RelationshipType.BELONGS_TO_SPEC,
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
            step_order=step_order,
        )

    @staticmethod
    def create_belongs_to_workflow_relationships_for_workflow_nodes(
        workflow_node: "Node", workflow_node_ids: List[str]
    ) -> List[dict]:
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
    def create_belongs_to_workflow_relationships_for_documentation_nodes(
        workflow_node: "Node", documentation_node_ids: List[str]
    ) -> List[dict]:
        """
        Create BELONGS_TO_WORKFLOW relationships from documentation nodes to workflow node.

        Args:
            workflow_node: The workflow InformationNode
            documentation_node_ids: List of documentation node IDs in the workflow

        Returns:
            List of relationship dicts suitable for database insertion via create_edges()
        """
        relationships = []

        for doc_node_id in documentation_node_ids:
            if doc_node_id:  # Ensure valid ID
                relationships.append(
                    {
                        "sourceId": doc_node_id,  # Documentation node
                        "targetId": workflow_node.hashed_id,  # Workflow node
                        "type": RelationshipType.BELONGS_TO_WORKFLOW.name,
                        "scopeText": "",
                    }
                )

        return relationships

    @staticmethod
    def create_describes_relationships(documentation_nodes: List[DocumentationNode]) -> List[dict]:
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
    ) -> List[dict]:
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
