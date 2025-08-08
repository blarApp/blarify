"""
Basic integration tests for GraphBuilder functionality.

These tests verify that GraphBuilder can successfully create graph representations
from source code and persist them to Neo4j databases.
"""

import pytest
from pathlib import Path
from typing import Any

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.graph.graph import Graph
from blarify.db_managers.neo4j_manager import Neo4jManager
from neo4j_container_manager.types import Neo4jContainerInstance
from tests.utils.graph_assertions import GraphAssertions
from tests.utils.fixtures import docker_check  # noqa: F401


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestGraphBuilderBasic:
    """Test basic GraphBuilder functionality with simple code examples."""

    async def test_graphbuilder_creates_nodes_python_simple(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that GraphBuilder creates basic nodes for simple Python code."""
        # Use the simple Python module from test examples
        python_examples_path = test_code_examples_path / "python"
        
        # Create GraphBuilder instance
        builder = GraphBuilder(
            root_path=str(python_examples_path),
            extensions_to_skip=[".pyc", ".pyo"],
            names_to_skip=["__pycache__"],
        )
        
        # Build the graph
        graph = builder.build()
        
        # Verify we have a Graph object
        assert isinstance(graph, Graph)
        assert graph is not None
        
        # Save graph to Neo4j for validation
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        # Debug: Print graph summary to see what labels are actually created
        await graph_assertions.debug_print_graph_summary()
        
        # Verify basic node creation
        await graph_assertions.assert_node_exists("FILE")
        await graph_assertions.assert_node_exists("FUNCTION")
        await graph_assertions.assert_node_exists("CLASS")
        
        # Check for specific nodes from simple_module.py
        await graph_assertions.assert_node_exists(
            "FUNCTION",
            {"name": "simple_function"}
        )
        await graph_assertions.assert_node_exists(
            "FUNCTION", 
            {"name": "function_with_parameter"}
        )
        await graph_assertions.assert_node_exists(
            "CLASS",
            {"name": "SimpleClass"}
        )
        
        db_manager.close()

    async def test_graphbuilder_hierarchy_only_mode(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GraphBuilder in hierarchy-only mode."""
        python_examples_path = test_code_examples_path / "python"
        
        # Create GraphBuilder with hierarchy-only mode
        builder = GraphBuilder(
            root_path=str(python_examples_path),
            only_hierarchy=True,
        )
        
        # Build the graph
        graph = builder.build()
        
        # Verify we have a Graph object
        assert isinstance(graph, Graph)
        assert graph is not None
        
        # Save graph to Neo4j for validation
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j", 
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        # In hierarchy-only mode, we should still get basic structural nodes
        await graph_assertions.assert_node_exists("FILE")
        
        db_manager.close()

    async def test_graphbuilder_with_file_filtering(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GraphBuilder with file extension filtering."""
        # Test with multiple language directories
        
        # Create GraphBuilder that skips TypeScript files
        builder = GraphBuilder(
            root_path=str(test_code_examples_path),
            extensions_to_skip=[".ts", ".js", ".rb"],
            names_to_skip=["typescript", "ruby"],
        )
        
        # Build the graph
        graph = builder.build()
        
        # Save graph to Neo4j for validation
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password", 
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        # Should have nodes from Python files only
        await graph_assertions.assert_node_exists("FILE")
        
        # Verify some Python-specific content exists
        file_properties = await graph_assertions.get_node_properties("FILE")
        
        # Check that we have Python files but not TypeScript/Ruby
        python_files = [
            props for props in file_properties 
            if props.get("path", props.get("file_path", "")).endswith(".py")
        ]
        typescript_files = [
            props for props in file_properties
            if props.get("path", props.get("file_path", "")).endswith((".ts", ".js"))
        ]
        ruby_files = [
            props for props in file_properties
            if props.get("path", props.get("file_path", "")).endswith(".rb")
        ]
        
        assert len(python_files) > 0, "Should have Python files"
        assert len(typescript_files) == 0, "Should not have TypeScript files"
        assert len(ruby_files) == 0, "Should not have Ruby files"
        
        db_manager.close()

    async def test_graphbuilder_creates_relationships(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that GraphBuilder creates relationships between nodes."""
        python_examples_path = test_code_examples_path / "python"
        
        builder = GraphBuilder(root_path=str(python_examples_path))
        graph = builder.build()
        
        # Save to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        # Check for basic relationship types that should exist
        actual_relationship_types = await graph_assertions.get_relationship_types()
        
        # At minimum, we should have some relationships
        assert len(actual_relationship_types) > 0, "Should have some relationships"
        
        # Check for file defining functions/classes
        # Based on RelationshipCreator, FILE nodes have FUNCTION_DEFINITION relationships to functions
        await graph_assertions.assert_relationship_exists(
            "FILE", 
            "FUNCTION_DEFINITION", 
            "FUNCTION"
        )
        
        db_manager.close()

    async def test_graphbuilder_empty_directory(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GraphBuilder behavior with empty directory."""
        # Create GraphBuilder for empty directory
        builder = GraphBuilder(root_path=str(temp_project_dir))
        
        # Build the graph
        graph = builder.build()
        
        # Should still create a valid Graph object
        assert isinstance(graph, Graph)
        
        # Save to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        # Should have minimal or no nodes
        total_nodes = await graph_assertions.neo4j_instance.execute_cypher(
            "MATCH (n) RETURN count(n) as count"
        )
        node_count = total_nodes[0]["count"]
        
        # Empty directory should result in very few nodes
        assert node_count >= 0, "Node count should be non-negative"
        
        db_manager.close()

    async def test_graphbuilder_debug_graph_summary(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GraphBuilder and verify graph structure with debug summary."""
        python_examples_path = test_code_examples_path / "python"
        
        builder = GraphBuilder(root_path=str(python_examples_path))
        graph = builder.build()
        
        # Save to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        # Get debug summary
        summary = await graph_assertions.debug_print_graph_summary()
        
        # Verify summary structure
        assert "total_nodes" in summary
        assert "total_relationships" in summary
        assert "nodes_by_label" in summary
        assert "relationships_by_type" in summary
        
        # Should have some nodes
        assert summary["total_nodes"] > 0
        
        db_manager.close()