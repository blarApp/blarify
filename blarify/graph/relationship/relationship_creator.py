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

            relationship = Relationship(
                start_node=node_referenced,
                end_node=node,
                rel_type=found_relationship_scope.relationship_type,
                scope_text=scope_text,
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
