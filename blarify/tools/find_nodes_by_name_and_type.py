from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


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
        "Find nodes by exact name and type in the Neo4j database. Precise and narrow search using exact matches."
    )
    company_id: str = Field(description="Company ID to search for in the Neo4j database")
    db_manager: Any = Field(description="Neo4jManager object to interact with the database")
    repo_id: str = Field(description="Repository ID to search for in the Neo4j database")
    diff_identifier: str = Field(description="Identifier for the PR on the graph, to search for in the Neo4j database")

    args_schema: type[BaseModel] = Input

    def _run(
        self,
        name: str,
        type: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> dict[str, Any] | str:
        """Retrieves all nodes that contain the given text."""

        nodes: list[NodeFoundByNameTypeResponse] = self.db_manager.get_node_by_name_and_type(
            name=name,
            node_type=type,
        )

        if len(nodes) > 15:
            return "Too many nodes found. Please refine your query or use another tool"

        nodes_dicts = [node.model_dump() for node in nodes]
        for node in nodes_dicts:
            node["diff_text"] = mark_deleted_or_added_lines(node.get("diff_text", None))

        return {
            "nodes": nodes_dicts,
        }
