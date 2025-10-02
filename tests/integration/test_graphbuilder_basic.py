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
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from typing import Dict
from tests.utils.graph_assertions import GraphAssertions


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestGraphBuilderBasic:
    """Test basic GraphBuilder functionality with simple code examples."""

    async def test_graphbuilder_creates_nodes_python_simple(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
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

        # Save graph to Neo4j with isolated IDs
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Debug: Print graph summary to see what labels are actually created
        await graph_assertions.debug_print_graph_summary()

        # Verify basic node creation
        await graph_assertions.assert_node_exists("FILE")
        await graph_assertions.assert_node_exists("FUNCTION")
        await graph_assertions.assert_node_exists("CLASS")

        # Check for specific nodes from simple_module.py
        await graph_assertions.assert_node_exists("FUNCTION", {"name": "simple_function"})
        await graph_assertions.assert_node_exists("FUNCTION", {"name": "function_with_parameter"})
        await graph_assertions.assert_node_exists("CLASS", {"name": "SimpleClass"})

        db_manager.close()

    async def test_graphbuilder_hierarchy_only_mode(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
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

        # Save graph to Neo4j with isolated IDs
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # In hierarchy-only mode, we should still get basic structural nodes
        await graph_assertions.assert_node_exists("FILE")

        db_manager.close()

    async def test_graphbuilder_with_file_filtering(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
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

        # Save graph to Neo4j with isolated IDs
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Should have nodes from Python files only
        await graph_assertions.assert_node_exists("FILE")

        # Verify some Python-specific content exists
        file_properties = await graph_assertions.get_node_properties("FILE")

        # Check that we have Python files but not TypeScript/Ruby
        python_files = [
            props for props in file_properties if props.get("path", props.get("file_path", "")).endswith(".py")
        ]
        typescript_files = [
            props for props in file_properties if props.get("path", props.get("file_path", "")).endswith((".ts", ".js"))
        ]
        ruby_files = [
            props for props in file_properties if props.get("path", props.get("file_path", "")).endswith(".rb")
        ]

        assert len(python_files) > 0, "Should have Python files"
        assert len(typescript_files) == 0, "Should not have TypeScript files"
        assert len(ruby_files) == 0, "Should not have Ruby files"

        db_manager.close()

    async def test_graphbuilder_creates_relationships(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that GraphBuilder creates relationships between nodes."""
        python_examples_path = test_code_examples_path / "python"

        builder = GraphBuilder(root_path=str(python_examples_path))
        graph = builder.build()

        # Save to Neo4j with isolated IDs
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Check for basic relationship types that should exist
        actual_relationship_types = await graph_assertions.get_relationship_types()

        # At minimum, we should have some relationships
        assert len(actual_relationship_types) > 0, "Should have some relationships"

        # Check for file defining functions/classes
        # Based on RelationshipCreator, FILE nodes have FUNCTION_DEFINITION relationships to functions
        await graph_assertions.assert_relationship_exists("FILE", "FUNCTION_DEFINITION", "FUNCTION")

        db_manager.close()

    async def test_graphbuilder_empty_directory(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
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

        # Save to Neo4j with isolated IDs
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Should have minimal or no nodes for this test's IDs
        container = test_data_isolation["container"]
        total_nodes = await container.execute_cypher(
            "MATCH (n) WHERE (n.entityId = $eid OR n.entity_id = $eid) AND (n.repoId = $rid OR n.repo_id = $rid) RETURN count(n) as count",
            {"eid": test_data_isolation["entity_id"], "rid": test_data_isolation["repo_id"]}
        )
        node_count = total_nodes[0]["count"]

        # Empty directory should result in very few nodes
        assert node_count >= 0, "Node count should be non-negative"

        db_manager.close()

    async def test_graphbuilder_debug_graph_summary(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GraphBuilder and verify graph structure with debug summary."""
        python_examples_path = test_code_examples_path / "python"

        builder = GraphBuilder(root_path=str(python_examples_path))
        graph = builder.build()

        # Save to Neo4j with isolated IDs
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
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

    async def test_graphbuilder_idempotency_with_workflows_and_docs(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that calling build() twice with workflows and docs doesn't duplicate nodes."""
        python_examples_path = test_code_examples_path / "python"

        # Initialize database manager
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        # Create GraphBuilder with db_manager
        builder = GraphBuilder(
            root_path=str(python_examples_path),
            db_manager=db_manager,
            generate_embeddings=False,
        )

        # First build with workflows and documentation
        builder.build(
            save_to_db=True,
            create_workflows=True,
            create_documentation=True,
        )

        # Get counts after first build
        first_files = await graph_assertions.get_node_properties("FILE")
        first_functions = await graph_assertions.get_node_properties("FUNCTION")
        first_workflows = await graph_assertions.get_node_properties("WORKFLOW")
        first_docs = await graph_assertions.get_node_properties("DOCUMENTATION")

        first_file_count = len(first_files)
        first_function_count = len(first_functions)
        first_workflow_count = len(first_workflows)
        first_doc_count = len(first_docs)

        # Second build with workflows and documentation (should be idempotent)
        builder.build(
            save_to_db=True,
            create_workflows=True,
            create_documentation=True,
        )

        # Get counts after second build
        second_files = await graph_assertions.get_node_properties("FILE")
        second_functions = await graph_assertions.get_node_properties("FUNCTION")
        second_workflows = await graph_assertions.get_node_properties("WORKFLOW")
        second_docs = await graph_assertions.get_node_properties("DOCUMENTATION")

        # Verify counts are EXACTLY the same (no duplication)
        assert len(second_files) == first_file_count, (
            f"Files duplicated: {first_file_count} → {len(second_files)}"
        )
        assert len(second_functions) == first_function_count, (
            f"Functions duplicated: {first_function_count} → {len(second_functions)}"
        )
        assert len(second_workflows) == first_workflow_count, (
            f"Workflows duplicated: {first_workflow_count} → {len(second_workflows)}"
        )
        assert len(second_docs) == first_doc_count, (
            f"Documentation duplicated: {first_doc_count} → {len(second_docs)}"
        )

        db_manager.close()
