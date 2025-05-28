from blarify.code_hierarchy.languages.FoundRelationshipScope import FoundRelationshipScope
from .language_definitions import LanguageDefinitions
from blarify.graph.relationship import RelationshipType

import tree_sitter_go as tsgo
from tree_sitter import Language, Parser

from typing import Optional, Set, Dict

from blarify.graph.node import NodeLabels
from tree_sitter import Node
from blarify.graph.node import Node as GraphNode


class GoDefinitions(LanguageDefinitions):
    CONTROL_FLOW_STATEMENTS = []
    CONSEQUENCE_STATEMENTS = []
    
    def get_language_name() -> str:
        return "go"

    def get_parsers_for_extensions() -> Dict[str, Parser]:
        return {
            ".go": Parser(Language(tsgo.language())),
        }

    def should_create_node(node: Node) -> bool:
        return LanguageDefinitions._should_create_node_base_implementation(
            node,
            ["type_spec", "type_alias", "method_declaration", "function_declaration"],
        )

    def get_identifier_node(node: Node) -> Node:
        return LanguageDefinitions._get_identifier_node_base_implementation(node)

    def get_body_node(node: Node) -> Node:
        return LanguageDefinitions._get_body_node_base_implementation(node)

    def get_relationship_type(node: GraphNode, node_in_point_reference: Node) -> Optional[FoundRelationshipScope]:
        return GoDefinitions._find_relationship_type(
            node_label=node.label,
            node_in_point_reference=node_in_point_reference,
        )

    def get_node_label_from_type(type: str) -> NodeLabels:
        return {
            "type_spec": NodeLabels.CLASS,
            "type_alias": NodeLabels.CLASS,
            "method_declaration": NodeLabels.FUNCTION,
            "function_declaration": NodeLabels.FUNCTION,
        }[type]

    def get_language_file_extensions() -> Set[str]:
        return {".go"}

    def _find_relationship_type(node_label: str, node_in_point_reference: Node) -> Optional[FoundRelationshipScope]:
        relationship_types = GoDefinitions._get_relationship_types_by_label()
        relevant_relationship_types = relationship_types.get(node_label, {})

        return LanguageDefinitions._traverse_and_find_relationships(
            node_in_point_reference, relevant_relationship_types
        )

    def _get_relationship_types_by_label() -> dict[str, RelationshipType]:
        return {
            NodeLabels.CLASS: {
                "import_declaration": RelationshipType.IMPORTS,
                "field_declaration": RelationshipType.TYPES,
                "composite_literal": RelationshipType.INSTANTIATES,
            },
            NodeLabels.FUNCTION: {
                "import_declaration": RelationshipType.IMPORTS,
                "call_expression": RelationshipType.CALLS,
            },
        }
