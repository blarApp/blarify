# Task 02: Core Algorithm Transformation

## Overview
Replace the recursive thread-blocking implementation in RecursiveDFSProcessor with an iterative, batch-based approach that enables thread reuse. No backwards compatibility needed - completely replace the current implementation.

## Prerequisites
- Task 01 completed (database infrastructure)
- Understanding that `_get_call_stack_children` ONLY uses CALL relationships
- Understanding that `_get_hierarchy_children` uses CONTAINS relationships

## Test-Driven Development Plan

### Step 1: Remove Recursive Implementation and Test New Iterative Approach
**Integration Test First** (`tests/integration/test_thread_pool_exhaustion.py`):
```python
import threading
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch
from uuid import uuid4

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
    CREATE (root:FILE {path: '/root.py'})
    WITH root
    UNWIND range(1, 50) as i
    CREATE (child:FILE {path: '/child' + i + '.py'})
    CREATE (root)-[:CONTAINS]->(child)
    WITH child
    UNWIND range(1, 2) as j  
    CREATE (grandchild:FILE {path: '/gc' + id(child) + '_' + j + '.py'})
    CREATE (child)-[:CONTAINS]->(grandchild)
    """
    db_manager.run_query(setup_query, {})
    
    # Track thread usage
    thread_tracker = ThreadTracker()
    
    # Mock LLM provider
    mock_llm = Mock()
    mock_llm.get_completion.return_value = "Mock description"
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=mock_llm,
        max_workers=10
    )
    
    with thread_tracker:
        result = processor.process_node("/root.py")
    
    # Verify: No thread exhaustion
    assert thread_tracker.max_concurrent_threads <= 10
    assert thread_tracker.total_unique_threads <= 15  # Some overhead OK
    assert thread_tracker.thread_reuse_count > 100  # Significant reuse
    
    # Verify: All nodes processed
    assert "root.py" in result
    assert result is not None
    
    db_manager.close()
```

**Implementation**: Replace entire `process_node()` and `_process_node_recursive()` with new implementation

### Step 2: Test Hierarchy vs Call Stack Processing
**Integration Test First** (`tests/integration/test_thread_pool_exhaustion.py`):
```python
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
    CREATE (file1:FILE {path: '/file1.py'})
    CREATE (class1:CLASS {path: '/file1.py:ClassA'})
    CREATE (method1:FUNCTION {path: '/file1.py:ClassA:method1'})
    CREATE (file1)-[:CONTAINS]->(class1)
    CREATE (class1)-[:CONTAINS]->(method1)
    
    // Call stack structure (CALL only)
    CREATE (func1:FUNCTION {path: '/utils.py:helper'})
    CREATE (func2:FUNCTION {path: '/utils.py:process'})
    CREATE (func3:FUNCTION {path: '/utils.py:validate'})
    CREATE (method1)-[:CALLS]->(func1)
    CREATE (func1)-[:CALLS]->(func2)
    CREATE (func2)-[:CALLS]->(func3)
    """
    db_manager.run_query(setup_query, {})
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=Mock(),
        max_workers=5
    )
    
    # Test hierarchy processing
    hierarchy_result = processor.process_node("/file1.py", use_hierarchy=True)
    
    # Verify: Hierarchy uses CONTAINS relationships
    assert "ClassA" in hierarchy_result
    assert "method1" in hierarchy_result
    
    # Test call stack processing  
    call_stack_result = processor.process_node("/file1.py:ClassA:method1", use_hierarchy=False)
    
    # Verify: Call stack uses CALL relationships only
    assert "helper" in call_stack_result
    assert "process" in call_stack_result
    assert "validate" in call_stack_result
    
    db_manager.close()
```

**Implementation**: Ensure `_get_hierarchy_children()` uses CONTAINS and `_get_call_stack_children()` uses CALL

