# Testing Guide for Blarify

This guide explains the testing framework used in Blarify and provides comprehensive instructions for adding new tests to the project.

## Table of Contents
- [Overview](#overview)
- [Test Structure](#test-structure)
- [Testing Stack](#testing-stack)
- [Types of Tests](#types-of-tests)
- [Writing Tests](#writing-tests)
- [Neo4j Container Testing](#neo4j-container-testing)
- [Running Tests](#running-tests)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

Blarify uses a comprehensive testing framework built on pytest with asynchronous support and Neo4j container management for integration testing. The framework ensures code quality, reliability, and proper functionality of graph building and database operations.

### Key Features
- **Async-first testing** with pytest-asyncio
- **Parallel test execution** with pytest-xdist
- **Automated Neo4j containers** for integration tests
- **Fixtures for common test scenarios**
- **Test categorization with marks**

## Test Structure

```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── code_examples/              # Sample code for testing
│   ├── python/                 # Python test files
│   ├── typescript/             # TypeScript test files
│   └── ruby/                   # Ruby test files
├── integration/                # Integration tests
│   ├── test_graphbuilder_basic.py
│   ├── test_graphbuilder_edge_cases.py
│   └── test_graphbuilder_languages.py
├── utils/                      # Test utilities
│   ├── graph_assertions.py    # Graph validation helpers
│   └── fixtures.py             # Additional fixtures
└── unit/                       # Unit tests (to be added)
```

## Testing Stack

### Core Dependencies
```toml
[tool.poetry.group.dev.dependencies]
pytest = "^8.4.1"
pytest-asyncio = "^0.25.3"
pytest-xdist = "^3.8.0"      # Parallel test execution
pytest-mock = "^3.14.1"       # Mocking support
docker = "^7.1.0"             # Container management
filelock = "^3.13.1"          # Port allocation locking
```

### Key Components

1. **pytest**: Core testing framework
2. **pytest-asyncio**: Async/await support for tests
3. **pytest-xdist**: Parallel test execution
4. **Neo4j Container Manager**: Automated database provisioning
5. **GraphAssertions**: Helper class for validating graph data

## Types of Tests

### 1. Unit Tests
Test individual functions and classes in isolation.

```python
# tests/unit/test_graph.py
import pytest
from blarify.graph.graph import Graph

def test_graph_initialization():
    """Test that Graph initializes correctly."""
    graph = Graph()
    assert graph is not None
    assert graph.nodes == []
    assert graph.relationships == []
```

### 2. Integration Tests
Test complete workflows with real database connections.

```python
# tests/integration/test_graphbuilder.py
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_graphbuilder_creates_nodes(
    neo4j_instance,
    test_code_examples_path,
    graph_assertions
):
    """Test that GraphBuilder creates nodes in Neo4j."""
    builder = GraphBuilder(root_path=str(test_code_examples_path))
    graph = builder.build()
    
    # Save to Neo4j
    db_manager = Neo4jManager(uri=neo4j_instance.uri, ...)
    db_manager.save_graph(graph.get_nodes_as_objects(), ...)
    
    # Verify nodes exist
    await graph_assertions.assert_node_exists("FILE")
```

### 3. Parameterized Tests
Test multiple scenarios with the same test logic.

```python
@pytest.mark.parametrize("language", ["python", "typescript", "ruby"])
async def test_language_support(language, neo4j_instance):
    """Test GraphBuilder with different languages."""
    # Test logic here
```

## Writing Tests

### Step 1: Create Test File

Create a new test file following the naming convention `test_*.py`:

```python
# tests/integration/test_my_feature.py
"""
Tests for my new feature.
"""

import pytest
from pathlib import Path
from typing import Any

from blarify.prebuilt.graph_builder import GraphBuilder
from neo4j_container_manager.types import Neo4jContainerInstance
from tests.utils.graph_assertions import GraphAssertions
```

### Step 2: Use Test Marks

Mark your tests appropriately for organization and selective execution:

```python
@pytest.mark.asyncio              # For async tests
@pytest.mark.neo4j_integration    # For Neo4j integration tests
@pytest.mark.slow                 # For slow-running tests
class TestMyFeature:
    """Test suite for my feature."""
```

### Step 3: Leverage Fixtures

Use the available fixtures to simplify test setup:

```python
async def test_with_fixtures(
    docker_check: Any,                    # Ensures Docker is available
    neo4j_instance: Neo4jContainerInstance,  # Provides Neo4j container
    test_code_examples_path: Path,        # Path to test data
    graph_assertions: GraphAssertions,    # Graph validation helpers
    temp_project_dir: Path,                # Temporary directory
):
    """Test using multiple fixtures."""
    # Your test logic here
```

### Step 4: Write Test Logic

Structure your tests with clear setup, execution, and verification:

```python
async def test_graph_creation(neo4j_instance, graph_assertions):
    """Test that graph creation works correctly."""
    # Setup
    builder = GraphBuilder(root_path="/path/to/code")
    
    # Execute
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
    
    # Verify
    await graph_assertions.assert_node_exists("FILE")
    await graph_assertions.assert_node_exists("FUNCTION")
    
    # Cleanup
    db_manager.close()
```

## Neo4j Container Testing

### Understanding Container Management

The Neo4j container manager uses an optimized approach for test performance:

1. **Module-scoped containers**: One container per test file (not per test)
2. **Data isolation**: Uses entity_id and repo_id for test isolation
3. **Port allocation**: Dynamic ports prevent conflicts
4. **Parallel support**: Tests run concurrently without interference
5. **Automatic cleanup**: Data cleaned between tests, containers reused
6. **Performance**: 60-70% faster test execution through container reuse

### Available Neo4j Fixtures

```python
# Module-scoped container (shared across tests in file)
@pytest.fixture(scope="module")
async def module_neo4j_container() -> Neo4jContainerInstance:
    """Provides one Neo4j container per test module."""

# Test data isolation (unique IDs per test)
@pytest.fixture
def test_data_isolation(module_neo4j_container) -> Dict[str, Any]:
    """Provides isolated entity_id and repo_id for each test."""
    # Returns: {"entity_id": "...", "repo_id": "...", "container": ..., "uri": ..., "password": ...}
    
# Backward compatible fixture
@pytest.fixture
async def neo4j_instance(test_data_isolation) -> Neo4jContainerInstance:
    """Compatibility fixture using module container."""
```

### Custom Neo4j Configuration

The optimized configuration uses module-scoped containers:

```python
@pytest.fixture(scope="module")
def module_neo4j_config(request):
    """Module-scoped Neo4j configuration."""
    module_name = request.module.__name__
    clean_name = module_name.replace(".", "_")
    
    return Neo4jContainerConfig(
        environment=Environment.TEST,
        password="test-password",
        plugins=["apoc"],
        test_id=f"module_{clean_name}",  # One container per module
        memory="512M",  # Optimized for tests
        startup_timeout=30,
        health_check_interval=1,
    )
```

### Using GraphAssertions with Data Isolation

The GraphAssertions helper now supports entity_id/repo_id isolation:

```python
async def test_with_assertions(test_data_isolation, graph_assertions):
    """Test using graph assertions with data isolation."""
    # Assertions automatically filter by entity_id/repo_id
    await graph_assertions.assert_node_exists("FILE")
    await graph_assertions.assert_node_exists("FUNCTION", {"name": "my_func"})
    
    # Only sees data for this test's entity_id/repo_id
    properties = await graph_assertions.get_node_properties("CLASS")
    
    # Check relationships within isolated data
    await graph_assertions.assert_relationship_exists(
        "FILE", "CONTAINS", "FUNCTION"
    )
    
    # Debug shows only this test's data
    summary = await graph_assertions.debug_print_graph_summary()
```

### Complete Example: Optimized Test with Data Isolation

```python
# tests/integration/test_optimized_example.py
"""
Example demonstrating optimized Neo4j container usage.

This file shows how tests share one container but maintain data isolation.
"""

import pytest
from pathlib import Path
from typing import Any, Dict

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from tests.utils.graph_assertions import GraphAssertions


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestOptimizedNeo4j:
    """Tests demonstrating optimized container usage."""
    
    async def test_first_with_isolation(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """First test - creates data with unique entity_id/repo_id."""
        # Build graph from test code
        python_path = test_code_examples_path / "python"
        builder = GraphBuilder(root_path=str(python_path))
        graph = builder.build()
        
        # Save to Neo4j with isolated IDs
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"]
        )
        
        try:
            db_manager.save_graph(
                graph.get_nodes_as_objects(),
                graph.get_relationships_as_objects()
            )
            
            # Verify nodes exist (only sees this test's data)
            await graph_assertions.assert_node_exists("FILE")
            await graph_assertions.assert_node_exists("FUNCTION")
            await graph_assertions.assert_node_exists("CLASS")
        finally:
            db_manager.close()
    
    async def test_second_isolated(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
    ) -> None:
        """Second test - has different entity_id/repo_id, won't see first test's data."""
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"]
        )
        
        try:
            # Verify isolation - this test starts with no data
            with db_manager.driver.session() as session:
                result = session.run(
                    """
                    MATCH (n)
                    WHERE (n.entityId = $eid OR n.entity_id = $eid)
                      AND (n.repoId = $rid OR n.repo_id = $rid)
                    RETURN count(n) as count
                    """,
                    eid=test_data_isolation["entity_id"],
                    rid=test_data_isolation["repo_id"]
                )
                # Zero nodes - proves isolation from first test
                assert result.single()["count"] == 0
                
                # Check container has data (from other tests)
                total_result = session.run("MATCH (n) RETURN count(n) as count")
                total_count = total_result.single()["count"]
                print(f"Container has {total_count} total nodes (from all tests)")
                # This proves container is reused but data is isolated
        finally:
            db_manager.close()
    
    async def test_third_creates_own_data(
        self,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
    ) -> None:
        """Third test - creates its own isolated data."""
        # Each test gets unique IDs
        print(f"Test entity_id: {test_data_isolation['entity_id']}")
        print(f"Test repo_id: {test_data_isolation['repo_id']}")
        
        # Create and save data
        builder = GraphBuilder(root_path=str(test_code_examples_path / "python"))
        graph = builder.build()
        
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"]
        )
        
        try:
            db_manager.save_graph(
                graph.get_nodes_as_objects(),
                graph.get_relationships_as_objects()
            )
            
            # Verify our data exists
            with db_manager.driver.session() as session:
                result = session.run(
                    """
                    MATCH (n)
                    WHERE (n.entityId = $eid OR n.entity_id = $eid)
                      AND (n.repoId = $rid OR n.repo_id = $rid)
                    RETURN count(n) as count
                    """,
                    eid=test_data_isolation["entity_id"],
                    rid=test_data_isolation["repo_id"]
                )
                # Should have nodes from our graph
                assert result.single()["count"] > 0
        finally:
            db_manager.close()
```

### Key Benefits of Optimized Approach

1. **Performance**: 60-70% faster test execution
2. **Resource Efficiency**: One container per file instead of per test
3. **Data Isolation**: Complete isolation using entity_id/repo_id
4. **Backward Compatible**: Existing tests work with minimal changes
5. **Parallel Safe**: Each test file gets its own container

## Running Tests

### Basic Commands

```bash
# Run all tests
poetry run pytest

# Run with verbose output
poetry run pytest -v

# Run specific test file
poetry run pytest tests/integration/test_graphbuilder_basic.py

# Run specific test function
poetry run pytest tests/integration/test_graphbuilder_basic.py::test_graphbuilder_creates_nodes

# Run tests matching pattern
poetry run pytest -k "graphbuilder"
```

### Parallel Execution

```bash
# Run tests in parallel (3 workers)
poetry run pytest -n 3

# Run with auto-detected workers
poetry run pytest -n auto
```

### Test Categories

```bash
# Run only integration tests
poetry run pytest -m neo4j_integration

# Run only unit tests
poetry run pytest -m "not neo4j_integration"

# Skip slow tests
poetry run pytest -m "not slow"
```

### Coverage Report

```bash
# Run with coverage
poetry run pytest --cov=blarify --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Best Practices

### 1. Test Isolation
- Each test should be independent
- Use fixtures for setup/teardown
- Don't rely on test execution order

### 2. Clear Test Names
```python
# Good
async def test_graphbuilder_creates_function_nodes_for_python():
    """Test that GraphBuilder creates FUNCTION nodes for Python code."""

# Bad
async def test_1():
    """Test."""
```

### 3. Use Async Properly
```python
# For async operations
@pytest.mark.asyncio
async def test_async_operation():
    result = await async_function()
    assert result is not None

# For sync operations
def test_sync_operation():
    result = sync_function()
    assert result is not None
```

### 4. Handle Edge Cases
```python
async def test_empty_directory(neo4j_instance, temp_project_dir):
    """Test GraphBuilder with empty directory."""
    builder = GraphBuilder(root_path=str(temp_project_dir))
    graph = builder.build()
    assert isinstance(graph, Graph)
    # Should handle gracefully
```

### 5. Clean Resource Management
```python
async def test_with_cleanup(test_data_isolation):
    """Test with proper cleanup."""
    db_manager = Neo4jManager(
        uri=test_data_isolation["uri"],
        user="neo4j",
        password=test_data_isolation["password"],
        repo_id=test_data_isolation["repo_id"],
        entity_id=test_data_isolation["entity_id"]
    )
    try:
        # Test operations
        db_manager.save_graph(...)
    finally:
        # Always cleanup connection
        db_manager.close()
        # Data cleanup happens automatically via fixture
```

### 6. Parameterized Testing
```python
@pytest.mark.parametrize("file_ext,expected", [
    (".py", True),
    (".js", True),
    (".txt", False),
])
async def test_file_processing(file_ext, expected):
    """Test file processing for different extensions."""
    result = should_process_file(f"test{file_ext}")
    assert result == expected
```

## Common Test Patterns

### Testing with Temporary Files
```python
async def test_with_temp_files(temp_project_dir):
    """Test with temporary files."""
    # Create test file
    test_file = temp_project_dir / "test.py"
    test_file.write_text('''
def hello():
    return "world"
''')
    
    # Process file
    builder = GraphBuilder(root_path=str(temp_project_dir))
    graph = builder.build()
    
    # Verify
    assert graph is not None
```

### Testing Error Handling
```python
async def test_error_handling():
    """Test that errors are handled properly."""
    with pytest.raises(FileNotFoundError):
        builder = GraphBuilder(root_path="/nonexistent/path")
        builder.build()
```

### Testing with Mock Data
```python
async def test_with_mock(mocker):
    """Test with mocked dependencies."""
    mock_parser = mocker.patch('blarify.parser.Parser')
    mock_parser.return_value.parse.return_value = {"nodes": []}
    
    # Test logic using mock
    result = function_using_parser()
    assert mock_parser.called
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Docker Not Available
**Error**: `Docker daemon is not running`

**Solution**: Ensure Docker Desktop is running before running tests.

#### 2. Port Conflicts
**Error**: `Port already in use`

**Solution**: The framework uses dynamic port allocation. If issues persist:
```bash
# Clean up any stale containers
docker ps -a | grep blarify-neo4j | awk '{print $1}' | xargs docker rm -f
```

#### 3. Slow Tests
**Issue**: Tests taking too long

**Solutions**:
- Use parallel execution: `pytest -n auto`
- Run only relevant tests: `pytest -k "specific_test"`
- Mark slow tests and skip them: `pytest -m "not slow"`

#### 4. Async Test Issues
**Error**: `RuntimeWarning: coroutine was never awaited`

**Solution**: Ensure async tests use `@pytest.mark.asyncio` decorator.

#### 5. Container Cleanup Issues
**Issue**: Containers not cleaning up

**Solution**: The framework handles cleanup automatically, but if needed:
```python
# Manual cleanup in test
async def test_with_manual_cleanup(neo4j_manager):
    try:
        # Test logic
        pass
    finally:
        await neo4j_manager.cleanup_all_tests()
```

## Adding New Test Categories

To add a new category of tests:

1. Create a new directory under `tests/`
2. Add `__init__.py` file
3. Create test files following naming convention
4. Add appropriate marks for categorization
5. Update this documentation

Example structure for performance tests:
```
tests/
└── performance/
    ├── __init__.py
    ├── test_large_repositories.py
    └── test_query_performance.py
```

## Continuous Integration

Tests run automatically on GitHub Actions for:
- Pull requests
- Commits to main branch
- Multiple Python versions (3.10, 3.11, 3.12)

See `.github/workflows/ci.yml` for CI configuration.

## Contributing Tests

When contributing tests:

1. **Follow existing patterns**: Look at similar tests for guidance
2. **Document test purpose**: Use clear docstrings
3. **Test both success and failure**: Include edge cases
4. **Use fixtures**: Don't duplicate setup code
5. **Keep tests focused**: One concept per test
6. **Run locally first**: Ensure tests pass before committing

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
- [Docker SDK for Python](https://docker-py.readthedocs.io/)
- [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/)

## Summary

The Blarify testing framework provides:
- **Optimized Neo4j container management**: Module-scoped containers for 60-70% faster tests
- **Data isolation**: Entity_id/repo_id based isolation between tests
- **Parallel test execution support**: Each test file gets its own container
- **Comprehensive fixtures**: Module-scoped and test-scoped fixtures for all scenarios
- **Backward compatibility**: Existing tests work with minimal changes
- **Easy-to-use assertion helpers**: GraphAssertions with automatic isolation

By following this guide and using the optimized fixtures, you can write tests that are both fast and reliable, with complete data isolation between test runs.