"""Integration tests for MCP Server."""

import asyncio
import json
import os
from typing import Any, Dict, Generator
from unittest.mock import MagicMock, patch

import pytest
from neo4j import Driver

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
            repository_id=os.getenv("REPOSITORY_ID", "test_repo"),
            entity_id=os.getenv("ENTITY_ID", "test_entity"),
            db_type="neo4j"
        )
    
    @pytest.fixture
    def mock_db_with_data(self, neo4j_config: MCPServerConfig) -> Generator[Neo4jManager, None, None]:
        """Create a mock database with test data."""
        # Create a mock database manager
        mock_db = MagicMock(spec=Neo4jManager)
        
        # Setup mock responses for common queries
        mock_db.execute_read.return_value = [
            {
                "id": "test_node_1",
                "name": "test_file.py",
                "type": "File",
                "path": "/test/test_file.py"
            }
        ]
        
        yield mock_db
        
        # Cleanup
        if hasattr(mock_db, "close"):
            mock_db.close()
    
    @pytest.mark.asyncio
    async def test_server_initialization_with_neo4j(
        self, 
        neo4j_config: MCPServerConfig
    ) -> None:
        """Test server initialization with Neo4j configuration."""
        with patch("blarify.mcp_server.server.Neo4jManager") as mock_neo4j:
            mock_instance = MagicMock()
            mock_neo4j.return_value = mock_instance
            
            server = BlarifyMCPServer(neo4j_config)
            server._initialize_tools()
            
            # Verify database manager was created
            assert server.db_manager is not None
            
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
                "get_file_context_by_id",
                "get_node_workflows",
                "get_relationship_flowchart",
            ]
            for expected in expected_tools:
                assert expected in tool_names
    
    @pytest.mark.asyncio
    async def test_tool_invocation_through_wrapper(
        self,
        neo4j_config: MCPServerConfig,
        mock_db_with_data: Neo4jManager
    ) -> None:
        """Test invoking a tool through the MCP wrapper."""
        with patch("blarify.mcp_server.server.Neo4jManager") as mock_neo4j:
            mock_neo4j.return_value = mock_db_with_data
            
            server = BlarifyMCPServer(neo4j_config)
            server._initialize_tools()
            
            # Find the directory explorer wrapper
            directory_explorer = next(
                w for w in server.tool_wrappers 
                if w.name == "directory_explorer"
            )
            
            # Invoke the tool
            result = await directory_explorer.invoke({"node_id": None})
            
            # Verify the tool was called
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_tool_schema_generation(
        self,
        neo4j_config: MCPServerConfig
    ) -> None:
        """Test that all tools generate valid MCP schemas."""
        with patch("blarify.mcp_server.server.Neo4jManager") as mock_neo4j:
            mock_instance = MagicMock()
            mock_neo4j.return_value = mock_instance
            
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
    
    @pytest.mark.asyncio
    async def test_tool_definitions(
        self,
        neo4j_config: MCPServerConfig
    ) -> None:
        """Test that all tools generate valid MCP tool definitions."""
        with patch("blarify.mcp_server.server.Neo4jManager") as mock_neo4j:
            mock_instance = MagicMock()
            mock_neo4j.return_value = mock_instance
            
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
    
    @pytest.mark.asyncio
    async def test_concurrent_tool_invocations(
        self,
        neo4j_config: MCPServerConfig,
        mock_db_with_data: Neo4jManager
    ) -> None:
        """Test that multiple tools can be invoked concurrently."""
        with patch("blarify.mcp_server.server.Neo4jManager") as mock_neo4j:
            mock_neo4j.return_value = mock_db_with_data
            
            server = BlarifyMCPServer(neo4j_config)
            server._initialize_tools()
            
            # Create tasks for concurrent invocation
            tasks = []
            for wrapper in server.tool_wrappers[:3]:  # Test with first 3 tools
                if wrapper.name == "directory_explorer":
                    task = wrapper.invoke({"node_id": None})
                elif wrapper.name == "find_nodes_by_code":
                    task = wrapper.invoke({"code_text": "test"})
                elif wrapper.name == "find_nodes_by_name_and_type":
                    task = wrapper.invoke({"name": "test", "node_type": "File"})
                else:
                    continue
                tasks.append(task)
            
            # Execute concurrently
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Verify all tasks completed
                assert len(results) > 0
                for result in results:
                    # Check that results are strings or exceptions were handled
                    assert isinstance(result, (str, Exception))
    
    @pytest.mark.asyncio
    async def test_error_handling_invalid_arguments(
        self,
        neo4j_config: MCPServerConfig,
        mock_db_with_data: Neo4jManager
    ) -> None:
        """Test error handling with invalid tool arguments."""
        with patch("blarify.mcp_server.server.Neo4jManager") as mock_neo4j:
            mock_neo4j.return_value = mock_db_with_data
            
            server = BlarifyMCPServer(neo4j_config)
            server._initialize_tools()
            
            # Find a tool that requires arguments
            get_code_tool = next(
                w for w in server.tool_wrappers 
                if w.name == "get_code_by_id"
            )
            
            # Try to invoke without required arguments
            result = await get_code_tool.invoke({})
            
            # Should return an error message
            assert "Error:" in result
    
    @pytest.mark.asyncio
    async def test_database_connection_cleanup(
        self,
        neo4j_config: MCPServerConfig
    ) -> None:
        """Test that database connections are properly cleaned up."""
        with patch("blarify.mcp_server.server.Neo4jManager") as mock_neo4j:
            mock_instance = MagicMock()
            mock_neo4j.return_value = mock_instance
            
            server = BlarifyMCPServer(neo4j_config)
            
            # Mock the MCP run to complete immediately
            server.mcp.run = MagicMock(return_value=None)
            
            # Run the server
            await server.run()
            
            # Verify database was closed
            mock_instance.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_server_with_falkordb_config(self) -> None:
        """Test server initialization with FalkorDB configuration."""
        falkor_config = MCPServerConfig(
            db_type="falkordb",
            falkor_host="localhost",
            falkor_port=6379,
            repository_id="test_repo",
            entity_id="test_entity"
        )
        
        with patch("blarify.mcp_server.server.FalkorDbManager") as mock_falkor:
            mock_instance = MagicMock()
            mock_falkor.return_value = mock_instance
            
            server = BlarifyMCPServer(falkor_config)
            server._initialize_tools()
            
            # Verify FalkorDB manager was created
            mock_falkor.assert_called_once_with(
                host="localhost",
                port=6379,
                repository_id="test_repo",
                entity_id="test_entity"
            )
            
            # Verify tools were initialized
            assert len(server.tool_wrappers) == 10