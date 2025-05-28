from abc import ABC, abstractmethod
from tree_sitter import Parser
from typing import Set
from blarify.code_hierarchy.languages.FoundRelationshipScope import FoundRelationshipScope
from blarify.graph.node import NodeLabels
from tree_sitter import Node
from typing import Optional, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from blarify.graph.relationship import RelationshipType


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
    def should_create_node(node: Node) -> bool:
        """This method should return a boolean indicating if a node should be created"""

    def _should_create_node_base_implementation(node: Node, node_labels_that_should_be_created: List[str]) -> bool:
        return node.type in node_labels_that_should_be_created

    @staticmethod
    @abstractmethod
    def get_identifier_node(node: Node) -> Node:
        """This method should return the identifier node for a given node,
        this name will be used as the node name in the graph.

        This node should match the LSP document symbol range.
        """

    @staticmethod
    def _get_identifier_node_base_implementation(node: Node) -> Node:
        if identifier := node.child_by_field_name("name"):
            return identifier
        error = f"No identifier node found for node type {node.type} at {node.start_point} - {node.end_point}"
        raise IdentifierNodeNotFound(error)

    @staticmethod
    @abstractmethod
    def get_body_node(node: Node) -> Node:
        """This method should return the body node for a given node,
        this node should contain the code block for the node without any signatures.
        """

    @staticmethod
    def _get_body_node_base_implementation(node: Node) -> Node:
        if body := node.child_by_field_name("body"):
            return body

        raise BodyNodeNotFound(f"No body node found for node type {node.type} at {node.start_point} - {node.end_point}")

    @staticmethod
    @abstractmethod
    def get_relationship_type(node: Node, node_in_point_reference: Node) -> Optional[FoundRelationshipScope]:
        """This method should tell you how the node is being used in the node_in_point_reference"""

    @staticmethod
    def _traverse_and_find_relationships(node: Node, relationship_mapping: dict) -> Optional[FoundRelationshipScope]:
        while node is not None:
            relationship_type = LanguageDefinitions._get_relationship_type_for_node(node, relationship_mapping)
            if relationship_type:
                return FoundRelationshipScope(node_in_scope=node, relationship_type=relationship_type)
            node = node.parent
        return None

    @staticmethod
    def _get_relationship_type_for_node(
        tree_sitter_node: Node, relationships_types: dict
    ) -> Optional["RelationshipType"]:
        if tree_sitter_node is None:
            return None

        return relationships_types.get(tree_sitter_node.type, None)

    @staticmethod
    @abstractmethod
    def get_node_label_from_type(type: str) -> NodeLabels:
        """This method should return the node label for a given node type"""

    @staticmethod
    @abstractmethod
    def get_language_file_extensions() -> Set[str]:
        """This method should return the file extensions for the language"""

    @staticmethod
    @abstractmethod
    def get_parsers_for_extensions() -> Dict[str, Parser]:
        """This method should return the parsers for the language"""
