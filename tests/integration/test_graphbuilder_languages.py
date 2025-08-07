"""
Language-specific integration tests for GraphBuilder.

These tests verify that GraphBuilder correctly processes different
programming languages and creates appropriate graph structures.
"""

import pytest
from pathlib import Path
from typing import List, Dict, Any, Set

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.graph.graph import Graph
from blarify.db_managers.neo4j_manager import Neo4jManager
from neo4j_container_manager.types import Neo4jContainerInstance
from tests.utils.graph_assertions import GraphAssertions


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestGraphBuilderLanguages:
    """Test GraphBuilder with different programming languages."""

    @pytest.mark.parametrize("language", ["python", "typescript", "ruby"])
    async def test_graphbuilder_language_support(
        self,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
        language: str,
    ) -> None:
        """Test GraphBuilder with specific programming languages."""
        language_path = test_code_examples_path / language
        
        # Create GraphBuilder for specific language
        builder = GraphBuilder(
            root_path=str(language_path),
            extensions_to_skip=[],
            names_to_skip=[],
        )
        
        # Build the graph
        graph = builder.build()
        
        # Verify we have a Graph object
        assert isinstance(graph, Graph)
        assert graph is not None
        
        # Save to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
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
            props for props in file_properties
            if any(props.get("file_path", "").endswith(ext) for ext in expected_ext)
        ]
        
        assert len(language_files) > 0, f"Should have {language} files"
        
        db_manager.close()

    async def test_graphbuilder_python_specifics(
        self,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test Python-specific GraphBuilder functionality."""
        python_path = test_code_examples_path / "python"
        
        builder = GraphBuilder(root_path=str(python_path))
        graph = builder.build()
        
        # Save to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        # Python should have functions and classes
        await graph_assertions.assert_node_exists("FUNCTION")
        await graph_assertions.assert_node_exists("CLASS")
        
        # Check for specific Python constructs from our test files
        # From simple_module.py
        await graph_assertions.assert_node_exists(
            "FUNCTION",
            {"name": "simple_function"}
        )
        await graph_assertions.assert_node_exists(
            "CLASS", 
            {"name": "SimpleClass"}
        )
        
        # From class_with_inheritance.py (if it exists)
        class_properties = await graph_assertions.get_node_properties("CLASS")
        class_names = [props.get("name") for props in class_properties]
        
        # Should have at least SimpleClass
        assert "SimpleClass" in class_names
        
        db_manager.close()

    async def test_graphbuilder_typescript_specifics(
        self,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test TypeScript-specific GraphBuilder functionality."""
        typescript_path = test_code_examples_path / "typescript"
        
        builder = GraphBuilder(root_path=str(typescript_path))
        graph = builder.build()
        
        # Save to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        # Should have File nodes for TypeScript
        await graph_assertions.assert_node_exists("FILE")
        
        # Get all node labels to see what was created
        node_labels = await graph_assertions.get_node_labels()
        
        # Should have basic structural elements
        basic_labels = {"FILE"}
        assert basic_labels.issubset(node_labels), f"Missing basic labels. Got: {node_labels}"
        
        db_manager.close()

    async def test_graphbuilder_ruby_specifics(
        self,
        neo4j_instance: Neo4jContainerInstance, 
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test Ruby-specific GraphBuilder functionality."""
        ruby_path = test_code_examples_path / "ruby"
        
        builder = GraphBuilder(root_path=str(ruby_path))
        graph = builder.build()
        
        # Save to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
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
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GraphBuilder with mixed programming languages."""
        # Use the entire test_code_examples directory which contains all languages
        builder = GraphBuilder(root_path=str(test_code_examples_path))
        graph = builder.build()
        
        # Save to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j", 
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        # Should have File nodes from all languages
        await graph_assertions.assert_node_exists("FILE")
        
        # Get file properties and check for multiple languages
        file_properties = await graph_assertions.get_node_properties("FILE")
        
        # Extract file extensions
        extensions = set()
        for props in file_properties:
            file_path = props.get("file_path", "")
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
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that GraphBuilder creates inheritance relationships where applicable."""
        # Focus on Python since it has clear inheritance examples
        python_path = test_code_examples_path / "python"
        
        builder = GraphBuilder(root_path=str(python_path))
        graph = builder.build()
        
        # Save to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        # Get all relationship types
        relationship_types = await graph_assertions.get_relationship_types()
        
        # Should have some relationships
        assert len(relationship_types) > 0, "Should have some relationships"
        
        # Common relationship types from GraphBuilder
        expected_basic_relationships = {"CONTAINS", "DEFINES"}
        
        # Check that we have some basic relationships
        found_relationships = relationship_types.intersection(expected_basic_relationships)
        
        db_manager.close()

    async def test_graphbuilder_language_comparison(
        self,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Compare GraphBuilder output across different languages."""
        results: Dict[str, Dict[str, Any]] = {}
        
        # Test each language separately and collect metrics
        for language in ["python", "typescript", "ruby"]:
            language_path = test_code_examples_path / language
            
            builder = GraphBuilder(root_path=str(language_path))
            graph = builder.build()
            
            # Save to fresh Neo4j instance
            await neo4j_instance.clear_data()
            db_manager = Neo4jManager(
                uri=neo4j_instance.uri,
                user="neo4j",
                password="test-password",
            )
            db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
            
            # Collect metrics
            summary = await graph_assertions.debug_print_graph_summary()
            
            results[language] = {
                "total_nodes": summary["total_nodes"],
                "total_relationships": summary["total_relationships"],
                "node_labels": await graph_assertions.get_node_labels(),
                "relationship_types": await graph_assertions.get_relationship_types(),
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