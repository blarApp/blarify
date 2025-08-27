# Task 04: Performance Monitoring and Metrics

## Overview
Add performance monitoring to track thread utilization, processing rates, and identify bottlenecks in the new iterative implementation.

## Prerequisites
- Task 01-03 completed
- Understanding of threading metrics

## Test-Driven Development Plan

### Step 1: Thread Utilization Monitoring
**Integration Test First** (`tests/integration/test_performance_monitoring.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_thread_utilization_monitoring(
    neo4j_instance: Neo4jContainerInstance
):
    """Test that thread utilization is properly monitored."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create 50 nodes
    setup_query = """
    UNWIND range(1, 50) as i
    CREATE (n:FILE {path: '/file' + i + '.py'})
    """
    db_manager.run_query(setup_query, {})
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=Mock(),
        max_workers=5,
        enable_monitoring=True  # Enable monitoring
    )
    
    # Process and get metrics
    result = processor.process_node("/file1.py")
    metrics = processor.get_metrics()
    
    # Verify: Metrics collected
    assert "thread_utilization" in metrics
    assert "avg_thread_utilization" in metrics
    assert "peak_thread_utilization" in metrics
    assert "total_threads_used" in metrics
    
    # Verify: Reasonable values
    assert 0 <= metrics["avg_thread_utilization"] <= 1.0
    assert metrics["peak_thread_utilization"] <= 1.0
    assert metrics["total_threads_used"] <= 5
    
    # Verify: Thread reuse metrics
    assert "thread_reuse_count" in metrics
    assert metrics["thread_reuse_count"] > 0  # Some reuse occurred
    
    db_manager.close()
```

**Implementation**: Add `ThreadMonitor` class and integrate with processor

### Step 2: Processing Rate Tracking
**Integration Test First** (`tests/integration/test_performance_monitoring.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_processing_rate_tracking(
    neo4j_instance: Neo4jContainerInstance
):
    """Test that processing rates are tracked accurately."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create hierarchy
    setup_query = """
    CREATE (root:FILE {path: '/root.py'})
    WITH root
    UNWIND range(1, 20) as i
    CREATE (child:FILE {path: '/child' + i + '.py'})
    CREATE (root)-[:CONTAINS]->(child)
    """
    db_manager.run_query(setup_query, {})
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=Mock(),
        max_workers=4,
        enable_monitoring=True
    )
    
    start_time = time.time()
    result = processor.process_node("/root.py")
    elapsed = time.time() - start_time
    
    metrics = processor.get_metrics()
    
    # Verify: Processing rate metrics
    assert "nodes_processed" in metrics
    assert "processing_time" in metrics
    assert "nodes_per_second" in metrics
    assert "avg_node_processing_time" in metrics
    
    # Verify: Accurate counts
    assert metrics["nodes_processed"] == 21  # root + 20 children
    assert abs(metrics["processing_time"] - elapsed) < 0.1
    assert metrics["nodes_per_second"] > 0
    
    # Verify: Batch metrics
    assert "total_batches" in metrics
    assert "avg_batch_size" in metrics
    assert metrics["total_batches"] > 0
    
    db_manager.close()
```

**Implementation**: Add processing rate tracking to metrics

### Step 3: Memory Usage Monitoring
**Integration Test First** (`tests/integration/test_performance_monitoring.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_memory_usage_monitoring(
    neo4j_instance: Neo4jContainerInstance
):
    """Test that memory usage is tracked during processing."""
    import psutil
    import os
    
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create large hierarchy
    setup_query = """
    CREATE (root:FILE {path: '/root.py'})
    WITH root
    UNWIND range(1, 100) as i
    CREATE (child:FILE {path: '/child' + i + '.py'})
    CREATE (root)-[:CONTAINS]->(child)
    """
    db_manager.run_query(setup_query, {})
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=Mock(),
        max_workers=10,
        enable_monitoring=True
    )
    
    # Get initial memory
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    result = processor.process_node("/root.py")
    
    metrics = processor.get_metrics()
    
    # Verify: Memory metrics collected
    assert "initial_memory_mb" in metrics
    assert "peak_memory_mb" in metrics
    assert "memory_growth_mb" in metrics
    
    # Verify: Reasonable memory usage
    assert metrics["peak_memory_mb"] > metrics["initial_memory_mb"]
    assert metrics["memory_growth_mb"] < 100  # Less than 100MB growth
    
    db_manager.close()
```

**Implementation**: Add memory monitoring to metrics

### Step 4: Bottleneck Detection
**Integration Test First** (`tests/integration/test_performance_monitoring.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_bottleneck_detection(
    neo4j_instance: Neo4jContainerInstance
):
    """Test that bottlenecks are identified in processing."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create nodes with varying complexity
    setup_query = """
    CREATE (root:FILE {path: '/root.py'})
    CREATE (complex:FILE {path: '/complex.py', size: 10000})
    CREATE (simple1:FILE {path: '/simple1.py', size: 100})
    CREATE (simple2:FILE {path: '/simple2.py', size: 100})
    CREATE (root)-[:CONTAINS]->(complex)
    CREATE (root)-[:CONTAINS]->(simple1)
    CREATE (root)-[:CONTAINS]->(simple2)
    """
    db_manager.run_query(setup_query, {})
    
    # Mock processing with variable time based on "size"
    def mock_process(node_path: str) -> str:
        if "complex" in node_path:
            time.sleep(1.0)  # Slow node
        else:
            time.sleep(0.1)  # Fast node
        return f"Processed {node_path}"
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=Mock(),
        max_workers=3,
        enable_monitoring=True
    )
    
    with patch.object(processor, '_process_single_node', side_effect=mock_process):
        result = processor.process_node("/root.py")
    
    metrics = processor.get_metrics()
    
    # Verify: Bottleneck detection
    assert "slowest_nodes" in metrics
    assert len(metrics["slowest_nodes"]) > 0
    assert "/complex.py" in metrics["slowest_nodes"][0]["path"]
    assert metrics["slowest_nodes"][0]["time"] > 0.5
    
    # Verify: Thread idle time tracking
    assert "total_idle_time" in metrics
    assert "idle_time_percentage" in metrics
    
    db_manager.close()
```

**Implementation**: Add bottleneck detection to monitoring

### Step 5: Performance Report Generation
**Integration Test First** (`tests/integration/test_performance_monitoring.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_performance_report_generation(
    neo4j_instance: Neo4jContainerInstance,
    tmp_path: Path
):
    """Test that comprehensive performance reports are generated."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create test graph
    setup_query = """
    CREATE (root:FILE {path: '/root.py'})
    WITH root
    UNWIND range(1, 30) as i
    CREATE (child:FILE {path: '/child' + i + '.py'})
    CREATE (root)-[:CONTAINS]->(child)
    """
    db_manager.run_query(setup_query, {})
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=Mock(),
        max_workers=5,
        enable_monitoring=True
    )
    
    result = processor.process_node("/root.py")
    
    # Generate report
    report_path = tmp_path / "performance_report.json"
    processor.save_performance_report(str(report_path))
    
    # Verify: Report created
    assert report_path.exists()
    
    # Load and verify report content
    import json
    with open(report_path) as f:
        report = json.load(f)
    
    # Verify: Report sections
    assert "summary" in report
    assert "thread_metrics" in report
    assert "processing_metrics" in report
    assert "memory_metrics" in report
    assert "bottlenecks" in report
    assert "recommendations" in report
    
    # Verify: Recommendations based on metrics
    if report["thread_metrics"]["avg_utilization"] < 0.5:
        assert any("reduce max_workers" in r.lower() 
                  for r in report["recommendations"])
    
    if report["memory_metrics"]["growth_mb"] > 50:
        assert any("memory" in r.lower() 
                  for r in report["recommendations"])
    
    db_manager.close()
```

**Implementation**: Add performance report generation

## Success Criteria
- [ ] All integration tests pass
- [ ] Thread utilization accurately tracked
- [ ] Processing rates calculated correctly
- [ ] Memory usage monitored
- [ ] Bottlenecks identified
- [ ] Performance reports generated
- [ ] Metrics help identify optimization opportunities
- [ ] No pyright type errors
- [ ] Clean ruff checks

## Files to Create/Modify
1. Create: `blarify/documentation/utils/performance_monitor.py`
   - `ThreadMonitor` class
   - `PerformanceMetrics` class
   - Bottleneck detection logic
2. Modify: `blarify/documentation/utils/recursive_dfs_processor.py`
   - Integrate monitoring
   - Add `get_metrics()` method
   - Add `save_performance_report()` method
3. Create: `tests/integration/test_performance_monitoring.py`

## Dependencies
- Tasks 01-03 must be complete

## Next Task
Task 05: Integration and End-to-End Testing