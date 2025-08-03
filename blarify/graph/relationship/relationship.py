from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from blarify.graph.node import Node
    from blarify.graph.relationship import RelationshipType


class Relationship:
    start_node: "Node"
    end_node: "Node"
    rel_type: "RelationshipType"
    scope_text: str
    start_line: Optional[int]
    reference_character: Optional[int]

    def __init__(
        self, 
        start_node: "Node", 
        end_node: "Node", 
        rel_type: "RelationshipType", 
        scope_text: str = "",
        start_line: Optional[int] = None,
        reference_character: Optional[int] = None
    ):
        self.start_node = start_node
        self.end_node = end_node
        self.rel_type = rel_type
        self.scope_text = scope_text
        self.start_line = start_line
        self.reference_character = reference_character

    def as_object(self) -> dict:
        obj = {
            "sourceId": self.start_node.hashed_id,
            "targetId": self.end_node.hashed_id,
            "type": self.rel_type.name,
            "scopeText": self.scope_text,
        }
        
        # Add CALL-specific attributes if they exist
        if self.start_line is not None:
            obj["startLine"] = self.start_line
        if self.reference_character is not None:
            obj["referenceCharacter"] = self.reference_character
            
        return obj

    def __str__(self) -> str:
        return f"{self.start_node} --[{self.rel_type}]-> {self.end_node}"
