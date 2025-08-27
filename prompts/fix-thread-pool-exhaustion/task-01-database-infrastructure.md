# Task 01: Database Infrastructure for Processing Status

## Overview
Add Neo4j query functions to track node processing status and manage processing sessions. Focus on actual database operations and state management rather than query string validation.

## Prerequisites
- Understanding of existing query patterns in `blarify/db_managers/queries.py`
- Neo4j database connection configured
- Review existing integration test patterns in `tests/integration/`

## Test-Driven Development Plan

### Step 1: Initialize Processing Session
**Integration Test First** (`tests/integration/test_processing_session.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_initialize_processing_session_marks_all_nodes_pending(
    neo4j_instance: Neo4jContainerInstance,
    test_code_examples_path: Path
):
    """Test that initializing a session marks all nodes as pending."""
    # Setup: Create graph with nodes
    builder = GraphBuilder(root_path=str(test_code_examples_path))
    graph = builder.build()
    
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j", 
        password="test-password"
    )
    db_manager.save_graph(
        graph.get_nodes_as_objects(),
        graph.get_relationships_as_objects()
    )
    
    # Execute: Initialize session
    session_id = f"test-session-{uuid4()}"
    query = initialize_processing_session_query()
    result = db_manager.run_query(query, {
        "session_id": session_id,
        "root_path": str(test_code_examples_path)
    })
    
    # Verify: All nodes have pending status
    check_query = """
    MATCH (n)
    WHERE n.processing_status_$session_id IS NOT NULL
    RETURN count(n) as total, 
           count(CASE WHEN n.processing_status_$session_id = 'pending' THEN 1 END) as pending
    """
    check_result = db_manager.run_query(
        check_query.replace("$session_id", session_id), {}
    )
    
    assert check_result[0]["total"] > 0
    assert check_result[0]["total"] == check_result[0]["pending"]
    
    # Cleanup
    db_manager.close()
```

**Implementation**: Add `initialize_processing_session_query()` to `blarify/db_managers/queries.py`

### Step 2: Mark Node Processing Status
**Integration Test First** (`tests/integration/test_processing_session.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_mark_node_processing_status_updates_correctly(
    neo4j_instance: Neo4jContainerInstance,
    test_code_examples_path: Path
):
    """Test that marking node status updates the database correctly."""
    # Setup
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create a test node
    create_query = """
    CREATE (n:FILE {path: $path})
    RETURN n
    """
    node_path = "/test/file.py"
    db_manager.run_query(create_query, {"path": node_path})
    
    session_id = f"test-{uuid4()}"
    
    # Initialize session
    init_query = initialize_processing_session_query()
    db_manager.run_query(init_query, {"session_id": session_id})
    
    # Execute: Mark as in_progress
    mark_query = mark_processing_status_query()
    db_manager.run_query(mark_query, {
        "node_path": node_path,
        "status": "in_progress",
        "session_id": session_id
    })
    
    # Verify: Status changed
    verify_query = f"""
    MATCH (n:FILE {{path: $path}})
    RETURN n.processing_status_{session_id} as status
    """
    result = db_manager.run_query(verify_query, {"path": node_path})
    assert result[0]["status"] == "in_progress"
    
    # Execute: Mark as completed
    db_manager.run_query(mark_query, {
        "node_path": node_path,
        "status": "completed",
        "session_id": session_id
    })
    
    # Verify: Status changed to completed
    result = db_manager.run_query(verify_query, {"path": node_path})
    assert result[0]["status"] == "completed"
    
    db_manager.close()
```

**Implementation**: Add `mark_processing_status_query()` to `blarify/db_managers/queries.py`

### Step 3: Get Processable Nodes (Bottom-up Order)
**Integration Test First** (`tests/integration/test_processing_session.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_get_processable_nodes_returns_leaves_first(
    neo4j_instance: Neo4jContainerInstance
):
    """Test that processable nodes query returns leaf nodes first (bottom-up)."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Setup: Create hierarchy
    # parent -> child1 -> grandchild1
    #        -> child2
    setup_query = """
    CREATE (parent:FILE {path: '/parent.py'})
    CREATE (child1:FILE {path: '/child1.py'})
    CREATE (child2:FILE {path: '/child2.py'})
    CREATE (grandchild:FILE {path: '/grandchild.py'})
    CREATE (parent)-[:CONTAINS]->(child1)
    CREATE (parent)-[:CONTAINS]->(child2)
    CREATE (child1)-[:CONTAINS]->(grandchild)
    """
    db_manager.run_query(setup_query, {})
    
    session_id = f"test-{uuid4()}"
    
    # Initialize session
    init_query = initialize_processing_session_query()
    db_manager.run_query(init_query, {"session_id": session_id})
    
    # Execute: Get first batch of processable nodes
    get_query = get_processable_nodes_query()
    batch1 = db_manager.run_query(get_query, {
        "session_id": session_id,
        "batch_size": 10
    })
    
    # Verify: Should get leaf nodes (grandchild and child2)
    paths = [node["path"] for node in batch1]
    assert "/grandchild.py" in paths
    assert "/child2.py" in paths
    assert "/parent.py" not in paths  # Has unprocessed children
    assert "/child1.py" not in paths  # Has unprocessed children
    
    # Mark leaves as completed
    mark_query = mark_processing_status_query()
    for path in ["/grandchild.py", "/child2.py"]:
        db_manager.run_query(mark_query, {
            "node_path": path,
            "status": "completed",
            "session_id": session_id
        })
    
    # Execute: Get next batch
    batch2 = db_manager.run_query(get_query, {
        "session_id": session_id,
        "batch_size": 10
    })
    
    # Verify: Now child1 is processable
    paths = [node["path"] for node in batch2]
    assert "/child1.py" in paths
    assert "/parent.py" not in paths  # child1 not complete yet
    
    db_manager.close()
```

**Implementation**: Add `get_processable_nodes_query()` to `blarify/db_managers/queries.py`

### Step 4: Cleanup Session
**Integration Test First** (`tests/integration/test_processing_session.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_cleanup_session_removes_all_session_data(
    neo4j_instance: Neo4jContainerInstance
):
    """Test that cleanup removes all session-specific data."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Setup: Create nodes and initialize session
    create_query = """
    CREATE (n1:FILE {path: '/file1.py'})
    CREATE (n2:FILE {path: '/file2.py'})
    """
    db_manager.run_query(create_query, {})
    
    session_id = f"test-{uuid4()}"
    
    # Initialize and mark some nodes
    init_query = initialize_processing_session_query()
    db_manager.run_query(init_query, {"session_id": session_id})
    
    mark_query = mark_processing_status_query()
    db_manager.run_query(mark_query, {
        "node_path": "/file1.py",
        "status": "completed",
        "session_id": session_id
    })
    
    # Verify session data exists
    check_query = f"""
    MATCH (n)
    WHERE n.processing_status_{session_id} IS NOT NULL
    RETURN count(n) as count
    """
    result = db_manager.run_query(check_query, {})
    assert result[0]["count"] > 0
    
    # Execute: Cleanup session
    cleanup_query = cleanup_session_query()
    db_manager.run_query(cleanup_query, {"session_id": session_id})
    
    # Verify: Session data removed
    result = db_manager.run_query(check_query, {})
    assert result[0]["count"] == 0
    
    # Verify: Nodes still exist
    node_check = "MATCH (n:FILE) RETURN count(n) as count"
    result = db_manager.run_query(node_check, {})
    assert result[0]["count"] == 2
    
    db_manager.close()
```

**Implementation**: Add `cleanup_session_query()` to `blarify/db_managers/queries.py`

### Step 5: Session Isolation Test
**Integration Test** (`tests/integration/test_processing_session.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_concurrent_sessions_are_isolated(
    neo4j_instance: Neo4jContainerInstance
):
    """Test that multiple sessions don't interfere with each other."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Setup: Create shared nodes
    create_query = """
    CREATE (n1:FILE {path: '/shared1.py'})
    CREATE (n2:FILE {path: '/shared2.py'})
    """
    db_manager.run_query(create_query, {})
    
    session1 = f"session1-{uuid4()}"
    session2 = f"session2-{uuid4()}"
    
    # Initialize both sessions
    init_query = initialize_processing_session_query()
    for session in [session1, session2]:
        db_manager.run_query(init_query, {"session_id": session})
    
    # Mark node as completed in session1 only
    mark_query = mark_processing_status_query()
    db_manager.run_query(mark_query, {
        "node_path": "/shared1.py",
        "status": "completed",
        "session_id": session1
    })
    
    # Get processable nodes for each session
    get_query = get_processable_nodes_query()
    
    nodes_session1 = db_manager.run_query(get_query, {
        "session_id": session1,
        "batch_size": 10
    })
    
    nodes_session2 = db_manager.run_query(get_query, {
        "session_id": session2,
        "batch_size": 10
    })
    
    # Verify isolation
    paths1 = [n["path"] for n in nodes_session1]
    paths2 = [n["path"] for n in nodes_session2]
    
    # Session1 should not see completed node
    assert "/shared1.py" not in paths1
    assert "/shared2.py" in paths1
    
    # Session2 should see all nodes as processable
    assert "/shared1.py" in paths2
    assert "/shared2.py" in paths2
    
    # Cleanup
    cleanup_query = cleanup_session_query()
    for session in [session1, session2]:
        db_manager.run_query(cleanup_query, {"session_id": session})
    
    db_manager.close()
```

## Success Criteria
- [ ] All integration tests pass
- [ ] Session isolation verified with concurrent tests
- [ ] Bottom-up processing order confirmed
- [ ] Cleanup properly removes session data
- [ ] Performance acceptable for 10K+ nodes
- [ ] No pyright type errors
- [ ] Clean ruff checks

## Files to Create/Modify
1. Modify: `blarify/db_managers/queries.py` - Add 4 query functions
2. Create: `tests/integration/test_processing_session.py` - Integration tests

## Dependencies
- None (this is the foundation task)

## Next Task
Task 02: Core Algorithm Transformation (Transform recursive to iterative)