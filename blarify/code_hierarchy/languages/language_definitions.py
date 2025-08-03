from abc import ABC, abstractmethod
from tree_sitter import Parser
from tree_sitter import Node as TreeSitterNode
from typing import Set, Optional, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from blarify.code_hierarchy.languages.FoundRelationshipScope import FoundRelationshipScope
    from blarify.graph.relationship.relationship_type import RelationshipType
    from blarify.graph.node.types.node_labels import NodeLabels


class BodyNodeNotFound(Exception):
    pass


class IdentifierNodeNotFound(Exception):
    pass


class LanguageDefinitions(ABC):
    CONTROL_FLOW_STATEMENTS = []
    CONSEQUENCE_STATEMENTS = []

    @staticmethod
    @abstractmethod
    def get_language_name() -> str:
        """
        This method should return the language name.

        This name MUST match the LSP specification
        https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocumentItem
        """

    @staticmethod
    @abstractmethod
    def should_create_node(node: TreeSitterNode) -> bool:
        """This method should return a boolean indicating if a node should be created"""

    @staticmethod
    def _should_create_node_base_implementation(node: TreeSitterNode, node_labels_that_should_be_created: List[str]) -> bool:
        return node.type in node_labels_that_should_be_created

    @staticmethod
    @abstractmethod
    def get_identifier_node(node: TreeSitterNode) -> TreeSitterNode:
        """This method should return the identifier node for a given node,
        this name will be used as the node name in the graph.

        This node should match the LSP document symbol range.
        """

    @staticmethod
    def _get_identifier_node_base_implementation(node: TreeSitterNode) -> TreeSitterNode:
        if identifier := node.child_by_field_name("name"):
            return identifier
        error = f"No identifier node found for node type {node.type} at {node.start_point} - {node.end_point}"
        raise IdentifierNodeNotFound(error)

    @staticmethod
    @abstractmethod
    def get_body_node(node: TreeSitterNode) -> TreeSitterNode:
        """This method should return the body node for a given node,
        this node should contain the code block for the node without any signatures.
        """

    @staticmethod
    def _get_body_node_base_implementation(node: TreeSitterNode) -> TreeSitterNode:
        if body := node.child_by_field_name("body"):
            return body

        raise BodyNodeNotFound(f"No body node found for node type {node.type} at {node.start_point} - {node.end_point}")

    @staticmethod
    @abstractmethod
    def get_relationship_type(node: TreeSitterNode, node_in_point_reference: TreeSitterNode) -> Optional["FoundRelationshipScope"]:
        """This method should tell you how the node is being used in the node_in_point_reference"""

    @staticmethod
    def _traverse_and_find_relationships(node: Optional[TreeSitterNode], relationship_mapping: Dict[str, "RelationshipType"]) -> Optional["FoundRelationshipScope"]:
        # Import FoundRelationshipScope at runtime since it's in the same module package
        from blarify.code_hierarchy.languages.FoundRelationshipScope import FoundRelationshipScope
        
        while node is not None:
            relationship_type = LanguageDefinitions._get_relationship_type_for_node(node, relationship_mapping)
            if relationship_type:
                return FoundRelationshipScope(node_in_scope=node, relationship_type=relationship_type)
            node = node.parent
        return None

    @staticmethod
    def _get_relationship_type_for_node(
        tree_sitter_node: Optional[TreeSitterNode], relationships_types: Dict[str, "RelationshipType"]
    ) -> Optional["RelationshipType"]:
        if tree_sitter_node is None:
            return None

        return relationships_types.get(tree_sitter_node.type, None)

    @staticmethod
    @abstractmethod
    def get_node_label_from_type(type: str) -> "NodeLabels":
        """This method should return the node label for a given node type"""

    @staticmethod
    @abstractmethod
    def get_language_file_extensions() -> Set[str]:
        """This method should return the file extensions for the language"""

    @staticmethod
    @abstractmethod
    def get_parsers_for_extensions() -> Dict[str, Parser]:
        """This method should return the parsers for the language"""
