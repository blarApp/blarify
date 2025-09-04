import logging
from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager

logger = logging.getLogger(__name__)


class Input(BaseModel):
    node_id: Optional[str] = Field(
        default=None, description="The node ID of the directory to list, leave this blank to list the root directory"
    )


class DirectoryExplorerTool(BaseTool):
    """
    Tool for exploring directory structure in the code graph using Neo4j queries.
    Provides navigation through the hierarchical structure of the repository.
    """

    name: str = "directory_explorer"
    description: str = "Explore the directory structure of a code repository."
    db_manager: AbstractDbManager

    args_schema: type[BaseModel] = Input  # type: ignore

    def _run(self, run_manager: Any, node_id: Optional[str] = None) -> str:
        """
        List the contents of a directory in the code repository.

        Args:
            node_id: The node ID of the directory to list. If None, lists the repository root.

        Returns:
            String representation of directory contents with file/folder structure
        """
        try:
            # If no node_id provided, find and use repo root
            if node_id is None:
                node_id = self._find_repo_root()
                if not node_id:
                    return "Error: Could not find repository root"

            # Get directory contents
            contents = self._list_directory_children(node_id)

            if not contents:
                return f"Directory is empty or node '{node_id}' not found"

            # Format the output
            return self._format_directory_listing(contents, node_id)

        except Exception as e:
            logger.error(f"Error listing directory contents: {e}")
            return f"Error listing directory: {str(e)}"

    def _find_repo_root(self) -> str:
        """
        Find and return the root node of the repository.

        Returns:
            The node ID of the repository root, or error message if not found
        """
        try:
            root_id = self._find_repo_root_query()
            if root_id:
                root_info = self._get_node_info(root_id)
                return f"Repository root found: {root_id}\nPath: {root_info.get('path', 'Unknown')}\nName: {root_info.get('name', 'Unknown')}"
            else:
                return "Repository root not found"
        except Exception as e:
            logger.error(f"Error finding repo root: {e}")
            return f"Error finding repository root: {str(e)}"

    def _find_repo_root_query(self) -> Optional[str]:
        """
        Find the root node of the repository using Neo4j query.
        The root is typically a node that has no incoming 'contains' relationships.
        """

        try:
            # Query to find root nodes (nodes with no incoming 'contains' relationships)
            # and belong to the specific repo
            query = """
            MATCH (root:NODE {entityId: $entity_id, repoId: $repo_id})
            WHERE root.level=0
            AND root.name <> "DELETED"
            RETURN root.node_id as node_id, root.node_path as path, root.name as name
            ORDER BY root.node_path
            LIMIT 1
            """
            result = self.db_manager.query(query, {})

            logger.debug(f"Root query returned {len(result) if result else 0} results")

            if result and len(result) > 0:
                root_node = result[0]
                logger.info(f"✅ Found repo root: {root_node['node_id']} at path: {root_node['path']}")
                return root_node["node_id"]

            return None

        except Exception as e:
            logger.error(f"❌ Error finding repo root: {e}")
            import traceback

            logger.debug(f"Full traceback: {traceback.format_exc()}")
            return None

    def _list_directory_children(self, node_id: str) -> list[Dict[str, str | List[str]]]:
        """
        List all children of a directory node using the 'contains' relationship.
        """
        try:
            query = """
            MATCH (parent:NODE {node_id: $node_id, entityId: $entity_id, repoId: $repo_id})-[:CONTAINS]->(child:NODE)
            WHERE parent.entityId = $entity_id
            AND child.entityId = $entity_id
            RETURN child.node_id as node_id,
                   child.name as name,
                   child.node_path as path,
                   labels(child) as type
            ORDER BY child.name ASC
            """

            result = self.db_manager.query(query, {"node_id": node_id})

            return result if result else []

        except Exception as e:
            logger.error(f"Error listing directory children for {node_id}: {e}")
            return []

    def _get_node_info(self, node_id: str) -> Dict[str, str]:
        """Get basic information about a node."""
        try:
            query = """
            MATCH (n:NODE {node_id: $node_id, entityId: $entity_id})
            RETURN n.node_id as node_id,
                   n.name as name,
                   n.node_path as path
            """

            result = self.db_manager.query(query, {"node_id": node_id})

            return result[0] if result and len(result) > 0 else {}

        except Exception as e:
            logger.error(f"Error getting node info for {node_id}: {e}")
            return {}

    def _format_directory_listing(self, contents: List[Dict[str, str | List[str]]], parent_node_id: str) -> str:
        """
        Format directory contents into a readable string representation.
        """
        try:
            # Get parent info
            parent_info = self._get_node_info(parent_node_id)
            parent_path = parent_info.get("path", "Unknown")

            output = f"Directory listing for: {parent_path} (Node ID: {parent_node_id})\n"
            output += "=" * 60 + "\n\n"

            if not contents:
                output += "Empty directory\n"
                return output

            # Separate directories and files
            directories = []
            files = []

            for item in contents:
                if "FOLDER" in item.get("type", []):
                    directories.append(item)
                else:
                    files.append(item)

            # List directories first
            if directories:
                output += "📁 Directories:\n"
                for directory in directories:
                    name = directory.get("name", "Unknown")
                    node_id = directory.get("node_id", "Unknown")
                    output += f"  └── {name}/ (ID: {node_id})\n"
                output += "\n"

            # Then list files
            if files:
                output += "📄 Files:\n"
                for file in files:
                    name = file.get("name", "Unknown")
                    node_id = file.get("node_id", "Unknown")

                    output += f"  └── {name} (ID: {node_id})\n"

            output += f"\nTotal items: {len(contents)} ({len(directories)} directories, {len(files)} files)\n"

            return output

        except Exception as e:
            logger.error(f"Error formatting directory listing: {e}")
            return f"Error formatting directory listing: {str(e)}"