### Step 3: Batch Processing with Bottom-Up Order
**Integration Test First** (`tests/integration/test_thread_pool_exhaustion.py`):
```python
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
    CREATE (root:FILE {path: '/root.py'})
    CREATE (c1:FILE {path: '/child1.py'})
    CREATE (c2:FILE {path: '/child2.py'})
    CREATE (gc1:FILE {path: '/grandchild1.py'})
    CREATE (gc2:FILE {path: '/grandchild2.py'})
    CREATE (ggc:FILE {path: '/great_grandchild.py'})
    CREATE (root)-[:CONTAINS]->(c1)
    CREATE (root)-[:CONTAINS]->(c2)
    CREATE (c1)-[:CONTAINS]->(gc1)
    CREATE (c1)-[:CONTAINS]->(gc2)
    CREATE (gc1)-[:CONTAINS]->(ggc)
    """
    db_manager.run_query(setup_query, {})
    
    processing_order = []
    
    def mock_process(node_path: str) -> str:
        processing_order.append(node_path)
        return f"Processed {node_path}"
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=Mock(),
        max_workers=3
    )
    
    with patch.object(processor, '_process_single_node', side_effect=mock_process):
        processor.process_node("/root.py")
    
    # Verify: Bottom-up order
    # Leaves should be processed first
    assert processing_order.index("/great_grandchild.py") < processing_order.index("/grandchild1.py")
    assert processing_order.index("/grandchild1.py") < processing_order.index("/child1.py")
    assert processing_order.index("/grandchild2.py") < processing_order.index("/child1.py")
    assert processing_order.index("/child2.py") < processing_order.index("/root.py")
    assert processing_order.index("/child1.py") < processing_order.index("/root.py")
    assert processing_order[-1] == "/root.py"  # Root is last
    
    db_manager.close()
```

**Implementation**: Implement bottom-up batch selection in new algorithm

### Step 4: Thread Harvesting with as_completed
**Integration Test First** (`tests/integration/test_thread_pool_exhaustion.py`):
```python
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
    UNWIND range(1, 30) as i
    CREATE (n:FILE {path: '/file' + i + '.py'})
    """
    db_manager.run_query(setup_query, {})
    
    # Track when threads are released
    thread_release_times = {}
    active_threads = set()
    
    def mock_process_with_timing(node_path: str) -> str:
        thread_id = threading.current_thread().ident
        active_threads.add(thread_id)
        
        # Variable processing time to test harvesting
        process_time = random.uniform(0.1, 0.5)
        time.sleep(process_time)
        
        active_threads.remove(thread_id)
        thread_release_times[node_path] = time.time()
        return f"Processed {node_path}"
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=Mock(),
        max_workers=5  # Limited pool to force reuse
    )
    
    start_time = time.time()
    
    with patch.object(processor, '_process_single_node', side_effect=mock_process_with_timing):
        processor.process_node("/file1.py")  # Trigger batch processing
    
    # Verify: Threads were harvested and reused
    unique_threads = len(set(thread_release_times.keys()))
    assert unique_threads == 30  # All nodes processed
    
    # Check that threads were released at different times (not all at once)
    release_times = sorted(thread_release_times.values())
    time_spread = release_times[-1] - release_times[0]
    assert time_spread > 1.0  # Processing was spread out
    
    # Verify thread reuse (30 tasks with only 5 threads)
    assert len(active_threads) == 0  # All threads released
    
    db_manager.close()
```

**Implementation**: Use `concurrent.futures.as_completed()` for immediate thread harvesting

### Step 5: Cycle Detection Integration
**Integration Test First** (`tests/integration/test_thread_pool_exhaustion.py`):
```python
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
    CREATE (f1:FUNCTION {path: '/file.py:func1'})
    CREATE (f2:FUNCTION {path: '/file.py:func2'})
    CREATE (f3:FUNCTION {path: '/file.py:func3'})
    CREATE (f1)-[:CALLS]->(f2)
    CREATE (f2)-[:CALLS]->(f3)
    CREATE (f3)-[:CALLS]->(f1)  // Cycle!
    """
    db_manager.run_query(setup_query, {})
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=Mock(),
        max_workers=3
    )
    
    # Should handle cycle gracefully
    result = processor.process_node("/file.py:func1", use_hierarchy=False)
    
    # Verify: Cycle detected and handled
    assert result is not None
    assert "func1" in result
    assert "[CYCLE_DETECTED]" in result or "recursive" in result.lower()
    
    # Verify: Processing completed without infinite loop
    assert len(result) < 10000  # Reasonable size, not infinite
    
    db_manager.close()
```

