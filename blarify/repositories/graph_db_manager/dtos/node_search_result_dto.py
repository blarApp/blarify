"""NodeSearchResultDTO for representing node search results."""

from typing import List
from pydantic import BaseModel, ConfigDict

from .edge_dto import EdgeDTO


class NodeSearchResultDTO(BaseModel):
    """Data Transfer Object for node search results."""

    model_config = ConfigDict(frozen=True)

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
