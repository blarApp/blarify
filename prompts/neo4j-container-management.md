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

## Current Implementation Status

✅ **Phase 1: Core Container Manager** - COMPLETED
- Created `neo4j_container_manager/` package with full structure
- Implemented all core modules: container_manager.py, port_manager.py, volume_manager.py, data_manager.py, types.py, fixtures.py

✅ **Phase 2: Container Lifecycle Management** - COMPLETED
- Implemented Neo4jContainerManager with Docker SDK integration
- Direct Docker API usage (removed testcontainers dependency)
- Full async/await support throughout the codebase
- Context manager support for automatic cleanup

✅ **Phase 3: Dynamic Port Management** - COMPLETED
- PortManager implementation with dynamic allocation
- File-based lock system for tracking allocated ports
- Port conflict resolution with retry logic
- Cleanup of stale allocations

✅ **Phase 4: Test Data Management** - COMPLETED
- VolumeManager with automatic cleanup for test volumes
- Ephemeral volumes with unique naming scheme
- Volume lifecycle tied to container lifecycle

✅ **Phase 5: Test Isolation** - COMPLETED
- Unique container naming with test IDs
- Automatic cleanup on test completion
- Support for parallel test execution

✅ **Phase 6: Test Data Setup** - COMPLETED
- DataManager with support for multiple formats (Cypher, JSON, CSV)
- Sample data creation methods
- Test data loading from files
- Data export functionality

✅ **Phase 7: Test Lifecycle Integration** - COMPLETED
- Comprehensive pytest fixtures in fixtures.py
- Session and function scoped fixtures
- Parameterized fixtures for testing different configurations
- Helper fixtures for common operations

⚠️ **Phase 8: Neo4j Connectivity and Data Validation Tests** - PARTIALLY COMPLETED
- Basic integration tests exist in test_integration.py
- Tests verify container lifecycle, data loading, and queries
- **MISSING**: Specific tests validating Blarify's Neo4jManager integration
- **MISSING**: APOC procedure verification tests
- **MISSING**: Tests demonstrating actual Blarify node/edge creation

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

## Implementation Details

### Completed Package Structure

The `neo4j_container_manager/` package has been fully implemented with:

```
neo4j_container_manager/
├── __init__.py               # Main exports ✅
├── container_manager.py      # Core container lifecycle ✅
├── port_manager.py          # Dynamic port allocation ✅
├── volume_manager.py        # Data persistence management ✅
├── data_manager.py          # Import/export functionality ✅
├── types.py                 # Type definitions and dataclasses ✅
├── fixtures.py              # Pytest fixtures ✅
├── tests/
│   ├── __init__.py          # ✅
│   ├── test_integration.py  # Integration tests ✅
│   ├── test_port_manager.py # Port manager unit tests ✅
│   ├── test_types.py        # Type validation tests ✅
│   └── test_neo4j_connectivity.py  # ❌ MISSING - Blarify integration
└── README.md                # ❌ MISSING

### Key Implementation Highlights

1. **Container Lifecycle Management (container_manager.py)**
   - Direct Docker SDK integration (no testcontainers dependency)
   - Automatic port allocation and conflict resolution
   - Health checking with configurable timeouts
   - Support for Neo4j 5.x with proper environment variables
   - APOC plugin support configuration

2. **Type System (types.py)**
   - Comprehensive type definitions with dataclasses
   - Environment enum (TEST, DEVELOPMENT)
   - ContainerStatus tracking
   - Exception hierarchy for better error handling
   - Neo4jContainerInstance with built-in driver support

3. **Port Management (port_manager.py)**
   - Dynamic port allocation starting from base ports
   - File-based locking system for concurrent access
   - Automatic cleanup of stale allocations
   - Support for all Neo4j ports (bolt, http, https, backup)

4. **Volume Management (volume_manager.py)**
   - Automatic volume creation and cleanup
   - Test-specific ephemeral volumes
   - Persistent volumes for development mode
   - Volume naming conventions for easy identification

5. **Data Management (data_manager.py)**
   - Support for multiple data formats (Cypher, JSON, CSV)
   - Sample data generation for testing
   - Data export functionality
   - Parameterized query support

6. **Testing Fixtures (fixtures.py)**
   - Comprehensive pytest fixture collection
   - Session and function scoped fixtures
   - Parameterized fixtures for version testing
   - Helper fixtures for common operations

## Still Needed: Phase 8 - Neo4j Connectivity Tests

The main missing component is comprehensive testing of Blarify's Neo4jManager integration with the container system. This would validate that:

1. **Blarify's Neo4jManager can connect to test containers**
2. **APOC procedures are available and working**
3. **Node and edge creation using Blarify's methods work correctly**
4. **Data isolation between test containers is maintained**

### Proposed test_neo4j_connectivity.py Structure:

```python
# tests/test_neo4j_connectivity.py
import pytest
from blarify.db_managers.neo4j_manager import Neo4jManager
from neo4j_container_manager import Neo4jContainerManager, Neo4jContainerConfig, Environment

