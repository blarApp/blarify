"""
InformationNode Search Tool for workflow discovery.

This tool searches InformationNodes by keywords, title, or info_type,
working exclusively with the documentation layer without exposing code.
"""

from typing import Any, Dict, List, Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.db_managers.db_manager import AbstractDbManager


class InformationNodeSearchInput(BaseModel):
    query: str = Field(description="Search query to find InformationNodes by keywords in title, content, or info_type")


class InformationNodeSearchTool(BaseTool):
    name: str = "information_node_search"
    description: str = "Search InformationNodes by keywords in title, content, or info_type. Returns semantic descriptions of components without exposing code."

    args_schema: Type[BaseModel] = InformationNodeSearchInput
    db_manager: AbstractDbManager = Field(description="Database manager to interact with the graph database")
    company_id: str = Field(description="Company ID for database queries")
    repo_id: str = Field(description="Repository ID for database queries")

    def __init__(
        self,
        db_manager: AbstractDbManager,
        company_id: str,
        repo_id: str,
    ):
        super().__init__(
            db_manager=db_manager,
            company_id=company_id,
            repo_id=repo_id,
        )

    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> List[Dict[str, Any]]:
        """Search InformationNodes by query and return their descriptions."""
        try:
            query = query.strip()
            # Cypher query to search InformationNodes by keywords and include described code node ID
            cypher_query = """
            MATCH (info:INFORMATION {entityId: $entity_id, repoId: $repo_id, layer: "documentation"})
            WHERE info.title CONTAINS $query 
               OR info.content CONTAINS $query 
               OR info.info_type CONTAINS $query
            OPTIONAL MATCH (info)-[:DESCRIBES]->(code_node)
            RETURN info.node_id as node_id,
                   info.title as title,
                   info.content as content,
                   info.info_type as info_type,
                   info.source_path as source_path,
                   info.source_labels as source_labels,
                   code_node.id as source_node_id
            ORDER BY size(info.content) DESC
            LIMIT 20
            """

            parameters = {"entity_id": self.company_id, "repo_id": self.repo_id, "query": query}

            results = self.db_manager.query(cypher_query, parameters)

            if not results:
                return []

            # Format results for the agent
            formatted_results = []
            for result in results:
                formatted_result = {
                    "node_id": result.get("node_id", ""),
                    "title": result.get("title", ""),
                    "content": result.get("content", "")[:500]
                    + ("..." if len(result.get("content", "")) > 500 else ""),
                    "info_type": result.get("info_type", ""),
                    "source_path": result.get("source_path", ""),
                    "source_labels": result.get("source_labels", []),
                    "source_name": result.get("source_name", ""),
                    "source_node_id": result.get("source_node_id", ""),
                }
                formatted_results.append(formatted_result)

            return formatted_results

        except Exception as e:
            return [{"error": f"Failed to search InformationNodes: {str(e)}"}]
