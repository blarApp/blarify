from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


# Pydantic Response Models (replacement for blarify DTOs)
class NodeFoundByPathResponse(BaseModel):
    """Node found by path response model."""
    node_id: str
    node_name: str
    node_type: list[str]
    file_path: str
    code: Optional[str] = None


class Input(BaseModel):
    path: str = Field(description="relative path to the node", min_length=1)


class FindNodesByPath(BaseTool):
    name: str = "find_nodes_by_path"
    description: str = "Searches for nodes by path in the Neo4j database"

    company_id: str = Field(description="Company ID to search for in the Neo4j database")
    db_manager: Any = Field(description="Neo4jManager object to interact with the database")
    repo_id: str = Field(description="Repository ID to search for in the Neo4j database")
    diff_identifier: str = Field(description="Identifier for the PR on the graph, to search for in the Neo4j database")

    args_schema: type[BaseModel] = Input

    def _run(
        self,
        path: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> dict[str, Any] | str:
        """Retrivies all nodes that contain the given path."""

        nodes: list[NodeFoundByPathResponse] = self.db_manager.get_nodes_by_path(
            path=path,
        )

        nodes_as_dict = [node.model_dump() for node in nodes]

        if len(nodes) > 15:
            return "Too many nodes found. Please refine your query or use another tool"

        nodes: list[NodeFoundByPathResponse] = nodes_as_dict
        return {
            "nodes": nodes,
            "too many nodes": False,
        }
