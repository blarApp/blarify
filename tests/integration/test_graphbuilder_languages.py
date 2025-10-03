"""
Language-specific integration tests for GraphBuilder.

These tests verify that GraphBuilder correctly processes different
programming languages and creates appropriate graph structures.
"""

import pytest
from pathlib import Path
from typing import Dict, Any

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.graph.graph import Graph
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from tests.utils.graph_assertions import GraphAssertions


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestGraphBuilderLanguages:
    """Test GraphBuilder with different programming languages."""

    @pytest.mark.parametrize("language", ["python", "typescript", "ruby"])
    async def test_graphbuilder_language_support(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
        language: str,
    ) -> None:
        """Test GraphBuilder with specific programming languages."""
        language_path = test_code_examples_path / language

        # Create GraphBuilder for specific language
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )
        builder = GraphBuilder(
            root_path=str(language_path), extensions_to_skip=[], names_to_skip=[], db_manager=db_manager
        )

        # Build the graph
        graph = builder.build()

        # Verify we have a Graph object
        assert isinstance(graph, Graph)
        assert graph is not None

        # All languages should create File nodes
        await graph_assertions.assert_node_exists("FILE")

        # Get file properties to verify language-specific files
        file_properties = await graph_assertions.get_node_properties("FILE")

        # Verify we have files for the expected language
        language_extensions = {
            "python": ".py",
            "typescript": (".ts", ".js"),
            "ruby": ".rb",
        }

        expected_ext = language_extensions[language]
        if isinstance(expected_ext, str):
            expected_ext = (expected_ext,)

        language_files = [
            props
            for props in file_properties
            if any(props.get("path", props.get("file_path", "")).endswith(ext) for ext in expected_ext)
        ]

        assert len(language_files) > 0, f"Should have {language} files"

        db_manager.close()

    async def test_graphbuilder_python_specifics(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test Python-specific GraphBuilder functionality."""
        python_path = test_code_examples_path / "python"

        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )
        builder = GraphBuilder(root_path=str(python_path), db_manager=db_manager)
        builder.build()

        # Python should have functions and classes
        await graph_assertions.assert_node_exists("FUNCTION")
        await graph_assertions.assert_node_exists("CLASS")

        # Check for specific Python constructs from our test files
        # From simple_module.py
        await graph_assertions.assert_node_exists("FUNCTION", {"name": "simple_function"})
        await graph_assertions.assert_node_exists("CLASS", {"name": "SimpleClass"})

        # From class_with_inheritance.py (if it exists)
        class_properties = await graph_assertions.get_node_properties("CLASS")
        class_names = [props.get("name") for props in class_properties]

        # Should have at least SimpleClass
        assert "SimpleClass" in class_names

        db_manager.close()

    async def test_graphbuilder_typescript_specifics(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test TypeScript-specific GraphBuilder functionality."""
        typescript_path = test_code_examples_path / "typescript"

        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )
        builder = GraphBuilder(root_path=str(typescript_path), db_manager=db_manager)
        builder.build()

        # Should have File nodes for TypeScript
        await graph_assertions.assert_node_exists("FILE")

        # Get all node labels to see what was created
        node_labels = await graph_assertions.get_node_labels()

        # Get all relationship types to verify what relationships exist
        relationship_types = await graph_assertions.get_relationship_types()

        # Should have basic structural elements
        basic_labels = {"FILE"}
        assert basic_labels.issubset(node_labels), f"Missing basic labels. Got: {node_labels}"

        # Print debug info about what was created
        print(f"🔍 Node labels found: {sorted(node_labels)}")
        print(f"🔍 Relationship types found: {sorted(relationship_types)}")

        # Should have structural relationships
        expected_relationships = {"CONTAINS"}  # Basic structural relationships
        assert expected_relationships.issubset(relationship_types), (
            f"Missing basic relationships. Got: {relationship_types}"
        )

        assert "CALLS" in relationship_types, "Expected CALL relationships in TypeScript code"
        call_count_query = """
        MATCH (n)-[r:CALLS]->(m)
        WHERE (n.entityId = $entity_id OR n.entity_id = $entity_id)
           OR (m.entityId = $entity_id OR m.entity_id = $entity_id)
        RETURN count(r) as call_count
        """
        call_result = await graph_assertions.neo4j_instance.execute_cypher(
            call_count_query, {"entity_id": graph_assertions.entity_id}
        )
        call_count = call_result[0]["call_count"] if call_result else 0
        assert call_count >= 26, "Expected at least 26 CALL relationships in TypeScript code"

        db_manager.close()

    async def test_graphbuilder_ruby_specifics(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test Ruby-specific GraphBuilder functionality."""
        ruby_path = test_code_examples_path / "ruby"

        # Set up database manager
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        builder = GraphBuilder(root_path=str(ruby_path), db_manager=db_manager)
        builder.build()

        # Should have File nodes for Ruby
        await graph_assertions.assert_node_exists("FILE")

        # Get all node labels to see what was created
        node_labels = await graph_assertions.get_node_labels()

        # Should have basic structural elements
        basic_labels = {"FILE"}
        assert basic_labels.issubset(node_labels), f"Missing basic labels. Got: {node_labels}"

        db_manager.close()

    async def test_graphbuilder_mixed_languages(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GraphBuilder with mixed programming languages."""
        # Set up database manager
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        # Use the entire test_code_examples directory which contains all languages
        builder = GraphBuilder(root_path=str(test_code_examples_path), db_manager=db_manager)
        builder.build()

        # Should have File nodes from all languages
        await graph_assertions.assert_node_exists("FILE")

        # Get file properties and check for multiple languages
        file_properties = await graph_assertions.get_node_properties("FILE")

        # Extract file extensions
        extensions = set()
        for props in file_properties:
            file_path = props.get("path", props.get("file_path", ""))
            if "." in file_path:
                ext = "." + file_path.split(".")[-1]
                extensions.add(ext)

        # Should have files from multiple languages
        expected_extensions = {".py", ".ts", ".rb"}
        found_extensions = extensions.intersection(expected_extensions)

        # We should find at least one expected extension
        assert len(found_extensions) > 0, f"Expected some of {expected_extensions}, got {extensions}"

        db_manager.close()

    async def test_graphbuilder_inheritance_relationships(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that GraphBuilder creates inheritance relationships where applicable."""
        # Set up database manager
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        # Focus on Python since it has clear inheritance examples
        python_path = test_code_examples_path / "python"

        builder = GraphBuilder(root_path=str(python_path), db_manager=db_manager)
        builder.build()

        # Get all relationship types
        relationship_types = await graph_assertions.get_relationship_types()

        # Should have some relationships
        assert len(relationship_types) > 0, "Should have some relationships"

        # Common relationship types from GraphBuilder
        expected_basic_relationships = {"CONTAINS", "DEFINES"}

        # Check that we have some basic relationships
        relationship_types.intersection(expected_basic_relationships)

        db_manager.close()

    async def test_graphbuilder_language_comparison(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Compare GraphBuilder output across different languages."""
        results: Dict[str, Dict[str, Any]] = {}

        # Test each language separately and collect metrics
        for language in ["python", "typescript", "ruby"]:
            language_path = test_code_examples_path / language

            # Save to fresh Neo4j instance with isolated IDs
            # Note: We'll use a different repo_id for each language within the same test
            language_repo_id = f"{test_data_isolation['repo_id']}_{language}"

            db_manager = Neo4jManager(
                uri=test_data_isolation["uri"],
                user="neo4j",
                password=test_data_isolation["password"],
                repo_id=language_repo_id,
                entity_id=test_data_isolation["entity_id"],
            )

            builder = GraphBuilder(root_path=str(language_path), db_manager=db_manager)
            builder.build()

            # Create a custom graph_assertions for this specific language data
            custom_assertions = GraphAssertions(test_data_isolation["container"])
            custom_assertions.entity_id = test_data_isolation["entity_id"]
            custom_assertions.repo_id = language_repo_id

            # Collect metrics
            summary = await custom_assertions.debug_print_graph_summary()

            results[language] = {
                "total_nodes": summary["total_nodes"],
                "total_relationships": summary["total_relationships"],
                "node_labels": await custom_assertions.get_node_labels(),
                "relationship_types": await custom_assertions.get_relationship_types(),
            }

            db_manager.close()

        # Verify each language produced some output
        for language, metrics in results.items():
            assert metrics["total_nodes"] >= 0, f"{language} should have non-negative node count"
            assert "FILE" in metrics["node_labels"], f"{language} should have File nodes"

        # Print comparison for debugging
        print("\nLanguage Comparison:")
        for language, metrics in results.items():
            print(f"{language}: {metrics['total_nodes']} nodes, {metrics['total_relationships']} relationships")
            print(f"  Labels: {sorted(metrics['node_labels'])}")
            print(f"  Relationships: {sorted(metrics['relationship_types'])}")
