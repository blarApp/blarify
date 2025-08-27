# Task 05: Integration and End-to-End Testing

## Overview
Comprehensive integration testing with real code examples and end-to-end workflow validation to ensure the new implementation works correctly in production scenarios.

## Prerequisites
- Tasks 01-04 completed
- All components integrated

## Test-Driven Development Plan

### Step 1: Real Python Code Processing
**Integration Test First** (`tests/integration/test_e2e_thread_pool_fix.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_process_real_python_codebase(
    neo4j_instance: Neo4jContainerInstance,
    test_code_examples_path: Path
):
    """Test processing real Python code without thread exhaustion."""
    # Use actual Python examples from test_code_examples_path
    builder = GraphBuilder(root_path=str(test_code_examples_path / "python"))
    graph = builder.build()
    
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Save graph to database
    db_manager.save_graph(
        graph.get_nodes_as_objects(),
        graph.get_relationships_as_objects()
    )
    
    # Create real LLM mock that returns meaningful descriptions
    mock_llm = Mock()
    def generate_description(prompt: str) -> str:
        if "class" in prompt.lower():
            return "A Python class for data processing"
        elif "function" in prompt.lower():
            return "A function that processes input data"
        else:
            return "A Python module"
    mock_llm.get_completion.side_effect = generate_description
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=mock_llm,
        max_workers=10,
        enable_monitoring=True
    )
    
    # Process main file
    main_file = test_code_examples_path / "python" / "main.py"
    result = processor.process_node(str(main_file))
    
    # Verify: Processing completed
    assert result is not None
    assert len(result) > 0
    
    # Verify: No thread exhaustion
    metrics = processor.get_metrics()
    assert metrics["thread_reuse_count"] > 0
    assert metrics["avg_thread_utilization"] > 0.5
    
    # Verify: Descriptions generated
    assert "class for data processing" in result or "function that processes" in result
    
    db_manager.close()
```

### Step 2: Mixed Language Processing
**Integration Test First** (`tests/integration/test_e2e_thread_pool_fix.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
@pytest.mark.parametrize("language", ["python", "typescript", "ruby"])
async def test_process_multiple_languages(
    neo4j_instance: Neo4jContainerInstance,
    test_code_examples_path: Path,
    language: str
):
    """Test processing different programming languages."""
    language_path = test_code_examples_path / language
    if not language_path.exists():
        pytest.skip(f"No {language} examples available")
    
    builder = GraphBuilder(root_path=str(language_path))
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
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=Mock(),
        max_workers=5
    )
    
    # Find a file to process
    files = list(language_path.glob("**/*.*"))
    if files:
        result = processor.process_node(str(files[0]))
        assert result is not None
    
    db_manager.close()
```

### Step 3: Integration with DocumentationCreator
**Integration Test First** (`tests/integration/test_e2e_thread_pool_fix.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_integration_with_documentation_creator(
    neo4j_instance: Neo4jContainerInstance,
    test_code_examples_path: Path
):
    """Test that RecursiveDFSProcessor integrates with DocumentationCreator."""
    from blarify.documentation.documentation_creator import DocumentationCreator
    
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Build and save graph
    builder = GraphBuilder(root_path=str(test_code_examples_path / "python"))
    graph = builder.build()
    db_manager.save_graph(
        graph.get_nodes_as_objects(),
        graph.get_relationships_as_objects()
    )
    
    # Create documentation with new processor
    doc_creator = DocumentationCreator(
        db_manager=db_manager,
        llm_provider=Mock(),
        use_parallel_processing=True,  # Use thread pool
        max_workers=8
    )
    
    # Should use RecursiveDFSProcessor internally
    with patch('blarify.documentation.utils.recursive_dfs_processor.RecursiveDFSProcessor.process_node') as mock_process:
        mock_process.return_value = "Mocked documentation"
        
        result = doc_creator.create_documentation(
            root_path=str(test_code_examples_path / "python")
        )
        
        # Verify processor was called
        assert mock_process.called
        
    # Verify: Documentation created
    assert result is not None
    
    db_manager.close()
```

### Step 4: Stress Test with Large Graph
**Integration Test First** (`tests/integration/test_e2e_thread_pool_fix.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
@pytest.mark.slow
async def test_stress_test_large_graph(
    neo4j_instance: Neo4jContainerInstance
):
    """Stress test with 1000+ node graph to verify no exhaustion."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create large hierarchical structure
    setup_query = """
    // Create 3-level hierarchy with 1000+ nodes
    CREATE (root:FILE {path: '/project/root.py'})
    WITH root
    UNWIND range(1, 20) as i
    CREATE (pkg:PACKAGE {path: '/project/package' + i})
    CREATE (root)-[:CONTAINS]->(pkg)
    WITH pkg
    UNWIND range(1, 10) as j
    CREATE (module:FILE {path: pkg.path + '/module' + j + '.py'})
    CREATE (pkg)-[:CONTAINS]->(module)
    WITH module
    UNWIND range(1, 5) as k
    CREATE (func:FUNCTION {path: module.path + ':func' + k})
    CREATE (module)-[:CONTAINS]->(func)
    """
    db_manager.run_query(setup_query, {})
    
    # Add CALL relationships for complexity
    call_query = """
    MATCH (f1:FUNCTION), (f2:FUNCTION)
    WHERE f1 <> f2 AND rand() < 0.1  // 10% chance of call
    WITH f1, f2 LIMIT 500
    CREATE (f1)-[:CALLS]->(f2)
    """
    db_manager.run_query(call_query, {})
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=Mock(),
        max_workers=20,  # Higher thread count
        enable_monitoring=True,
        timeout=300  # 5 minute timeout
    )
    
    start_time = time.time()
    result = processor.process_node("/project/root.py")
    elapsed = time.time() - start_time
    
    # Verify: Completed without exhaustion
    assert result is not None
    
    metrics = processor.get_metrics()
    
    # Performance assertions
    assert metrics["nodes_processed"] > 1000
    assert metrics["thread_reuse_count"] > metrics["nodes_processed"] / 20
    assert elapsed < 120  # Complete within 2 minutes
    assert metrics["avg_thread_utilization"] > 0.7
    
    # Verify: No thread exhaustion occurred
    assert metrics["peak_threads_used"] <= 20
    
    db_manager.close()
```

### Step 5: Cycle Handling in Real Scenarios
**Integration Test First** (`tests/integration/test_e2e_thread_pool_fix.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_cycle_handling_real_scenario(
    neo4j_instance: Neo4jContainerInstance
):
    """Test cycle handling with realistic recursive code patterns."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Create realistic recursive pattern (e.g., recursive descent parser)
    setup_query = """
    CREATE (parser:FILE {path: '/parser.py'})
    CREATE (parse_expr:FUNCTION {path: '/parser.py:parse_expression'})
    CREATE (parse_term:FUNCTION {path: '/parser.py:parse_term'})
    CREATE (parse_factor:FUNCTION {path: '/parser.py:parse_factor'})
    CREATE (parse_primary:FUNCTION {path: '/parser.py:parse_primary'})
    
    CREATE (parser)-[:CONTAINS]->(parse_expr)
    CREATE (parser)-[:CONTAINS]->(parse_term)
    CREATE (parser)-[:CONTAINS]->(parse_factor)
    CREATE (parser)-[:CONTAINS]->(parse_primary)
    
    // Recursive calls
    CREATE (parse_expr)-[:CALLS]->(parse_term)
    CREATE (parse_term)-[:CALLS]->(parse_factor)
    CREATE (parse_factor)-[:CALLS]->(parse_primary)
    CREATE (parse_primary)-[:CALLS]->(parse_expr)  // Cycle!
    
    // Additional non-cyclic calls
    CREATE (parse_expr)-[:CALLS]->(parse_factor)
    CREATE (parse_term)-[:CALLS]->(parse_primary)
    """
    db_manager.run_query(setup_query, {})
    
    processor = RecursiveDFSProcessor(
        db_manager=db_manager,
        llm_provider=Mock(),
        max_workers=4,
        enable_monitoring=True
    )
    
    # Process with cycle detection
    result = processor.process_node("/parser.py:parse_expression", use_hierarchy=False)
    
    # Verify: Completed despite cycles
    assert result is not None
    assert "parse_expression" in result
    assert "parse_term" in result
    assert "parse_factor" in result
    assert "parse_primary" in result
    
    # Verify: Cycle was detected and handled
    assert "[CYCLE" in result or "recursive" in result.lower()
    
    # Verify: No infinite processing
    metrics = processor.get_metrics()
    assert metrics["nodes_processed"] <= 10  # Should not process infinitely
    
    db_manager.close()
```

### Step 6: Concurrent Processing Sessions
**Integration Test First** (`tests/integration/test_e2e_thread_pool_fix.py`):
```python
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_concurrent_documentation_generation(
    neo4j_instance: Neo4jContainerInstance,
    test_code_examples_path: Path
):
    """Test multiple concurrent documentation generation sessions."""
    import asyncio
    
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password"
    )
    
    # Build shared graph
    builder = GraphBuilder(root_path=str(test_code_examples_path))
    graph = builder.build()
    db_manager.save_graph(
        graph.get_nodes_as_objects(),
        graph.get_relationships_as_objects()
    )
    
    async def process_file(file_path: str, processor_id: int):
        processor = RecursiveDFSProcessor(
            db_manager=db_manager,
            llm_provider=Mock(),
            max_workers=3,
            enable_monitoring=True
        )
        
        result = processor.process_node(file_path)
        metrics = processor.get_metrics()
        
        return {
            "processor_id": processor_id,
            "result": result,
            "metrics": metrics
        }
    
    # Get multiple files to process
    files = list((test_code_examples_path / "python").glob("*.py"))[:5]
    
    # Process concurrently
    tasks = [
        process_file(str(file), i) 
        for i, file in enumerate(files)
    ]
    
    results = await asyncio.gather(*tasks)
    
    # Verify: All completed successfully
    assert len(results) == len(files)
    for r in results:
        assert r["result"] is not None
        assert r["metrics"]["nodes_processed"] > 0
    
    # Verify: No interference between sessions
    session_ids = set()
    for r in results:
        # Each should have unique session
        assert r["metrics"].get("session_id") not in session_ids
        if r["metrics"].get("session_id"):
            session_ids.add(r["metrics"]["session_id"])
    
    db_manager.close()
```

## Performance Benchmarks

### Benchmark Test
```python
@pytest.mark.benchmark
async def test_performance_benchmark(benchmark, neo4j_instance):
    """Benchmark new implementation vs baseline."""
    
    def setup():
        # Setup graph with 100 nodes
        return create_test_graph(100)
    
    def process_graph(graph):
        processor = RecursiveDFSProcessor(...)
        return processor.process_node("/root")
    
    result = benchmark.pedantic(
        process_graph,
        setup=setup,
        rounds=5,
        iterations=3
    )
    
    # Assert performance improvements
    assert benchmark.stats["mean"] < 10.0  # Average under 10 seconds
    assert benchmark.stats["stddev"] < 2.0  # Consistent performance
```

## Success Criteria
- [ ] All integration tests pass
- [ ] Real code processing works without exhaustion
- [ ] Multiple languages supported
- [ ] DocumentationCreator integration working
- [ ] 1000+ node graphs handled efficiently
- [ ] Cycles detected and handled properly
- [ ] Concurrent sessions work correctly
- [ ] Performance benchmarks met
- [ ] No pyright type errors
- [ ] Clean ruff checks

## Files to Create
1. Create: `tests/integration/test_e2e_thread_pool_fix.py`
2. Create: `tests/benchmarks/test_thread_pool_performance.py` (optional)

## Dependencies
- Tasks 01-04 must be complete
- All components integrated

## Next Task
Task 06: Documentation Updates