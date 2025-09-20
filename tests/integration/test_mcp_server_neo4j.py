"""Integration tests for MCP Server with real Neo4j containers."""

import asyncio
import json
from pathlib import Path
from typing import Any, Optional, Dict

import pytest
from blarify.mcp_server.server import BlarifyMCPServer
from blarify.mcp_server.tools import MCPToolWrapper
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from tests.utils.graph_assertions import GraphAssertions


@pytest.mark.integration
@pytest.mark.neo4j_integration
@pytest.mark.asyncio
class TestMCPServerNeo4jIntegration:
    """Integration tests for MCP Server with real Neo4j database."""

    async def test_mcp_server_initialization(self, docker_check: Any, mcp_server_with_neo4j: BlarifyMCPServer) -> None:
        """Test that MCP server initializes correctly with Neo4j."""
        assert mcp_server_with_neo4j is not None
        assert mcp_server_with_neo4j.db_manager is not None
        assert len(mcp_server_with_neo4j.tool_wrappers) == 10

        # Verify tool names
        tool_names = [wrapper.name for wrapper in mcp_server_with_neo4j.tool_wrappers]
        expected_tools = [
            "directory_explorer",
            "find_nodes_by_code",
            "find_nodes_by_name_and_type",
            "find_nodes_by_path",
            "get_blame_by_id",
            "get_code_by_id",
            "get_commit_by_id",
            "see_node_in_file_context",
            "get_node_workflows",
            "get_relationship_flowchart",
        ]
        for tool in expected_tools:
            assert tool in tool_names

    async def test_directory_explorer_with_data(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        mcp_server_with_neo4j: BlarifyMCPServer,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test DirectoryExplorerTool with actual graph data."""
        # First, populate the database with test data
        python_path = test_code_examples_path / "python"
        builder = GraphBuilder(root_path=str(python_path))
        graph = builder.build()

        # Save graph to Neo4j
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password="test-password",
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )
        try:
            db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

            # Verify data was saved
            await graph_assertions.assert_node_exists("FILE")

            # Now test the MCP tool
            directory_explorer = self._get_tool_wrapper(mcp_server_with_neo4j, "directory_explorer")
            assert directory_explorer is not None

            # Test listing root directory
            result = await directory_explorer.invoke({})
            assert result is not None
            assert isinstance(result, str)
            # The result should contain some directory information
            assert len(result) > 0
        finally:
            db_manager.close()

    async def test_find_nodes_by_code_with_data(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        mcp_server_with_neo4j: BlarifyMCPServer,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test FindNodesByCode with actual code in database."""
        # Populate database with Python code examples
        python_path = test_code_examples_path / "python"
        builder = GraphBuilder(root_path=str(python_path))
        graph = builder.build()

        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password="test-password",
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )
        try:
            db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

            # Test the tool
            find_code_tool = self._get_tool_wrapper(mcp_server_with_neo4j, "find_nodes_by_code")
            assert find_code_tool is not None

            # Search for "def" which should exist in Python files
            result = await find_code_tool.invoke({"code_text": "def"})
            assert result is not None
            assert isinstance(result, str)
            # Should find some function definitions
            assert len(result) > 0
        finally:
            db_manager.close()

    async def test_get_code_by_id_with_data(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        mcp_server_with_neo4j: BlarifyMCPServer,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GetCodeByIdTool with actual nodes in database."""
        # Populate database
        python_path = test_code_examples_path / "python"
        builder = GraphBuilder(root_path=str(python_path))
        graph = builder.build()

        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password="test-password",
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )
        try:
            db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

            # Get a node ID from the graph
            nodes = graph.get_nodes_as_objects()
            if nodes:
                test_node = nodes[0]
                node_id = test_node.get("node_id", "")

                if node_id:
                    # Test the tool
                    get_code_tool = self._get_tool_wrapper(mcp_server_with_neo4j, "get_code_by_id")
                    assert get_code_tool is not None

                    result = await get_code_tool.invoke({"node_id": node_id})
                    assert result is not None
                    assert isinstance(result, str)
                    assert len(result) > 0
        finally:
            db_manager.close()

    async def test_all_tool_schemas_valid(self, mcp_server_with_neo4j: BlarifyMCPServer) -> None:
        """Test that all tools generate valid MCP schemas."""
        for wrapper in mcp_server_with_neo4j.tool_wrappers:
            schema = wrapper.get_mcp_schema()

            # Verify basic schema structure
            assert "type" in schema
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "required" in schema
            assert isinstance(schema["properties"], dict)
            assert isinstance(schema["required"], list)

            # Verify JSON serialization
            json_str = json.dumps(schema)
            assert json_str is not None

            # Verify tool definition
            definition = wrapper.to_mcp_tool_definition()
            assert definition["name"] == wrapper.name
            assert definition["description"] is not None
            assert definition["inputSchema"] == schema

    async def test_concurrent_tool_execution(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        mcp_server_with_neo4j: BlarifyMCPServer,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test multiple tools executing concurrently."""
        # Populate database
        python_path = test_code_examples_path / "python"
        builder = GraphBuilder(root_path=str(python_path))
        graph = builder.build()

        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password="test-password",
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )
        try:
            db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

            # Get multiple tool wrappers
            directory_tool = self._get_tool_wrapper(mcp_server_with_neo4j, "directory_explorer")
            code_search_tool = self._get_tool_wrapper(mcp_server_with_neo4j, "find_nodes_by_code")
            name_search_tool = self._get_tool_wrapper(mcp_server_with_neo4j, "find_nodes_by_name_and_type")

            assert directory_tool is not None
            assert code_search_tool is not None
            assert name_search_tool is not None

            # Create concurrent tasks
            tasks = [
                directory_tool.invoke({}),
                code_search_tool.invoke({"code_text": "def"}),
                name_search_tool.invoke({"name": "test", "node_type": "FUNCTION"}),
            ]

            # Execute concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify all completed
            assert len(results) == 3
            for result in results:
                if not isinstance(result, Exception):
                    assert isinstance(result, str)
        finally:
            db_manager.close()

    async def test_tool_error_handling(self, mcp_server_with_neo4j: BlarifyMCPServer) -> None:
        """Test error handling when tools receive invalid input."""
        # Test with missing required parameters
        get_code_tool = self._get_tool_wrapper(mcp_server_with_neo4j, "get_code_by_id")
        assert get_code_tool is not None

        # This should return an error since node_id is required
        result = await get_code_tool.invoke({})
        assert result is not None
        assert "Error:" in result

        # Test with invalid node_id
        result = await get_code_tool.invoke({"node_id": "nonexistent_node_12345"})
        assert result is not None
        # The tool should handle this gracefully
        assert isinstance(result, str)

    async def test_find_nodes_by_path(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        mcp_server_with_neo4j: BlarifyMCPServer,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test FindNodesByPath tool."""
        # Populate database
        python_path = test_code_examples_path / "python"
        builder = GraphBuilder(root_path=str(python_path))
        graph = builder.build()

        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password="test-password",
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )
        try:
            db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

            # Test the tool
            find_path_tool = self._get_tool_wrapper(mcp_server_with_neo4j, "find_nodes_by_path")
            assert find_path_tool is not None

            # Get actual paths from the graph
            nodes = graph.get_nodes_as_objects()
            test_paths = []
            for node in nodes[:2]:  # Get first 2 paths
                if "file_path" in node:
                    test_paths.append(node["file_path"])

            if test_paths:
                result = await find_path_tool.invoke({"paths": test_paths})
                assert result is not None
                assert isinstance(result, str)
                assert len(result) > 0
        finally:
            db_manager.close()

    async def test_get_file_context_by_id(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        mcp_server_with_neo4j: BlarifyMCPServer,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GetFileContextByIdTool."""
        # Populate database
        python_path = test_code_examples_path / "python"
        builder = GraphBuilder(root_path=str(python_path))
        graph = builder.build()

        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password="test-password",
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )
        try:
            db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

            # Get a function node for testing
            nodes = graph.get_nodes_as_objects()
            function_node = None
            for node in nodes:
                if node.get("type") == "FUNCTION":
                    function_node = node
                    break

            if function_node:
                # Test the tool
                context_tool = self._get_tool_wrapper(mcp_server_with_neo4j, "see_node_in_file_context")
                assert context_tool is not None

                result = await context_tool.invoke(
                    {"node_id": function_node["attributes"]["node_id"], "context_lines": 5}
                )
                assert result is not None
                assert isinstance(result, str)
                assert len(result) > 0
        finally:
            db_manager.close()

    def _get_tool_wrapper(self, server: BlarifyMCPServer, tool_name: str) -> Optional[MCPToolWrapper]:
        """Helper to get a tool wrapper by name."""
        for wrapper in server.tool_wrappers:
            if wrapper.name == tool_name:
                return wrapper
        return None
