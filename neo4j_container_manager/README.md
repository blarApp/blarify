# Neo4j Container Management for Testing

A robust Neo4j container management system focused on testing that provides automatic test container lifecycle management, dynamic port allocation, clean test isolation, and transparent operation for developers.

## Features

🚀 **Automatic Container Lifecycle**: Containers start when tests run, stop when done  
🔀 **Dynamic Port Allocation**: Avoids conflicts between parallel test runs  
🔒 **Clean Test Isolation**: Separate containers/data for each test suite  
📊 **Test Data Management**: Quick data import/export for test scenarios  
🎯 **Transparent Operation**: Developers never need to manually manage containers  
🐍 **Full Type Safety**: Complete type annotations with Python 3.10+ support  

## Quick Start

### Installation

Add to your `pyproject.toml`:

```toml
[tool.poetry.dependencies]
testcontainers = {extras = ["neo4j"], version = "^4.9.0"}
docker = "^7.1.0"
filelock = "^3.16.1"

[tool.poetry.group.dev.dependencies]
pytest-asyncio = "^0.25.0"
```

### Basic Usage

```python
import pytest
from neo4j_container_manager import Neo4jTestContainerManager, Neo4jContainerConfig

@pytest.fixture
async def neo4j_instance():
    manager = Neo4jTestContainerManager()
    instance = await manager.start_for_test(
        Neo4jContainerConfig(
            environment='test',
            password='test-password'
        )
    )
    yield instance
    await instance.stop()

async def test_example(neo4j_instance):
    # Container is automatically provisioned and cleaned up
    result = await neo4j_instance.execute_cypher("RETURN 1 as test")
    assert result[0]['test'] == 1
```

### Using Pre-built Fixtures

```python
# Just import and use - no setup required!
from neo4j_container_manager.fixtures import neo4j_instance

async def test_with_clean_database(neo4j_instance):
    # Fresh, empty Neo4j database for each test
    result = await neo4j_instance.execute_cypher("MATCH (n) RETURN count(n) as count")
    assert result[0]["count"] == 0

async def test_with_sample_data(neo4j_instance_with_sample_data):
    # Pre-loaded with sample graph data
    result = await neo4j_instance.execute_cypher("MATCH (n:Person) RETURN count(n) as count")
    assert result[0]["count"] > 0
```

## Configuration Options

### Neo4j Container Configuration

```python
from neo4j_container_manager import Neo4jContainerConfig, Environment

config = Neo4jContainerConfig(
    environment=Environment.TEST,           # 'test' or 'development'
    password='your-password',              # Neo4j password
    username='neo4j',                      # Neo4j username (default: 'neo4j')
    memory='1G',                           # Memory limit (default: '512M')
    neo4j_version='5.25.1',               # Neo4j version (default: '5.25.1')
    plugins=['apoc'],                      # Neo4j plugins to install
    startup_timeout=120,                   # Startup timeout in seconds
    test_id='my-test-suite',              # Unique test identifier
    custom_config={                        # Custom Neo4j configuration
        'dbms.security.auth_enabled': 'true'
    }
)
```

### Available Fixtures

| Fixture | Description |
|---------|-------------|
| `neo4j_manager` | Session-scoped container manager |
| `neo4j_instance` | Function-scoped clean Neo4j instance |
| `neo4j_instance_with_sample_data` | Instance pre-loaded with sample data |
| `neo4j_instance_empty` | Guaranteed empty instance |
| `neo4j_test_data_path` | Temporary directory for test data files |
| `sample_cypher_file` | Sample .cypher file for testing |
| `sample_json_file` | Sample .json file for testing |
| `neo4j_query_helper` | Utility functions for common queries |

## Test Data Management

### Loading Data from Files

```python
# Cypher files
await neo4j_instance.load_test_data('./test-data/sample.cypher')

# JSON files  
await neo4j_instance.load_test_data('./test-data/nodes.json')

# CSV files
await neo4j_instance.load_test_data('./test-data/people.csv')
```

### Programmatic Data Creation

```python
from neo4j_container_manager.data_manager import DataManager

data_manager = DataManager(neo4j_instance)

# Create sample datasets
await data_manager.create_sample_data('basic')    # Basic Person/Company graph
await data_manager.create_sample_data('graph')    # More complex relationships

# Clear all data
await data_manager.clear_all_data()
```

