# Blarify Integration Testing Guide

This directory contains comprehensive integration tests for Blarify's GraphBuilder functionality, focusing on end-to-end testing of graph construction workflows.

## Overview

The Blarify test suite validates that the GraphBuilder can successfully:
- Parse source code across multiple programming languages
- Create appropriate graph structures (nodes and relationships)
- Persist graphs to Neo4j databases
- Handle edge cases and error conditions gracefully

## Directory Structure

```
tests/
├── README.md                                   # This documentation
├── conftest.py                                # Shared pytest fixtures and configuration
├── integration/                               # Integration test modules
│   ├── __init__.py
│   ├── test_graphbuilder_basic.py            # Core GraphBuilder functionality
│   ├── test_graphbuilder_languages.py        # Language-specific testing
│   ├── test_graphbuilder_edge_cases.py       # Error handling and boundary cases
│   └── prebuilt/
│       └── test_graphbuilder_prebuilt.py     # Prebuilt GraphBuilder interface
├── code_examples/                             # Test source code samples
│   ├── python/                               # Python code examples
│   │   ├── simple_module.py                  # Basic Python constructs
│   │   ├── class_with_inheritance.py         # Inheritance examples
│   │   └── imports_example.py                # Import relationship testing
│   ├── typescript/                           # TypeScript code examples
│   │   ├── simple_class.ts                   # Basic TypeScript class
│   │   ├── interface_inheritance.ts          # Interface definitions
│   │   └── module_exports.ts                 # Module system testing
│   └── ruby/                                 # Ruby code examples
│       ├── simple_class.rb                   # Basic Ruby class
│       ├── module_example.rb                 # Ruby module system
│       └── inheritance_example.rb            # Class inheritance
└── utils/                                     # Testing utilities
    ├── __init__.py
    └── graph_assertions.py                   # Neo4j graph validation helpers
```

## Running Tests

### Prerequisites

1. **Docker**: Required for Neo4j container management
2. **Poetry**: For dependency management
3. **Python 3.10+**: Required Python version

### Installation

```bash
# Install dependencies
poetry install

# Verify Docker is running
docker --version
```

### Running All Integration Tests

```bash
# Run all integration tests
poetry run pytest tests/integration/

# Run with verbose output
poetry run pytest tests/integration/ -v

# Run specific test categories
poetry run pytest tests/integration/ -m "neo4j_integration"
```

### Running Specific Test Files

```bash
# Basic GraphBuilder functionality
poetry run pytest tests/integration/test_graphbuilder_basic.py

# Language-specific tests
poetry run pytest tests/integration/test_graphbuilder_languages.py

# Edge cases and error handling
poetry run pytest tests/integration/test_graphbuilder_edge_cases.py

# Prebuilt interface tests
poetry run pytest tests/integration/prebuilt/test_graphbuilder_prebuilt.py
```

### Running Individual Tests

```bash
# Run a specific test method
poetry run pytest tests/integration/test_graphbuilder_basic.py::TestGraphBuilderBasic::test_graphbuilder_creates_nodes_python_simple

# Run tests with specific parameters
poetry run pytest tests/integration/test_graphbuilder_languages.py -k "python"
```

## Neo4j Container Management

The test suite uses Docker containers to provide isolated Neo4j instances for each test. This ensures:
- No interference between tests
- Clean database state for each test
- Automatic container lifecycle management

### Key Fixtures

- `neo4j_instance`: Provides a fresh Neo4j container for each test
- `neo4j_manager`: Session-scoped container manager
- `graph_assertions`: Helper for validating graph structure with Cypher queries

### Container Configuration

```python
# Tests automatically use these defaults:
config = Neo4jContainerConfig(
    environment=Environment.TEST,
    password="test-password",
    memory="512M",
    startup_timeout=60,
)
```

## Test Categories

### Basic Functionality Tests (`test_graphbuilder_basic.py`)

Tests core GraphBuilder operations:
- Node creation for simple code examples
- Hierarchy-only vs full analysis modes
- File filtering and extensions
- Basic relationship creation
- Empty directory handling

Example test:
```python
async def test_graphbuilder_creates_nodes_python_simple(
    neo4j_instance: Neo4jContainerInstance,
    test_code_examples_path: Path,
    graph_assertions: GraphAssertions,
) -> None:
    """Test that GraphBuilder creates basic nodes for simple Python code."""
    python_examples_path = test_code_examples_path / "python"
    
    builder = GraphBuilder(root_path=str(python_examples_path))
    graph = builder.build()
    
    # Save to Neo4j and validate
    db_manager = Neo4jDbManager(uri=neo4j_instance.uri, user="neo4j", password="test-password")
    await db_manager.save_graph_async(graph)
    
    # Verify expected nodes exist
    await graph_assertions.assert_node_exists("File")
    await graph_assertions.assert_node_exists("Function", {"name": "simple_function"})
    await graph_assertions.assert_node_exists("Class", {"name": "SimpleClass"})
```

### Language-Specific Tests (`test_graphbuilder_languages.py`)

Tests GraphBuilder with different programming languages:
- Python, TypeScript, and Ruby support
- Language-specific node types and relationships
- Mixed-language project handling
- Parameterized tests across languages

