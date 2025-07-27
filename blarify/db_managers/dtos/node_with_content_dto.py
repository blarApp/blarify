from typing import List, Optional
from pydantic import BaseModel


class NodeWithContentDto(BaseModel):
    """DTO for nodes with full content, used in recursive DFS processing."""
    
    id: str
    name: str
    labels: List[str]
    path: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    content: str = ""
    relationship_type: Optional[str] = None  # Used when retrieved as a child

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "labels": self.labels,
            "path": self.path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content,
            "relationship_type": self.relationship_type,
        }