import logging
from typing import Any, Optional

from langchain.tools import tool
from langchain_core.tools import BaseTool

# Use SWE-agent logging system for consistency
try:
    from sweagent.utils.log import get_logger

    logger = get_logger("directory-explorer", emoji="📁")
except ImportError:
    logger = logging.getLogger(__name__)


class DirectoryExplorerTool:
    """
    Tool for exploring directory structure in the code graph using Neo4j queries.
    Provides navigation through the hierarchical structure of the repository.
    """

    def __init__(self, company_graph_manager: Any, company_id: str, repo_id: str):
        self.company_graph_manager = company_graph_manager
        self.company_id = company_id
        self.repo_id = repo_id
        self._repo_root_cache = None

        # Log initialization parameters for debugging
        logger.info(f"DirectoryExplorerTool initialized with company_id='{company_id}', repo_id='{repo_id}'")
        logger.info(f"Neo4j manager available: {company_graph_manager.is_available()}")
        if hasattr(company_graph_manager, "neo4j_available"):
            logger.info(f"Neo4j connection status: {company_graph_manager.neo4j_available}")

    def get_tool(self) -> BaseTool:
        @tool
        def list_directory_contents(node_id: Optional[str] = None) -> str:
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

        return list_directory_contents

    def get_find_repo_root_tool(self) -> BaseTool:
        @tool
        def find_repo_root() -> str:
            """
            Find and return the root node of the repository.

            Returns:
                The node ID of the repository root, or error message if not found
            """
            try:
                root_id = self._find_repo_root()
                if root_id:
                    root_info = self._get_node_info(root_id)
                    return f"Repository root found: {root_id}\nPath: {root_info.get('path', 'Unknown')}\nName: {root_info.get('name', 'Unknown')}"
                else:
                    return "Repository root not found"
            except Exception as e:
                logger.error(f"Error finding repo root: {e}")
                return f"Error finding repository root: {str(e)}"

        return find_repo_root

    def _find_repo_root(self) -> Optional[str]:
        """
        Find the root node of the repository using Neo4j query.
        The root is typically a node that has no incoming 'contains' relationships.
        """

        logger.info(f"Searching for repository root with entity_id='{self.company_id}', repo_id='{self.repo_id}'")

        # Check if Neo4j is available
        if not self.company_graph_manager.is_available():
            logger.error("Neo4j manager is not available - cannot find repository root")
            return None

        try:
            # Query to find root nodes (nodes with no incoming 'contains' relationships)
            # and belong to the specific repo
            query = """
            MATCH (root:NODE {entityId: $entity_id, repoId: $repoId})
            WHERE root.level=0
            AND root.name <> "DELETED"
            RETURN root.node_id as node_id, root.node_path as path, root.name as name
            ORDER BY root.node_path
            LIMIT 1
            """

            logger.debug(
                f"Executing root query with parameters: entity_id='{self.company_id}', repoId='{self.repo_id}'"
            )
            result = self.company_graph_manager.query(query, {"entity_id": self.company_id, "repoId": self.repo_id})

            logger.debug(f"Root query returned {len(result) if result else 0} results")

            if result and len(result) > 0:
                root_node = result[0]
                logger.info(f"✅ Found repo root: {root_node['node_id']} at path: {root_node['path']}")
                return root_node["node_id"]

            return None

        except Exception as e:
            logger.error(f"❌ Error finding repo root: {e}")
            logger.error(f"Query parameters: entity_id='{self.company_id}', repo_id='{self.repo_id}'")
            import traceback

            logger.debug(f"Full traceback: {traceback.format_exc()}")
            return None

    def _list_directory_children(self, node_id: str) -> list[dict]:
        """
        List all children of a directory node using the 'contains' relationship.
        """
        try:
            query = """
            MATCH (parent:NODE {node_id: $node_id})-[:CONTAINS]->(child:NODE)
            WHERE parent.entityId = $entity_id
            AND child.entityId = $entity_id
            RETURN child.node_id as node_id,
                   child.name as name,
                   child.node_path as path,
                   labels(child) as type
            ORDER BY child.name ASC
            """

            result = self.company_graph_manager.query(query, {"node_id": node_id, "entity_id": self.company_id})

            return result if result else []

        except Exception as e:
            logger.error(f"Error listing directory children for {node_id}: {e}")
            return []

    def _get_node_info(self, node_id: str) -> dict:
        """Get basic information about a node."""
        try:
            query = """
            MATCH (n:NODE {node_id: $node_id, entityId: $entity_id})
            RETURN n.node_id as node_id,
                   n.name as name,
                   n.node_path as path
            """

            result = self.company_graph_manager.query(query, {"node_id": node_id, "entity_id": self.company_id})

            return result[0] if result and len(result) > 0 else {}

        except Exception as e:
            logger.error(f"Error getting node info for {node_id}: {e}")
            return {}

    def _format_directory_listing(self, contents: list[dict], parent_node_id: str) -> str:
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
                if "FOLDER" in item.get("type"):
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

    def _find_node_by_path(self, path: str) -> Optional[str]:
        """Find a node by its path."""
        try:
            # Normalize path (remove leading/trailing slashes)
            normalized_path = path.strip("/")

            query = """
            MATCH (n:NODE {entityId: $entity_id, repoId: $repoId})
            WHERE n.node_path = $path
            RETURN n.node_id as node_id
            LIMIT 1
            """

            result = self.company_graph_manager.query(
                query, {"entity_id": self.company_id, "repoId": self.repo_id, "path": normalized_path}
            )

            return result[0]["node_id"] if result and len(result) > 0 else None

        except Exception as e:
            logger.error(f"Error finding node by path {path}: {e}")
            return None
