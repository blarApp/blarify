"""Integration tests for thread pool exhaustion fix - iterative DFS implementation."""

import threading
import time
import random
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Set, List, Optional, Any
from unittest.mock import Mock, patch

import pytest

from blarify.db_managers.neo4j_manager import Neo4jManager
from blarify.documentation.utils.recursive_dfs_processor import RecursiveDFSProcessor
from blarify.graph.graph_environment import GraphEnvironment


# Neo4jContainerInstance type for testing
class Neo4jContainerInstance:
    def __init__(self) -> None:
        self.uri: str = "bolt://localhost:7687"
        self.user: str = "neo4j"
        self.password: str = "test-password"


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


class PerformanceMonitor:
    """Monitor performance metrics during test execution."""

    def __init__(self):
        self.total_time: float = 0
        self.avg_thread_utilization: float = 0
        self.max_memory_mb: float = 0
        self._start_time: Optional[float] = None
        self._thread_samples: List[int] = []

    def __enter__(self):
        self._start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.total_time = time.time() - self._start_time
        if self._thread_samples:
            self.avg_thread_utilization = sum(self._thread_samples) / len(self._thread_samples)


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_iterative_processing_handles_deep_hierarchy(
    neo4j_instance: Neo4jContainerInstance
):
    """Test that new iterative implementation handles deep hierarchies efficiently."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create deep hierarchy (100+ nodes)
    setup_query = """
    CREATE (root:FILE {path: '/root.py', id: 'root', name: 'root.py', content: 'root content'})
    WITH root
    UNWIND range(1, 50) as i
    CREATE (child:FILE {path: '/child' + i + '.py', id: 'child' + i, name: 'child' + i + '.py', content: 'child content'})
    CREATE (root)-[:CONTAINS]->(child)
    WITH child
    UNWIND range(1, 2) as j  
    CREATE (grandchild:FILE {path: '/gc' + id(child) + '_' + j + '.py', id: 'gc' + id(child) + '_' + j, name: 'gc' + id(child) + '_' + j + '.py', content: 'gc content'})
    CREATE (child)-[:CONTAINS]->(grandchild)
    """
    db_manager.run_query(setup_query, {})
    
    # Track thread usage
    thread_tracker = ThreadTracker()
    
    # Mock LLM provider
    mock_llm = Mock()
    mock_llm.call_dumb_agent.return_value = Mock(content="Mock description")
    
    # Create graph environment
    graph_env = GraphEnvironment("test-company", "test-repo")
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        agent_caller=mock_llm,
        company_id="test-company",
        repo_id="test-repo",
        graph_environment=graph_env,
        max_workers=10
    )
    
    with thread_tracker:
        result = processor.process_node("/root.py")
    
    # Verify: No thread exhaustion
    assert thread_tracker.max_concurrent_threads <= 10
    assert thread_tracker.total_unique_threads <= 15  # Some overhead OK
    assert thread_tracker.thread_reuse_count > 100  # Significant reuse
    
    # Verify: All nodes processed
    assert "root.py" in str(result.hierarchical_analysis)
    assert result.error is None
    
    db_manager.close()


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_hierarchy_vs_call_stack_processing(
    neo4j_instance: Neo4jContainerInstance
):
    """Test that hierarchy (CONTAINS) and call stack (CALL) are processed correctly."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Setup: Create nodes with both CONTAINS and CALL relationships
    setup_query = """
    // Hierarchy structure (CONTAINS)
    CREATE (file1:FILE {path: '/file1.py', id: 'file1', name: 'file1.py', content: 'file content'})
    CREATE (class1:CLASS {path: '/file1.py:ClassA', id: 'class1', name: 'ClassA', content: 'class content'})
    CREATE (method1:FUNCTION {path: '/file1.py:ClassA:method1', id: 'method1', name: 'method1', content: 'method content'})
    CREATE (file1)-[:CONTAINS]->(class1)
    CREATE (class1)-[:CONTAINS]->(method1)
    
    // Call stack structure (CALL only)
    CREATE (func1:FUNCTION {path: '/utils.py:helper', id: 'func1', name: 'helper', content: 'helper content'})
    CREATE (func2:FUNCTION {path: '/utils.py:process', id: 'func2', name: 'process', content: 'process content'})
    CREATE (func3:FUNCTION {path: '/utils.py:validate', id: 'func3', name: 'validate', content: 'validate content'})
    CREATE (method1)-[:CALLS]->(func1)
    CREATE (func1)-[:CALLS]->(func2)
    CREATE (func2)-[:CALLS]->(func3)
    """
    db_manager.run_query(setup_query, {})
    
    # Mock LLM provider
    mock_llm = Mock()
    mock_llm.call_dumb_agent.return_value = Mock(content="Mock description")
    
    # Create graph environment
    graph_env = GraphEnvironment("test-company", "test-repo")
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        agent_caller=mock_llm,
        company_id="test-company",
        repo_id="test-repo",
        graph_environment=graph_env,
        max_workers=5
    )
    
    # Test hierarchy processing
    hierarchy_result = processor.process_node("/file1.py")
    
    # Verify: Hierarchy uses CONTAINS relationships
    assert "ClassA" in str(hierarchy_result.hierarchical_analysis)
    assert "method1" in str(hierarchy_result.hierarchical_analysis)
    
    # Test call stack processing  
    call_stack_result = processor.process_node("/file1.py:ClassA:method1")
    
    # Verify: Call stack uses CALL relationships only
    assert "helper" in str(call_stack_result.hierarchical_analysis)
    assert "process" in str(call_stack_result.hierarchical_analysis)
    assert "validate" in str(call_stack_result.hierarchical_analysis)
    
    db_manager.close()


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_batch_processing_maintains_bottom_up_order(
    neo4j_instance: Neo4jContainerInstance
):
    """Test that batch processing maintains bottom-up order (leaves first)."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create hierarchy
    setup_query = """
    CREATE (root:FILE {path: '/root.py', id: 'root', name: 'root.py', content: 'root content'})
    CREATE (c1:FILE {path: '/child1.py', id: 'c1', name: 'child1.py', content: 'c1 content'})
    CREATE (c2:FILE {path: '/child2.py', id: 'c2', name: 'child2.py', content: 'c2 content'})
    CREATE (gc1:FILE {path: '/grandchild1.py', id: 'gc1', name: 'grandchild1.py', content: 'gc1 content'})
    CREATE (gc2:FILE {path: '/grandchild2.py', id: 'gc2', name: 'grandchild2.py', content: 'gc2 content'})
    CREATE (ggc:FILE {path: '/great_grandchild.py', id: 'ggc', name: 'great_grandchild.py', content: 'ggc content'})
    CREATE (root)-[:CONTAINS]->(c1)
    CREATE (root)-[:CONTAINS]->(c2)
    CREATE (c1)-[:CONTAINS]->(gc1)
    CREATE (c1)-[:CONTAINS]->(gc2)
    CREATE (gc1)-[:CONTAINS]->(ggc)
    """
    db_manager.run_query(setup_query, {})
    
    processing_order: List[str] = []
    
    def mock_process(node) -> str:
        processing_order.append(node.path)
        return f"Processed {node.path}"
    
    # Mock LLM provider
    mock_llm = Mock()
    
    # Create graph environment
    graph_env = GraphEnvironment("test-company", "test-repo")
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        agent_caller=mock_llm,
        company_id="test-company",
        repo_id="test-repo",
        graph_environment=graph_env,
        max_workers=3
    )
    
    # Mock the leaf processing to track order
    original_process_leaf = processor._process_leaf_node
    
    def track_process_leaf(node):
        processing_order.append(node.path)
        return original_process_leaf(node)
    
    with patch.object(processor, '_process_leaf_node', side_effect=track_process_leaf):
        with patch.object(mock_llm, 'call_dumb_agent', return_value=Mock(content="Mock description")):
            processor.process_node("/root.py")
    
    # Verify: Bottom-up order
    # Leaves should be processed first
    assert processing_order.index("/great_grandchild.py") < processing_order.index("/grandchild1.py")
    assert processing_order.index("/grandchild1.py") < processing_order.index("/child1.py")
    assert processing_order.index("/grandchild2.py") < processing_order.index("/child1.py")
    assert processing_order.index("/child2.py") < processing_order.index("/root.py")
    assert processing_order.index("/child1.py") < processing_order.index("/root.py")
    # Root might not be in processing_order if it's processed as parent
    
    db_manager.close()


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_thread_harvesting_with_as_completed(
    neo4j_instance: Neo4jContainerInstance
):
    """Test that threads are harvested immediately using as_completed()."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create many independent nodes
    setup_query = """
    CREATE (root:FILE {path: '/root.py', id: 'root', name: 'root.py', content: 'root content'})
    WITH root
    UNWIND range(1, 30) as i
    CREATE (n:FILE {path: '/file' + i + '.py', id: 'file' + i, name: 'file' + i + '.py', content: 'file content'})
    CREATE (root)-[:CONTAINS]->(n)
    """
    db_manager.run_query(setup_query, {})
    
    # Track when threads are released
    thread_release_times: Dict[str, float] = {}
    active_threads: Set[int] = set()
    lock = threading.Lock()
    
    def mock_process_with_timing(system_prompt, input_dict, output_schema, input_prompt, config, timeout):
        thread_id = threading.current_thread().ident
        with lock:
            active_threads.add(thread_id)
        
        # Variable processing time to test harvesting
        process_time = random.uniform(0.01, 0.05)
        time.sleep(process_time)
        
        with lock:
            active_threads.discard(thread_id)
            thread_release_times[input_dict.get('node_name', 'unknown')] = time.time()
        return Mock(content=f"Processed {input_dict.get('node_name', 'unknown')}")
    
    # Mock LLM provider
    mock_llm = Mock()
    mock_llm.call_dumb_agent.side_effect = mock_process_with_timing
    
    # Create graph environment
    graph_env = GraphEnvironment("test-company", "test-repo")
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        agent_caller=mock_llm,
        company_id="test-company",
        repo_id="test-repo",
        graph_environment=graph_env,
        max_workers=5  # Limited pool to force reuse
    )
    
    start_time = time.time()
    processor.process_node("/root.py")  # Trigger batch processing
    
    # Verify: Threads were harvested and reused
    unique_nodes = len(thread_release_times)
    assert unique_nodes >= 30  # All nodes processed
    
    # Check that threads were released at different times (not all at once)
    release_times = sorted(thread_release_times.values())
    if len(release_times) > 1:
        time_spread = release_times[-1] - release_times[0]
        assert time_spread > 0.1  # Processing was spread out
    
    # Verify all threads released
    assert len(active_threads) == 0  # All threads released
    
    db_manager.close()


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_cycle_detection_in_iterative_processing(
    neo4j_instance: Neo4jContainerInstance
):
    """Test that cycle detection works with new iterative approach."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create cycle in call graph
    setup_query = """
    CREATE (f1:FUNCTION {path: '/file.py:func1', id: 'f1', name: 'func1', content: 'func1 content'})
    CREATE (f2:FUNCTION {path: '/file.py:func2', id: 'f2', name: 'func2', content: 'func2 content'})
    CREATE (f3:FUNCTION {path: '/file.py:func3', id: 'f3', name: 'func3', content: 'func3 content'})
    CREATE (f1)-[:CALLS]->(f2)
    CREATE (f2)-[:CALLS]->(f3)
    CREATE (f3)-[:CALLS]->(f1)  // Cycle!
    """
    db_manager.run_query(setup_query, {})
    
    # Mock LLM provider
    mock_llm = Mock()
    mock_llm.call_dumb_agent.return_value = Mock(content="Mock description with cycle handling")
    
    # Create graph environment
    graph_env = GraphEnvironment("test-company", "test-repo")
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        agent_caller=mock_llm,
        company_id="test-company",
        repo_id="test-repo",
        graph_environment=graph_env,
        max_workers=3
    )
    
    # Should handle cycle gracefully
    result = processor.process_node("/file.py:func1")
    
    # Verify: Cycle detected and handled
    assert result.error is None
    assert "func1" in str(result.hierarchical_analysis)
    # The cycle should be detected by the existing cycle detection logic
    
    db_manager.close()


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_error_recovery_in_batch_processing(
    neo4j_instance: Neo4jContainerInstance
):
    """Test that errors in individual nodes are handled gracefully."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create nodes
    setup_query = """
    CREATE (parent:FILE {path: '/parent.py', id: 'parent', name: 'parent.py', content: 'parent content'})
    CREATE (good1:FILE {path: '/good1.py', id: 'good1', name: 'good1.py', content: 'good1 content'})
    CREATE (bad:FILE {path: '/bad.py', id: 'bad', name: 'bad.py', content: 'bad content'})
    CREATE (good2:FILE {path: '/good2.py', id: 'good2', name: 'good2.py', content: 'good2 content'})
    CREATE (parent)-[:CONTAINS]->(good1)
    CREATE (parent)-[:CONTAINS]->(bad)
    CREATE (parent)-[:CONTAINS]->(good2)
    """
    db_manager.run_query(setup_query, {})
    
    # Mock LLM that fails for specific node
    mock_llm = Mock()
    def llm_side_effect(system_prompt, input_dict, output_schema, input_prompt, config, timeout):
        if "bad.py" in str(input_dict.get("node_name", "")):
            raise Exception("LLM API error")
        return Mock(content="Description")
    mock_llm.call_dumb_agent.side_effect = llm_side_effect
    
    # Create graph environment
    graph_env = GraphEnvironment("test-company", "test-repo")
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        agent_caller=mock_llm,
        company_id="test-company",
        repo_id="test-repo",
        graph_environment=graph_env,
        max_workers=3
    )
    
    # Should complete despite error
    result = processor.process_node("/parent.py")
    
    # Verify: Parent and good children processed
    assert result.error is None
    assert "parent.py" in str(result.hierarchical_analysis)
    # Check that good files were processed
    descriptions = [node.get("content", "") for node in result.information_nodes]
    assert any("Description" in d for d in descriptions)  # Good nodes processed
    assert any("Error" in d or "error" in d for d in descriptions)  # Bad node has error
    
    db_manager.close()


