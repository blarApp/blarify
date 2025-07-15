from typing import Any, Dict, List, Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.agents.utils import normalize_node_path, mark_deleted_or_added_lines
from blarify.db_managers.dtos.node_found_by_text import NodeFoundByTextDto
from blarify.db_managers.neo4j_manager import Neo4jManager


class Input(BaseModel):
    code: str = Field(description="Text to search for in the database", min_length=1)


class FindNodesByCode(BaseTool):
    name: str = "find_nodes_by_code"
    description: str = "Searches for nodes by code in the Neo4j database"

    company_id: str = Field(description="Company ID to search for in the Neo4j database")
    db_manager: Neo4jManager = Field(description="Neo4jManager object to interact with the database")
    repo_id: str = Field(description="Repository ID to search for in the Neo4j database")
    diff_identifier: str = Field(description="Identifier for the PR on the graph, to search for in the Neo4j database")

    args_schema: Type[BaseModel] = Input

    def _run(
        self,
        code: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Dict[str, Any] | str:
        """Retrivies all nodes that contain the given text."""

        nodes: List[NodeFoundByTextDto] = self.db_manager.get_nodes_by_text(
            text=code,
            company_id=self.company_id,
            repo_id=self.repo_id,
            diff_identifier=self.diff_identifier,
        )

        nodes_as_dict = [node.as_dict() for node in nodes]

        if len(nodes) > 15:
            return "Too many nodes found. Please refine your query or use another tool"

        # If are two nodes with the same normalized node path, just return the node with the diff identifier = self.diff_identifier
        # In fact, this return the node from the PR instead of the base branch.
        seen_paths = {}

        filtered_nodes = []

        for node in nodes_as_dict:
            node["diff_text"] = mark_deleted_or_added_lines(node["diff_text"])
            normalized_path = normalize_node_path(node["node_path"])
            if normalized_path not in seen_paths:
                seen_paths[normalized_path] = node
            else:
                # If we find a duplicate path, keep the node that matches our diff_identifier
                if node.get("diff_identifier") == self.diff_identifier:
                    seen_paths[normalized_path] = node

        filtered_nodes: List[NodeFoundByTextDto] = list(seen_paths.values())
        return {
            "nodes": filtered_nodes,
            "too many nodes": False,
        }
