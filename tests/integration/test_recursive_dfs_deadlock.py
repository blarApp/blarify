"""Integration tests for RecursiveDFSProcessor deadlock prevention.

This test suite verifies that the deadlock detection and prevention mechanisms
work correctly, especially with high worker counts (75+) that previously caused hangs.
"""

import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from blarify.agents.llm_provider import LLMProvider
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.documentation.utils.recursive_dfs_processor import (
    ThreadDependencyTracker,
)
from blarify.graph.graph import Graph
from blarify.prebuilt.graph_builder import GraphBuilder
from tests.utils.circular_dependency_loader import CircularDependencyLoader


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def call_dumb_agent(
        self,
        system_prompt: str,  # noqa: ARG002
        input_dict: Dict[str, Any],
        output_schema: Optional[BaseModel] = None,  # noqa: ARG002
        ai_model: Optional[str] = None,  # noqa: ARG002
        input_prompt: Optional[str] = "Start",  # noqa: ARG002
        config: Optional[Dict[str, Any]] = None,  # noqa: ARG002
        timeout: Optional[int] = None,  # noqa: ARG002
    ) -> Any:
        """Mock implementation that returns consistent responses."""
        node_name = input_dict.get("node_name", "unknown")
        # Return object with content attribute for compatibility
        return type(
            "Response",
            (),
            {"content": f"Mock description for {node_name}. This is a test response analyzing the code structure."},
        )()

    def call_react_agent(
        self,
        system_prompt: str,  # noqa: ARG002
        tools: List[BaseTool],  # noqa: ARG002
        input_dict: Dict[str, Any],  # noqa: ARG002
        input_prompt: Optional[str],  # noqa: ARG002
        output_schema: Optional[BaseModel] = None,  # noqa: ARG002
        main_model: Optional[str] = "gpt-4.1",  # noqa: ARG002
    ) -> Any:
        """Mock React agent response."""
        return {"framework": "Test Framework", "main_folders": ["."]}