### Custom Data Specs

```python
from neo4j_container_manager.types import TestDataSpec, DataFormat

spec = TestDataSpec(
    file_path=Path('custom_data.cypher'),
    format=DataFormat.CYPHER,
    clear_before_load=True,
    parameters={'year': 2024, 'company': 'TechCorp'}
)

data_manager = DataManager(neo4j_instance)
result = await data_manager.load_data_from_spec(spec)
```

## Advanced Usage

### Parallel Test Execution

Containers automatically allocate unique ports to avoid conflicts:

```python
# These tests can run in parallel safely
@pytest.mark.parametrize("test_data", ["dataset1", "dataset2", "dataset3"])
async def test_parallel_execution(neo4j_instance, test_data):
    # Each test gets its own container with unique ports
    await neo4j_instance.execute_cypher(f"CREATE (n:Test {{data: '{test_data}'}})")
    # Tests are completely isolated
```

### Custom Container Configuration

```python
@pytest.fixture
async def high_memory_neo4j():
    manager = Neo4jTestContainerManager()
    config = Neo4jContainerConfig(
        environment=Environment.TEST,
        password='test-password',
        memory='2G',                    # Higher memory for performance tests
        plugins=['apoc', 'gds'],       # Additional plugins
        startup_timeout=180            # Longer timeout for plugin installation
    )
    
    instance = await manager.start_for_test(config)
    yield instance
    await instance.stop()
```

### Health Checking and Monitoring

```python
# Check container health
health = await neo4j_instance.health_check()
print(f"Status: {health['status']}, Response time: {health['response_time_ms']}ms")

# Get container statistics  
manager = Neo4jTestContainerManager()
stats = await manager.health_check_all()
for container_id, health in stats.items():
    print(f"Container {container_id}: {health['status']}")
```

### Performance Testing Utilities

```python
async def test_query_performance(neo4j_instance, neo4j_performance_monitor):
    # Time query execution
    result, execution_time = await neo4j_performance_monitor.time_query(
        neo4j_instance,
        "MATCH (n) RETURN count(n)"
    )
    
    assert execution_time < 0.1  # Should complete in under 100ms
    
    # Get performance statistics
    stats = neo4j_performance_monitor.get_query_stats()
    print(f"Average query time: {stats['average_time']:.3f}s")
```

### Testing Different Neo4j Versions

```python
@pytest.mark.parametrize("neo4j_version", ["5.23.0", "5.24.0", "5.25.1"])
async def test_across_versions(neo4j_manager, neo4j_version):
    config = Neo4jContainerConfig(
        environment=Environment.TEST,
        password='test-password',
        neo4j_version=neo4j_version
    )
    
    instance = await neo4j_manager.start_for_test(config)
    try:
        # Test compatibility across versions
        result = await instance.execute_cypher("RETURN 1 as test")
        assert result[0]['test'] == 1
    finally:
        await instance.stop()
```

## Data Formats

### Cypher Files

```cypher
// sample.cypher
CREATE (alice:Person {name: 'Alice', age: 30});
CREATE (bob:Person {name: 'Bob', age: 25});
CREATE (company:Company {name: 'TechCorp'});

MATCH (alice:Person {name: 'Alice'}), (company:Company {name: 'TechCorp'})
CREATE (alice)-[:WORKS_FOR]->(company);
```

### JSON Files

```json
{
  "nodes": [
    {"labels": ["Person"], "name": "Alice", "age": 30},
    {"labels": ["Person"], "name": "Bob", "age": 25},
    {"labels": ["Company"], "name": "TechCorp"}
  ],
  "relationships": [
    {
      "start_node": {"labels": ["Person"], "name": "Alice"},
      "end_node": {"labels": ["Company"], "name": "TechCorp"},
      "type": "WORKS_FOR"
    }
  ]
}
```

### CSV Files

```csv
name,age,labels,department
Alice,30,Person,Engineering
Bob,25,Person,Marketing
Charlie,35,Person,Engineering
```

## Error Handling

The system provides comprehensive error handling with specific exception types:

```python
from neo4j_container_manager.types import (
    ContainerStartupError,
    PortAllocationError,
    DataLoadError,
    VolumeManagementError
)

try:
    instance = await manager.start_for_test(config)
except ContainerStartupError as e:
    # Handle container startup failures
    print(f"Failed to start container: {e}")
except PortAllocationError as e:
    # Handle port allocation conflicts
    print(f"Port allocation failed: {e}")
```

## Development Mode

For local development (containers persist between runs):

```python
import asyncio
from neo4j_container_manager import Neo4jTestContainerManager, Neo4jContainerConfig

async def main():
    manager = Neo4jTestContainerManager()
    dev_instance = await manager.start_for_test(
        Neo4jContainerConfig(
            environment='development',  # Persistent container
            password='dev-password',
            memory='2G'
        )
    )
    
    print(f"Neo4j available at: {dev_instance.uri}")
    print(f"Neo4j Browser: {dev_instance.http_uri}")
    
    # Container will persist until manually stopped
    # await dev_instance.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

## Configuration for CI/CD

### GitHub Actions

```yaml
name: Tests with Neo4j

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      docker:
        options: --privileged
        
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        
    - name: Install dependencies
      run: |
        pip install poetry
        poetry install
        
    - name: Run tests with Neo4j containers
      run: |
        poetry run pytest tests/ -v
        # Neo4j containers are automatically managed
```

### Docker Compose (Optional)

```yaml
# docker-compose.test.yml
version: '3.8'
services:
  test-runner:
    build: .
    environment:
      - NEO4J_CONTAINER_MODE=test
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: pytest tests/ -v
```

## Troubleshooting

### Common Issues

#### Docker Not Available
```
ImportError: Docker and testcontainers dependencies are required
```
**Solution**: Ensure Docker is installed and running, and install required dependencies.

#### Port Conflicts
```
PortAllocationError: Failed to allocate ports for container
```
**Solution**: The system automatically handles port conflicts. If this persists, check for processes binding to port ranges 7474-8474.

#### Container Startup Timeout
```
ContainerStartupError: Neo4j container did not become ready within 60 seconds
```
**Solution**: Increase `startup_timeout` in configuration, especially when using plugins.

#### Memory Issues
```
Container failed to start due to memory constraints
```
**Solution**: Reduce `memory` setting or ensure Docker has sufficient memory allocated.

### Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Detailed container lifecycle logging will be displayed
```

Check container logs:

```python
manager = Neo4jTestContainerManager()
logs = await manager.get_container_logs(container_id)
print(logs)
```

## Performance Considerations

### Resource Usage

- Default memory: 512M per container
- Startup time: ~10-30 seconds depending on plugins
- Port range: 7474-8474 (auto-allocated)
- Volume cleanup: Automatic for test containers

### Optimization Tips

1. **Reuse fixtures at appropriate scope**: Use session-scoped fixtures for expensive setup
2. **Minimize container restarts**: Group related tests together
3. **Use appropriate memory limits**: Don't over-allocate memory for simple tests
4. **Clean up data instead of containers**: Use `clear_data()` between tests when possible

### Benchmarks

Typical performance on modern development machine:

- Container startup: 15-20 seconds
- Container shutdown: 2-3 seconds  
- Query execution: <1ms for simple queries
- Data loading: ~1000 nodes/second via Cypher
- Parallel containers: 5-10 simultaneous without issues

## Contributing

This Neo4j container management system is part of the Blarify project. When contributing:

1. **Follow type safety**: All code must be fully typed with no `Any` types except for external dependencies
2. **Write comprehensive tests**: Test coverage should be >90% 
3. **Update documentation**: Keep this README current with new features
4. **Test across Python versions**: Ensure compatibility with Python 3.10+
5. **Test with Docker variants**: Test with Docker Desktop, Podman, etc.

## Architecture Overview

```
neo4j_container_manager/
├── __init__.py                # Main exports and version
├── types.py                   # Type definitions and dataclasses
├── container_manager.py       # Core container lifecycle management
├── port_manager.py           # Dynamic port allocation with file locking
├── volume_manager.py         # Docker volume management and cleanup
├── data_manager.py           # Test data import/export (Cypher/JSON/CSV)
├── fixtures.py               # Pytest fixtures and helpers
└── tests/                    # Comprehensive test suite
    ├── test_types.py
    ├── test_port_manager.py
    ├── test_integration.py
    └── ...
```

## License

This project follows the same license as the parent Blarify project (MIT License).