from dataclasses import dataclass
from tree_sitter import Node
from blarify.graph.relationship.relationship_type import RelationshipType
from typing import Optional


@dataclass
class FoundRelationshipScope:
    node_in_scope: Optional[Node]
    relationship_type: RelationshipType

    def __str__(self) -> str:
        return f"FoundRelationshipScope({self.node_in_scope}, {self.relationship_type})"