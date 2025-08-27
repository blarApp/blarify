# Task 03: Session Management and Cleanup

## Overview
Implement proper session management to isolate concurrent processing runs and ensure cleanup of session data.

## Prerequisites
- Task 01 completed (database infrastructure)
- Task 02 completed (core algorithm transformation)

## Test-Driven Development Plan

### Step 1: Session Initialization in Process Method
**Integration Test First** (`tests/integration/test_session_management.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_process_node_creates_and_cleans_session(
    neo4j_instance: Neo4jContainerInstance
):
    """Test that process_node creates a session and cleans it up."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create simple hierarchy
    setup_query = """
    CREATE (root:FILE {path: '/root.py'})
    CREATE (child:FILE {path: '/child.py'})
    CREATE (root)-[:CONTAINS]->(child)
    """
    db_manager.run_query(setup_query, {})
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=Mock(),
        max_workers=2
    )
    
    # Capture session_id during processing
    captured_session_id = None
    
    def capture_session(query, params):
        nonlocal captured_session_id
        if "session_id" in params:
            captured_session_id = params["session_id"]
        return original_run_query(query, params)
    
    original_run_query = db_manager.run_query
    with patch.object(db_manager, 'run_query', side_effect=capture_session):
        result = processor.process_node("/root.py")
    
    # Verify: Session was created
    assert captured_session_id is not None
    assert len(captured_session_id) > 0
    
    # Verify: Session was cleaned up
    check_query = f"""
    MATCH (n)
    WHERE n.processing_status_{captured_session_id} IS NOT NULL
    RETURN count(n) as count
    """
    remaining = db_manager.run_query(check_query, {})
    assert remaining[0]["count"] == 0  # Session data cleaned up
    
    # Verify: Original nodes still exist
    node_check = "MATCH (n:FILE) RETURN count(n) as count"
    nodes = db_manager.run_query(node_check, {})
    assert nodes[0]["count"] == 2
    
    db_manager.close()
```

**Implementation**: Add session lifecycle management to `process_node()`

### Step 2: Concurrent Session Isolation
**Integration Test First** (`tests/integration/test_session_management.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_concurrent_processing_sessions_isolated(
    neo4j_instance: Neo4jContainerInstance
):
    """Test that concurrent process_node calls don't interfere."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create shared graph
    setup_query = """
    CREATE (root:FILE {path: '/shared/root.py'})
    CREATE (c1:FILE {path: '/shared/child1.py'})
    CREATE (c2:FILE {path: '/shared/child2.py'})
    CREATE (root)-[:CONTAINS]->(c1)
    CREATE (root)-[:CONTAINS]->(c2)
    """
    db_manager.run_query(setup_query, {})
    
    # Run two processors concurrently
    processor1 = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=Mock(),
        max_workers=2
    )
    
    processor2 = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=Mock(),
        max_workers=2
    )
    
    import asyncio
    
    async def run_processor(processor, path):
        return processor.process_node(path)
    
    # Run concurrently
    results = await asyncio.gather(
        run_processor(processor1, "/shared/root.py"),
        run_processor(processor2, "/shared/root.py")
    )
    
    # Verify: Both completed successfully
    assert results[0] is not None
    assert results[1] is not None
    assert "root.py" in results[0]
    assert "root.py" in results[1]
    
    # Verify: No session data remains
    check_query = """
    MATCH (n)
    WHERE any(key in keys(n) WHERE key STARTS WITH 'processing_status_')
    RETURN count(n) as count
    """
    remaining = db_manager.run_query(check_query, {})
    assert remaining[0]["count"] == 0
    
    db_manager.close()
```

**Implementation**: Ensure session isolation with unique IDs

### Step 3: Session Cleanup on Error
**Integration Test First** (`tests/integration/test_session_management.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_session_cleanup_on_processing_error(
    neo4j_instance: Neo4jContainerInstance
):
    """Test that session is cleaned up even when processing fails."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create nodes
    setup_query = """
    CREATE (root:FILE {path: '/root.py'})
    CREATE (child:FILE {path: '/child.py'})
    CREATE (root)-[:CONTAINS]->(child)
    """
    db_manager.run_query(setup_query, {})
    
    # Mock LLM that always fails
    mock_llm = Mock()
    mock_llm.get_completion.side_effect = Exception("LLM service unavailable")
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=mock_llm,
        max_workers=2
    )
    
    captured_session_id = None
    
    def capture_session(query, params):
        nonlocal captured_session_id
        if "session_id" in params and not captured_session_id:
            captured_session_id = params["session_id"]
        return original_run_query(query, params)
    
    original_run_query = db_manager.run_query
    
    # Process should handle error
    with patch.object(db_manager, 'run_query', side_effect=capture_session):
        try:
            result = processor.process_node("/root.py")
        except Exception:
            pass  # Expected to fail
    
    # Verify: Session was cleaned up despite error
    if captured_session_id:
        check_query = f"""
        MATCH (n)
        WHERE n.processing_status_{captured_session_id} IS NOT NULL
        RETURN count(n) as count
        """
        remaining = db_manager.run_query(check_query, {})
        assert remaining[0]["count"] == 0  # Cleaned up
    
    db_manager.close()
```

**Implementation**: Add try/finally for session cleanup

### Step 4: Session Timeout Handling
**Integration Test First** (`tests/integration/test_session_management.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_session_timeout_handling(
    neo4j_instance: Neo4jContainerInstance
):
    """Test that sessions have timeout and are cleaned up."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create nodes
    setup_query = """
    CREATE (root:FILE {path: '/root.py'})
    UNWIND range(1, 100) as i
    CREATE (child:FILE {path: '/child' + i + '.py'})
    """
    db_manager.run_query(setup_query, {})
    
    # Mock slow processing
    def slow_process(node_path: str) -> str:
        time.sleep(0.5)  # Simulate slow processing
        return f"Processed {node_path}"
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=Mock(),
        max_workers=2,
        timeout=5  # 5 second timeout
    )
    
    start_time = time.time()
    
    with patch.object(processor, '_process_single_node', side_effect=slow_process):
        with pytest.raises(TimeoutError):
            processor.process_node("/root.py")
    
    elapsed = time.time() - start_time
    
    # Verify: Timeout triggered
    assert elapsed < 10  # Should timeout at 5 seconds
    
    # Verify: Session cleaned up after timeout
    check_query = """
    MATCH (n)
    WHERE any(key in keys(n) WHERE key STARTS WITH 'processing_status_')
    RETURN count(n) as count
    """
    remaining = db_manager.run_query(check_query, {})
    assert remaining[0]["count"] == 0
    
    db_manager.close()
```

**Implementation**: Add timeout handling to process_node

## Success Criteria
- [ ] All integration tests pass
- [ ] Sessions are created and cleaned up properly
- [ ] Concurrent sessions don't interfere
- [ ] Cleanup happens even on errors
- [ ] Timeout handling works
- [ ] No session data persists after processing
- [ ] No pyright type errors
- [ ] Clean ruff checks

## Files to Modify
1. Modify: `blarify/documentation/utils/recursive_dfs_processor.py`
   - Add session initialization in `process_node()`
   - Add cleanup in finally block
   - Add timeout handling
   - Generate unique session IDs
2. Create: `tests/integration/test_session_management.py`

## Dependencies
- Task 01 (database infrastructure)
- Task 02 (core algorithm transformation)

## Next Task
Task 04: Performance Monitoring and Metrics