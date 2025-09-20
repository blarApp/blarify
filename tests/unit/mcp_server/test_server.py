"""Unit tests for MCP Server."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from blarify.mcp_server.config import MCPServerConfig
from blarify.mcp_server.server import BlarifyMCPServer


class TestBlarifyMCPServer:
    """Test suite for BlarifyMCPServer."""
    
    @pytest.fixture
    def config(self) -> MCPServerConfig:
        """Create a test configuration."""
        return MCPServerConfig(
            neo4j_uri="bolt://localhost:7687",
            neo4j_username="test_user",
            neo4j_password="test_pass",
            repository_id="test_repo",
            entity_id="test_entity",
            db_type="neo4j"
        )
    
    @pytest.fixture
    def server(self, config: MCPServerConfig) -> BlarifyMCPServer:
        """Create a server instance."""
        with patch("blarify.mcp_server.server.FastMCP"):
            return BlarifyMCPServer(config)
    
    def test_server_initialization(self, server: BlarifyMCPServer, config: MCPServerConfig) -> None:
        """Test server initialization."""
        assert server.config == config
        assert server.db_manager is None
        assert server.tool_wrappers == []
    
    @patch("blarify.mcp_server.server.Neo4jManager")
    def test_initialize_neo4j_manager(
        self, 
        mock_neo4j_manager: Mock, 
        server: BlarifyMCPServer
    ) -> None:
        """Test Neo4j database manager initialization."""
        mock_instance = MagicMock()
        mock_neo4j_manager.return_value = mock_instance
        
        db_manager = server._initialize_db_manager()
        
        assert db_manager == mock_instance
        mock_neo4j_manager.assert_called_once_with(
            uri="bolt://localhost:7687",
            user="test_user",
            password="test_pass",
            repo_id="test_repo",
            entity_id="test_entity"
        )
    
    @patch("blarify.mcp_server.server.FalkorDBManager")
    def test_initialize_falkor_manager(
        self,
        mock_falkor_manager: Mock,
        config: MCPServerConfig
    ) -> None:
        """Test FalkorDB manager initialization."""
        config.db_type = "falkordb"
        config.falkor_host = "localhost"
        config.falkor_port = 6379
        
        with patch("blarify.mcp_server.server.FastMCP"):
            server = BlarifyMCPServer(config)
        
        mock_instance = MagicMock()
        mock_falkor_manager.return_value = mock_instance
        
        db_manager = server._initialize_db_manager()
        
        assert db_manager == mock_instance
        mock_falkor_manager.assert_called_once_with(
            uri="localhost",
            repo_id="test_repo",
            entity_id="test_entity"
        )
    
    def test_invalid_db_type(self, config: MCPServerConfig) -> None:
        """Test error with invalid database type."""
        config.db_type = "invalid"  # type: ignore
        
        with patch("blarify.mcp_server.server.FastMCP"):
            server = BlarifyMCPServer(config)
        
        with pytest.raises(ValueError) as exc_info:
            server._initialize_db_manager()
        
        assert "Unsupported database type" in str(exc_info.value)
    
    @patch("blarify.mcp_server.server.GetNodeWorkflowsTool")
    @patch("blarify.mcp_server.server.Neo4jManager")
    def test_initialize_tools(
        self,
        mock_neo4j_manager: Mock,
        mock_workflows_tool: Mock,
        server: BlarifyMCPServer
    ) -> None:
        """Test tool initialization."""
        # Import the actual AbstractDbManager to create a proper mock
        from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager
        
        mock_db = MagicMock(spec=AbstractDbManager)
        mock_neo4j_manager.return_value = mock_db
        
        # Mock the workflows tool that requires Neo4jManager specifically
        mock_workflows_instance = MagicMock()
        mock_workflows_tool.return_value = mock_workflows_instance
        
        # Mock the _register_tool_with_mcp method
        server._register_tool_with_mcp = MagicMock()
        
        server._initialize_tools()
        
        # Check that database manager was created
        assert server.db_manager == mock_db
        
        # Check that tools were created and wrapped
        assert len(server.tool_wrappers) == 10  # We have 10 tools
        
        # Check that each tool was registered with MCP
        assert server._register_tool_with_mcp.call_count == 10
    
    def test_register_tool_with_mcp(self, server: BlarifyMCPServer) -> None:
        """Test registering a tool with the MCP server."""
        # Create a mock wrapper
        mock_wrapper = MagicMock()
        mock_wrapper.name = "test_tool"
        mock_wrapper.description = "Test tool description"
        mock_wrapper.get_mcp_schema.return_value = {
            "type": "object",
            "properties": {
                "test_field": {"type": "string", "description": "Test field"}
            },
            "required": ["test_field"]
        }
        
        # Mock the FastMCP tool method
        mock_tool_decorator = MagicMock()
        server.mcp.tool = MagicMock(return_value=mock_tool_decorator)
        
        # Register the tool
        server._register_tool_with_mcp(mock_wrapper)
        
        # Check that the tool was registered with correct parameters
        server.mcp.tool.assert_called_once_with(
            name="test_tool",
            description="Test tool description"
        )
        
        # Check that the decorator was applied
        mock_tool_decorator.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_server(self, server: BlarifyMCPServer) -> None:
        """Test running the server."""
        # Mock the necessary methods
        server._initialize_tools = MagicMock()
        # Create an async mock for run
        async def mock_run():
            return None
        server.mcp.run = MagicMock(return_value=mock_run())
        server.db_manager = MagicMock()
        
        # Run the server
        await server.run()
        
        # Check that tools were initialized
        server._initialize_tools.assert_called_once()
        
        # Check that MCP run was called
        server.mcp.run.assert_called_once()
        
        # Check that database was closed
        server.db_manager.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_server_error_handling(self, server: BlarifyMCPServer) -> None:
        """Test error handling when running the server."""
        # Mock initialization to raise an error
        server._initialize_tools = MagicMock(side_effect=Exception("Init error"))
        
        # Run the server and expect it to raise
        with pytest.raises(Exception) as exc_info:
            await server.run()
        
        assert "Init error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_run_server_cleanup_on_error(self, server: BlarifyMCPServer) -> None:
        """Test that database is cleaned up even on error."""
        # Setup mocks
        server._initialize_tools = MagicMock()
        server.mcp.run = MagicMock(side_effect=Exception("Run error"))
        server.db_manager = MagicMock()
        
        # Run the server and expect it to raise
        with pytest.raises(Exception):
            await server.run()
        
        # Check that database was still closed
        server.db_manager.close.assert_called_once()
    
    def test_config_validation_on_init(self) -> None:
        """Test that configuration is validated on initialization."""
        config = MCPServerConfig(
            db_type="falkordb",
            falkor_host=None,  # Invalid - missing required field
            falkor_port=None
        )
        
        with patch("blarify.mcp_server.server.FastMCP"):
            with pytest.raises(ValueError) as exc_info:
                BlarifyMCPServer(config)
        
        assert "FalkorDB requires" in str(exc_info.value)