@pytest.mark.asyncio
@pytest.mark.performance
async def test_large_scale_processing_performance(
    neo4j_instance: Neo4jContainerInstance
):
    """Test processing 1000+ nodes with good thread utilization."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create 1000+ node graph
    setup_query = """
    CREATE (root:FILE {path: '/root.py', id: 'root', name: 'root.py', content: 'root content'})
    WITH root
    UNWIND range(1, 100) as i
    CREATE (child:FILE {path: '/level1/child' + i + '.py', id: 'l1_' + i, name: 'child' + i + '.py', content: 'child content'})
    CREATE (root)-[:CONTAINS]->(child)
    WITH child
    UNWIND range(1, 10) as j
    CREATE (grandchild:FILE {path: '/level2/gc' + id(child) + '_' + j + '.py', id: 'l2_' + id(child) + '_' + j, name: 'gc' + id(child) + '_' + j + '.py', content: 'gc content'})
    CREATE (child)-[:CONTAINS]->(grandchild)
    """
    db_manager.run_query(setup_query, {})
    
    # Mock LLM provider with fast responses
    mock_llm = Mock()
    mock_llm.call_dumb_agent.return_value = Mock(content="Mock description")
    
    # Create graph environment
    graph_env = GraphEnvironment("test-company", "test-repo")
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        agent_caller=mock_llm,
        company_id="test-company",
        repo_id="test-repo",
        graph_environment=graph_env,
        max_workers=20
    )
    
    monitor = PerformanceMonitor()
    
    with monitor:
        result = processor.process_node("/root.py")
    
    # Performance assertions
    assert monitor.total_time < 60  # Complete in under 1 minute
    assert result.error is None
    # Since we're testing with mock LLM, processing should be very fast
    
    db_manager.close()