Example parameterized test:
```python
@pytest.mark.parametrize("language", ["python", "typescript", "ruby"])
async def test_graphbuilder_language_support(
    neo4j_instance: Neo4jContainerInstance,
    test_code_examples_path: Path,
    graph_assertions: GraphAssertions,
    language: str,
) -> None:
    """Test GraphBuilder with specific programming languages."""
    language_path = test_code_examples_path / language
    
    builder = GraphBuilder(root_path=str(language_path))
    graph = builder.build()
    
    # Language-specific validation logic...
```

### Edge Cases and Error Handling (`test_graphbuilder_edge_cases.py`)

Tests boundary conditions and error scenarios:
- Non-existent file paths
- Empty source files
- Syntax errors in source code
- Large files and deeply nested directories
- Special characters in file names
- Mixed valid/invalid file combinations

### Prebuilt Interface Tests (`test_graphbuilder_prebuilt.py`)

Tests the simplified GraphBuilder API:
- Simple API usage patterns
- Configuration options
- Hierarchy vs full analysis comparison
- Custom GraphEnvironment usage
- Multiple builds from same instance
- Error recovery scenarios

## Adding New Tests

### 1. Create New Code Examples

When adding support for a new language or testing scenario:

```python
# tests/code_examples/new_language/example.ext
# Create representative code examples that demonstrate:
# - Basic language constructs (functions, classes, modules)
# - Language-specific features (inheritance, imports, etc.)
# - Edge cases relevant to your language
```

### 2. Write Integration Tests

```python
# tests/integration/test_new_feature.py
import pytest
from pathlib import Path
from blarify.prebuilt.graph_builder import GraphBuilder
from tests.utils.graph_assertions import GraphAssertions

@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestNewFeature:
    async def test_new_functionality(
        self,
        neo4j_instance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test description."""
        # Test implementation
        pass
```

### 3. Use Graph Assertions

The `GraphAssertions` helper provides methods for validating graph structure:

```python
# Verify nodes exist
await graph_assertions.assert_node_exists("NodeLabel", {"property": "value"})

# Count nodes
await graph_assertions.assert_node_count("NodeLabel", expected_count=5)

# Verify relationships
await graph_assertions.assert_relationship_exists(
    "StartLabel", "RELATIONSHIP_TYPE", "EndLabel"
)

# Get node properties for custom validation
properties = await graph_assertions.get_node_properties("NodeLabel")

# Debug graph structure
summary = await graph_assertions.debug_print_graph_summary()
```

### 4. Follow Testing Conventions

- Use descriptive test names: `test_graphbuilder_feature_description`
- Include proper type annotations for all parameters and return values
- Use async/await for database operations
- Clean up database connections with proper context management
- Add docstrings explaining test purpose and expectations

## Troubleshooting

### Docker Issues

```bash
# Check Docker is running
docker ps

# Clean up orphaned containers
docker container prune

# Check available ports
docker port $(docker ps -q)
```

### Neo4j Connection Issues

```bash
# Check if Neo4j container is running
docker logs <container_id>

# Verify test configuration
poetry run pytest tests/integration/ -v --tb=short
```

### Test Failures

1. **Container Startup Timeouts**: Increase `startup_timeout` in test configuration
2. **Memory Issues**: Adjust Neo4j memory settings or reduce test scope
3. **Parsing Errors**: Check that code examples have valid syntax
4. **Path Issues**: Ensure test code examples exist and are accessible

### Common Issues

**Test hangs during execution**:
- Check Docker daemon is running
- Verify no port conflicts with existing services
- Increase container startup timeout

**Graph validation failures**:
- Use `debug_print_graph_summary()` to inspect actual graph structure
- Check that GraphBuilder processed expected files
- Verify Neo4j query syntax in assertions

**Import errors**:
- Ensure all dependencies are installed: `poetry install`
- Check Python path includes project root
- Verify test files are in correct directories

## Performance Considerations

- Tests use isolated Neo4j containers, which adds startup overhead
- Large code examples may slow test execution
- Consider parameterized tests to reduce duplication
- Use session-scoped fixtures where appropriate

## Contributing Guidelines

### Test Quality Standards

1. **Comprehensive Coverage**: Tests should cover happy path, edge cases, and error conditions
2. **Clear Documentation**: All tests must have descriptive docstrings
3. **Proper Type Annotations**: Follow project typing standards (no `Any` types)
4. **Isolation**: Tests should not depend on each other or external state
5. **Reproducibility**: Tests should produce consistent results across environments

### Code Review Checklist

- [ ] Test names clearly describe functionality being tested
- [ ] All parameters and return values have type annotations
- [ ] Database connections are properly managed and cleaned up
- [ ] Code examples are minimal but representative
- [ ] Error conditions are tested appropriately
- [ ] Documentation is clear and complete

### Adding New Language Support

1. Create representative code examples in `tests/code_examples/new_language/`
2. Add language-specific test cases to `test_graphbuilder_languages.py`
3. Update parameterized tests to include new language
4. Test edge cases specific to the new language
5. Update this documentation with language-specific notes

## References

- [Neo4j Container Manager Documentation](../neo4j_container_manager/README.md)
- [GraphBuilder Implementation](../blarify/prebuilt/graph_builder.py)
- [pytest Documentation](https://docs.pytest.org/)
- [Neo4j Cypher Documentation](https://neo4j.com/docs/cypher-manual/current/)

For additional help or questions about the test suite, please refer to the project documentation or create an issue in the repository.