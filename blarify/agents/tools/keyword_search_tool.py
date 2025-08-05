from typing import Any, Dict, List, Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.db_managers.neo4j_manager import Neo4jManager


class KeywordSearchInput(BaseModel):
    query: str = Field(description="Keyword to search for in the Neo4j database")


class KeywordSearchTool(BaseTool):
    name: str = "keyword_search"
    description: str = "Searches for a keyword in the path, name or node_id of the nodes in the Neo4j database"

    args_schema: Type[BaseModel] = KeywordSearchInput
    db_manager: Neo4jManager = Field(description="Neo4jManager object to interact with the database")
    company_id: str = Field(description="Company ID to search for in the Neo4j database")

    def __init__(self, db_manager: Neo4jManager, company_id: str):
        super().__init__(db_manager=db_manager, company_id=company_id)

    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> List[Dict[str, Any]]:
        """Returns a function code given a query that can be function name, path or node_id. returns the best matches."""

        result = self.db_manager.search_code(query, self.company_id)

        if not result:
            return "No code found for the given query"
        result = result if result else "No result found"

        return result
