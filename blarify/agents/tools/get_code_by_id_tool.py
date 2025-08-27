from typing import Dict, Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.repositories.graph_db_manager.queries import get_code_by_id


class NodeIdInput(BaseModel):
    node_id: str = Field(
        description="The node id (an UUID like hash id) of the node to get the code and/or the diff text."
    )

    @field_validator("node_id", mode="before")
    @classmethod
    def format_node_id(cls, value: any) -> any:
        value = str(value).strip()
        if isinstance(value, str) and len(value) == 32:
            return value
        raise ValueError("Node id must be a 32 character string UUID like hash id")


class GetCodeByIdTool(BaseTool):
    name: str = "get_code_by_id"
    description: str = "Searches for node by id in the Neo4j database"

    args_schema: Type[BaseModel] = NodeIdInput

    db_manager: Neo4jManager = Field(description="Neo4jManager object to interact with the database")
    company_id: str = Field(description="Company ID to search for in the Neo4j database")
    diff_identifier: Optional[str] = Field(
        description="Pull Request id to search for in the Neo4j database, could be None if not reviewing a PR"
    )

    def __init__(
        self,
        db_manager: Neo4jManager,
        company_id: str,
        diff_identifier: Optional[str] = None,
        handle_validation_error: bool = False,
    ):
        super().__init__(
            db_manager=db_manager,
            company_id=company_id,
            diff_identifier=diff_identifier,
            handle_validation_error=handle_validation_error,
        )

    def _run(
        self,
        node_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Dict[str, str]:
        """Returns a function code given a node_id. returns the node text and the neighbors of the node."""
        node_result = get_code_by_id(self.db_manager, node_id=node_id, entity_id=self.company_id)

        if not node_result:
            return f"No code found for the given query: {node_id}"

        return_dict = {
            "name": node_result.get("name", ""),
            "labels": node_result.get("labels", []),
            "code": node_result.get("text", ""),
        }

        return return_dict