@pytest.mark.asyncio
class TestNeo4jConnectivity:
    """Test Blarify's Neo4jManager integration with container system."""

    
    async def test_neo4j_container_connectivity(self, neo4j_instance):
        """Test basic connectivity to Neo4j container."""
        # Initialize Blarify's Neo4jManager with container details
        manager = Neo4jManager(
            repo_id="test-repo",
            entity_id="test-entity",
            uri=neo4j_instance.uri,
            user=neo4j_instance.config.username,
            password=neo4j_instance.config.password
        )
        
        try:
            # Test basic connectivity
            with manager.driver.session() as session:
                result = session.run("RETURN 'Connected' as status")
                record = result.single()
                assert record["status"] == "Connected"
        finally:
            manager.close()
    
    async def test_apoc_procedures_available(self, neo4j_manager):
        """Test that APOC procedures required by Blarify are available."""
        config = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="test-password",
            plugins=["apoc"],  # Ensure APOC is installed
            test_id="apoc-test"
        )
        
        # Use container with APOC
        instance = await neo4j_manager.start_for_test(config)
        
        manager = Neo4jManager(
            repo_id="test-repo",
            entity_id="test-entity",
            uri=instance.uri,
            user=instance.config.username,
            password=instance.config.password
        )
        
        try:
            # Check APOC merge procedures used by Blarify
            with manager.driver.session() as session:
                result = session.run("""
                    CALL apoc.help('merge') 
                    YIELD name 
                    WHERE name IN ['apoc.merge.node', 'apoc.merge.relationship']
                    RETURN collect(name) as procedures
                """)
                record = result.single()
                procedures = record["procedures"]
                assert "apoc.merge.node" in procedures
                assert "apoc.merge.relationship" in procedures
        finally:
            manager.close()
            await instance.stop()
    
    async def test_blarify_node_creation(self, neo4j_instance):
        """Test creating nodes using Blarify's Neo4jManager."""
        manager = Neo4jManager(
            repo_id="test-repo",
            entity_id="test-entity",
            uri=neo4j_instance.uri,
            user=neo4j_instance.config.username,
            password=neo4j_instance.config.password
        )
        
        try:
            # Create test nodes using Blarify's format
            test_nodes = [
                {
                    "type": "Function",
                    "extra_labels": ["Python"],
                    "attributes": {
                        "node_id": "func-1",
                        "name": "test_function",
                        "path": "/test/file.py",
                        "start_line": 1,
                        "end_line": 10,
                        "text": "def test_function(): pass"
                    }
                },
                {
                    "type": "Class",
                    "extra_labels": ["Python"],
                    "attributes": {
                        "node_id": "class-1",
                        "name": "TestClass",
                        "path": "/test/file.py",
                        "start_line": 12,
                        "end_line": 20,
                        "text": "class TestClass: pass"
                    }
                }
            ]
            
            # Create nodes
            manager.create_nodes(test_nodes)
            
            # Verify nodes were created
            with manager.driver.session() as session:
                result = session.run("""
                    MATCH (n:NODE)
                    WHERE n.repoId = $repoId AND n.entityId = $entityId
                    RETURN n.node_id as id, n.name as name, labels(n) as labels
                    ORDER BY n.node_id
                """, repoId="test-repo", entityId="test-entity")
                
                nodes = list(result)
                assert len(nodes) == 2
                
                # Check first node
                assert nodes[0]["id"] == "class-1"  # Ordered by node_id
                assert nodes[0]["name"] == "TestClass"
                assert "Class" in nodes[0]["labels"]
                assert "Python" in nodes[0]["labels"]
                assert "NODE" in nodes[0]["labels"]
                
                # Check second node
                assert nodes[1]["id"] == "func-1"
                assert nodes[1]["name"] == "test_function"
                assert "Function" in nodes[1]["labels"]
                
        finally:
            manager.close()
    
    async def test_blarify_edge_creation(self, neo4j_instance):
        """Test creating edges using Blarify's Neo4jManager."""
        manager = Neo4jManager(
            repo_id="test-repo",
            entity_id="test-entity",
            uri=neo4j_instance.uri,
            user=neo4j_instance.config.username,
            password=neo4j_instance.config.password
        )
        
        try:
            # First create nodes
            nodes = [
                {
                    "type": "Function",
                    "extra_labels": [],
                    "attributes": {
                        "node_id": "caller",
                        "name": "caller_function"
                    }
                },
                {
                    "type": "Function", 
                    "extra_labels": [],
                    "attributes": {
                        "node_id": "callee",
                        "name": "callee_function"
                    }
                }
            ]
            manager.create_nodes(nodes)
            
            # Create edge
            edges = [{
                "sourceId": "caller",
                "targetId": "callee",
                "type": "CALLS",
                "line_number": 5,
                "call_type": "direct"
            }]
            manager.create_edges(edges)
            
            # Verify edge was created
            with manager.driver.session() as session:
                result = session.run("""
                    MATCH (a:NODE {node_id: 'caller'})-[r:CALLS]->(b:NODE {node_id: 'callee'})
                    WHERE a.repoId = $repoId AND a.entityId = $entityId
                    RETURN r.line_number as line, r.call_type as type
                """, repoId="test-repo", entityId="test-entity")
                
                record = result.single()
                assert record["line"] == 5
                assert record["type"] == "direct"
                
        finally:
            manager.close()
    
    async def test_data_isolation_between_containers(self, neo4j_manager):
        """Test that data is isolated between different test containers."""
        # First container
        config1 = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="test-password",
            plugins=["apoc"],
            test_id="isolation-test-1"
        )
        instance1 = await neo4j_manager.start_for_test(config1)
        
        manager1 = Neo4jManager(
            repo_id="test-repo",
            entity_id="test-entity",
            uri=instance1.uri,
            user=instance1.config.username,
            password=instance1.config.password
        )
        
        try:
            # Create data in first container
            test_node = [{
                "type": "TestNode",
                "extra_labels": ["Container1"],
                "attributes": {
                    "node_id": "test-1",
                    "name": "container1_data"
                }
            }]
            manager1.create_nodes(test_node)
            
            # Verify data exists
            with manager1.driver.session() as session:
                result = session.run("""
                    MATCH (n:TestNode)
                    WHERE n.repoId = $repoId AND n.entityId = $entityId
                    RETURN count(n) as count
                """, repoId="test-repo", entityId="test-entity")
                assert result.single()["count"] == 1
        finally:
            manager1.close()
            await instance1.stop()
        
        # Second container
        config2 = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="test-password",
            plugins=["apoc"],
            test_id="isolation-test-2"
        )
        instance2 = await neo4j_manager.start_for_test(config2)
        
        manager2 = Neo4jManager(
            repo_id="test-repo",
            entity_id="test-entity",
            uri=instance2.uri,
            user=instance2.config.username,
            password=instance2.config.password
        )
        
        try:
            # Verify no data from first container
            with manager2.driver.session() as session:
                result = session.run("""
                    MATCH (n:TestNode)
                    WHERE n.repoId = $repoId AND n.entityId = $entityId
                    RETURN count(n) as count
                """, repoId="test-repo", entityId="test-entity")
                assert result.single()["count"] == 0
        finally:
            manager2.close()
            await instance2.stop()
