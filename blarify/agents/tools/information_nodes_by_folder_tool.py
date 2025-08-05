"""
InformationNodes by Folder Tool for workflow discovery.

This tool retrieves all InformationNodes from specific folder paths,
helping understand folder-level functionality and architectural organization.
"""

from typing import Any, Dict, List, Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.db_managers.db_manager import AbstractDbManager


class InformationNodesByFolderInput(BaseModel):
    folder_node_id: str = Field(
        description="Node ID of the folder InformationNode to explore (e.g., 'aa203a8096fd36b42c4c2bab6efc4e08'). DO NOT include a '\n' or comments."
    )


class InformationNodesByFolderTool(BaseTool):
    name: str = "information_nodes_by_folder"
    description: str = "Get all InformationNodes related to a specific folder node. Input should be ONLY the node_id (e.g., 'aa203a8096fd36b42c4c2bab6efc4e08') from the folder context provided to you. Do NOT include folder names, '\\n', or comments."

    args_schema: Type[BaseModel] = InformationNodesByFolderInput
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
        folder_node_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> List[Dict[str, Any]]:
        """Get all InformationNodes related to the specified folder node using hierarchy relationships."""
        try:
            # Trim newline characters from folder_node_id
            folder_node_id = folder_node_id.strip()

            # Cypher query to find InformationNodes related to the folder using hierarchy relationships
            # Pattern: folder_info -> DESCRIBES -> folder_code -> CONTAINS -> child_code <- DESCRIBES <- info
            cypher_query = """
            MATCH (folder_info:INFORMATION {node_id: $folder_node_id, entityId: $entity_id, repoId: $repo_id})
            MATCH (folder_info)-[:DESCRIBES]->(folder_code)
            MATCH (folder_code)-[:CONTAINS]->(child_code)
            MATCH (info:INFORMATION {entityId: $entity_id, repoId: $repo_id, layer: "documentation"})-[:DESCRIBES]->(child_code)
            WHERE info.node_id <> $folder_node_id
            RETURN info.node_id as node_id,
                   info.title as title,
                   info.content as content,
                   info.info_type as info_type,
                   info.source_path as source_path,
                   info.source_labels as source_labels,
                   child_code.id as source_node_id
            ORDER BY info.source_path, info.title
            LIMIT 30
            """

            parameters = {"entity_id": self.company_id, "repo_id": self.repo_id, "folder_node_id": folder_node_id}

            results = self.db_manager.query(cypher_query, parameters)

            if not results:
                return [{"message": f"No InformationNodes found related to folder node {folder_node_id}"}]

            # Format results for the agent
            formatted_results = []
            for result in results:
                formatted_result = {
                    "node_id": result.get("node_id", ""),
                    "title": result.get("title", ""),
                    "content": result.get("content", "")[:400]
                    + ("..." if len(result.get("content", "")) > 400 else ""),
                    "info_type": result.get("info_type", ""),
                    "source_path": result.get("source_path", ""),
                    "source_labels": result.get("source_labels", []),
                    "source_name": result.get("source_name", ""),
                    "source_node_id": result.get("source_node_id", ""),
                }
                formatted_results.append(formatted_result)

            return formatted_results

        except Exception as e:
            return [{"error": f"Failed to retrieve InformationNodes for folder node {folder_node_id}: {str(e)}"}]
