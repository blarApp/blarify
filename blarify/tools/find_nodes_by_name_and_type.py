from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager


# Pydantic Response Models (replacement for blarify DTOs)
class NodeFoundByNameTypeResponse(BaseModel):
    """Node found by name and type response model."""

    node_id: str
    node_name: str
    node_type: list[str]
    file_path: str
    code: Optional[str] = None


# Simplified utility functions (removing blar dependencies)
def mark_deleted_or_added_lines(text: str) -> str:
    """Mark deleted or added lines (simplified implementation)."""
    return text


class Input(BaseModel):
    name: str = Field(description="Name to search for in the Neo4j database", min_length=1)
    type: str = Field(
        description="Type to search for in the Neo4j database (values: 'FUNCTION', 'CLASS', 'FILE', 'FOLDER')"
    )


class FindNodesByNameAndType(BaseTool):
    name: str = "find_nodes_by_name_and_type"
    description: str = (
        "Find nodes by exact name and type in the graph database. Precise and narrow search using exact matches. "
        "File names need to include the extension, but classes or functions only need the name."
    )
    db_manager: AbstractDbManager = Field(description="Neo4jManager object to interact with the database")

    args_schema: type[BaseModel] = Input  # type: ignore[assignment]

    def _run(
        self,
        name: str,
        type: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> dict[str, Any] | str:
        """Retrieves all nodes that contain the given text."""

        dto_nodes = self.db_manager.get_node_by_name_and_type(
            name=name,
            node_type=type,
        )

        # Convert DTOs to response models
        nodes: list[NodeFoundByNameTypeResponse] = []
        for dto in dto_nodes:
            response_node = NodeFoundByNameTypeResponse(
                node_id=dto.node_id,
                node_name=dto.node_name,
                node_type=dto.node_type,
                file_path=dto.file_path,
                code=dto.code,
            )
            nodes.append(response_node)

        if len(nodes) > 15:
            return "Too many nodes found. Please refine your query or use another tool"

        nodes_dicts = [node.model_dump() for node in nodes]
        for node in nodes_dicts:
            # Handle diff_text if it exists, otherwise skip
            diff_text = node.get("diff_text")
            if diff_text is not None:
                node["diff_text"] = mark_deleted_or_added_lines(diff_text)

        return {
            "nodes": nodes_dicts,
        }
