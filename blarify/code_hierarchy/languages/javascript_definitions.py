from typing import Set, Optional
from blarify.code_hierarchy.languages.FoundRelationshipScope import FoundRelationshipScope
from blarify.graph.relationship import RelationshipType
from blarify.graph.node import NodeLabels

from tree_sitter import Node, Language, Parser
from blarify.graph.node import Node as GraphNode

from .language_definitions import LanguageDefinitions
import tree_sitter_javascript as tsjavascript
from typing import Dict


class JavascriptDefinitions(LanguageDefinitions):
    CONTROL_FLOW_STATEMENTS = ["for_statement", "if_statement", "while_statement", "else_clause"]
    CONSEQUENCE_STATEMENTS = ["statement_block"]
    
    def get_language_name() -> str:
        return "javascript"

    def get_parsers_for_extensions() -> Dict[str, Parser]:
        return {
            ".js": Parser(Language(tsjavascript.language())),
            ".jsx": Parser(Language(tsjavascript.language())),
        }

    @staticmethod
    def should_create_node(node: Node) -> bool:
        if node.type == "variable_declarator":
            return JavascriptDefinitions._is_variable_declaration_arrow_function(node)

        return LanguageDefinitions._should_create_node_base_implementation(
            node, ["class_declaration", "function_declaration", "method_definition", "interface_declaration"]
        )

    @staticmethod
    def _is_variable_declaration_arrow_function(node: Node) -> bool:
        if node.type == "variable_declarator" and (children := node.child_by_field_name("value")):
            return children.type == "arrow_function"

    @staticmethod
    def get_identifier_node(node: Node) -> Node:
        return LanguageDefinitions._get_identifier_node_base_implementation(node)

    @staticmethod
    def get_relationship_type(node: GraphNode, node_in_point_reference: Node) -> Optional[FoundRelationshipScope]:
        return JavascriptDefinitions._find_relationship_type(
            node_label=node.label,
            node_in_point_reference=node_in_point_reference,
        )

    @staticmethod
    def _find_relationship_type(node_label: str, node_in_point_reference: Node) -> Optional[FoundRelationshipScope]:
        relationship_types = JavascriptDefinitions._get_relationship_types_by_label()
        relevant_relationship_types = relationship_types.get(node_label, {})

        return LanguageDefinitions._traverse_and_find_relationships(
            node_in_point_reference, relevant_relationship_types
        )

    @staticmethod
    def _get_relationship_types_by_label() -> dict:
        return {
            NodeLabels.CLASS: {
                "import_specifier": RelationshipType.IMPORTS,
                "import_clause": RelationshipType.IMPORTS,
                "new_expression": RelationshipType.INSTANTIATES,
                "class_heritage": RelationshipType.INHERITS,
                "variable_declarator": RelationshipType.ASSIGNS,
                "type_annotation": RelationshipType.TYPES,
            },
            NodeLabels.FUNCTION: {
                "import_specifier": RelationshipType.IMPORTS,
                "import_clause": RelationshipType.IMPORTS,
                "call_expression": RelationshipType.CALLS,
                "variable_declarator": RelationshipType.ASSIGNS,
            },
        }

    @staticmethod
    def _traverse_and_find_relationships(node: Node, relationship_mapping: dict) -> Optional[RelationshipType]:
        while node is not None:
            relationship_type = JavascriptDefinitions._get_relationship_type_for_node(node, relationship_mapping)
            if relationship_type:
                return relationship_type
            node = node.parent
        return None

    def _get_relationship_type_for_node(
        tree_sitter_node: Node, relationships_types: dict
    ) -> Optional[RelationshipType]:
        if tree_sitter_node is None:
            return None

        return relationships_types.get(tree_sitter_node.type, None)

    def get_body_node(node: Node) -> Node:
        if JavascriptDefinitions._is_variable_declaration_arrow_function(node):
            return node.child_by_field_name("value").child_by_field_name("body")

        return LanguageDefinitions._get_body_node_base_implementation(node)

    def get_language_file_extensions() -> Set[str]:
        return {".js", ".jsx"}

    def get_node_label_from_type(type: str) -> NodeLabels:
        # This method may need to be refactored to take the node instead in order to verify more complex node types
        if type == "variable_declarator":
            return NodeLabels.FUNCTION

        return {
            "class_declaration": NodeLabels.CLASS,
            "function_declaration": NodeLabels.FUNCTION,
            "method_definition": NodeLabels.FUNCTION,
            "interface_declaration": NodeLabels.CLASS,
        }[type]
