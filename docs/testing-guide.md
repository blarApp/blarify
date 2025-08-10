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

The Neo4j container manager automatically provisions isolated database instances for each test:

1. **Automatic provisioning**: Containers start when needed
2. **Port allocation**: Dynamic ports prevent conflicts
3. **Data isolation**: Each test gets a clean database
4. **Parallel support**: Tests run concurrently without interference
5. **Automatic cleanup**: Containers stop after tests complete

### Available Neo4j Fixtures

```python
# Basic Neo4j instance
@pytest.fixture
async def neo4j_instance() -> Neo4jContainerInstance:
    """Provides a fresh Neo4j container for each test."""
    
# Neo4j with sample data
@pytest.fixture
async def neo4j_instance_with_sample_data() -> Neo4jContainerInstance:
    """Neo4j instance pre-loaded with sample data."""
    
# Empty Neo4j instance
@pytest.fixture
async def neo4j_instance_empty() -> Neo4jContainerInstance:
    """Guaranteed empty Neo4j database."""
```

### Custom Neo4j Configuration

Override the default configuration for specific test needs:

```python
@pytest.fixture
def neo4j_config(request):
    """Custom Neo4j configuration."""
    import uuid
    
    return Neo4jContainerConfig(
        environment=Environment.TEST,
        password="test-password",
        plugins=["apoc"],  # Add APOC plugin
        memory="1G",       # Set memory limit
        test_id=f"test-{uuid.uuid4().hex[:8]}",  # Unique ID
    )
```

### Using GraphAssertions

The GraphAssertions helper simplifies graph validation:

```python
async def test_with_assertions(graph_assertions):
    """Test using graph assertions."""
    # Check node existence
    await graph_assertions.assert_node_exists("FILE")
    await graph_assertions.assert_node_exists("FUNCTION", {"name": "my_func"})
    
    # Get node properties
    properties = await graph_assertions.get_node_properties("CLASS")
    
    # Check relationships
    await graph_assertions.assert_relationship_exists(
        "FILE", "CONTAINS", "FUNCTION"
    )
    
    # Debug graph content
    summary = await graph_assertions.debug_print_graph_summary()
```

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
async def test_with_cleanup(neo4j_instance):
    """Test with proper cleanup."""
    db_manager = Neo4jManager(uri=neo4j_instance.uri, ...)
    try:
        # Test operations
        db_manager.save_graph(...)
    finally:
        # Always cleanup
        db_manager.close()
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
- Automated Neo4j container management
- Parallel test execution support
- Comprehensive fixtures for common scenarios
- Clear patterns for different test types
- Easy-to-use assertion helpers

By following this guide, you can confidently add tests that maintain code quality and ensure Blarify's reliability.