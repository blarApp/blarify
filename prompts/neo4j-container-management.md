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

  beforeAll(async () => {
    containerManager = new Neo4jTestContainerManager();
  });

  beforeEach(async () => {
    // Start a fresh Neo4j container for each test
    containerInstance = await containerManager.startForTest({
      environment: 'test',
      password: 'test-password',
      testId: expect.getState().currentTestName,
      plugins: ['apoc'] // Required for Blarify's APOC-based operations
    });

    // Initialize Neo4j manager with container connection details
    const uri = containerInstance.uri; // bolt://localhost:XXXXX
    neo4jManager = new Neo4jManager(
      'test-repo-id',
      'test-entity-id',
      50, // max_connections
      uri,
      'neo4j',
      'test-password'
    );
  });

  afterEach(async () => {
    if (neo4jManager) {
      neo4jManager.close();
    }
    if (containerInstance) {
      await containerInstance.stop();
    }
  });

  afterAll(async () => {
    await containerManager.cleanupAllTests();
  });

  describe('Container Health Verification', () => {
    test('should verify Neo4j container is up and running', async () => {
      // Test 1: Verify container is running
      expect(await containerInstance.isRunning()).toBe(true);
      
      // Test 2: Verify Neo4j service is accessible via bolt protocol
      const healthCheckQuery = 'RETURN "Neo4j is ready" as status';
      const result = await neo4jManager.query(healthCheckQuery);
      
      expect(result).toHaveLength(1);
      expect(result[0].status).toBe('Neo4j is ready');
    });

    test('should verify APOC plugin is loaded and accessible', async () => {
      // Verify APOC procedures are available (required for Blarify's node/edge creation)
      const apocCheckQuery = 'CALL apoc.help("apoc") YIELD name RETURN count(name) as procedureCount';
      const result = await neo4jManager.query(apocCheckQuery);
      
      expect(result).toHaveLength(1);
      expect(result[0].procedureCount).toBeGreaterThan(0);
    });
  });

  describe('Node Creation and Retrieval Tests', () => {
    test('should create test nodes using Neo4j manager', async () => {
      // Test 2: Create test nodes using the manager's create_nodes method
      const testNodes = [
        {
          type: 'Function',
          extra_labels: ['TestFunction'],
          attributes: {
            node_id: 'test-func-1',
            name: 'testFunction',
            path: '/test/file.py',
            start_line: 1,
            end_line: 10,
            text: 'def testFunction(): pass'
          }
        },
        {
          type: 'Class',
          extra_labels: ['TestClass'],
          attributes: {
            node_id: 'test-class-1',
            name: 'TestClass',
            path: '/test/class.py',
            start_line: 1,
            end_line: 20,
            text: 'class TestClass: pass'
          }
        }
      ];

      // Create nodes using the manager - this will use APOC procedures internally
      await neo4jManager.create_nodes(testNodes);

      // Verify nodes were created by querying for them
      const verifyQuery = `
        MATCH (n:NODE {repoId: $repoId, entityId: $entityId})
        WHERE n.node_id IN ['test-func-1', 'test-class-1']
        RETURN n.node_id as nodeId, n.name as name, n.type as type, labels(n) as labels
        ORDER BY n.node_id
      `;

      const result = await neo4jManager.query(verifyQuery, {
        repoId: 'test-repo-id',
        entityId: 'test-entity-id'
      });

      expect(result).toHaveLength(2);
      
      // Verify function node
      const functionNode = result.find(n => n.nodeId === 'test-func-1');
      expect(functionNode).toBeDefined();
      expect(functionNode.name).toBe('testFunction');
      expect(functionNode.labels).toContain('Function');
      expect(functionNode.labels).toContain('TestFunction');
      expect(functionNode.labels).toContain('NODE');

      // Verify class node
      const classNode = result.find(n => n.nodeId === 'test-class-1');
      expect(classNode).toBeDefined();
      expect(classNode.name).toBe('TestClass');
      expect(classNode.labels).toContain('Class');
      expect(classNode.labels).toContain('TestClass');
      expect(classNode.labels).toContain('NODE');
    });

    test('should retrieve created nodes with specific query parameters', async () => {
      // Test 3: Retrieve the created nodes using different query patterns
      
      // First create a test node
      const testNode = [{
        type: 'Module',
        extra_labels: ['PythonModule'],
        attributes: {
          node_id: 'test-module-1',
          name: 'test_module',
          path: '/test/module.py',
          start_line: 1,
          end_line: 50,
          text: 'import os\n\ndef main(): pass'
        }
      }];

      await neo4jManager.create_nodes(testNode);

      // Test querying by node properties
      const nodeByIdQuery = `
        MATCH (n:NODE {node_id: $nodeId, repoId: $repoId, entityId: $entityId})
        RETURN n.node_id as nodeId, n.name as name, n.path as path, n.text as text
      `;

      const nodeResult = await neo4jManager.query(nodeByIdQuery, {
        nodeId: 'test-module-1',
        repoId: 'test-repo-id',
        entityId: 'test-entity-id'
      });

      expect(nodeResult).toHaveLength(1);
      expect(nodeResult[0].nodeId).toBe('test-module-1');
      expect(nodeResult[0].name).toBe('test_module');
      expect(nodeResult[0].path).toBe('/test/module.py');
      expect(nodeResult[0].text).toContain('import os');

      // Test querying by type labels
      const nodesByTypeQuery = `
        MATCH (n:NODE:Module {repoId: $repoId, entityId: $entityId})
        RETURN count(n) as moduleCount
      `;

      const typeResult = await neo4jManager.query(nodesByTypeQuery, {
        repoId: 'test-repo-id',
        entityId: 'test-entity-id'
      });

      expect(typeResult).toHaveLength(1);
      expect(typeResult[0].moduleCount).toBeGreaterThan(0);
    });

    test('should handle edge creation and relationship queries', async () => {
      // Create nodes for edge testing
      const sourceNode = [{
        type: 'Function',
        extra_labels: ['Caller'],
        attributes: {
          node_id: 'caller-func',
          name: 'callerFunction',
          path: '/test/caller.py',
          start_line: 1,
          end_line: 5
        }
      }];

      const targetNode = [{
        type: 'Function', 
        extra_labels: ['Callee'],
        attributes: {
          node_id: 'callee-func',
          name: 'calleeFunction',
          path: '/test/callee.py',
          start_line: 10,
          end_line: 15
        }
      }];

      await neo4jManager.create_nodes([...sourceNode, ...targetNode]);

      // Create edge between the nodes
      const testEdges = [{
        sourceId: 'caller-func',
        targetId: 'callee-func',
        type: 'CALLS',
        line_number: 3,
        call_type: 'direct'
      }];

      await neo4jManager.create_edges(testEdges);

      // Query for the created relationship
      const relationshipQuery = `
        MATCH (caller:NODE {node_id: 'caller-func', repoId: $repoId, entityId: $entityId})-[r:CALLS]->(callee:NODE {node_id: 'callee-func', repoId: $repoId, entityId: $entityId})
        RETURN caller.name as callerName, callee.name as calleeName, r.line_number as lineNumber, r.call_type as callType
      `;

      const relationshipResult = await neo4jManager.query(relationshipQuery, {
        repoId: 'test-repo-id',
        entityId: 'test-entity-id'
      });

      expect(relationshipResult).toHaveLength(1);
      expect(relationshipResult[0].callerName).toBe('callerFunction');
      expect(relationshipResult[0].calleeName).toBe('calleeFunction');
      expect(relationshipResult[0].lineNumber).toBe(3);
      expect(relationshipResult[0].callType).toBe('direct');
    });
  });

  describe('Data Isolation and Cleanup Tests', () => {
    test('should ensure test data isolation between containers', async () => {
      // Create test data in current container
      const testNodes = [{
        type: 'IsolationTest',
        extra_labels: ['Container1'],
        attributes: {
          node_id: 'isolation-test-1',
          name: 'container1Node'
        }
      }];

      await neo4jManager.create_nodes(testNodes);

      // Verify data exists in current container
      let result = await neo4jManager.query(
        'MATCH (n:IsolationTest {repoId: $repoId, entityId: $entityId}) RETURN count(n) as nodeCount',
        { repoId: 'test-repo-id', entityId: 'test-entity-id' }
      );
      expect(result[0].nodeCount).toBe(1);

      // Stop current container and start new one
      neo4jManager.close();
      await containerInstance.stop();

      containerInstance = await containerManager.startForTest({
        environment: 'test',
        password: 'test-password',
        testId: 'isolation-test-2',
        plugins: ['apoc']
      });

      neo4jManager = new Neo4jManager(
        'test-repo-id',
        'test-entity-id',
        50,
        containerInstance.uri,
        'neo4j',
        'test-password'
      );

      // Verify data does not exist in new container (isolation)
      result = await neo4jManager.query(
        'MATCH (n:IsolationTest {repoId: $repoId, entityId: $entityId}) RETURN count(n) as nodeCount',
        { repoId: 'test-repo-id', entityId: 'test-entity-id' }
      );
      expect(result[0].nodeCount).toBe(0);
    });

    test('should support data cleanup operations', async () => {
      // Create test data
      const testNodes = [{
        type: 'CleanupTest',
        extra_labels: ['ToBeDeleted'],
        attributes: {
          node_id: 'cleanup-test-1',
          name: 'nodeToDelete',
          path: '/test/cleanup.py'
        }
      }];

      await neo4jManager.create_nodes(testNodes);

      // Verify data exists
      let result = await neo4jManager.query(
        'MATCH (n:CleanupTest {repoId: $repoId, entityId: $entityId}) RETURN count(n) as nodeCount',
        { repoId: 'test-repo-id', entityId: 'test-entity-id' }
      );
      expect(result[0].nodeCount).toBe(1);

      // Use manager's path-based deletion method
      await neo4jManager.detatch_delete_nodes_with_path('/test/cleanup.py');

      // Verify data is deleted
      result = await neo4jManager.query(
        'MATCH (n:CleanupTest {repoId: $repoId, entityId: $entityId}) RETURN count(n) as nodeCount',
        { repoId: 'test-repo-id', entityId: 'test-entity-id' }
      );
      expect(result[0].nodeCount).toBe(0);
    });
  });

  describe('Error Handling and Recovery', () => {
    test('should handle connection errors gracefully', async () => {
      // Stop the container to simulate connection failure
      await containerInstance.stop();

      // Attempt to query - should throw an appropriate error
      await expect(
        neo4jManager.query('RETURN 1 as test')
      ).rejects.toThrow();
    });

    test('should handle malformed queries appropriately', async () => {
      // Test malformed Cypher query
      await expect(
        neo4jManager.query('INVALID CYPHER SYNTAX')
      ).rejects.toThrow();
    });
  });
});
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

1. **Create GitHub issue** describing the feature
2. **Create feature branch**: `feature/neo4j-container-management`
3. **Implement incrementally** with tests for each phase
4. **Document usage** in README with examples
5. **Create pull request** with comprehensive description
6. **Update test suites** to use the new container manager

This component will provide a reliable foundation for all Neo4j testing in the Blarify ecosystem, making database testing truly seamless for developers.