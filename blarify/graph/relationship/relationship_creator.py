from typing import List, TYPE_CHECKING
from blarify.graph.relationship import Relationship, RelationshipType
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
    ) -> Relationship:
        scope_text = f"step_order:{step_order}" if step_order is not None else ""
        return Relationship(
            current_step_node,
            next_step_node,
            RelationshipType.WORKFLOW_STEP,
            scope_text,
        )

    @staticmethod
    def create_belongs_to_workflow_relationships_for_code_nodes(
        workflow_node: "Node", workflow_code_node_ids: List[str], db_manager
    ) -> List[dict]:
        """
        Create BELONGS_TO_WORKFLOW relationships from documentation nodes to workflow node.

        Finds all documentation nodes that describe the given code nodes and creates
        BELONGS_TO_WORKFLOW relationships from documentation nodes to the workflow node.

        Args:
            workflow_node: The workflow InformationNode
            workflow_code_node_ids: List of code node IDs that are part of the workflow
            db_manager: Database manager to query for documentation nodes

        Returns:
            List of relationship dicts suitable for database insertion via create_edges()
        """
        # Query to find documentation nodes that describe these code nodes
        doc_query = """
        UNWIND $workflow_code_node_ids AS codeNodeId
        MATCH (doc:INFORMATION {layer: 'documentation'})-[:DESCRIBES]->(code:NODE {node_id: codeNodeId})
        RETURN doc.node_id as doc_id
        """
        doc_result = db_manager.query(
            cypher_query=doc_query, parameters={"workflow_code_node_ids": workflow_code_node_ids}
        )

        # Create BELONGS_TO_WORKFLOW relationships from documentation nodes to workflow node
        relationships = []
        doc_node_ids = [doc["doc_id"] for doc in doc_result if doc.get("doc_id")]

        for doc_node_id in doc_node_ids:
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
    def create_workflow_step_relationships_for_code_sequence(
        workflow_node: "Node", workflow_code_node_ids: List[str], db_manager
    ) -> List[dict]:
        """
        Create WORKFLOW_STEP relationships between documentation nodes for a workflow sequence.

        Finds documentation nodes that describe the code nodes and creates WORKFLOW_STEP
        relationships between consecutive documentation nodes with workflow_id in scope.

        Args:
            workflow_node: The workflow InformationNode
            workflow_code_node_ids: List of code node IDs in execution order
            db_manager: Database manager to query for documentation nodes

        Returns:
            List of relationship dicts suitable for database insertion via create_edges()
        """
        if len(workflow_code_node_ids) < 2:
            return []

        # Query to find documentation nodes that describe these code nodes, maintaining order
        doc_query = """
        UNWIND range(0, size($workflow_code_node_ids)-1) AS idx
        WITH idx, $workflow_code_node_ids[idx] AS codeNodeId
        MATCH (doc:INFORMATION {layer: 'documentation'})-[:DESCRIBES]->(code:NODE {node_id: codeNodeId})
        RETURN idx, doc.node_id as doc_id
        ORDER BY idx
        """
        doc_result = db_manager.query(
            cypher_query=doc_query, parameters={"workflow_code_node_ids": workflow_code_node_ids}
        )

        # Create ordered list of documentation node IDs
        doc_nodes_by_order = {}
        for result in doc_result:
            if result.get("doc_id"):
                doc_nodes_by_order[result["idx"]] = result["doc_id"]

        # Create WORKFLOW_STEP relationships between consecutive documentation nodes
        relationships = []
        for i in range(len(workflow_code_node_ids) - 1):
            current_doc_id = doc_nodes_by_order.get(i)
            next_doc_id = doc_nodes_by_order.get(i + 1)

            if current_doc_id and next_doc_id:
                scope_text = f"step_order:{i + 1},workflow_id:{workflow_node.hashed_id}"
                relationships.append(
                    {
                        "sourceId": current_doc_id,  # Current documentation node
                        "targetId": next_doc_id,  # Next documentation node
                        "type": RelationshipType.WORKFLOW_STEP.name,
                        "scopeText": scope_text,
                    }
                )

        return relationships
