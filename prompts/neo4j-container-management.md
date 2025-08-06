# Neo4j Container Management for Blarify

## Problem Statement

Currently, testing Blarify requires manual Neo4j container management, including:
- Starting/stopping containers for tests
- Managing port conflicts between test runs
- Ensuring test isolation and data cleanup
- Handling different test environments

This creates friction for development and testing workflows. Neo4j for testing should be an implementation detail that "just works" transparently.

## Feature Overview

Create a robust Neo4j container management system focused on testing that:
1. **Automatically manages test container lifecycle** - starts when tests run, stops when done
2. **Uses dynamic port allocation** - avoids conflicts between parallel test runs
3. **Provides clean test isolation** - separate containers/data for each test suite
4. **Supports test data setup/teardown** - quick data import/export for test scenarios
5. **Works transparently** - developers never need to manually manage containers

## Technical Requirements

### Core Dependencies
- testcontainers-python for container management
- Docker SDK for Python (docker-py) for advanced operations
- Python socket library for dynamic port allocation during tests
- Neo4j 5.x Community Edition image
- File system operations for test data setup/teardown
- pytest fixtures for test lifecycle integration

### Architecture Requirements
- Single responsibility: Neo4j test container management only
- Reusable across different test suites and components
- Test-environment focused (primarily test, with dev support)
- Automatic cleanup after test completion
- Fast startup/teardown for efficient testing

## Implementation Plan

### Phase 1: Core Container Manager
Create `neo4j_container_manager/` package with:

```
neo4j_container_manager/
├── __init__.py               # Main exports
├── container_manager.py      # Core container lifecycle
├── port_manager.py          # Dynamic port allocation
├── volume_manager.py        # Data persistence management
├── data_manager.py          # Import/export functionality
├── types.py                 # Type definitions and dataclasses
├── tests/
│   ├── test_container_manager.py
│   ├── test_port_manager.py
│   └── test_integration.py
├── pyproject.toml
└── README.md
```

### Phase 2: Container Lifecycle Management

```python
from dataclasses import dataclass
from typing import Optional, List, Literal
from abc import ABC, abstractmethod

@dataclass
class Neo4jContainerConfig:
    environment: Literal['test', 'development']
    password: str
    data_path: Optional[str] = None  # Custom test data directory
    username: str = 'neo4j'
    plugins: Optional[List[str]] = None  # e.g., ['apoc'] for test scenarios
    memory: Optional[str] = None  # e.g., '1G' - lighter for tests
    test_id: Optional[str] = None  # Unique identifier for test isolation

@dataclass
class Neo4jContainerInstance:
    uri: str  # bolt://localhost:XXXXX
    http_uri: str  # http://localhost:XXXXX
    container_id: str
    volume: str  # Volume name for test data
    
    async def stop(self) -> None:
        """Stop the container"""
        pass
    
    async def is_running(self) -> bool:
        """Check if container is running"""
        pass
    
    async def load_test_data(self, path: str) -> None:
        """Load test data from file"""
        pass
    
    async def clear_data(self) -> None:
        """Clear all data in the database"""
        pass

class Neo4jTestContainerManager:
    async def start_for_test(self, config: Neo4jContainerConfig) -> Neo4jContainerInstance:
        """Start a Neo4j container for testing"""
        pass
    
    async def stop_test(self, container_id: str) -> None:
        """Stop a specific test container"""
        pass
    
    async def cleanup_all_tests(self) -> None:
        """Clean up all test containers"""
        pass
    
    async def list_test_containers(self) -> List[Neo4jContainerInstance]:
        """List all active test containers"""
        pass
```

### Phase 3: Dynamic Port Management
- Use Python's socket library to find available ports (7474+n, 7687+n)
- Track allocated ports in a lock file using filelock
- Release ports on container stop
- Handle port conflicts gracefully with retry logic

### Phase 4: Test Data Management
- Create ephemeral volumes for test data (auto-cleanup)
- Volume naming: `blarify-neo4j-test-{testId}-{timestamp}`
- Quick data loading for test scenarios
- Automatic cleanup after test completion

### Phase 5: Test Isolation
- Each test gets unique container: `blarify-neo4j-test-{uuid}`
- Test volumes auto-cleanup after test run
- Parallel test support with unique containers
- Mock mode for unit tests (no real Docker)

### Phase 6: Test Data Setup
- Load test data from JSON/Cypher files
- Include test fixtures and sample data
- Support for different test scenarios
- Fast reset between test cases

### Phase 7: Test Lifecycle Integration
- Register test cleanup handlers with pytest fixtures
- Integration with pytest-asyncio for async tests
- Handle test interruption and cleanup via pytest hooks
- Health checks optimized for test speed

## Testing Strategy

### Unit Tests
- Mock Docker API for container operations
- Test port allocation logic
- Test volume naming and management
- Test configuration validation

