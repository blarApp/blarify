from typing import Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager


class Input(BaseModel):
    path: str = Field(
        default="/",
        description="Folder path to list contents of (e.g., '/src'). Defaults to root.",
    )


class GetDirectoryTree(BaseTool):
    name: str = "get_directory_tree"
    description: str = (
        "List the contents of a folder in the repository. "
        "Shows immediate children (files and subfolders) with their node IDs. "
        "Use the returned IDs with get_code_analysis to inspect specific files. "
        "Call repeatedly with different paths to explore the codebase structure."
    )
    db_manager: AbstractDbManager = Field(description="Database manager for queries")

    args_schema: type[BaseModel] = Input  # type: ignore[assignment]

    def _run(
        self,
        path: str = "/",
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """List contents of a folder in the repository."""
        normalized_path = self._normalize_path(path)

        children = self._query_folder_contents(normalized_path)

        if not children:
            if normalized_path == "/":
                return "No files found in the repository root."
            return f"Folder '{normalized_path}' not found or is empty."

        return self._format_tree_output(normalized_path, children)

    def _normalize_path(self, path: str) -> str:
        """Normalize the input path."""
        if not path:
            return "/"
        normalized = path.strip()
        if not normalized.startswith("/"):
            normalized = "/" + normalized
        if normalized != "/" and normalized.endswith("/"):
            normalized = normalized.rstrip("/")
        return normalized

    def _query_folder_contents(self, path: str) -> list[dict[str, str | list[str]]]:
        """Query the graph for folder contents."""
        query = """
        MATCH (parent:FOLDER)-[:CONTAINS]->(child)
        WHERE parent.path ENDS WITH $path
          AND parent.entityId = $entity_id
          AND ($repo_ids IS NULL OR parent.repoId IN $repo_ids)
          AND (child:FOLDER OR child:FILE)
        RETURN child.name as name,
               child.path as path,
               child.hashed_id as id,
               labels(child) as labels
        ORDER BY
          CASE WHEN 'FOLDER' IN labels(child) THEN 0 ELSE 1 END,
          child.name
        """
        results = self.db_manager.query(query, parameters={"path": path})
        return results

    def _format_tree_output(
        self, path: str, children: list[dict[str, str | list[str]]]
    ) -> str:
        """Format the results as an ASCII tree."""
        lines: list[str] = [path]

        for i, child in enumerate(children):
            is_last = i == len(children) - 1
            prefix = "└── " if is_last else "├── "

            labels = child.get("labels", [])
            is_folder = "FOLDER" in labels if isinstance(labels, list) else False
            icon = "📁" if is_folder else "📄"

            name = child.get("name", "unknown")
            node_id = child.get("id", "unknown")

            lines.append(f"{prefix}{icon} {name} [id: {node_id}]")

        return "\n".join(lines)
