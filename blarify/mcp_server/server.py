"""MCP Server implementation for Blarify tools."""

import asyncio
import logging
import sys
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

from blarify.mcp_server.config import MCPServerConfig
from blarify.mcp_server.tools import MCPToolWrapper
from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager
from blarify.repositories.graph_db_manager.falkordb_manager import FalkorDBManager
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager

# Import all Blarify tools
from blarify.tools import (
    DirectoryExplorerTool,
    FindNodesByCode,
    FindNodesByNameAndType,
    FindNodesByPath,
    GetBlameByIdTool,
    GetCodeByIdTool,
    GetCommitByIdTool,
    GetFileContextByIdTool,
    GetNodeWorkflowsTool,
    GetRelationshipFlowchart,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BlarifyMCPServer:
    """MCP Server for Blarify tools."""

    def __init__(self, config: Optional[MCPServerConfig] = None) -> None:
        """Initialize the MCP server."""
        self.config = config or MCPServerConfig.from_env()
        self.config.validate_for_db_type()

        # Initialize FastMCP server
        self.mcp = FastMCP("Blarify Tools")

        # Initialize database manager
        self.db_manager: Optional[AbstractDbManager] = None
        self.tool_wrappers: List[MCPToolWrapper] = []

    def _initialize_db_manager(self) -> AbstractDbManager:
        """Initialize the database manager based on configuration."""
        if self.config.db_type == "neo4j":
            return Neo4jManager(
                uri=self.config.neo4j_uri,
                user=self.config.neo4j_username,
                password=self.config.neo4j_password,
                repo_id=self.config.root_path,  # Use root_path as repo_id
                entity_id=self.config.entity_id,
            )
        elif self.config.db_type == "falkordb":
            if not self.config.falkor_host:
                raise ValueError("FalkorDB configuration incomplete")
            return FalkorDBManager(
                uri=self.config.falkor_host,
                repo_id=self.config.root_path,  # Use root_path as repo_id
                entity_id=self.config.entity_id,
            )
        else:
            raise ValueError(f"Unsupported database type: {self.config.db_type}")

    def _initialize_tools(self) -> None:
        """Initialize all Blarify tools with the database manager."""
        if not self.db_manager:
            self.db_manager = self._initialize_db_manager()

        # Create instances of all tools
        tools = [
            DirectoryExplorerTool(db_manager=self.db_manager),
            FindNodesByCode(db_manager=self.db_manager),
            FindNodesByNameAndType(db_manager=self.db_manager),
            FindNodesByPath(db_manager=self.db_manager),
            GetBlameByIdTool(
                db_manager=self.db_manager,
                repo_owner="",  # Will be configured via environment
                repo_name="",  # Will be configured via environment
            ),
            GetCodeByIdTool(db_manager=self.db_manager),
            GetCommitByIdTool(db_manager=self.db_manager),
            GetFileContextByIdTool(db_manager=self.db_manager),
            GetNodeWorkflowsTool(db_manager=self.db_manager),  # type: ignore[arg-type]
            GetRelationshipFlowchart(db_manager=self.db_manager),
        ]

        # Wrap each tool for MCP
        self.tool_wrappers = [MCPToolWrapper(tool) for tool in tools]

        # Register tools with FastMCP
        for wrapper in self.tool_wrappers:
            self._register_tool_with_mcp(wrapper)

    def _register_tool_with_mcp(self, wrapper: MCPToolWrapper) -> None:
        """Register a tool wrapper with the FastMCP server."""
        # Since FastMCP doesn't support **kwargs, we create a function that
        # accepts a single Dict[str, Any] parameter for all arguments

        async def tool_function(arguments: Dict[str, Any] = {}) -> str:
            """Execute the tool with the provided arguments."""
            result = await wrapper.invoke(arguments)
            return str(result)

        # Register with FastMCP
        self.mcp.tool(name=wrapper.name, description=wrapper.description)(tool_function)

        logger.info(f"Registered tool: {wrapper.name}")

    async def run(self) -> None:
        """Run the MCP server."""
        try:
            logger.info("Initializing Blarify MCP Server...")

            # Initialize database and tools
            self._initialize_tools()

            logger.info(f"Loaded {len(self.tool_wrappers)} tools")
            logger.info(f"Database type: {self.config.db_type}")

            # Run the FastMCP server
            self.mcp.run()

        except Exception as e:
            logger.error(f"Error running MCP server: {e}")
            raise
        finally:
            # Clean up database connections
            if self.db_manager:
                try:
                    self.db_manager.close()
                except Exception:
                    pass


def main() -> None:
    """Main entry point for the MCP server."""
    try:
        # Load configuration from environment
        config = MCPServerConfig.from_env()

        # Create and run server
        server = BlarifyMCPServer(config)

        # Run the async server
        asyncio.run(server.run())

    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