**Implementation**: Integrate cycle detection into new iterative algorithm

### Step 6: Error Recovery
**Integration Test First** (`tests/integration/test_thread_pool_exhaustion.py`):
```python
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
    CREATE (parent:FILE {path: '/parent.py'})
    CREATE (good1:FILE {path: '/good1.py'})
    CREATE (bad:FILE {path: '/bad.py'})
    CREATE (good2:FILE {path: '/good2.py'})
    CREATE (parent)-[:CONTAINS]->(good1)
    CREATE (parent)-[:CONTAINS]->(bad)
    CREATE (parent)-[:CONTAINS]->(good2)
    """
    db_manager.run_query(setup_query, {})
    
    # Mock LLM that fails for specific node
    mock_llm = Mock()
    def llm_side_effect(prompt):
        if "bad.py" in prompt:
            raise Exception("LLM API error")
        return "Description"
    mock_llm.get_completion.side_effect = llm_side_effect
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=mock_llm,
        max_workers=3
    )
    
    # Should complete despite error
    result = processor.process_node("/parent.py")
    
    # Verify: Parent and good children processed
    assert "parent.py" in result
    assert "good1.py" in result
    assert "good2.py" in result
    
    # Bad node should have error placeholder
    assert "bad.py" in result
    assert "[ERROR]" in result or "failed" in result.lower()
    
    db_manager.close()
```

**Implementation**: Add robust error handling to batch processing

## Performance Testing

### Large Scale Test
```python
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
    CREATE (root:FILE {path: '/root.py'})
    WITH root
    UNWIND range(1, 100) as i
    CREATE (child:FILE {path: '/level1/child' + i + '.py'})
    CREATE (root)-[:CONTAINS]->(child)
    WITH child
    UNWIND range(1, 10) as j
    CREATE (grandchild:FILE {path: '/level2/gc' + id(child) + '_' + j + '.py'})
    CREATE (child)-[:CONTAINS]->(grandchild)
    """
    db_manager.run_query(setup_query, {})
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=Mock(),
        max_workers=20
    )
    
    monitor = PerformanceMonitor()
    
    with monitor:
        result = processor.process_node("/root.py")
    
    # Performance assertions
    assert monitor.total_time < 60  # Complete in under 1 minute
    assert monitor.avg_thread_utilization > 0.75  # 75%+ utilization
    assert monitor.max_memory_mb < 500  # Reasonable memory usage
    
    db_manager.close()
```

## Success Criteria
- [ ] All integration tests pass
- [ ] Complete replacement of recursive implementation
- [ ] Thread reuse demonstrated with as_completed()
- [ ] Bottom-up processing order maintained
- [ ] Hierarchy (CONTAINS) vs Call Stack (CALL) correctly handled
- [ ] Cycle detection integrated
- [ ] Error recovery working
- [ ] Thread utilization > 80% average
- [ ] No pyright type errors
- [ ] Clean ruff checks

## Files to Modify
1. Modify: `blarify/documentation/utils/recursive_dfs_processor.py`
   - REMOVE: `_process_node_recursive()` method completely
   - REPLACE: `process_node()` with iterative implementation
   - ADD: `_process_batch()` with `as_completed()`
   - ADD: `_get_processable_batch()` for bottom-up selection
   - KEEP: `_get_hierarchy_children()` (uses CONTAINS)
   - KEEP: `_get_call_stack_children()` (uses CALL only)
   - ADD: Error handling and cycle detection
2. Create: `tests/integration/test_thread_pool_exhaustion.py`

## Dependencies
- Task 01 (database infrastructure) must be complete

## Next Task
Task 03: Session Management and Cleanup