### Integration Tests
- Real Docker container creation/destruction for tests
- Test data persistence during test runs
- Port conflict resolution between parallel tests
- Test data loading and cleanup workflows

### End-to-End Tests
- Full test suite integration
- Multi-test scenario isolation
- Test crash recovery and cleanup

## Configuration Examples

### Test Usage with pytest
```python
import pytest
from neo4j_container_manager import Neo4jTestContainerManager, Neo4jContainerConfig

@pytest.fixture(scope="session")
async def neo4j_manager():
    """Session-scoped fixture for container manager"""
    manager = Neo4jTestContainerManager()
    yield manager
    await manager.cleanup_all_tests()

@pytest.fixture
async def neo4j_instance(neo4j_manager, request):
    """Function-scoped fixture for test container"""
    instance = await neo4j_manager.start_for_test(
        Neo4jContainerConfig(
            environment='test',
            password='test-password',
            test_id=request.node.name
        )
    )
    
    # Load test data
    await instance.load_test_data('./test-fixtures/sample-graph.cypher')
    
    yield instance
    
    await instance.stop()

# Usage in tests
async def test_example(neo4j_instance):
    # neo4j_instance is automatically provisioned and cleaned up
    assert await neo4j_instance.is_running()
```

### Development Usage
```python
# For local development
import asyncio
from neo4j_container_manager import Neo4jTestContainerManager, Neo4jContainerConfig

async def main():
    manager = Neo4jTestContainerManager()
    dev_instance = await manager.start_for_test(
        Neo4jContainerConfig(
            environment='development',
            password='dev-password',
            memory='2G'
        )
    )
    
    print(f"Neo4j available at: {dev_instance.uri}")
    
    # Use for development work
    # Manual cleanup when done
    await dev_instance.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

## Success Criteria

1. **Zero test configuration** - Neo4j "just works" for all tests
2. **No port conflicts** - Parallel tests run without interference
3. **Clean test isolation** - Tests never affect each other
4. **Fast test startup** - Minimal overhead for test execution
5. **Automatic cleanup** - No leftover containers or data
6. **Easy test data setup** - Simple fixtures and data loading
7. **Reliable test runs** - Handles test interruptions gracefully

## Implementation Notes

1. **Container Naming Convention**:
   - Development: `blarify-neo4j-dev`
   - Test: `blarify-neo4j-test-{uuid}`

2. **Volume Naming Convention**:
   - Development: `blarify-neo4j-dev-data`
   - Test: `blarify-neo4j-test-{uuid}-data` (auto-cleanup)

3. **Port Allocation Strategy**:
   - Start from base ports (7474, 7687)
   - Increment by 10 for each test instance
   - Track in temp file during test runs

4. **Health Check Implementation**:
   - Wait for Neo4j to be ready for tests
   - Verify bolt and HTTP endpoints quickly
   - Optimized retry timing for test speed

5. **Error Handling**:
   - Graceful degradation if Docker not available
   - Clear error messages for test setup issues
   - Automatic cleanup of failed test containers

## Error Scenarios and Recovery

1. **Docker not available**: Provide clear error message and skip tests gracefully
2. **Port allocation failures**: Retry with different port ranges for parallel tests
3. **Container startup failures**: Clear error reporting and test failure
4. **Test interruption**: Automatic cleanup of test containers
5. **Test data corruption**: Fresh container for each test run
6. **Network issues**: Retry with timeout, fail fast for tests

## Monitoring and Logging

1. **Test-focused logging** with levels (debug, info, warn, error)
2. **Test performance metrics**: Container startup time, test data loading speed
3. **Resource monitoring**: Memory usage during tests
4. **Test status tracking**: Which tests are using which containers
5. **Debug mode**: Verbose logging for test troubleshooting

## Version Compatibility

1. **Neo4j versions**: Support 5.x, with version detection
2. **Docker API**: Compatible with Docker 20.x+
3. **Python**: Require Python 3.10+ (matching project requirements)
4. **Platform support**: Windows, macOS, Linux
5. **Architecture**: amd64 and arm64 (Apple Silicon)

## Migration Strategy

For existing test setups with manual Neo4j management:
1. **Detection**: Check for existing test Neo4j containers
2. **Gradual adoption**: Start with new tests, migrate existing ones
3. **Parallel setup**: Keep old test setup during transition
4. **Validation**: Ensure test results remain consistent
5. **Full migration**: Remove manual setup once validated

## Development Approach

1. **Create GitHub issue** describing the feature
2. **Create feature branch**: `feature/neo4j-container-management`
3. **Implement incrementally** with tests for each phase
4. **Document usage** in README with examples
5. **Create pull request** with comprehensive description
6. **Update test suites** to use the new container manager

This component will provide a reliable foundation for all Neo4j testing in the Blarify ecosystem, making database testing truly seamless for developers.