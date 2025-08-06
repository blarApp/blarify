from typing import List, Dict, Any

from blarify.graph.relationship.external_relationship import ExternalRelationship
from blarify.graph.relationship.relationship_type import RelationshipType


class ExternalRelationshipStore:
    relationships: List[ExternalRelationship]
    
    def __init__(self) -> None:
        self.relationships: List[ExternalRelationship] = []

    def add_relationship(self, relationship: ExternalRelationship) -> None:
        self.relationships.append(relationship)

    def create_and_add_relationship(self, start_node_id: str, end_node_id: str, rel_type: RelationshipType) -> None:
        relationship: ExternalRelationship = ExternalRelationship(start_node_id, end_node_id, rel_type)
        self.add_relationship(relationship)

    def get_relationships_as_objects(self) -> List[Dict[str, Any]]:
        return [relationship.as_object() for relationship in self.relationships]