```

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
- **Neo4j connectivity verification tests** - Verify containers are accessible via bolt protocol
- **Node creation/retrieval validation** - Test Blarify's Neo4j manager operations
- **Data isolation verification** - Ensure test containers don't interfere with each other

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
8. **Neo4j Manager Integration** - Seamless integration with Blarify's Neo4jManager class
9. **APOC Support Verification** - All APOC-dependent operations work correctly
10. **Data Operation Validation** - Node/edge creation and querying works as expected

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
   - **Verify APOC plugin availability** - Essential for Blarify's operations

5. **Error Handling**:
   - Graceful degradation if Docker not available
   - Clear error messages for test setup issues
   - Automatic cleanup of failed test containers

6. **Neo4j Manager Integration**:
   - Pass container connection details to Neo4jManager constructor
   - Support dynamic URI/port assignment from container instances
   - Ensure proper connection cleanup after tests
   - Validate APOC procedures are available for node/edge operations

## Error Scenarios and Recovery

1. **Docker not available**: Provide clear error message and skip tests gracefully
2. **Port allocation failures**: Retry with different port ranges for parallel tests
3. **Container startup failures**: Clear error reporting and test failure
4. **Test interruption**: Automatic cleanup of test containers
5. **Test data corruption**: Fresh container for each test run
6. **Network issues**: Retry with timeout, fail fast for tests
7. **APOC plugin missing**: Fail fast with clear error message about required plugins

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

1. **Create GitHub issue** describing the feature ✅
2. **Create feature branch**: `feature/neo4j-container-management` ✅
3. **Implement incrementally** with tests for each phase ✅ (Mostly complete)
4. **Document usage** in README with examples ❌ (Still needed)
5. **Create pull request** with comprehensive description ⏳ (Ready when docs complete)
6. **Update test suites** to use the new container manager ❌ (Still needed)

## Summary of Current State

### ✅ Completed
- Full neo4j_container_manager package implementation
- Core container lifecycle management with Docker SDK
- Dynamic port allocation and management
- Volume management with automatic cleanup
- Comprehensive data management (Cypher, JSON, CSV)
- Pytest fixtures for easy integration
- Basic integration tests
- Password validation (minimum 8 characters)
- Memory format validation
- Plugin validation

### ❌ Still Needed
1. **README.md** for the neo4j_container_manager package
2. **test_neo4j_connectivity.py** - Specific tests for Blarify's Neo4jManager integration
3. **Update Blarify's existing tests** to use the container manager fixtures
4. **Documentation** of best practices and usage examples

### 🔧 Next Steps
1. Create README.md with installation and usage instructions
2. Implement test_neo4j_connectivity.py with the Python test structure above
3. Update existing Blarify tests to use neo4j_instance fixture
4. Update CI/CD configuration to support Docker-based tests:
   - Add Docker service to `.github/workflows/ci.yml`
   - Use pytest markers to separate unit and integration tests
   - Consider running container tests only on one Python version to save CI time
5. Create pull request with comprehensive documentation

### CI/CD Integration Notes

The existing CI workflow (`ci.yml`) runs tests with `poetry run pytest -v` but doesn't currently support Docker. To enable the Neo4j container tests:

```yaml
# Add to ci.yml
services:
  docker:
    image: docker:dind
    options: --privileged

# Or use pytest markers to skip integration tests in CI:
- name: Run tests (excluding integration)
  run: poetry run pytest -v -m "not integration"

# Add a separate job for integration tests with Docker setup
integration-test:
  runs-on: ubuntu-latest
  services:
    docker:
      image: docker:dind
  steps:
    # ... setup steps ...
    - name: Run integration tests
      run: poetry run pytest -v -m "integration"
```

This component provides a reliable foundation for all Neo4j testing in the Blarify ecosystem, making database testing truly seamless for developers. The implementation is production-ready and follows Python best practices with comprehensive type hints and error handling.