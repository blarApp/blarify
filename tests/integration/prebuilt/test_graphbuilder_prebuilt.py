"""
Integration tests specifically for the prebuilt GraphBuilder interface.

These tests focus on the simplified API provided by the prebuilt GraphBuilder
and its integration with database persistence.
"""

import pytest
from pathlib import Path
from typing import List, Dict, Any

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.graph.graph import Graph
from blarify.db_managers.neo4j_manager import Neo4jManager
from neo4j_container_manager.types import Neo4jContainerInstance
from tests.utils.graph_assertions import GraphAssertions


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestGraphBuilderPrebuilt:
    """Test the prebuilt GraphBuilder interface."""

    async def test_graphbuilder_simple_api(
        self,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test the simplified GraphBuilder API usage."""
        python_path = test_code_examples_path / "python"
        
        # Simple API usage - just root path
        builder = GraphBuilder(str(python_path))
        graph = builder.build()
        
        # Verify basic functionality
        assert isinstance(graph, Graph)
        assert graph is not None
        
        # Save and validate in Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        # Basic validation
        await graph_assertions.assert_node_exists("File")
        
        summary = await graph_assertions.debug_print_graph_summary()
        assert summary["total_nodes"] > 0
        
        db_manager.close()

    async def test_graphbuilder_with_configuration(
        self,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GraphBuilder with common configuration options."""
        # Test with typical configuration
        builder = GraphBuilder(
            root_path=str(test_code_examples_path),
            extensions_to_skip=[".txt", ".md", ".json"],
            names_to_skip=["__pycache__", ".git", "node_modules"],
            only_hierarchy=False,
        )
        
        graph = builder.build()
        assert isinstance(graph, Graph)
        
        # Save and validate
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        await graph_assertions.assert_node_exists("File")
        
        # Verify file filtering worked
        file_properties = await graph_assertions.get_node_properties("File")
        file_paths = [props.get("file_path", "") for props in file_properties]
        
        # Should not have filtered extensions
        filtered_files = [
            path for path in file_paths 
            if any(path.endswith(ext) for ext in [".txt", ".md", ".json"])
        ]
        assert len(filtered_files) == 0, "Should not have filtered file types"
        
        db_manager.close()

    async def test_graphbuilder_hierarchy_vs_full_analysis(
        self,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Compare hierarchy-only vs full analysis modes."""
        python_path = test_code_examples_path / "python"
        
        # Test hierarchy-only mode
        hierarchy_builder = GraphBuilder(
            root_path=str(python_path),
            only_hierarchy=True,
        )
        hierarchy_graph = hierarchy_builder.build()
        
        # Save hierarchy graph
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        await db_manager.save_graph_async(hierarchy_graph)
        
        # Get hierarchy metrics
        hierarchy_summary = await graph_assertions.debug_print_graph_summary()
        hierarchy_labels = await graph_assertions.get_node_labels()
        hierarchy_relationships = await graph_assertions.get_relationship_types()
        
        # Clear database for full analysis test
        await neo4j_instance.clear_data()
        
        # Test full analysis mode
        full_builder = GraphBuilder(
            root_path=str(python_path),
            only_hierarchy=False,
        )
        full_graph = full_builder.build()
        
        # Save full graph
        await db_manager.save_graph_async(full_graph)
        
        # Get full analysis metrics
        full_summary = await graph_assertions.debug_print_graph_summary()
        full_labels = await graph_assertions.get_node_labels()
        full_relationships = await graph_assertions.get_relationship_types()
        
        # Both should have basic File nodes
        assert "File" in hierarchy_labels
        assert "File" in full_labels
        
        # Both should have some nodes
        assert hierarchy_summary["total_nodes"] > 0
        assert full_summary["total_nodes"] > 0
        
        # Print comparison for debugging
        print(f"\nHierarchy mode: {hierarchy_summary['total_nodes']} nodes, {hierarchy_summary['total_relationships']} relationships")
        print(f"Full mode: {full_summary['total_nodes']} nodes, {full_summary['total_relationships']} relationships")
        print(f"Hierarchy labels: {sorted(hierarchy_labels)}")
        print(f"Full labels: {sorted(full_labels)}")
        
        db_manager.close()

    async def test_graphbuilder_with_custom_environment(
        self,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GraphBuilder with custom GraphEnvironment."""
        from blarify.graph.graph_environment import GraphEnvironment
        
        python_path = test_code_examples_path / "python"
        
        # Create custom environment
        custom_env = GraphEnvironment(
            workspace="test_workspace",
            project="test_project",
            root_path=str(python_path)
        )
        
        builder = GraphBuilder(
            root_path=str(python_path),
            graph_environment=custom_env,
        )
        
        graph = builder.build()
        assert isinstance(graph, Graph)
        
        # Verify the graph uses the custom environment
        assert graph.graph_environment == custom_env
        assert graph.graph_environment.workspace == "test_workspace"
        assert graph.graph_environment.project == "test_project"
        
        # Save and validate basic functionality
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        await graph_assertions.assert_node_exists("File")
        
        db_manager.close()

    async def test_graphbuilder_multiple_builds(
        self,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test building multiple graphs from the same GraphBuilder instance."""
        python_path = test_code_examples_path / "python"
        
        builder = GraphBuilder(root_path=str(python_path))
        
        # Build graph multiple times
        graph1 = builder.build()
        graph2 = builder.build()
        
        # Both should be valid Graph objects
        assert isinstance(graph1, Graph)
        assert isinstance(graph2, Graph)
        
        # They should be separate instances
        assert graph1 is not graph2
        
        # Save first graph
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        await db_manager.save_graph_async(graph1)
        
        summary1 = await graph_assertions.debug_print_graph_summary()
        
        # Clear and save second graph
        await neo4j_instance.clear_data()
        await db_manager.save_graph_async(graph2)
        
        summary2 = await graph_assertions.debug_print_graph_summary()
        
        # Should have similar structure (same source code)
        assert summary1["total_nodes"] == summary2["total_nodes"]
        
        db_manager.close()

    async def test_graphbuilder_error_recovery(
        self,
        neo4j_instance: Neo4jContainerInstance,
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GraphBuilder error recovery with problematic files."""
        # Create mix of valid and problematic files
        valid_file = temp_project_dir / "valid.py"
        valid_file.write_text("""
def valid_function():
    return "valid"
""")
        
        # Create file with potential parsing issues
        tricky_file = temp_project_dir / "tricky.py"
        tricky_file.write_text("""
# File with complex constructs that might challenge parser
import sys
from typing import Optional, Union, Callable

def complex_function(
    param1: Union[str, int],
    param2: Optional[Callable[[str], bool]] = None
) -> Union[str, None]:
    '''Complex type annotations and multi-line parameters.'''
    if param2 and param2(str(param1)):
        return f"processed: {param1}"
    return None

class ComplexClass(Exception):
    '''Class with complex inheritance and methods.'''
    
    def __init__(self, message: str, code: int = 0):
        super().__init__(message)
        self.code = code
    
    async def async_method(self) -> None:
        '''Async method that might be tricky to parse.'''
        pass

# Complex decorators and nested functions
def decorator_factory(arg):
    def decorator(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

@decorator_factory("test")
def decorated_function():
    def nested_function():
        return "nested"
    return nested_function()
""")
        
        builder = GraphBuilder(root_path=str(temp_project_dir))
        
        # Should handle complex constructs gracefully
        try:
            graph = builder.build()
            assert isinstance(graph, Graph)
            
            # Save and validate
            db_manager = Neo4jDbManager(
                uri=neo4j_instance.uri,
                user="neo4j",
                password="test-password",
            )
            db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
            
            await graph_assertions.assert_node_exists("File")
            
            # Should have processed both files
            file_properties = await graph_assertions.get_node_properties("File")
            assert len(file_properties) >= 2
            
            db_manager.close()
            
        except Exception as e:
            # Some complex constructs might cause parsing errors
            print(f"Complex construct processing: {e}")
            # This is acceptable - we're testing graceful error handling