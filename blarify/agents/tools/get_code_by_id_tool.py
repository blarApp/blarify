from typing import Dict, List, Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from blarify.db_managers.dtos import EdgeDTO, NodeSearchResultDTO
from blarify.db_managers.neo4j_manager import Neo4jManager


def get_relations_str(*, node_name: str, relations: List[EdgeDTO], direction: str) -> str:
    if direction == "outbound":
        relationship_str = "{node_name} -> {relation.relationship_type} -> {relation.node_name}"
    else:
        relationship_str = "{relation.node_name} -> {relation.relationship_type} -> {node_name}"
    relation_str = ""
    for relation in relations:
        relation_str += f"""
RELATIONSHIP: {relationship_str.format(node_name=node_name, relation=relation)}
RELATION NODE ID: {relation.node_id}
RELATION NODE TYPE: {" | ".join(relation.node_type)}
"""
    return relation_str


def get_result_prompt(node_result: NodeSearchResultDTO) -> str:
    diff_text = f"\n\nDIFF TEXT: {node_result.diff_text}\n" if node_result.diff_text else ""

    output = f"""
NODE: ID: {node_result.node_id} | NAME: {node_result.node_name}
LABELS: {" | ".join(node_result.node_labels)}
CODE for {node_result.node_name}:
```
{node_result.code}
```
{diff_text}
"""
    return output


class NodeIdInput(BaseModel):
    node_id: str = Field(
        description="The node id (an UUID like hash id) of the node to get the code and/or the diff text."
    )

    @field_validator("node_id", mode="before")
    @classmethod
    def format_node_id(cls, value: any) -> any:
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
        try:
            node_result: NodeSearchResultDTO = self.db_manager.get_node_by_id_v2(
                node_id=node_id, company_id=self.company_id, diff_identifier=self.diff_identifier
            )
        except ValueError:
            return f"No code found for the given query: {node_id}"

        return_dict = {
            "name": node_result.node_name,
            "labels": node_result.node_labels,
            "code": node_result.code,
            "diff_text": node_result.diff_text,
        }

        return return_dict
