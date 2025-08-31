from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager
import logging

logger = logging.getLogger(__name__)


# Pydantic Response Models (replacement for blarify DTOs)
class NodeFoundByTextResponse(BaseModel):
    """Node found by text search response model."""

    node_id: str
    node_name: str
    node_type: list[str]
    code: str
    file_path: str
    similarity_score: Optional[float] = None


# Simplified utility functions (removing blar dependencies)
def normalize_node_path(path: str) -> str:
    """Normalize node path for consistent formatting."""
    return path.replace("\\", "/")


def mark_deleted_or_added_lines(text: str) -> str:
    """Mark deleted or added lines (simplified implementation)."""
    return text


class Input(BaseModel):
    code: str = Field(description="Text to search for in the database", min_length=1)


class FindNodesByCode(BaseTool):
    name: str = "find_nodes_by_code"
    description: str = "Searches for nodes by code in the Neo4j database"

    db_manager: AbstractDbManager = Field(description="Neo4jManager object to interact with the database")

    args_schema: type[BaseModel] = Input  # type: ignore

    def _run(
        self,
        code: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> dict[str, Any] | str:
        """Retrivies all nodes that contain the given text."""
        try:
            query = """
                MATCH (n:NODE {repoId: $repo_id, entityId: $entity_id})
                WHERE n.text CONTAINS $text OR n.name CONTAINS $text
                RETURN n.node_id as node_id, n.name as node_name, labels(n) as node_type,
                        n.text as code, n.path as file_path
                LIMIT 50"""
            nodes_result = self.db_manager.query(query, {"text": code})
            nodes = [NodeFoundByTextResponse(**node) for node in nodes_result]

            nodes_as_dict = [node.model_dump() for node in nodes]

            if len(nodes) > 15:
                return "Too many nodes found. Please refine your query or use another tool"

            # If are two nodes with the same normalized node path, just return the node with the diff identifier = self.diff_identifier
            # In fact, this return the node from the PR instead of the base branch.
            seen_paths = {}

            filtered_nodes = []

            for node in nodes_as_dict:
                # Use the correct field name that matches the DTO structure
                file_path = node.get("file_path", "")
                normalized_path = normalize_node_path(file_path)
                if normalized_path not in seen_paths:
                    seen_paths[normalized_path] = node
                else:
                    # If we find a duplicate path, keep the node that matches our diff_identifier
                    seen_paths[normalized_path] = node

            filtered_nodes: list[NodeFoundByTextResponse] = list(seen_paths.values())
            return {
                "nodes": filtered_nodes,
                "too many nodes": False,
            }
        except Exception as e:
            logger.error(f"Error in FindNodesByCode tool: {e}")
            return {"message": "Error running this tool"}
