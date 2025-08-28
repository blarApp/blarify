"""
Tests for cycle detection in recursive DFS processor.

This test suite verifies that cycle detection correctly identifies real cycles
and doesn't produce false positives for common patterns like shared dependencies.
"""

import pytest
from pathlib import Path
from typing import Any
import tempfile

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.repositories.graph_db_manager.queries import detect_function_cycles
from neo4j_container_manager.types import Neo4jContainerInstance
from tests.utils.graph_assertions import GraphAssertions


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestCycleDetection:
    """Test suite for verifying correct cycle detection."""

    async def test_existing_simple_cycle_detection(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ):
        """
        Test cycle detection with existing simple cycle examples.

        Uses the test_code_examples/circular_deps/simple_cycle directory
        which contains modules with actual circular dependencies.
        """
        # Use the existing simple cycle examples
        simple_cycle_path = test_code_examples_path / "circular_deps" / "simple_cycle"

        # Build graph
        builder = GraphBuilder(
            root_path=str(simple_cycle_path), extensions_to_skip=[".pyc", ".pyo"], names_to_skip=["__pycache__"]
        )
        graph = builder.build()

        # Save to Neo4j
        db_manager = Neo4jManager(uri=neo4j_instance.uri, user="neo4j", password="test-password")

        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Debug: Print graph summary to see what was created
        await graph_assertions.debug_print_graph_summary()

        # Check for cycles in functions
        function_props = await graph_assertions.get_node_properties("FUNCTION")

        cycles_found = {}
        for node in function_props:
            node_id = node.get("node_id")
            name = node.get("name")
            if node_id and name:
                cycles = detect_function_cycles(db_manager, node_id)
                if cycles:
                    cycles_found[name] = cycles
                    print(f"Cycles for {name}: {cycles}")

        # These functions should have actual cycles due to circular imports
        # Note: The cycle detection may vary based on how the imports are resolved
        assert cycles_found != {}

        db_manager.close()

    async def test_existing_complex_cycle_detection(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ):
        """
        Test cycle detection with existing complex cycle examples.

        Uses the test_code_examples/circular_deps/complex_cycle directory
        which contains modules with more complex circular dependencies.
        """
        # Use the existing complex cycle examples
        complex_cycle_path = test_code_examples_path / "circular_deps" / "complex_cycle"

        # Build graph
        builder = GraphBuilder(
            root_path=str(complex_cycle_path), extensions_to_skip=[".pyc", ".pyo"], names_to_skip=["__pycache__"]
        )
        graph = builder.build()

        # Save to Neo4j
        db_manager = Neo4jManager(uri=neo4j_instance.uri, user="neo4j", password="test-password")

        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Check for cycles in functions
        function_props = await graph_assertions.get_node_properties("FUNCTION")

        cycles_found = {}
        for node in function_props:
            node_id = node.get("node_id")
            name = node.get("name")
            if node_id and name:
                cycles = detect_function_cycles(db_manager, node_id)
                if cycles:
                    cycles_found[name] = cycles

        # Independent functions should not have cycles
        if "independent_function" in [n.get("name") for n in function_props]:
            assert "independent_function" not in cycles_found or not cycles_found.get("independent_function"), (
                "independent_function should not have cycles"
            )

        print(f"Complex cycles found: {cycles_found}")

        db_manager.close()

    async def test_shared_dependency_not_cycle(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ):
        """
        Test that shared dependencies are NOT incorrectly flagged as cycles.

        Pattern tested:
        - Multiple functions call the same shared utilities
        - Shared utilities are NOT cycles, just common dependencies
        """
        # Use the shared dependency example from code_examples
        shared_dep_path = test_code_examples_path / "circular_deps" / "shared_dependency"

        # Build graph
        builder = GraphBuilder(
            root_path=str(shared_dep_path), extensions_to_skip=[".pyc", ".pyo"], names_to_skip=["__pycache__"]
        )
        graph = builder.build()

        # Save to Neo4j
        db_manager = Neo4jManager(uri=neo4j_instance.uri, user="neo4j", password="test-password")

        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Debug: Print graph summary
        await graph_assertions.debug_print_graph_summary()

        # Check for cycles
        function_props = await graph_assertions.get_node_properties("FUNCTION")
        
        print(f"Checking shared dependency functions: {[n.get('name') for n in function_props]}")

        cycles_found = {}
        for node in function_props:
            node_id = node.get("node_id")
            name = node.get("name")
            if node_id and name:
                cycles = detect_function_cycles(db_manager, node_id)
                if cycles:
                    cycles_found[name] = cycles
                    print(f"WARNING: Found unexpected cycle in {name}: {cycles}")
                    
        # None of the shared utility functions should have cycles
        assert len(cycles_found) == 0, f"No functions should have cycles, but found: {cycles_found}"
        
        # Specifically check that shared utilities don't have cycles
        shared_utils = ["validate_input", "log_activity", "transform_data", "format_output", "process_request"]
        for util_name in shared_utils:
            if util_name in cycles_found:
                assert False, f"Shared utility {util_name} incorrectly detected as having a cycle"
        
        print("✓ All shared dependencies correctly have no cycles")

        db_manager.close()

    async def test_real_direct_recursion(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        graph_assertions: GraphAssertions,
    ):
        """
        Test that real direct recursion IS correctly detected.

        Pattern tested:
        - factorial calls itself (direct recursion)
        - This should be detected as a cycle
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_recursion.py"
            test_file.write_text('''
def factorial(n):
    """Calculate factorial recursively."""
    if n <= 1:
        return 1
    return n * factorial(n - 1)

def main():
    """Entry point."""
    result = factorial(5)
    return result
''')

            # Build and save graph
            builder = GraphBuilder(
                root_path=str(temp_dir), extensions_to_skip=[".pyc", ".pyo"], names_to_skip=["__pycache__"]
            )
            graph = builder.build()

            db_manager = Neo4jManager(uri=neo4j_instance.uri, user="neo4j", password="test-password")

            db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

            # Check for cycles
            function_props = await graph_assertions.get_node_properties("FUNCTION")

            # Debug: Check if CALLS relationships exist
            calls_query = """
            MATCH (f:FUNCTION)-[r:CALLS]->(target)
            WHERE f.entityId = 'default_user' AND f.repoId = 'default_repo'
            RETURN f.name as caller, target.name as callee, type(r) as rel_type
            """
            calls_result = await neo4j_instance.execute_cypher(calls_query)
            print(f"CALLS relationships found: {calls_result}")

            factorial_found = False
            for node in function_props:
                if node.get("name") == "factorial":
                    factorial_found = True
                    print(f"Testing factorial node with ID: {node.get('node_id')}")
                    cycles = detect_function_cycles(db_manager, node.get("node_id"))
                    print(f"Cycles detected for factorial: {cycles}")
                    # Should detect the self-recursion
                    assert len(cycles) > 0, "factorial should have a cycle (direct recursion)"
                    # The cycle should contain factorial calling itself
                    assert any("factorial" in cycle for cycle in cycles), "Cycle should contain factorial"
                    break

            assert factorial_found, "factorial function not found in graph"

            db_manager.close()

    async def test_mutual_recursion(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ):
        """
        Test that mutual recursion IS correctly detected.

        Pattern tested:
        - is_even calls is_odd, is_odd calls is_even
        - count_down_even calls count_down_odd and vice versa
        - tree_traversal_left calls tree_traversal_right and vice versa
        """
        # Use the mutual recursion example from code_examples
        mutual_recursion_path = test_code_examples_path / "circular_deps" / "mutual_recursion"

        # Build and save graph
        builder = GraphBuilder(
            root_path=str(mutual_recursion_path), extensions_to_skip=[".pyc", ".pyo"], names_to_skip=["__pycache__"]
        )
        graph = builder.build()

        db_manager = Neo4jManager(uri=neo4j_instance.uri, user="neo4j", password="test-password")

        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Debug: Print graph summary
        await graph_assertions.debug_print_graph_summary()

        # Check for cycles in all functions
        function_props = await graph_assertions.get_node_properties("FUNCTION")
        
        print(f"Checking mutual recursion functions: {[n.get('name') for n in function_props]}")

        cycles_by_function = {}
        for node in function_props:
            name = node.get("name")
            node_id = node.get("node_id")
            if node_id and name:
                cycles = detect_function_cycles(db_manager, node_id)
                if cycles:
                    cycles_by_function[name] = cycles
                    print(f"Cycles for {name}: {cycles}")

        # Check is_even/is_odd mutual recursion
        assert len(cycles_by_function.get("is_even", [])) > 0, "is_even should be in a cycle"
        assert len(cycles_by_function.get("is_odd", [])) > 0, "is_odd should be in a cycle"
        
        # Verify the cycle contains both functions
        is_even_cycles = cycles_by_function.get("is_even", [])
        found_even_odd_cycle = any("is_even" in cycle and "is_odd" in cycle for cycle in is_even_cycles)
        assert found_even_odd_cycle, "Expected to find a cycle containing both is_even and is_odd"
        print("✓ is_even/is_odd mutual recursion correctly detected")

        # Check count_down_even/count_down_odd mutual recursion
        assert len(cycles_by_function.get("count_down_even", [])) > 0, "count_down_even should be in a cycle"
        assert len(cycles_by_function.get("count_down_odd", [])) > 0, "count_down_odd should be in a cycle"
        print("✓ count_down_even/count_down_odd mutual recursion correctly detected")

        # Check tree traversal mutual recursion
        assert len(cycles_by_function.get("tree_traversal_left", [])) > 0, "tree_traversal_left should be in a cycle"
        assert len(cycles_by_function.get("tree_traversal_right", [])) > 0, "tree_traversal_right should be in a cycle"
        print("✓ tree_traversal_left/tree_traversal_right mutual recursion correctly detected")
        
        # Helper functions should NOT have cycles
        assert "test_even_odd" not in cycles_by_function or len(cycles_by_function["test_even_odd"]) == 0, \
            "test_even_odd helper should not have cycles"
        assert "create_sample_tree" not in cycles_by_function or len(cycles_by_function["create_sample_tree"]) == 0, \
            "create_sample_tree helper should not have cycles"
        print("✓ Helper functions correctly have no cycles")

        db_manager.close()
