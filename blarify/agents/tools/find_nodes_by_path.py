from typing import Any, Dict, List, Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.db_managers.dtos.node_found_by_path import NodeFoundByPathDto
from blarify.db_managers.neo4j_manager import Neo4jManager


class Input(BaseModel):
    path: str = Field(description="relative path to the node", min_length=1)


class FindNodesByPath(BaseTool):
    name: str = "find_nodes_by_path"
    description: str = "Searches for nodes by path in the Neo4j database"

    company_id: str = Field(description="Company ID to search for in the Neo4j database")
    db_manager: Neo4jManager = Field(description="Neo4jManager object to interact with the database")
    repo_id: str = Field(description="Repository ID to search for in the Neo4j database")
    diff_identifier: str = Field(description="Identifier for the PR on the graph, to search for in the Neo4j database")

    args_schema: Type[BaseModel] = Input

    def _run(
        self,
        path: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Dict[str, Any] | str:
        """Retrivies all nodes that contain the given path."""

        nodes: List[NodeFoundByPathDto] = self.db_manager.get_nodes_by_path(
            path=path,
            company_id=self.company_id,
            repo_id=self.repo_id,
            diff_identifier=self.diff_identifier,
        )

        nodes_as_dict = [node.as_dict() for node in nodes]

        if len(nodes) > 20:
            return "Too many nodes found. Please refine your query or use another tool"

        nodes: List[NodeFoundByPathDto] = nodes_as_dict
        return {
            "nodes": nodes,
            "too many nodes": False,
        }
