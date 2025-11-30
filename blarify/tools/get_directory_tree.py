from typing import Optional, TypedDict

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager


class TreeNode(TypedDict):
    name: str
    node_id: str | None
    is_folder: bool
    children: dict[str, "TreeNode"]


class DirectoryChild(BaseModel):
    name: str
    path: str
    node_id: str
    is_folder: bool


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
        "Call repeatedly with different paths to explore and expand the tree. "
        "The tree accumulates across calls, showing all explored paths."
    )
    db_manager: AbstractDbManager = Field(description="Database manager for queries")

    args_schema: type[BaseModel] = Input  # type: ignore[assignment]

    _explored_paths: dict[str, list[DirectoryChild]] = PrivateAttr(default_factory=dict)

    def _run(
        self,
        path: str = "/",
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """List contents of a folder in the repository."""
        normalized_path = self._normalize_path(path)

        if normalized_path not in self._explored_paths:
            children = self._query_folder_contents(normalized_path)

            if not children:
                if normalized_path == "/" and not self._explored_paths:
                    return "No files found in the repository root."
                if not self._explored_paths:
                    return f"Folder '{normalized_path}' not found or is empty."
                return self._render_accumulated_tree()

            parsed_children = self._parse_children(children)
            self._explored_paths[normalized_path] = parsed_children

        return self._render_accumulated_tree()

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

    def _parse_children(
        self, children: list[dict[str, str | list[str]]]
    ) -> list[DirectoryChild]:
        """Parse query results into DirectoryChild objects."""
        parsed: list[DirectoryChild] = []
        for child in children:
            labels = child.get("labels", [])
            is_folder = "FOLDER" in labels if isinstance(labels, list) else False
            name = child.get("name", "unknown")
            path = child.get("path", "")
            node_id = child.get("id", "unknown")

            parsed.append(
                DirectoryChild(
                    name=str(name),
                    path=str(path),
                    node_id=str(node_id),
                    is_folder=is_folder,
                )
            )
        return parsed

    def _render_accumulated_tree(self) -> str:
        """Render the full accumulated tree."""
        if not self._explored_paths:
            return "No paths explored yet."

        tree = self._build_tree_structure()
        return self._render_tree_node(tree)

    def _build_tree_structure(self) -> dict[str, TreeNode]:
        """Build a nested tree structure from explored paths."""
        tree: dict[str, TreeNode] = {
            "/": {"name": "/", "node_id": None, "is_folder": True, "children": {}}
        }

        for parent_path, children in sorted(self._explored_paths.items()):
            parent_node = self._get_or_create_node(tree, parent_path)
            parent_children = parent_node["children"]

            for child in children:
                parent_children[child.name] = {
                    "name": child.name,
                    "node_id": child.node_id,
                    "is_folder": child.is_folder,
                    "children": {},
                }

        return tree

    def _get_or_create_node(
        self, tree: dict[str, TreeNode], path: str
    ) -> TreeNode:
        """Get or create a node at the given path."""
        if path == "/":
            return tree["/"]

        parts = path.strip("/").split("/")
        current = tree["/"]

        for part in parts:
            children = current["children"]

            if part not in children:
                children[part] = {
                    "name": part,
                    "node_id": None,
                    "is_folder": True,
                    "children": {},
                }
            current = children[part]

        return current

    def _render_tree_node(self, tree: dict[str, TreeNode]) -> str:
        """Recursively render a tree node."""
        lines: list[str] = []
        root = tree.get("/")
        if root:
            lines.append("/")
            lines.extend(self._render_children(root["children"], ""))
        return "\n".join(lines)

    def _render_children(
        self, children: dict[str, TreeNode], prefix: str
    ) -> list[str]:
        """Render children nodes."""
        lines: list[str] = []
        sorted_children = sorted(
            children.items(),
            key=lambda x: (0 if x[1]["is_folder"] else 1, x[0].lower()),
        )

        for i, (name, node) in enumerate(sorted_children):
            is_last = i == len(sorted_children) - 1
            connector = "└── " if is_last else "├── "
            child_prefix = prefix + ("    " if is_last else "│   ")

            is_folder = node["is_folder"]
            icon = "📁" if is_folder else "📄"
            node_id = node["node_id"]

            if node_id:
                lines.append(f"{prefix}{connector}{icon} {name} [id: {node_id}]")
            else:
                lines.append(f"{prefix}{connector}{icon} {name}")

            node_children = node["children"]
            if node_children:
                lines.extend(self._render_children(node_children, child_prefix))

        return lines
