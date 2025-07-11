from typing import Dict, Optional, Set
from tree_sitter import Language, Node, Parser
from blarify.code_hierarchy.languages.FoundRelationshipScope import FoundRelationshipScope
from blarify.code_hierarchy.languages.language_definitions import LanguageDefinitions
import tree_sitter_php as tsphp

from blarify.graph.node.types.node_labels import NodeLabels
from blarify.graph.relationship.relationship_type import RelationshipType


class PhpDefinitions(LanguageDefinitions):
    """
    This class defines the PHP language server and its file extensions.
    """

    CONTROL_FLOW_STATEMENTS = ["if_statement", "while_statement", "for_statement"]
    CONSEQUENCE_STATEMENTS = ["compound_statement"]

    def get_language_name() -> str:
        return "php"

    def get_parsers_for_extensions() -> Dict[str, Parser]:
        return {
            ".php": Parser(Language(tsphp.language_php())),
        }

    def should_create_node(node: Node) -> bool:
        return LanguageDefinitions._should_create_node_base_implementation(
            node, ["class_declaration", "function_definition", "method_declaration"]
        )

    def get_identifier_node(node: Node) -> Node:
        return LanguageDefinitions._get_identifier_node_base_implementation(node)

    def get_body_node(node: Node) -> Node:
        return LanguageDefinitions._get_body_node_base_implementation(node)

    def get_node_label_from_type(type: str) -> NodeLabels:
        return {
            "class_declaration": NodeLabels.CLASS,
            "function_definition": NodeLabels.FUNCTION,
            "method_declaration": NodeLabels.FUNCTION,
        }[type]

    def get_language_file_extensions() -> Set[str]:
        return {".php"}
    
    def get_relationship_type(node, node_in_point_reference: Node) -> Optional[FoundRelationshipScope]:
        return PhpDefinitions._find_relationship_type(
            node_label=node.label,
            node_in_point_reference=node_in_point_reference,
        )
    
    def _find_relationship_type(node_label: str, node_in_point_reference: Node) -> Optional[FoundRelationshipScope]:
        relationship_types = PhpDefinitions._get_relationship_types_by_label()
        relevant_relationship_types = relationship_types.get(node_label, {})

        return LanguageDefinitions._traverse_and_find_relationships(
            node_in_point_reference, relevant_relationship_types
        )

    def _get_relationship_types_by_label() -> dict[str, RelationshipType]:
        return {
            NodeLabels.CLASS: {
                "namespace_use_declaration": RelationshipType.IMPORTS,
                "base_clause": RelationshipType.INHERITS,
                "object_creation_expression": RelationshipType.INSTANTIATES,
                "typing": RelationshipType.TYPES,
                "simple_parameter": RelationshipType.TYPES,
            },
            NodeLabels.FUNCTION: {
                "function_call_expression": RelationshipType.CALLS,
                "member_call_expression": RelationshipType.CALLS,
                "namespace_use_declaration": RelationshipType.IMPORTS,
                "assignment_expression": RelationshipType.ASSIGNS,
            },
        }
