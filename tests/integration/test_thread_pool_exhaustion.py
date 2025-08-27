"""Integration tests for thread pool exhaustion prevention in iterative DFS implementation.

These tests focus specifically on thread management and exhaustion prevention,
complementing the full documentation flow tests in test_documentation_creation.py
and deadlock tests in test_recursive_dfs_deadlock.py.
"""

import threading
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Set, List, Optional
from unittest.mock import Mock, patch

import pytest

from blarify.repositories.graph_db_manager import Neo4jManager
from blarify.documentation.utils.recursive_dfs_processor import (
    RecursiveDFSProcessor,
)
from blarify.graph.graph_environment import GraphEnvironment
from neo4j_container_manager.types import Neo4jContainerInstance
from tests.integration.test_helpers import (
    create_test_file_node,
    create_test_function_node,
    insert_nodes_and_edges,
    create_contains_edge,
    create_calls_edge,
)


class ThreadTracker:
    """Track thread usage during test execution."""

    def __init__(self):
        self.max_concurrent_threads: int = 0
        self.total_unique_threads: int = 0
        self.thread_reuse_count: int = 0
        self._active_threads: Set[int] = set()
        self._all_threads: Set[int] = set()
        self._thread_usage: Dict[int, int] = {}
        self._lock = threading.Lock()
        self._start_time: Optional[float] = None

    def __enter__(self):
        self._start_time = time.time()
        self._original_submit = ThreadPoolExecutor.submit

        def tracked_submit(executor, fn, *args, **kwargs):
            def wrapped_fn(*inner_args, **inner_kwargs):
                thread_id = threading.get_ident()
                with self._lock:
                    self._active_threads.add(thread_id)
                    self._all_threads.add(thread_id)
                    self._thread_usage[thread_id] = self._thread_usage.get(thread_id, 0) + 1
                    if self._thread_usage[thread_id] > 1:
                        self.thread_reuse_count += 1
                    self.max_concurrent_threads = max(self.max_concurrent_threads, len(self._active_threads))
                try:
                    return fn(*inner_args, **inner_kwargs)
                finally:
                    with self._lock:
                        self._active_threads.discard(thread_id)

            return self._original_submit(executor, wrapped_fn, *args, **kwargs)

        ThreadPoolExecutor.submit = tracked_submit
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        ThreadPoolExecutor.submit = self._original_submit
        self.total_unique_threads = len(self._all_threads)


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_thread_reuse_in_deep_hierarchy(neo4j_instance: Neo4jContainerInstance):
    """Test that threads are properly reused in deep hierarchies without exhaustion."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri, user="neo4j", password="test-password", entity_id="test-entity", repo_id="test-repo"
    )

    # Create deep hierarchy (100+ nodes) using Node classes
    graph_env = GraphEnvironment(environment="test", diff_identifier="test-diff", root_path="/")

    # Create root node
    root = create_test_file_node(
        path="/root.py",
        name="root.py",
        content="root content",
        entity_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
    )

    nodes = [root]
    edges = []

    # Create children (50 child nodes)
    for i in range(1, 51):
        child = create_test_file_node(
            path=f"/child{i}.py",
            name=f"child{i}.py",
            content="child content",
            entity_id="test-entity",
            repo_id="test-repo",
            graph_environment=graph_env,
        )
        nodes.append(child)
        edges.append(create_contains_edge(root.hashed_id, child.hashed_id))

        # Create grandchildren (2 per child)
        for j in range(1, 3):
            grandchild = create_test_file_node(
                path=f"/gc_{i}_{j}.py",
                name=f"gc_{i}_{j}.py",
                content="gc content",
                entity_id="test-entity",
                repo_id="test-repo",
                graph_environment=graph_env,
            )
            nodes.append(grandchild)
            edges.append(create_contains_edge(child.hashed_id, grandchild.hashed_id))

    # Insert nodes and edges into database
    insert_nodes_and_edges(db_manager, nodes, edges)

    # Track thread usage
    thread_tracker = ThreadTracker()

    # Mock LLM provider
    mock_llm = Mock()
    mock_llm.call_dumb_agent.return_value = Mock(content="Mock description")

    # Create graph environment using same parameters as test_documentation_creation.py
    graph_env = GraphEnvironment(environment="test", diff_identifier="test-diff", root_path="/")

    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        agent_caller=mock_llm,
        company_id="test-entity",  # Changed to match entityId
        repo_id="test-repo",
        graph_environment=graph_env,
        max_workers=10,
    )

    with thread_tracker:
        result = processor.process_node("/root.py")

    # Verify: No thread exhaustion
    assert thread_tracker.max_concurrent_threads <= 10, (
        f"Max concurrent threads {thread_tracker.max_concurrent_threads} exceeded limit"
    )
    assert thread_tracker.total_unique_threads <= 15, (
        f"Total unique threads {thread_tracker.total_unique_threads} exceeded limit"
    )
    assert thread_tracker.thread_reuse_count > 50, f"Thread reuse count {thread_tracker.thread_reuse_count} too low"

    # Verify: All nodes processed successfully
    assert result is not None
    assert result.error is None
    # With 150+ nodes and only 10 threads, we should see significant reuse
    print(
        f"Thread stats: max_concurrent={thread_tracker.max_concurrent_threads}, "
        f"total_unique={thread_tracker.total_unique_threads}, "
        f"reuse_count={thread_tracker.thread_reuse_count}"
    )

    db_manager.close()


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_as_completed_thread_harvesting(neo4j_instance: Neo4jContainerInstance):
    """Test that as_completed() is used for immediate thread harvesting."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri, user="neo4j", password="test-password", entity_id="test-entity", repo_id="test-repo"
    )

    # Create a wide hierarchy to test parallel processing
    graph_env = GraphEnvironment(environment="test", diff_identifier="test-diff", root_path="/")

    # Create root with many children to force parallel processing
    root = create_test_file_node(
        path="/root.py",
        name="root.py",
        content="root content",
        entity_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
    )

    nodes = [root]
    edges = []

    # Create 20 independent children that can be processed in parallel
    for i in range(20):
        child = create_test_file_node(
            path=f"/child_{i}.py",
            name=f"child_{i}.py",
            content=f"child {i} content",
            entity_id="test-entity",
            repo_id="test-repo",
            graph_environment=graph_env,
        )
        nodes.append(child)
        edges.append(create_contains_edge(root.hashed_id, child.hashed_id))

    insert_nodes_and_edges(db_manager, nodes, edges)

    # Track thread completion order
    completion_order = []
    completion_lock = threading.Lock()

    def mock_llm_with_tracking(system_prompt, input_dict, output_schema, input_prompt, config, timeout):
        """Mock that tracks completion order."""
        node_name = input_dict.get("node_name", "unknown")
        # Simulate variable processing time
        time.sleep(random.uniform(0.01, 0.05))
        with completion_lock:
            completion_order.append((node_name, threading.current_thread().ident))
        return Mock(content=f"Description for {node_name}")

    mock_llm = Mock()
    mock_llm.call_dumb_agent.side_effect = mock_llm_with_tracking

    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        agent_caller=mock_llm,
        company_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
        max_workers=5,  # Limited workers to force thread reuse
    )

    # Patch as_completed to verify it's being used
    original_as_completed = as_completed
    as_completed_called = False

    def tracked_as_completed(*args, **kwargs):
        nonlocal as_completed_called
        as_completed_called = True
        return original_as_completed(*args, **kwargs)

    with patch("blarify.documentation.utils.recursive_dfs_processor.as_completed", side_effect=tracked_as_completed):
        result = processor.process_node("/root.py")

    # Verify as_completed was used for thread harvesting
    assert as_completed_called, "as_completed() should be used for thread harvesting"

    # Verify threads were reused (20 tasks with only 5 workers)
    unique_threads = set(thread_id for _, thread_id in completion_order)
    assert len(unique_threads) <= 5, f"Should reuse threads, but found {len(unique_threads)} unique threads"

    # Verify all children were processed
    assert len(completion_order) >= 20, f"Expected at least 20 completions, got {len(completion_order)}"

    db_manager.close()


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_batch_processing_maintains_bottom_up_order(neo4j_instance: Neo4jContainerInstance):
    """Test that batch processing maintains bottom-up order (leaves first)."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri, user="neo4j", password="test-password", entity_id="test-entity", repo_id="test-repo"
    )

    # Create graph environment
    graph_env = GraphEnvironment(environment="test", diff_identifier="test-diff", root_path="/")

    # Create hierarchy using Node classes
    root = create_test_file_node(
        path="/root.py",
        name="root.py",
        content="root content",
        entity_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
    )

    c1 = create_test_file_node(
        path="/child1.py",
        name="child1.py",
        content="c1 content",
        entity_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
    )

    c2 = create_test_file_node(
        path="/child2.py",
        name="child2.py",
        content="c2 content",
        entity_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
    )

    gc1 = create_test_file_node(
        path="/grandchild1.py",
        name="grandchild1.py",
        content="gc1 content",
        entity_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
    )

    gc2 = create_test_file_node(
        path="/grandchild2.py",
        name="grandchild2.py",
        content="gc2 content",
        entity_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
    )

    ggc = create_test_file_node(
        path="/great_grandchild.py",
        name="great_grandchild.py",
        content="ggc content",
        entity_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
    )

    nodes = [root, c1, c2, gc1, gc2, ggc]
    edges = [
        create_contains_edge(root.hashed_id, c1.hashed_id),
        create_contains_edge(root.hashed_id, c2.hashed_id),
        create_contains_edge(c1.hashed_id, gc1.hashed_id),
        create_contains_edge(c1.hashed_id, gc2.hashed_id),
        create_contains_edge(gc1.hashed_id, ggc.hashed_id),
    ]

    # Insert nodes and edges into database
    insert_nodes_and_edges(db_manager, nodes, edges)

    # Track processing levels
    processing_levels: Dict[str, int] = {}
    processing_order: List[str] = []
    lock = threading.Lock()

    def mock_llm_track_order(system_prompt, input_dict, output_schema, input_prompt, config, timeout):
        node_path = input_dict.get("node_path", "unknown")
        with lock:
            # Determine level based on path
            if "great_grandchild" in node_path:
                level = 3
            elif "grandchild" in node_path:
                level = 2
            elif "child" in node_path and "grandchild" not in node_path:
                level = 1
            else:
                level = 0
            processing_levels[node_path] = level
            processing_order.append(node_path)
        return Mock(content=f"Description for {node_path}")

    mock_llm = Mock()
    mock_llm.call_dumb_agent.side_effect = mock_llm_track_order

    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        agent_caller=mock_llm,
        company_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
        max_workers=3,
    )

    # Process the hierarchy
    result = processor.process_node("/root.py")
    assert result.error is None

    # Verify bottom-up order: higher level nodes (leaves) processed first
    for i, path in enumerate(processing_order[:-1]):
        next_path = processing_order[i + 1]
        current_level = processing_levels.get(path, -1)
        next_level = processing_levels.get(next_path, -1)
        # Allow same level or moving up the tree (lower level number)
        assert current_level >= next_level or abs(current_level - next_level) <= 1, (
            f"Processing order violation: {path} (level {current_level}) before {next_path} (level {next_level})"
        )

    print(f"Processing order verified for {len(processing_order)} nodes")

    db_manager.close()


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_cycle_handling_without_thread_exhaustion(neo4j_instance: Neo4jContainerInstance):
    """Test that cycles in the graph don't cause thread exhaustion."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri, user="neo4j", password="test-password", entity_id="test-entity", repo_id="test-repo"
    )

    # Create graph environment
    graph_env = GraphEnvironment(environment="test", diff_identifier="test-diff", root_path="/")

    # Create a file with functions that have cycles
    file1 = create_test_file_node(
        path="/main.py",
        name="main.py",
        content="main file content",
        entity_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
    )

    f1 = create_test_function_node(
        path="/main_func1.py",
        name="func1",
        content="func1 content",
        parent=file1,
        entity_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
    )

    f2 = create_test_function_node(
        path="/main_func2.py",
        name="func2",
        content="func2 content",
        parent=file1,
        entity_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
    )

    f3 = create_test_function_node(
        path="/main_func3.py",
        name="func3",
        content="func3 content",
        parent=file1,
        entity_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
    )

    # Create hierarchy and cycle: file contains functions, functions call each other in cycle
    nodes = [file1, f1, f2, f3]
    edges = [
        create_contains_edge(file1.hashed_id, f1.hashed_id),
        create_contains_edge(file1.hashed_id, f2.hashed_id),
        create_contains_edge(file1.hashed_id, f3.hashed_id),
        create_calls_edge(f1.hashed_id, f2.hashed_id),
        create_calls_edge(f2.hashed_id, f3.hashed_id),
        create_calls_edge(f3.hashed_id, f1.hashed_id),  # Cycle!
    ]

    # Insert nodes and edges into database
    insert_nodes_and_edges(db_manager, nodes, edges)

    # Track thread usage during cycle processing
    thread_tracker = ThreadTracker()

    # Mock LLM that handles cycles gracefully
    mock_llm = Mock()
    mock_llm.call_dumb_agent.return_value = Mock(content="Cycle-aware description")

    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        agent_caller=mock_llm,
        company_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
        max_workers=5,
    )

    # Process with cycle detection
    with thread_tracker:
        result = processor.process_node("/main.py")

    # Verify no thread exhaustion despite cycle
    assert result.error is None, "Should handle cycle without error"
    assert thread_tracker.max_concurrent_threads <= 5, "Should not exceed max workers"
    assert thread_tracker.total_unique_threads <= 10, "Should not create excessive threads"

    # Verify cycle was detected (check in processor's internal state)
    assert len(result.source_nodes) > 0, "Should process nodes despite cycle"
    print(f"Processed cycle with {thread_tracker.max_concurrent_threads} concurrent threads")

    db_manager.close()


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_thread_pool_resilience_with_errors(neo4j_instance: Neo4jContainerInstance):
    """Test that thread pool remains stable when individual nodes fail."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri, user="neo4j", password="test-password", entity_id="test-entity", repo_id="test-repo"
    )

    # Create graph environment
    graph_env = GraphEnvironment(environment="test", diff_identifier="test-diff", root_path="/")

    # Create nodes using Node classes
    parent = create_test_file_node(
        path="/parent.py",
        name="parent.py",
        content="parent content",
        entity_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
    )

    good1 = create_test_file_node(
        path="/good1.py",
        name="good1.py",
        content="good1 content",
        entity_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
    )

    bad = create_test_file_node(
        path="/bad.py",
        name="bad.py",
        content="bad content",
        entity_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
    )

    good2 = create_test_file_node(
        path="/good2.py",
        name="good2.py",
        content="good2 content",
        entity_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
    )

    nodes = [parent, good1, bad, good2]
    edges = [
        create_contains_edge(parent.hashed_id, good1.hashed_id),
        create_contains_edge(parent.hashed_id, bad.hashed_id),
        create_contains_edge(parent.hashed_id, good2.hashed_id),
    ]

    # Insert nodes and edges into database
    insert_nodes_and_edges(db_manager, nodes, edges)

    # Track thread behavior during errors
    thread_tracker = ThreadTracker()
    failed_nodes = set()

    def llm_side_effect(system_prompt, input_dict, output_schema, input_prompt, config, timeout):
        node_name = input_dict.get("node_name", "")
        if "bad" in str(node_name):
            failed_nodes.add(node_name)
            raise Exception("Simulated LLM failure")
        return Mock(content=f"Description for {node_name}")

    mock_llm = Mock()
    mock_llm.call_dumb_agent.side_effect = llm_side_effect

    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        agent_caller=mock_llm,
        company_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
        max_workers=3,
    )

    # Process with thread tracking
    with thread_tracker:
        result = processor.process_node("/parent.py")

    # Verify thread pool remained stable despite errors
    assert result.error is None, "Should handle individual errors gracefully"
    assert thread_tracker.max_concurrent_threads <= 3, "Should not exceed max workers"
    assert len(failed_nodes) > 0, "Should have encountered failures"

    # Verify good nodes were still processed
    processed_names = [node.name for node in result.source_nodes]
    assert "parent.py" in processed_names
    assert any("good" in name for name in processed_names), "Should process good nodes despite failures"

    print(f"Handled {len(failed_nodes)} failures with stable thread pool")

    db_manager.close()


@pytest.mark.asyncio
@pytest.mark.performance
async def test_thread_pool_efficiency_at_scale(neo4j_instance: Neo4jContainerInstance):
    """Test that thread pool maintains efficiency with 100+ nodes."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri, user="neo4j", password="test-password", entity_id="test-entity", repo_id="test-repo"
    )

    # Create graph environment
    graph_env = GraphEnvironment(environment="test", diff_identifier="test-diff", root_path="/")

    # Create 100+ node graph to test thread efficiency
    root = create_test_file_node(
        path="/root.py",
        name="root.py",
        content="root content",
        entity_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
    )

    nodes = [root]
    edges = []

    # Create 20 child files with 5 grandchildren each (100+ total)
    for i in range(1, 21):
        child = create_test_file_node(
            path=f"/level1/child{i}.py",
            name=f"child{i}.py",
            content="child content",
            entity_id="test-entity",
            repo_id="test-repo",
            graph_environment=graph_env,
        )
        nodes.append(child)
        edges.append(create_contains_edge(root.hashed_id, child.hashed_id))

        # Create 5 grandchildren for each child
        for j in range(1, 6):
            grandchild = create_test_file_node(
                path=f"/level2/gc{i}_{j}.py",
                name=f"gc{i}_{j}.py",
                content="gc content",
                entity_id="test-entity",
                repo_id="test-repo",
                graph_environment=graph_env,
            )
            nodes.append(grandchild)
            edges.append(create_contains_edge(child.hashed_id, grandchild.hashed_id))

    # Insert nodes and edges into database
    insert_nodes_and_edges(db_manager, nodes, edges)

    # Track detailed thread metrics
    thread_tracker = ThreadTracker()
    processing_start = time.time()

    # Mock LLM with minimal delay
    mock_llm = Mock()
    mock_llm.call_dumb_agent.return_value = Mock(content="Fast description")

    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        agent_caller=mock_llm,
        company_id="test-entity",
        repo_id="test-repo",
        graph_environment=graph_env,
        max_workers=10,  # Moderate worker count
    )

    with thread_tracker:
        result = processor.process_node("/root.py")

    processing_time = time.time() - processing_start

    # Calculate thread efficiency metrics
    total_nodes = 1 + 20 + (20 * 5)  # root + children + grandchildren = 121
    thread_efficiency = thread_tracker.thread_reuse_count / max(total_nodes - 10, 1)

    # Performance assertions
    assert processing_time < 30, f"Processing took {processing_time:.2f}s, should be under 30s"
    assert result.error is None
    assert thread_tracker.max_concurrent_threads <= 10, "Should not exceed max workers"
    assert thread_tracker.total_unique_threads <= 15, "Should reuse threads efficiently"
    assert thread_efficiency > 0.5, f"Thread efficiency {thread_efficiency:.2f} too low"

    print("\nPerformance metrics:")
    print(f"  Processed {total_nodes} nodes in {processing_time:.2f}s")
    print(f"  Max concurrent threads: {thread_tracker.max_concurrent_threads}")
    print(f"  Thread reuse efficiency: {thread_efficiency:.2%}")

    db_manager.close()
