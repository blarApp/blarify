"""
InformationNode Relationship Traversal Tool for workflow discovery.

This tool finds related InformationNodes by traversing code layer relationships
(CALLS, IMPORTS, INHERITS) but returns only documentation layer results.
"""

from typing import Any, Dict, List, Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.db_managers.db_manager import AbstractDbManager


class InformationNodeRelationshipTraversalInput(BaseModel):
    info_node_id: str = Field(description="The node_id of the InformationNode to find relationships for")
    relationship_type: str = Field(
        description="Type of relationship to traverse: 'CALLS', 'IMPORTS', or 'INHERITS'", default="CALLS"
    )


class InformationNodeRelationshipTraversalTool(BaseTool):
    name: str = "information_node_relationship_traversal"
    description: str = "Find related InformationNodes by traversing code relationships. Use info_node_id (from previous tool results) and relationship_type ('CALLS', 'IMPORTS', or 'INHERITS'). Returns semantic descriptions of related components."

    args_schema: Type[BaseModel] = InformationNodeRelationshipTraversalInput
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
        info_node_id: str,
        relationship_type: str = "CALLS",
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> List[Dict[str, Any]]:
        """Find related InformationNodes through code layer relationships."""
        try:
            # Validate relationship type
            valid_relationships = ["CALLS", "IMPORTS", "INHERITS"]
            if relationship_type not in valid_relationships:
                return [{"error": f"Invalid relationship type. Must be one of: {valid_relationships}"}]

            # Cypher query to traverse relationships through code layer
            cypher_query = f"""
            MATCH (info:INFORMATION {{node_id: $info_id, entityId: $entity_id, repoId: $repo_id}})
                  -[:DESCRIBES]->(code_node)
            MATCH (code_node)-[rel:{relationship_type}]->(target_code)
            MATCH (target_info:INFORMATION {{entityId: $entity_id, repoId: $repo_id}})
                  -[:DESCRIBES]->(target_code)
            RETURN target_info.node_id as node_id,
                   target_info.title as title,
                   target_info.content as content,
                   target_info.info_type as info_type,
                   target_info.source_path as source_path,
                   target_info.source_labels as source_labels,
                   type(rel) as relationship_type,
                   labels(target_code) as target_code_type,
                   target_code.name as target_code_name
            ORDER BY target_info.title
            LIMIT 15
            """

            parameters = {"info_id": info_node_id, "entity_id": self.company_id, "repo_id": self.repo_id}

            results = self.db_manager.query(cypher_query, parameters)

            if not results:
                return []

            # Format results for the agent
            formatted_results = []
            for result in results:
                formatted_result = {
                    "node_id": result.get("node_id", ""),
                    "title": result.get("title", ""),
                    "content": result.get("content", "")[:300]
                    + ("..." if len(result.get("content", "")) > 300 else ""),
                    "info_type": result.get("info_type", ""),
                    "source_path": result.get("source_path", ""),
                    "source_labels": result.get("source_labels", []),
                    "source_name": result.get("source_name", ""),
                    "relationship_type": result.get("relationship_type", ""),
                    "target_code_type": result.get("target_code_type", []),
                    "target_code_name": result.get("target_code_name", ""),
                }
                formatted_results.append(formatted_result)

            return formatted_results

        except Exception as e:
            return [{"error": f"Failed to traverse InformationNode relationships: {str(e)}"}]
