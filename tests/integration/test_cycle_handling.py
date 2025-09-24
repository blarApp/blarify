"""
Tests for cycle handling in bottom-up batch processor.

This test suite verifies that the documentation creator can successfully process
codebases with cycles without getting stuck.
"""

import pytest
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.documentation.utils.bottom_up_batch_processor import BottomUpBatchProcessor
from blarify.graph.graph_environment import GraphEnvironment
from blarify.repositories.graph_db_manager.dtos.node_with_content_dto import NodeWithContentDto
from tests.utils.graph_assertions import GraphAssertions


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestCycleHandling:
    """Test suite for verifying that cycles are handled correctly."""

    async def test_simple_cycle_documentation(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ):
        """
        Test that documentation can be generated for code with simple cycles.

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

        # Save to Neo4j with isolated IDs
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Create a mock LLM provider
        mock_llm = Mock()
        mock_llm.call_dumb_agent.return_value = "Documentation for this node"

        # Create the batch processor
        graph_env = GraphEnvironment(
            environment=test_data_isolation["entity_id"],
            diff_identifier=test_data_isolation["repo_id"],
            root_path=str(simple_cycle_path),
        )

        processor = BottomUpBatchProcessor(
            db_manager=db_manager,
            agent_caller=mock_llm,
            graph_environment=graph_env,
            batch_size=5,
            max_workers=2,
        )

        # Get the root node for the simple cycle directory
        root_node_query = """
        MATCH (n:FOLDER {path: $path, entityId: $entity_id, repoId: $repo_id})
        RETURN n.node_id as id, n.name as name, labels(n) as labels,
               n.path as path, n.start_line as start_line, n.end_line as end_line
        LIMIT 1
        """
        root_result = db_manager.query(
            root_node_query,
            {
                "path": str(simple_cycle_path),
                "entity_id": test_data_isolation["entity_id"],
                "repo_id": test_data_isolation["repo_id"],
            }
        )

        if root_result:
            root_node = NodeWithContentDto(
                id=root_result[0]["id"],
                name=root_result[0]["name"],
                labels=root_result[0]["labels"],
                path=root_result[0]["path"],
                start_line=root_result[0].get("start_line"),
                end_line=root_result[0].get("end_line"),
            )

            # Process the node - should not get stuck on cycles
            total_processed = processor._process_node_query_based(root_node)

            # Verify that nodes were processed
            assert total_processed > 0, "Should have processed some nodes"

            # Check that functions in cycles were eventually processed
            cycle_function_query = """
            MATCH (n:FUNCTION {entityId: $entity_id, repoId: $repo_id})
            WHERE n.processing_status = 'completed'
            RETURN count(n) as completed_count
            """
            result = db_manager.query(
                cycle_function_query,
                {
                    "entity_id": test_data_isolation["entity_id"],
                    "repo_id": test_data_isolation["repo_id"],
                }
            )

            completed_count = result[0]["completed_count"] if result else 0
            assert completed_count > 0, "Functions in cycles should have been processed"

        db_manager.close()

    async def test_complex_cycle_documentation(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ):
        """
        Test documentation generation for complex cycle patterns.

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

        # Save to Neo4j with isolated IDs
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Create a mock LLM provider
        mock_llm = Mock()
        mock_llm.call_dumb_agent.return_value = "Documentation for complex cycle node"

        # Create the batch processor
        graph_env = GraphEnvironment(
            environment=test_data_isolation["entity_id"],
            diff_identifier=test_data_isolation["repo_id"],
            root_path=str(complex_cycle_path),
        )

        processor = BottomUpBatchProcessor(
            db_manager=db_manager,
            agent_caller=mock_llm,
            graph_environment=graph_env,
            batch_size=5,
            max_workers=2,
        )

        # Get the root node for the complex cycle directory
        root_node_query = """
        MATCH (n:FOLDER {path: $path, entityId: $entity_id, repoId: $repo_id})
        RETURN n.node_id as id, n.name as name, labels(n) as labels,
               n.path as path, n.start_line as start_line, n.end_line as end_line
        LIMIT 1
        """
        root_result = db_manager.query(
            root_node_query,
            {
                "path": str(complex_cycle_path),
                "entity_id": test_data_isolation["entity_id"],
                "repo_id": test_data_isolation["repo_id"],
            }
        )

        if root_result:
            root_node = NodeWithContentDto(
                id=root_result[0]["id"],
                name=root_result[0]["name"],
                labels=root_result[0]["labels"],
                path=root_result[0]["path"],
                start_line=root_result[0].get("start_line"),
                end_line=root_result[0].get("end_line"),
            )

            # Process the node - should complete even with complex cycles
            total_processed = processor._process_node_query_based(root_node)

            # Verify that processing completed
            assert total_processed > 0, "Should have processed nodes despite complex cycles"

            # Check that all nodes were eventually processed
            pending_query = """
            MATCH (n:NODE {entityId: $entity_id, repoId: $repo_id})
            WHERE n.processing_status IS NULL OR n.processing_status <> 'completed'
            RETURN count(n) as pending_count
            """
            result = db_manager.query(
                pending_query,
                {
                    "entity_id": test_data_isolation["entity_id"],
                    "repo_id": test_data_isolation["repo_id"],
                }
            )

            pending_count = result[0]["pending_count"] if result else 0
            # Allow for root node to remain unprocessed if it has no content
            assert pending_count <= 1, f"All nodes should be processed, but {pending_count} are still pending"

        db_manager.close()

    async def test_mutual_recursion_documentation(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ):
        """
        Test documentation generation for mutual recursion patterns.

        Pattern tested:
        - is_even calls is_odd, is_odd calls is_even
        - Documentation should be generated for both without getting stuck
        """
        # Use the mutual recursion example from code_examples
        mutual_recursion_path = test_code_examples_path / "circular_deps" / "mutual_recursion"

        # Build and save graph
        builder = GraphBuilder(
            root_path=str(mutual_recursion_path), extensions_to_skip=[".pyc", ".pyo"], names_to_skip=["__pycache__"]
        )
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

        # Create a mock LLM provider
        mock_llm = Mock()
        mock_llm.call_dumb_agent.return_value = "Documentation for mutually recursive function"

        # Create the batch processor
        graph_env = GraphEnvironment(
            environment=test_data_isolation["entity_id"],
            diff_identifier=test_data_isolation["repo_id"],
            root_path=str(mutual_recursion_path),
        )

        processor = BottomUpBatchProcessor(
            db_manager=db_manager,
            agent_caller=mock_llm,
            graph_environment=graph_env,
            batch_size=10,
            max_workers=2,
        )

        # Get the root node for the mutual recursion directory
        root_node_query = """
        MATCH (n:FOLDER {path: $path, entityId: $entity_id, repoId: $repo_id})
        RETURN n.node_id as id, n.name as name, labels(n) as labels,
               n.path as path, n.start_line as start_line, n.end_line as end_line
        LIMIT 1
        """
        root_result = db_manager.query(
            root_node_query,
            {
                "path": str(mutual_recursion_path),
                "entity_id": test_data_isolation["entity_id"],
                "repo_id": test_data_isolation["repo_id"],
            }
        )

        if root_result:
            root_node = NodeWithContentDto(
                id=root_result[0]["id"],
                name=root_result[0]["name"],
                labels=root_result[0]["labels"],
                path=root_result[0]["path"],
                start_line=root_result[0].get("start_line"),
                end_line=root_result[0].get("end_line"),
            )

            # Process the node - should handle mutual recursion correctly
            total_processed = processor._process_node_query_based(root_node)

            # Verify that processing completed successfully
            assert total_processed > 0, "Should have processed nodes with mutual recursion"

            # Check that mutually recursive functions were processed
            recursive_functions = ["is_even", "is_odd", "count_down_even", "count_down_odd",
                                  "tree_traversal_left", "tree_traversal_right"]

            for func_name in recursive_functions:
                func_query = """
                MATCH (n:FUNCTION {name: $name, entityId: $entity_id, repoId: $repo_id})
                RETURN n.processing_status as status
                """
                result = db_manager.query(
                    func_query,
                    {
                        "name": func_name,
                        "entity_id": test_data_isolation["entity_id"],
                        "repo_id": test_data_isolation["repo_id"],
                    }
                )

                if result:
                    status = result[0]["status"]
                    assert status == "completed", f"Function {func_name} should have been processed"

        db_manager.close()