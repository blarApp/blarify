from typing import Any, List, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager


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

    db_manager: AbstractDbManager = Field(description="Neo4jManager object to interact with the database")

    args_schema: type[BaseModel] = Input  # type: ignore

    def _run(
        self,
        path: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> dict[str, Any] | str:
        """Retrivies all nodes that contain the given path."""

        nodes: list[NodeFoundByPathResponse] = self.get_nodes_by_path(
            path=path,
        )

        nodes_as_dict = [node.model_dump() for node in nodes]

        if len(nodes) > 15:
            return "Too many nodes found. Please refine your query or use another tool"

        return {
            "nodes": nodes_as_dict,
            "too many nodes": False,
        }

    def get_nodes_by_path(self, path: str) -> List[NodeFoundByPathResponse]:
        """Get nodes by file path."""

        query = """
        MATCH (n:NODE {repoId: $repo_id, entityId: $entity_id})
        WHERE n.path CONTAINS $path and ('FILE' IN labels(n) OR 'FOLDER' IN labels(n))
        RETURN n.node_id as node_id, n.name as node_name, labels(n) as node_type,
               n.path as file_path, n.text as code
        """

        result = self.db_manager.query(query, {"path": path})

        nodes = []
        for node_data in result:
            nodes.append(
                NodeFoundByPathResponse(
                    node_id=node_data.get("node_id", ""),
                    node_name=node_data.get("node_name", ""),
                    node_type=node_data.get("node_type", []),
                    file_path=node_data.get("file_path", path),
                    code=node_data.get("code"),
                )
            )

        return nodes
