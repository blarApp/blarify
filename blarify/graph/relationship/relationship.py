from typing import TYPE_CHECKING, Optional, Dict, Any

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
    attributes: Dict[str, Any]

    def __init__(
        self, 
        start_node: "Node", 
        end_node: "Node", 
        rel_type: "RelationshipType", 
        scope_text: str = "",
        start_line: Optional[int] = None,
        reference_character: Optional[int] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        self.start_node = start_node
        self.end_node = end_node
        self.rel_type = rel_type
        self.scope_text = scope_text
        self.start_line = start_line
        self.reference_character = reference_character
        self.attributes = attributes or {}

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
        
        # Add any additional attributes
        for key, value in self.attributes.items():
            if key not in obj:  # Don't override existing fields
                obj[key] = value
            
        return obj

    def __str__(self) -> str:
        return f"{self.start_node} --[{self.rel_type}]-> {self.end_node}"


class WorkflowStepRelationship(Relationship):
    """Specialized relationship for WORKFLOW_STEP with additional workflow-specific attributes."""
    
    step_order: Optional[int]
    depth: Optional[int]
    call_line: Optional[int]
    call_character: Optional[int]
    relationship_type: Optional[str]
    
    def __init__(
        self,
        start_node: "Node",
        end_node: "Node", 
        rel_type: "RelationshipType",
        scope_text: str = "",
        step_order: Optional[int] = None,
        depth: Optional[int] = None,
        call_line: Optional[int] = None,
        call_character: Optional[int] = None,
        relationship_type: Optional[str] = None
    ):
        super().__init__(start_node, end_node, rel_type, scope_text)
        self.step_order = step_order
        self.depth = depth
        self.call_line = call_line
        self.call_character = call_character
        self.relationship_type = relationship_type
    
    def as_object(self) -> dict:
        obj = super().as_object()
        
        # Add workflow-specific attributes if they exist
        if self.step_order is not None:
            obj["step_order"] = self.step_order
        if self.depth is not None:
            obj["depth"] = self.depth
        if self.call_line is not None:
            obj["call_line"] = self.call_line
        if self.call_character is not None:
            obj["call_character"] = self.call_character
        if self.relationship_type is not None:
            obj["relationship_type"] = self.relationship_type
            
        return obj
    
    def __str__(self) -> str:
        step_info = f" (step {self.step_order})" if self.step_order is not None else ""
        return f"{self.start_node} --[{self.rel_type}{step_info}]-> {self.end_node}"
