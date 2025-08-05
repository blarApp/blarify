"""NodeSearchResultDTO for representing node search results."""

from typing import List
from pydantic import BaseModel

from .edge_dto import EdgeDTO


class NodeSearchResultDTO(BaseModel):
    """Data Transfer Object for node search results."""

    node_id: str
    node_name: str
    node_labels: List[str]
    path: str
    node_path: str
    code: str
    diff_text: str
    outbound_relations: List[EdgeDTO]
    inbound_relations: List[EdgeDTO]
    modified_node: bool

    class Config:
        """Pydantic configuration."""

        frozen = True
