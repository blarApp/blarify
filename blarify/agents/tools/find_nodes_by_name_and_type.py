from typing import Any, Dict, List, Optional, Type

from blarify.graph.node.types.node_labels import NodeLabels
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.agents.utils import mark_deleted_or_added_lines
from blarify.repositories.graph_db_manager.dtos.node_found_by_name_type import NodeFoundByNameTypeDto
from blarify.repositories.graph_db_manager import Neo4jManager


class Input(BaseModel):
    name: str = Field(description="Name to search for in the Neo4j database", min_length=1)
    type: NodeLabels = Field(description="Type to search for in the Neo4j database")


class FindNodesByNameAndType(BaseTool):
    name: str = "find_nodes_by_name_and_type"
    description: str = "Searches for nodes by name and type in the Neo4j database"

    company_id: str = Field(description="Company ID to search for in the Neo4j database")
    db_manager: Neo4jManager = Field(description="Neo4jManager object to interact with the database")
    repo_id: str = Field(description="Repository ID to search for in the Neo4j database")
    diff_identifier: str = Field(description="Identifier for the PR on the graph, to search for in the Neo4j database")

    args_schema: Type[BaseModel] = Input

    def _run(
        self,
        name: str,
        type: NodeLabels,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Dict[str, Any] | str:
        """Retrieves all nodes that contain the given text."""

        nodes: List[NodeFoundByNameTypeDto] = self.db_manager.get_node_by_name_and_type(
            name=name,
            type=type.value,
            company_id=self.company_id,
            repo_id=self.repo_id,
            diff_identifier=self.diff_identifier,
        )

        if len(nodes) > 15:
            return "Too many nodes found. Please refine your query or use another tool"

        nodes_dicts = [node.get_dict() for node in nodes]
        for node in nodes_dicts:
            node["diff_text"] = mark_deleted_or_added_lines(node.get("diff_text", None))

        return {
            "nodes": nodes_dicts,
        }
