"""EdgeDTO for representing graph edges/relationships."""

from typing import List
from pydantic import BaseModel, ConfigDict


class EdgeDTO(BaseModel):
    """Data Transfer Object for graph edges/relationships."""

    model_config = ConfigDict(frozen=True)

    relationship_type: str
    node_id: str
    node_name: str
    node_type: List[str]

    def __str__(self):
        return f"relationship_type: {self.relationship_type}, node_id: {self.node_id}, node_name: {self.node_name}, node_type: {self.node_type}"
