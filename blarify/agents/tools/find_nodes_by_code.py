from typing import Any, Dict, List, Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.agents.utils import normalize_node_path, mark_deleted_or_added_lines
from blarify.db_managers.dtos.node_found_by_text import NodeFoundByTextDto
from blarify.db_managers.neo4j_manager import Neo4jManager
from blarify.db_managers.queries import find_nodes_by_text_content


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
        """Retrieves all nodes that contain the given text."""

        # Use the new query function instead of the non-existent db_manager method
        nodes_data = find_nodes_by_text_content(
            db_manager=self.db_manager,
            entity_id=self.company_id,
            repo_id=self.repo_id,
            diff_identifier=self.diff_identifier,
            search_text=code,
        )

        # Convert to NodeFoundByTextDto objects
        nodes: List[NodeFoundByTextDto] = []
        for node_data in nodes_data:
            try:
                node_dto = NodeFoundByTextDto(
                    id=node_data.get("id", ""),
                    name=node_data.get("name", ""),
                    label=str(node_data.get("label", [])),  # Convert list to string
                    diff_text=node_data.get("diff_text", ""),
                    relevant_snippet=node_data.get("relevant_snippet", ""),
                    node_path=node_data.get("node_path", ""),
                )
                nodes.append(node_dto)
            except Exception:
                # Skip malformed nodes
                continue

        nodes_as_dict = [node.as_dict() for node in nodes]

        if len(nodes) > 20:
            return "Too many nodes found. Please refine your query or use another tool"

        # If are two nodes with the same normalized node path, just return the node with the diff identifier = self.diff_identifier
        # In fact, this return the node from the PR instead of the base branch.
        seen_paths = {}

        for node in nodes_as_dict:
            node["diff_text"] = mark_deleted_or_added_lines(node["diff_text"])
            normalized_path = normalize_node_path(node["node_path"])
            if normalized_path not in seen_paths:
                seen_paths[normalized_path] = node
            else:
                # If we find a duplicate path, keep the node that matches our diff_identifier
                if node.get("diff_identifier") == self.diff_identifier:
                    seen_paths[normalized_path] = node

        filtered_nodes = list(seen_paths.values())
        return {
            "nodes": filtered_nodes,
            "too many nodes": False,
        }