class SlowMockLLMProvider(MockLLMProvider):
    """Intentionally slow mock provider for timeout testing."""

    def call_dumb_agent(
        self,
        system_prompt: str,
        input_dict: Dict[str, Any],
        output_schema: Optional[BaseModel] = None,
        ai_model: Optional[str] = None,
        input_prompt: Optional[str] = "Start",
        config: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        """Slow mock implementation to trigger timeout scenarios."""
        time.sleep(2.0)  # Introduce delay
        return super().call_dumb_agent(
            system_prompt, input_dict, output_schema, ai_model, input_prompt, config, timeout
        )


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestRecursiveDFSDeadlockHandling:
    """Test deadlock detection and handling in RecursiveDFSProcessor."""

    async def test_high_worker_count_no_deadlock(
        self,
        docker_check: Any,
        neo4j_instance: Any,
        test_code_examples_path: Path,
    ) -> None:
        """
        CRITICAL TEST: Must pass with 75 workers (reproduces original hang issue).

        Test that documentation creation doesn't deadlock with 75 workers.
        This test reproduces the issue from test_documentation_creation.py
        where using 75 workers causes a hang.
        """
        # Use the Python examples directory
        python_examples_path = test_code_examples_path / "python"

        # Step 1: Create GraphBuilder and build the code graph
        builder = GraphBuilder(
            root_path=str(python_examples_path),
            extensions_to_skip=[".pyc", ".pyo"],
            names_to_skip=["__pycache__"],
        )

        graph = builder.build()
        assert isinstance(graph, Graph)

        # Step 2: Save graph to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
            entity_id="test-entity",
            repo_id="test-repo",
        )

        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Step 3: Create DocumentationCreator which uses RecursiveDFSProcessor internally
        from blarify.documentation.documentation_creator import DocumentationCreator

        doc_creator = DocumentationCreator(
            db_manager=db_manager,
            agent_caller=MockLLMProvider(),
            graph_environment=builder.graph_environment,
            company_id="test-entity",
            repo_id="test-repo",
            max_workers=75,  # This is the critical test - 75 workers causes hang
        )

        # Process with timeout to detect deadlock
        start_time = time.time()

        # Create documentation for all nodes (this internally uses RecursiveDFSProcessor)
        result = doc_creator.create_documentation(save_to_database=False)

        processing_time = time.time() - start_time

        # Verify no deadlock occurred (should complete within 30 seconds for test data)
        assert processing_time < 30.0, (
            f"Processing with 75 workers took {processing_time:.2f}s - likely deadlocked! "
            f"This indicates the deadlock prevention is not working."
        )

        # Verify successful processing
        assert result is not None, "Result should not be None"
        assert result.error is None, f"Processing failed with error: {result.error}"
        assert len(result.documentation_nodes) > 0, "Should have generated documentation nodes"

        print(f"Successfully processed with 75 workers in {processing_time:.2f}s")
        print(f"Generated {len(result.documentation_nodes)} documentation nodes")

        # Clean up
        db_manager.close()

    async def test_simple_circular_dependency_handling(
        self,
        docker_check: Any,
        neo4j_instance: Any,
        temp_project_dir: Path,
    ) -> None:
        """Test handling of simple A->B->C->A circular dependencies."""

        # Use pre-created circular dependency test case
        test_path = CircularDependencyLoader.get_simple_cycle_path()
        # Copy test files to temp directory for isolation
        shutil.copytree(test_path, temp_project_dir / "simple_cycle")
        test_project_path = temp_project_dir / "simple_cycle"

        # Build graph with GraphBuilder
        builder = GraphBuilder(root_path=str(test_project_path))
        graph = builder.build()

        # Save to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
            entity_id="test-entity",
            repo_id="test-repo",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Create DocumentationCreator which uses RecursiveDFSProcessor internally
        from blarify.documentation.documentation_creator import DocumentationCreator

        doc_creator = DocumentationCreator(
            db_manager=db_manager,
            agent_caller=MockLLMProvider(),  # Use mock for testing
            graph_environment=builder.graph_environment,
            company_id="test-entity",
            repo_id="test-repo",
            max_workers=75,  # High worker count to stress test
        )

        # Process the root directory - this should not deadlock
        start_time = time.time()
        result = doc_creator.create_documentation(save_to_database=False)
        processing_time = time.time() - start_time

        # Verify processing completed without deadlock
        assert processing_time < 60.0, f"Processing took too long ({processing_time}s), possible deadlock"
        assert result.error is None, f"Processing failed with error: {result.error}"
        assert len(result.documentation_nodes) > 0, "Should have generated documentation nodes"

        # The important test is that it doesn't deadlock - fallback may or may not be used
        # depending on how the threads are scheduled
        print(f"Processed {len(result.documentation_nodes)} nodes without deadlock")

        # Check if any fallback was used (optional - depends on thread scheduling)
        fallback_nodes = [
            node
            for node in result.documentation_nodes
            if hasattr(node, "metadata") and node.metadata and node.metadata.get("is_fallback", False)
        ]
        if len(fallback_nodes) > 0:
            print(f"Used fallback strategy for {len(fallback_nodes)} nodes")

        db_manager.close()

    async def test_complex_circular_dependency_with_branches(
        self,
        docker_check: Any,
        neo4j_instance: Any,
        temp_project_dir: Path,
    ) -> None:
        """Test handling of complex circular dependencies with multiple branches."""

        # Use pre-created complex circular dependency scenario
        test_path = CircularDependencyLoader.get_complex_cycle_path()
        # Copy test files to temp directory for isolation
        shutil.copytree(test_path, temp_project_dir / "complex_cycle")
        test_project_path = temp_project_dir / "complex_cycle"

        # Build graph with GraphBuilder
        builder = GraphBuilder(root_path=str(test_project_path))
        graph = builder.build()

        # Save to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
            entity_id="test-entity",
            repo_id="test-repo",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Create DocumentationCreator for high concurrency testing
        from blarify.documentation.documentation_creator import DocumentationCreator

        doc_creator = DocumentationCreator(
            db_manager=db_manager,
            agent_caller=MockLLMProvider(),
            graph_environment=builder.graph_environment,
            company_id="test-entity",
            repo_id="test-repo",
            max_workers=50,
        )

        start_time = time.time()
        result = doc_creator.create_documentation(save_to_database=False)
        processing_time = time.time() - start_time

        # Verify no deadlock and successful processing
        assert processing_time < 90.0, f"Complex processing took too long ({processing_time}s)"
        assert result.error is None, f"Processing failed: {result.error}"

        # Verify comprehensive documentation generation
        assert len(result.documentation_nodes) >= 6, "Should document all modules in complex scenario"

        db_manager.close()

    async def test_deadlock_detection_mechanism(
        self,
        docker_check: Any,
        neo4j_instance: Any,
        temp_project_dir: Path,
    ) -> None:
        """Test the deadlock detection mechanism directly."""

        tracker = ThreadDependencyTracker()

        # Simulate thread dependency scenario
        thread1 = "thread_1"
        thread2 = "thread_2"
        node_a = "node_a"
        node_b = "node_b"

        # Thread 1 processes node A
        tracker.register_processor(node_a, thread1)

        # Thread 2 processes node B
        tracker.register_processor(node_b, thread2)

        # Thread 1 wants to wait for node B (should be OK)
        can_wait = tracker.register_waiter(node_b, thread1)
        assert can_wait, "Thread 1 should be able to wait for node B"

        # Thread 2 wants to wait for node A (would create deadlock)
        can_wait = tracker.register_waiter(node_a, thread2)
        assert not can_wait, "Thread 2 waiting for node A should be detected as potential deadlock"

        # Clean up
        tracker.unregister_waiter(node_b, thread1)
        tracker.unregister_processor(node_a)
        tracker.unregister_processor(node_b)

    async def test_timeout_fallback_mechanism(
        self,
        docker_check: Any,
        neo4j_instance: Any,
        temp_project_dir: Path,
    ) -> None:
        """Test timeout-based fallback when waiting threads exceed timeout."""

        # Use pre-created simple circular dependency
        test_path = CircularDependencyLoader.get_simple_cycle_path()
        # Copy test files to temp directory for isolation
        shutil.copytree(test_path, temp_project_dir / "simple_cycle")
        test_project_path = temp_project_dir / "simple_cycle"

        # Build graph
        builder = GraphBuilder(root_path=str(test_project_path))
        graph = builder.build()

        # Save to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
            entity_id="test-entity",
            repo_id="test-repo",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Create DocumentationCreator with slow provider for timeout testing
        from blarify.documentation.documentation_creator import DocumentationCreator

        doc_creator = DocumentationCreator(
            db_manager=db_manager,
            agent_caller=SlowMockLLMProvider(),  # Intentionally slow for timeout testing
            graph_environment=builder.graph_environment,
            company_id="test-entity",
            repo_id="test-repo",
            max_workers=20,
        )

        # Access the processor to set timeout (if possible)
        if hasattr(doc_creator, "processor") and hasattr(doc_creator.processor, "fallback_timeout_seconds"):
            doc_creator.processor.fallback_timeout_seconds = 5.0  # Short timeout for testing

        start_time = time.time()
        result = doc_creator.create_documentation(save_to_database=False)
        processing_time = time.time() - start_time

        # Should complete within reasonable time due to timeout fallbacks
        assert processing_time < 30.0, f"Should complete quickly with timeouts ({processing_time}s)"
        assert result.error is None, "Should not error with timeout fallbacks"

        # The main test is that even with slow processing, it completes without hanging
        print(f"Processed {len(result.documentation_nodes) if result.documentation_nodes else 0} nodes")

        # Check if any timeout/fallback was used (optional)
        if result.documentation_nodes:
            timeout_fallbacks = [
                node
                for node in result.documentation_nodes
                if (
                    hasattr(node, "metadata")
                    and node.metadata
                    and node.metadata.get("fallback_reason") in ["circular_dependency_deadlock", "timeout"]
                )
            ]
            if len(timeout_fallbacks) > 0:
                print(f"Used timeout/fallback strategy for {len(timeout_fallbacks)} nodes")

        db_manager.close()
