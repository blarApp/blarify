"""Integration tests for MCP Server."""
# pyright: reportPrivateUsage=false

import json
import os
from typing import AsyncGenerator, Any

import pytest

from blarify.mcp_server.config import MCPServerConfig
from blarify.mcp_server.server import BlarifyMCPServer
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager


@pytest.mark.integration
class TestMCPServerIntegration:
    """Integration tests for MCP Server with real database."""

    @pytest.fixture
    def neo4j_config(self) -> MCPServerConfig:
        """Create Neo4j configuration from environment."""
        return MCPServerConfig(
            neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_username=os.getenv("NEO4J_USERNAME", "neo4j"),
            neo4j_password=os.getenv("NEO4J_PASSWORD", "password"),
            root_path=os.getenv("ROOT_PATH", "test_repo"),
            entity_id=os.getenv("ENTITY_ID", "test_entity"),
            db_type="neo4j",
        )

    @pytest.fixture
    async def mcp_server(self, neo4j_config: MCPServerConfig) -> AsyncGenerator[BlarifyMCPServer, Any]:
        """Create MCP server instance for testing."""
        server = BlarifyMCPServer(neo4j_config)
        server._initialize_tools()
        yield server
        # Cleanup
        if server.db_manager:
            server.db_manager.close()

    @pytest.mark.asyncio
    async def test_server_initialization_with_neo4j(self, neo4j_config: MCPServerConfig) -> None:
        """Test server initialization with Neo4j configuration."""
        server = BlarifyMCPServer(neo4j_config)
        server._initialize_tools()

        # Verify database manager was created
        assert server.db_manager is not None
        assert isinstance(server.db_manager, Neo4jManager)

        # Verify all tools were wrapped
        assert len(server.tool_wrappers) == 10

        # Verify tool names
        tool_names = [wrapper.name for wrapper in server.tool_wrappers]
        expected_tools = [
            "directory_explorer",
            "find_nodes_by_code",
            "find_nodes_by_name_and_type",
            "find_nodes_by_path",
            "get_blame_by_id",
            "get_code_by_id",
            "get_commit_by_id",
            "see_node_in_file_context",  # This is the actual tool name
            "get_node_workflows",
            "get_relationship_flowchart",
        ]
        for expected in expected_tools:
            assert expected in tool_names

        # Cleanup
        if server.db_manager:
            server.db_manager.close()

    @pytest.mark.asyncio
    async def test_tool_schema_generation(self, neo4j_config: MCPServerConfig) -> None:
        """Test that all tools generate valid MCP schemas."""
        server = BlarifyMCPServer(neo4j_config)
        server._initialize_tools()

        for wrapper in server.tool_wrappers:
            schema = wrapper.get_mcp_schema()

            # Verify basic schema structure
            assert "type" in schema
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "required" in schema
            assert isinstance(schema["properties"], dict)
            assert isinstance(schema["required"], list)

            # Verify the schema can be JSON serialized
            json_str = json.dumps(schema)
            assert json_str is not None

        # Cleanup
        if server.db_manager:
            server.db_manager.close()

    @pytest.mark.asyncio
    async def test_tool_definitions(self, neo4j_config: MCPServerConfig) -> None:
        """Test that all tools generate valid MCP tool definitions."""
        server = BlarifyMCPServer(neo4j_config)
        server._initialize_tools()

        for wrapper in server.tool_wrappers:
            definition = wrapper.to_mcp_tool_definition()

            # Verify definition structure
            assert "name" in definition
            assert "description" in definition
            assert "inputSchema" in definition

            # Verify types
            assert isinstance(definition["name"], str)
            assert isinstance(definition["description"], str)
            assert isinstance(definition["inputSchema"], dict)

            # Verify the definition can be JSON serialized
            json_str = json.dumps(definition)
            assert json_str is not None

        # Cleanup
        if server.db_manager:
            server.db_manager.close()

    @pytest.mark.asyncio
    async def test_error_handling_invalid_arguments(self, neo4j_config: MCPServerConfig) -> None:
        """Test error handling with invalid tool arguments."""
        server = BlarifyMCPServer(neo4j_config)
        server._initialize_tools()

        # Find a tool that requires arguments
        get_code_tool = next(w for w in server.tool_wrappers if w.name == "get_code_by_id")

        # Try to invoke without required arguments
        result = await get_code_tool.invoke({})

        # Should return an error message
        assert "Error:" in result or "error" in result.lower()

        # Cleanup
        if server.db_manager:
            server.db_manager.close()

    @pytest.mark.asyncio
    async def test_tool_wrapper_attributes(self, neo4j_config: MCPServerConfig) -> None:
        """Test that tool wrappers have all required attributes."""
        server = BlarifyMCPServer(neo4j_config)
        server._initialize_tools()

        for wrapper in server.tool_wrappers:
            # Check that wrapper has required attributes
            assert hasattr(wrapper, "name")
            assert hasattr(wrapper, "description")
            assert hasattr(wrapper, "get_mcp_schema")
            assert hasattr(wrapper, "invoke")
            assert hasattr(wrapper, "to_mcp_tool_definition")

            # Check that attributes are properly typed
            assert isinstance(wrapper.name, str)
            assert isinstance(wrapper.description, str)
            assert len(wrapper.name) > 0
            assert len(wrapper.description) > 0

        # Cleanup
        if server.db_manager:
            server.db_manager.close()

    @pytest.mark.asyncio
    async def test_database_connection_cleanup(self, neo4j_config: MCPServerConfig) -> None:
        """Test that database connections are properly cleaned up."""
        server = BlarifyMCPServer(neo4j_config)
        server._initialize_tools()

        # Verify database is connected
        assert server.db_manager is not None

        # Clean up the connection
        server.db_manager.close()

        # This test verifies cleanup runs without error
        assert True  # If we got here, cleanup worked
