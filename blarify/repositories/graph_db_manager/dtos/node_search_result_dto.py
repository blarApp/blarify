"""NodeSearchResultDTO for representing node search results."""

from typing import Optional, Any
from pydantic import BaseModel, ConfigDict

from .edge_dto import EdgeDTO


class ReferenceSearchResultDTO(BaseModel):
    """Data Transfer Object for node search results."""

    model_config = ConfigDict(frozen=True)

    node_id: str
    node_name: str
    node_labels: list[str]
    node_path: str
    code: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    file_path: Optional[str] = None
    # Enhanced fields for relationships
    inbound_relations: Optional[list[EdgeDTO]] = None
    outbound_relations: Optional[list[EdgeDTO]] = None
    # Documentation nodes that describe this code node
    documentation: Optional[str] = None
    # Workflows that this node belongs to
    workflows: Optional[list[dict[str, Any]]] = None
