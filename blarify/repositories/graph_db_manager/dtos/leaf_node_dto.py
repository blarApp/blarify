from typing import Optional, List
from pydantic import BaseModel


class LeafNodeDto(BaseModel):
    id: str
    name: str
    labels: List[str]
    path: str
    start_line: Optional[int]
    end_line: Optional[int]
    content: str

    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "labels": self.labels,
            "path": self.path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content,
        }