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
- Docker/Dockerode for container management
- Port-finder for dynamic port allocation during tests
- Neo4j 5.x Community Edition image
- File system operations for test data setup/teardown
- Test lifecycle hooks for cleanup

### Architecture Requirements
- Single responsibility: Neo4j test container management only
- Reusable across different test suites and components
- Test-environment focused (primarily test, with dev support)
- Automatic cleanup after test completion
- Fast startup/teardown for efficient testing

## Implementation Plan

### Phase 1: Core Container Manager
Create `neo4j-container-manager/` package with:

```
neo4j-container-manager/
├── src/
│   ├── index.ts              # Main exports
│   ├── container-manager.ts   # Core container lifecycle
│   ├── port-manager.ts       # Dynamic port allocation
│   ├── volume-manager.ts     # Data persistence management
│   ├── data-manager.ts       # Import/export functionality
│   └── types.ts              # TypeScript interfaces
├── tests/
│   ├── container-manager.test.ts
│   ├── port-manager.test.ts
│   └── integration.test.ts
├── package.json
├── tsconfig.json
└── README.md
```

### Phase 2: Container Lifecycle Management

```typescript
interface Neo4jContainerConfig {
  environment: 'test' | 'development';
  dataPath?: string;  // Custom test data directory
  password: string;
  username?: string;  // Default: neo4j
  plugins?: string[]; // e.g., ['apoc'] for test scenarios
  memory?: string;    // e.g., '1G' - lighter for tests
  testId?: string;    // Unique identifier for test isolation
}

interface Neo4jContainerInstance {
  uri: string;        // bolt://localhost:XXXXX
  httpUri: string;    // http://localhost:XXXXX
  containerId: string;
  volume: string;     // Volume name for test data
  stop(): Promise<void>;
  isRunning(): Promise<boolean>;
  loadTestData(path: string): Promise<void>;
  clearData(): Promise<void>;
}

class Neo4jTestContainerManager {
  async startForTest(config: Neo4jContainerConfig): Promise<Neo4jContainerInstance>;
  async stopTest(containerId: string): Promise<void>;
  async cleanupAllTests(): Promise<void>;
  async listTestContainers(): Promise<Neo4jContainerInstance[]>;
}
```

### Phase 3: Dynamic Port Management
- Use port-finder to get available ports (7474+n, 7687+n)
- Track allocated ports in a lock file
- Release ports on container stop
- Handle port conflicts gracefully

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
- Register test cleanup handlers
- Integration with test frameworks (Jest, Mocha, etc.)
- Handle test interruption and cleanup
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

### Test Usage with Jest
```typescript
let testInstance: Neo4jContainerInstance;
let testManager: Neo4jTestContainerManager;

beforeAll(async () => {
  testManager = new Neo4jTestContainerManager();
});

beforeEach(async () => {
  testInstance = await testManager.startForTest({
    environment: 'test',
    password: 'test-password',
    testId: expect.getState().currentTestName
  });
  
  // Load test data
  await testInstance.loadTestData('./test-fixtures/sample-graph.cypher');
});

afterEach(async () => {
  await testInstance.stop();
});

afterAll(async () => {
  await testManager.cleanupAllTests();
});
```

### Development Usage
```typescript
// For local development
const testManager = new Neo4jTestContainerManager();
const devInstance = await testManager.startForTest({
  environment: 'development',
  password: 'dev-password',
  memory: '2G'
});

// Use for development work
// Manual cleanup when done
await devInstance.stop();
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
3. **Node.js**: Require Node 16+ for modern features
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