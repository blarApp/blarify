from typing import Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from blarify.db_managers.neo4j_manager import Neo4jManager


class Input(BaseModel):
    node_id: str = Field(
        description="The node id (an UUID like hash id) of the node to get the relationship flowchart."
    )

    @field_validator("node_id", mode="before")
    @classmethod
    def format_node_id(cls, value: any) -> any:
        if isinstance(value, str) and len(value) == 32:
            return value
        raise ValueError("Node id must be a 32 character string UUID like hash id")


class GetRelationshipFlowchart(BaseTool):
    name: str = "get_relationship_flowchart"
    description: str = "Get the mermaid relationship flowchart for a given node"

    company_id: str = Field(description="Company ID to search for in the Neo4j database")
    db_manager: Neo4jManager = Field(description="Neo4jManager object to interact with the database")
    diff_identifier: str = Field(description="Identifier for the PR on the graph, to search for in the Neo4j database")

    args_schema: Type[BaseModel] = Input

    def __init__(
        self, company_id: str, db_manager: Neo4jManager, diff_identifier: str, handle_validation_error: bool = False
    ):
        super().__init__(
            company_id=company_id,
            db_manager=db_manager,
            diff_identifier=diff_identifier,
            handle_validation_error=handle_validation_error,
        )

    def _run(
        self,
        node_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Retrieves the mermaid relationship flowchart for a given node."""
        try:
            return self.db_manager.get_mermaid_graph(node_id, self.company_id, self.diff_identifier)
        except ValueError as e:
            return e
