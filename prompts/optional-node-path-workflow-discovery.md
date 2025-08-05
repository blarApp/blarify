# Optional Node Path Parameter to Workflow Discovery

## Title and Overview

**Feature**: Optional Node Path Parameter to Workflow Discovery  
**Component**: Blarify Workflow Discovery System  
**Context**: Blarify is a codebase analysis tool that converts source code repositories into graph structures for LLM analysis, supporting multiple languages through Tree-sitter and LSP integration.

This feature enhances the WorkflowCreator.discover_workflows() method by adding an optional node_path parameter that enables targeted workflow discovery. When provided, the system performs reverse traversal to find entry points that can reach the specified target node, making workflow analysis feasible for large repositories in SWE benchmark integration scenarios.

---

## Problem Statement

### Current Limitations
The existing workflow discovery system in Blarify analyzes entire repositories to find all entry points and their corresponding execution flows. While this comprehensive approach works well for medium-sized codebases, it presents significant challenges for integration with agent systems working on SWE (Software Engineering) benchmarks.

### Specific Problems
1. **Performance Bottleneck**: Large repositories (>10K files) require 5-30 minutes for full workflow discovery, making it prohibitively expensive for SWE benchmark scenarios
2. **Resource Waste**: Full repository analysis generates massive amounts of workflow data when only specific code paths are relevant to the issue being addressed
3. **Agent Integration Gap**: SWE benchmark agents need to analyze specific problematic nodes (functions/classes with issues) but cannot efficiently discover which entry points lead to those nodes
4. **Scalability Issues**: Current approach doesn't scale to enterprise-sized repositories where targeted analysis is essential

### Business Impact
- **SWE Benchmark Integration**: Cannot efficiently integrate with agent systems that need targeted workflow discovery
- **User Experience**: Long analysis times for large repositories create poor developer experience
- **Resource Costs**: Excessive computation and database storage for unnecessary workflow data
- **Competitive Disadvantage**: Other tools provide more efficient targeted analysis capabilities

### Technical Motivation
The current system's workflow discovery follows a "top-down" approach (entry points → callees), but SWE benchmark scenarios require a "bottom-up" approach (problematic node → callers → entry points). This directional mismatch necessitates a new discovery mode that can work backwards from target nodes to find relevant entry points.

---

## Feature Requirements

### Functional Requirements

#### Primary Functionality
1. **Optional Parameter Addition**: Add `node_path: Optional[str] = None` parameter to `WorkflowCreator.discover_workflows()` method
2. **Backward Compatibility**: When `node_path` is `None`, maintain exact current behavior (full repository analysis)
3. **Targeted Discovery**: When `node_path` is provided, discover only entry points that can reach the target node through call chains
4. **Upward Traversal**: Implement reverse CALLS relationship traversal to find all paths from target node to entry points
5. **Entry Point Definition**: Entry points are nodes with no incoming CALLS relationships (same definition as current system)

#### Secondary Functionality
1. **Path Validation**: Validate that the provided node_path exists in the database before processing
2. **Depth Limiting**: Apply same max_depth constraints to upward traversal as current downward traversal
3. **Cycle Detection**: Handle cycles in call graphs during upward traversal
4. **Performance Optimization**: Minimize database queries and memory usage for large call graphs

### Technical Requirements

#### Database Integration
1. **New Query Function**: Create `find_entry_points_for_node_path_query()` in `blarify/db_managers/queries.py`
2. **Cypher Query Implementation**: Use Neo4j/FalkorDB MATCH patterns with reverse CALLS traversal
3. **Parameter Binding**: Properly bind entity_id, repo_id, node_path, and max_depth parameters
4. **Result Formatting**: Return entry points in same format as `find_all_entry_points_hybrid()`

#### Method Updates
1. **_discover_entry_points() Enhancement**: Modify method to handle both scenarios:
   - Current behavior: Call `find_all_entry_points_hybrid()` when node_path is None
   - New behavior: Call `find_entry_points_for_node_path_query()` when node_path is provided
2. **Type Annotations**: Use `Optional[str]` for node_path parameter, avoid `Any` types
3. **Error Handling**: Graceful handling of invalid node_path values
4. **Logging Integration**: Add appropriate logging for targeted discovery mode

#### Code Quality Standards
1. **Type Hints**: All parameters and return values must have proper type hints
2. **Nested Typing**: Use specific types like `List[Dict[str, Any]]` instead of generic `list`
3. **Documentation**: Comprehensive docstrings following existing project patterns
4. **Code Quality**: Pass `poetry run ruff check` without warnings
5. **Consistent Patterns**: Follow existing code patterns and conventions

### Integration Requirements

#### Agent System Compatibility
1. **Interface Consistency**: Maintain same method signature structure for easy agent integration
2. **Result Format**: Return WorkflowDiscoveryResult objects with same structure regardless of discovery mode
3. **Performance Metrics**: Include timing and scope metrics in discovery results
4. **Error Propagation**: Provide clear error messages for agent systems to handle

#### Database Performance
1. **Query Optimization**: Efficient Cypher queries that leverage graph database strengths
2. **Index Usage**: Utilize existing database indexes for node_id and relationship queries
3. **Memory Management**: Stream results for large call graphs to avoid memory exhaustion
4. **Connection Pooling**: Reuse database connections efficiently

---

## Technical Analysis

### Current Implementation Review

#### Existing Architecture
The current workflow discovery system in `blarify/documentation/workflow_creator.py` follows this pattern:

1. **Entry Point Discovery**: Uses `find_all_entry_points_hybrid()` to find all nodes with no incoming CALLS relationships
2. **Downward Traversal**: For each entry point, traverses CALLS relationships downward to build execution flows
3. **Workflow Creation**: Converts execution flows into WorkflowNode objects with WORKFLOW_STEP relationships
4. **Database Storage**: Saves workflows as graph nodes with proper relationships

#### Current Query Patterns
```cypher
// Current entry point discovery
MATCH (entry:NODE {entityId: $entity_id, repoId: $repo_id, layer: 'code'})
WHERE (entry:FUNCTION)
  AND NOT ()-[:CALLS|USES|ASSIGNS]->(entry)
  AND (entry)-[:CALLS|USES|ASSIGNS]->()
```

```cypher
// Current workflow traversal (downward)
CALL apoc.path.expandConfig(entry, {
  relationshipFilter: "CALLS>",
  minLevel: 0, maxLevel: maxDepth,
  bfs: false,
  uniqueness: "NODE_PATH"
}) YIELD path
```

### Proposed Technical Approach

#### Reverse Traversal Query Design
The new query must traverse CALLS relationships in reverse direction:

```cypher
// Proposed upward traversal query
MATCH (target:NODE {node_id: $node_path, entityId: $entity_id, repoId: $repo_id})
CALL apoc.path.expandConfig(target, {
  relationshipFilter: "<CALLS",  // Reverse direction
  minLevel: 0, maxLevel: $max_depth,
  bfs: false,
  uniqueness: "NODE_PATH"
}) YIELD path
WITH last(nodes(path)) AS potential_entry
WHERE NOT ()-[:CALLS|USES|ASSIGNS]->(potential_entry)
RETURN DISTINCT potential_entry
```

#### Architecture Decisions

##### Database Query Strategy
1. **Single Query Approach**: Use one comprehensive Cypher query that combines upward traversal and entry point filtering
2. **Path Expansion**: Leverage APOC path expansion for efficient graph traversal
3. **Direction Reversal**: Use `<CALLS` relationship filter for upward traversal
4. **Entry Point Filtering**: Apply same entry point criteria as existing system

##### Method Design Pattern
1. **Polymorphic Behavior**: Same method signature with different internal logic based on node_path parameter
2. **Early Validation**: Check node_path existence before expensive traversal operations
3. **Result Normalization**: Ensure both discovery modes return identical result structures
4. **Performance Monitoring**: Track and log performance differences between modes

##### Error Handling Strategy
1. **Input Validation**: Verify node_path exists and is accessible before traversal
2. **Graceful Degradation**: Fall back to empty result set rather than throwing exceptions
3. **Detailed Logging**: Provide clear error messages for debugging and monitoring
4. **Exception Chaining**: Preserve original exception context for troubleshooting

### Dependencies and Integration Points

#### Database Manager Integration
- **AbstractDbManager**: Uses existing database abstraction layer
- **Cypher Query Execution**: Leverages current `db_manager.query()` method
- **Parameter Binding**: Uses existing parameter binding patterns
- **Result Processing**: Follows current result formatting conventions

#### Workflow Creator Integration
- **discover_workflows() Method**: Enhanced with optional parameter
- **_discover_entry_points() Method**: Modified to handle both scenarios
- **Result Model Compatibility**: Maintains WorkflowDiscoveryResult structure
- **Performance Metrics**: Includes timing information for both modes

#### Graph Environment Integration
- **Node ID Generation**: Uses existing graph environment for consistent IDs
- **Relationship Creation**: Leverages existing relationship creation patterns
- **Database Layer**: Maintains separation between code, documentation, workflow, and spec layers

### Performance Considerations

#### Query Performance
1. **Index Utilization**: Leverages existing indexes on node_id, entityId, repoId
2. **Traversal Efficiency**: APOC path expansion optimized for graph traversal
3. **Result Limiting**: Early termination when max_depth reached
4. **Memory Usage**: Streaming results to handle large call graphs

#### Comparison Metrics
- **Full Repository**: 5-30 minutes for large repositories (current)
- **Targeted Discovery**: Expected 10-60 seconds for specific node analysis (new)
- **Memory Reduction**: 90%+ reduction in memory usage for targeted scenarios
- **Database Load**: Significantly reduced query complexity and result set size

#### Scalability Factors
1. **Call Graph Depth**: Performance scales with maximum call stack depth
2. **Repository Size**: Targeted approach scales better than full repository analysis
3. **Database Size**: Query performance depends on total graph size and indexing
4. **Concurrent Usage**: Multiple targeted queries can run simultaneously

---

## Implementation Plan

### Phase 1: Database Query Implementation (High Priority)

#### Deliverables
1. **New Query Function**: `find_entry_points_for_node_path_query()` in `queries.py`
2. **Helper Function**: `find_entry_points_for_node_path()` function implementation
3. **Query Testing**: Validate query performance and correctness
4. **Documentation**: Comprehensive function documentation

#### Implementation Steps
1. **Create Query Function**: Write Cypher query with proper APOC path expansion
2. **Parameter Validation**: Add input validation for node_path parameter
3. **Result Formatting**: Ensure results match existing entry point format
4. **Error Handling**: Implement proper exception handling and logging
5. **Performance Testing**: Test with various repository sizes and call graph depths

#### Acceptance Criteria
- [ ] Query correctly identifies entry points that can reach target node
- [ ] Results format matches `find_all_entry_points_hybrid()` output
- [ ] Query performance under 60 seconds for typical scenarios
- [ ] Proper error handling for non-existent nodes
- [ ] Comprehensive logging for debugging and monitoring

### Phase 2: Workflow Creator Enhancement (High Priority)

#### Deliverables
1. **Method Signature Update**: Add `node_path: Optional[str] = None` parameter
2. **Logic Implementation**: Conditional logic for targeted vs. full discovery
3. **Backward Compatibility**: Ensure existing usage continues to work
4. **Integration Testing**: Validate both discovery modes work correctly

#### Implementation Steps
1. **Signature Update**: Modify `discover_workflows()` method signature
2. **Parameter Passing**: Thread node_path parameter through to `_discover_entry_points()`
3. **Conditional Logic**: Implement branching logic based on node_path value
4. **Result Consistency**: Ensure both modes return compatible results
5. **Documentation Update**: Update method docstrings with new parameter

#### Acceptance Criteria
- [ ] Method accepts optional node_path parameter
- [ ] Backward compatibility maintained (existing calls work unchanged) 
- [ ] Targeted discovery produces correct workflow results
- [ ] Performance improvement demonstrated for large repositories
- [ ] Type hints and documentation are complete

### Phase 3: Integration and Testing (Medium Priority)

#### Deliverables
1. **Unit Tests**: Comprehensive test coverage for new functionality
2. **Integration Tests**: End-to-end testing with real repository data
3. **Performance Benchmarks**: Comparative performance analysis
4. **Documentation**: Updated API documentation and usage examples

#### Implementation Steps
1. **Unit Test Creation**: Test both query function and method enhancement
2. **Mock Data Setup**: Create test scenarios with known call graphs
3. **Performance Testing**: Benchmark targeted vs. full discovery
4. **Edge Case Testing**: Handle cycles, deep call stacks, invalid inputs
5. **Documentation Updates**: Update docstrings, API docs, and examples

#### Acceptance Criteria
- [ ] Test coverage > 90% for new code paths
- [ ] Performance benchmarks demonstrate expected improvements
- [ ] Edge cases handled gracefully
- [ ] Documentation reflects new functionality
- [ ] All existing tests continue to pass

### Phase 4: Optimization and Polish (Low Priority)

#### Deliverables
1. **Query Optimization**: Fine-tune Cypher queries for maximum performance
2. **Caching Layer**: Add caching for frequently accessed entry points
3. **Monitoring Integration**: Add metrics and monitoring for production use
4. **Usage Analytics**: Track adoption and performance of targeted discovery

#### Implementation Steps
1. **Query Profiling**: Analyze query execution plans and optimize
2. **Cache Implementation**: Add intelligent caching for entry point results
3. **Metrics Addition**: Include performance and usage metrics
4. **Production Monitoring**: Set up alerts and dashboards
5. **User Feedback**: Collect and analyze usage patterns

### Risk Mitigation Strategies

#### Technical Risks
1. **Query Performance**: Risk of slow upward traversal in large graphs
   - *Mitigation*: Implement query timeouts and depth limits
   - *Contingency*: Fall back to breadth-first search if depth-first is slow

2. **Memory Usage**: Risk of excessive memory usage during traversal
   - *Mitigation*: Use streaming results and pagination
   - *Contingency*: Implement result limiting and progressive disclosure

3. **Graph Cycles**: Risk of infinite loops in cyclic call graphs
   - *Mitigation*: Use APOC uniqueness constraints
   - *Contingency*: Implement manual cycle detection and breaking

#### Integration Risks
1. **Backward Compatibility**: Risk of breaking existing integrations
   - *Mitigation*: Extensive regression testing
   - *Contingency*: Feature flag to disable new functionality

2. **Database Compatibility**: Risk of APOC dependency issues
   - *Mitigation*: Validate APOC availability before query execution
   - *Contingency*: Implement native Cypher fallback queries

### Resource Requirements

#### Development Resources
- **Senior Developer**: 2-3 weeks for implementation and testing
- **Database Expert**: 1 week for query optimization and performance tuning
- **QA Engineer**: 1 week for comprehensive testing and validation

#### Infrastructure Resources
- **Test Database**: Neo4j/FalkorDB instance for testing large repositories
- **Performance Testing**: Infrastructure for benchmarking different scenarios
- **Monitoring Setup**: Tooling for production performance monitoring

---

## Testing Requirements

### Unit Testing Strategy

#### Core Functionality Tests
1. **Parameter Validation Tests**
   - Test with valid node_path values
   - Test with invalid/non-existent node_path values
   - Test with None node_path (backward compatibility)
   - Test with empty string node_path

2. **Query Function Tests**
   - Test `find_entry_points_for_node_path_query()` with various graph structures
   - Test upward traversal with different call chain depths
   - Test entry point identification accuracy
   - Test performance with large result sets

3. **Integration Tests**
   - Test `discover_workflows()` with both parameter modes
   - Test result format consistency between modes
   - Test workflow creation and database storage
   - Test relationship creation accuracy

#### Edge Case Testing
1. **Graph Structure Edge Cases**
   - Nodes with no callers (already entry points)
   - Nodes in cyclic call chains
   - Deeply nested call hierarchies (>20 levels)
   - Disconnected graph components

2. **Data Edge Cases**
   - Empty repository (no nodes)
   - Single node repository
   - Repository with only entry points
   - Large repository (>10K nodes)

3. **Parameter Edge Cases**
   - Very long node_path strings
   - Node paths with special characters
   - Malformed node identifiers
   - Node paths from different repositories

### Integration Testing Needs

#### Database Integration
1. **Multi-Database Testing**
   - Test with Neo4j Community Edition
   - Test with FalkorDB
   - Test with different database versions
   - Test with various graph sizes

2. **Performance Integration**
   - Test query performance under load
   - Test concurrent discovery operations
   - Test memory usage patterns
   - Test database connection handling

#### Workflow Integration
1. **End-to-End Workflows**
   - Test complete workflow discovery pipeline
   - Test workflow node creation and storage
   - Test relationship creation accuracy
   - Test result serialization and deserialization

2. **Agent System Integration**
   - Test SWE benchmark scenario workflows
   - Test targeted discovery with real repository data
   - Test performance improvements in agent scenarios
   - Test error handling in agent integration

### Performance Testing Requirements

#### Benchmark Scenarios
1. **Small Repository** (<1K nodes)
   - Full discovery vs. targeted discovery timing
   - Memory usage comparison
   - Database load comparison
   - Result accuracy validation

2. **Medium Repository** (1K-10K nodes)
   - Performance scaling analysis
   - Memory usage patterns
   - Query optimization effectiveness
   - Concurrent usage impact

3. **Large Repository** (>10K nodes)
   - Feasibility testing for targeted discovery
   - Performance improvement quantification
   - Resource usage monitoring
   - Scalability limits identification

#### Performance Metrics
1. **Timing Metrics**
   - Query execution time
   - Total discovery time
   - Memory allocation time
   - Result processing time

2. **Resource Metrics**
   - Peak memory usage
   - Database query count
   - Network bandwidth usage
   - CPU utilization patterns

3. **Accuracy Metrics**
   - Entry point identification accuracy
   - Workflow completeness
   - False positive/negative rates
   - Result consistency validation

### Error Scenarios and Validation

#### Input Validation Errors
1. **Invalid Node Path**
   - Non-existent node identifiers
   - Malformed node path strings
   - Node paths from wrong repository
   - Node paths with wrong entity ID

2. **Database Connection Errors**
   - Network connectivity issues
   - Authentication failures
   - Timeout scenarios
   - Connection pool exhaustion

#### Processing Error Scenarios
1. **Query Execution Errors**
   - APOC function unavailability
   - Query timeout scenarios
   - Memory exhaustion during traversal
   - Database lock conflicts

2. **Result Processing Errors**
   - Malformed query results
   - Type conversion errors
   - Result serialization failures
   - Relationship creation errors

#### Recovery and Fallback Testing
1. **Graceful Degradation**
   - Fall back to empty results on errors
   - Maintain partial results when possible
   - Clear error messaging for debugging
   - Proper exception logging

2. **System Resilience**
   - Continue operation after individual failures
   - Maintain system stability under load
   - Proper resource cleanup on errors
   - Recovery from temporary failures

---

## Success Criteria

### Measurable Outcomes

#### Performance Improvements
1. **Speed Enhancement**
   - **Target**: 90% reduction in discovery time for targeted scenarios
   - **Baseline**: Current full repository analysis (5-30 minutes)
   - **Goal**: Targeted discovery in 10-60 seconds
   - **Measurement**: Execution time comparison across repository sizes

2. **Resource Efficiency**
   - **Target**: 90% reduction in memory usage for targeted scenarios
   - **Baseline**: Current memory footprint for full discovery
   - **Goal**: Memory usage proportional to call chain depth, not repository size
   - **Measurement**: Peak memory usage monitoring

3. **Database Load Reduction**
   - **Target**: 95% reduction in query complexity for targeted scenarios
   - **Baseline**: Current full repository graph traversal
   - **Goal**: Query complexity proportional to upward call paths only
   - **Measurement**: Query execution plan analysis and timing

#### Functionality Completeness
1. **Feature Parity**
   - **Target**: 100% backward compatibility with existing workflows
   - **Measurement**: All existing tests pass without modification
   - **Validation**: No regression in current functionality

2. **Result Accuracy**
   - **Target**: 100% accuracy in entry point identification for targeted discovery
   - **Measurement**: Manual validation against known call graphs
   - **Validation**: Cross-validation with full discovery results

3. **API Consistency**
   - **Target**: Identical result format regardless of discovery mode
   - **Measurement**: Result structure validation and schema compliance
   - **Validation**: Automated testing of result format consistency

### Quality Metrics

#### Code Quality Standards
1. **Type Safety**
   - **Target**: 100% type hint coverage for new code
   - **Tool**: mypy static type checking
   - **Standard**: No type errors or warnings

2. **Code Quality**
   - **Target**: Pass all ruff checks without warnings
   - **Tool**: `poetry run ruff check` 
   - **Standard**: No linting violations

3. **Documentation Coverage**
   - **Target**: Comprehensive docstrings for all new functions and methods
   - **Standard**: Google-style docstrings with parameter descriptions
   - **Validation**: Documentation review and approval

#### Test Coverage Requirements
1. **Unit Test Coverage**
   - **Target**: >90% line coverage for new code
   - **Tool**: pytest with coverage reporting
   - **Scope**: All new functions and modified methods

2. **Integration Test Coverage**
   - **Target**: 100% coverage of critical user scenarios
   - **Scope**: Both targeted and full discovery workflows
   - **Validation**: End-to-end scenario testing

3. **Edge Case Coverage**
   - **Target**: All identified edge cases have corresponding tests
   - **Scope**: Error conditions, boundary conditions, performance limits
   - **Validation**: Systematic edge case analysis and testing

### Performance Benchmarks

#### Timing Benchmarks
1. **Small Repository Performance** (<1K nodes)
   - **Full Discovery**: Baseline measurement (current system)
   - **Targeted Discovery**: <5 seconds (new system)
   - **Improvement Factor**: Expected 10-50x faster

2. **Medium Repository Performance** (1K-10K nodes)
   - **Full Discovery**: 1-5 minutes (current system)
   - **Targeted Discovery**: <30 seconds (new system)  
   - **Improvement Factor**: Expected 10-100x faster

3. **Large Repository Performance** (>10K nodes)
   - **Full Discovery**: 5-30 minutes (current system)
   - **Targeted Discovery**: <60 seconds (new system)
   - **Improvement Factor**: Expected 50-1000x faster

#### Memory Benchmarks
1. **Memory Usage Scaling**
   - **Current System**: Memory usage scales with repository size
   - **New System**: Memory usage scales with call chain depth only
   - **Target**: Memory usage independent of repository size for targeted discovery

2. **Peak Memory Usage**
   - **Reduction Target**: 90% reduction in peak memory for targeted scenarios
   - **Measurement**: Memory profiling during discovery operations
   - **Validation**: Sustained memory usage below target thresholds

### User Satisfaction Metrics

#### Developer Experience
1. **API Usability**
   - **Target**: Simple parameter addition with intuitive behavior
   - **Measurement**: Developer feedback and adoption rates
   - **Success**: Developers can use targeted discovery without additional training

2. **Error Handling Quality**
   - **Target**: Clear, actionable error messages for all failure scenarios
   - **Measurement**: Error message clarity and resolution time
   - **Success**: Developers can debug issues without support escalation

3. **Documentation Quality**
   - **Target**: Complete, accurate documentation with examples
   - **Measurement**: Documentation completeness and accuracy review
   - **Success**: Developers can implement targeted discovery from documentation alone

#### Production Readiness
1. **Reliability**
   - **Target**: 99.9% success rate for valid inputs
   - **Measurement**: Production error monitoring and alerting
   - **Success**: System operates reliably under production loads

2. **Monitoring and Observability**
   - **Target**: Complete visibility into performance and usage patterns
   - **Measurement**: Metrics collection and dashboard availability
   - **Success**: Operations team can monitor and troubleshoot effectively

3. **Scalability**
   - **Target**: System scales to enterprise repository sizes
   - **Measurement**: Performance testing with realistic data volumes
   - **Success**: Consistent performance across all supported repository sizes

---

## Implementation Steps

### Workflow Overview: Issue Creation to PR Review

This implementation follows a complete software development lifecycle with proper GitHub integration, testing, and code review processes. The workflow is designed for WorkflowMaster execution with comprehensive task tracking and validation.

### Step 1: GitHub Issue Creation

#### Create Comprehensive GitHub Issue
**Objective**: Document the feature request with detailed requirements and acceptance criteria

**Actions**:
1. **Issue Title**: "Add Optional Node Path Parameter to Workflow Discovery for SWE Benchmark Integration"
2. **Issue Description**: Include complete problem statement, business justification, and technical requirements
3. **Acceptance Criteria**: List all measurable success criteria from this prompt
4. **Labels**: Add appropriate labels (`enhancement`, `performance`, `api-change`, `swe-benchmark`)
5. **Milestone**: Assign to appropriate project milestone
6. **Assignee**: Assign to implementing developer

**Issue Template**:
```markdown
## Problem Statement
Current workflow discovery analyzes entire repositories, making it too expensive for SWE benchmark integration with large codebases.

## Proposed Solution
Add optional `node_path` parameter to `WorkflowCreator.discover_workflows()` method that enables reverse traversal to find entry points reaching a specific target node.

## Technical Requirements
- Add `node_path: Optional[str] = None` parameter
- Implement upward CALLS traversal when node_path provided
- Maintain backward compatibility when node_path is None
- Create new database query `find_entry_points_for_node_path_query()`
- Update `_discover_entry_points()` method for both scenarios

## Acceptance Criteria
- [ ] Method accepts optional node_path parameter
- [ ] Backward compatibility maintained
- [ ] 90% performance improvement for targeted scenarios
- [ ] All existing tests pass
- [ ] Type hints use Optional[str], avoid Any
- [ ] Pass `poetry run ruff check`

## Files to Modify
- `blarify/db_managers/queries.py` - Add new query function
- `blarify/documentation/workflow_creator.py` - Update discover_workflows method

## Performance Targets
- Targeted discovery: <60 seconds vs 5-30 minutes for full analysis
- Memory reduction: 90% for targeted scenarios
- Database query reduction: 95% complexity reduction
```

### Step 2: Branch Management and Setup

#### Create Feature Branch from Current Branch
**Objective**: Set up proper Git workflow branching strategy

**Actions**:
1. **Source Branch**: `feat/optional-node-path-workflow-discovery` (current working branch)
2. **Target Branch**: Create new feature branch from current branch (NOT from main)
3. **Branch Name**: `feat/add-node-path-workflow-discovery`
4. **Branch Protection**: Ensure branch follows established naming conventions

**Git Commands**:
```bash
git checkout feat/optional-node-path-workflow-discovery
git pull origin feat/optional-node-path-workflow-discovery
git checkout -b feat/add-node-path-workflow-discovery
git push -u origin feat/add-node-path-workflow-discovery
```

### Step 3: Research and Analysis Phase

#### Codebase Analysis and Technical Discovery
**Objective**: Analyze existing implementations and validate technical approach

**Research Tasks**:
1. **Query Pattern Analysis**
   - Study existing APOC path expansion usage in `find_code_workflows_query()`
   - Analyze current entry point discovery patterns in `find_all_entry_points_hybrid()`
   - Review relationship traversal patterns and performance characteristics
   - Document query execution plans and optimization opportunities

2. **Database Schema Validation**
   - Verify CALLS relationship structure and properties
   - Confirm node_id indexing and query performance
   - Validate APOC function availability in target databases
   - Test reverse relationship traversal feasibility

3. **Integration Point Mapping**
   - Map all callers of `discover_workflows()` method
   - Identify potential breaking changes and mitigation strategies
   - Document result format requirements and compatibility constraints
   - Analyze performance impact on existing usage patterns

4. **Error Handling Pattern Study**
   - Review existing error handling patterns in WorkflowCreator
   - Study database error handling and recovery mechanisms
   - Document logging patterns and monitoring integration points
   - Plan exception handling strategy for new functionality

**Deliverables**:
- Technical analysis document with findings and recommendations
- Performance baseline measurements from existing system
- Risk assessment and mitigation strategies
- Detailed implementation plan with time estimates

### Step 4: Database Query Implementation

#### Implement Core Database Query Functionality
**Objective**: Create robust, performant database query for upward traversal

**Implementation Tasks**:

##### 4.1: Create find_entry_points_for_node_path_query()
```python
def find_entry_points_for_node_path_query() -> str:
    """
    Returns a Cypher query for finding entry points that can reach a specific target node.
    
    This query performs upward traversal through CALLS relationships to find all entry points
    (nodes with no incoming CALLS relationships) that have execution paths leading to the
    target node specified by node_path.
    
    Returns:
        str: The Cypher query string for upward entry point discovery
    """
    return """
    // Find target node
    MATCH (target:NODE {
        node_id: $node_path,
        entityId: $entity_id, 
        repoId: $repo_id,
        layer: 'code'
    })
    
    // Perform upward traversal to find all nodes that can reach target
    CALL apoc.path.expandConfig(target, {
        relationshipFilter: "<CALLS",
        minLevel: 0, 
        maxLevel: $max_depth,
        bfs: false,
        uniqueness: "NODE_PATH"
    }) YIELD path
    
    // Extract potential entry points (last node in each upward path)
    WITH last(nodes(path)) AS potential_entry, path
    
    // Filter to only true entry points (no incoming CALLS relationships)
    WHERE potential_entry:FUNCTION
      AND NOT ()-[:CALLS|USES|ASSIGNS]->(potential_entry)
      AND (potential_entry)-[:CALLS|USES|ASSIGNS]->()
      AND NOT potential_entry.name IN ['__init__', '__new__', 'constructor', 'initialize', 'init', 'new']
    
    RETURN DISTINCT 
        potential_entry.node_id as id,
        potential_entry.name as name,
        potential_entry.path as path,
        labels(potential_entry) as labels,
        length(path) as distance_to_target
    ORDER BY distance_to_target, potential_entry.path, potential_entry.name
    """
```

##### 4.2: Create Helper Function Implementation
```python
def find_entry_points_for_node_path(
    db_manager: AbstractDbManager, 
    entity_id: str, 
    repo_id: str, 
    node_path: str,
    max_depth: int = 20
) -> List[Dict[str, Any]]:
    """
    Finds entry points that can reach a specific target node through call chains.
    
    This function performs upward traversal from the target node to discover all entry points
    that have execution paths leading to the target. Used for targeted workflow discovery
    in SWE benchmark scenarios where analyzing specific problematic code is needed.
    
    Args:
        db_manager: Database manager instance for query execution
        entity_id: The entity ID to filter results
        repo_id: The repository ID to filter results  
        node_path: The target node ID to find entry points for
        max_depth: Maximum depth for upward traversal (default: 20)
        
    Returns:
        List of entry point dictionaries with id, name, path, labels, distance_to_target
        
    Raises:
        ValueError: If node_path doesn't exist in the database
        Exception: For database connection or query execution errors
    """
```

##### 4.3: Input Validation and Error Handling Implementation
```python
# Validate node_path exists before expensive traversal
validate_query = """
MATCH (n:NODE {node_id: $node_path, entityId: $entity_id, repoId: $repo_id})
RETURN n.node_id as id, n.name as name
LIMIT 1
"""

validation_result = db_manager.query(
    cypher_query=validate_query,
    parameters={"node_path": node_path, "entity_id": entity_id, "repo_id": repo_id}
)

if not validation_result:
    logger.error(f"Target node not found: {node_path}")
    raise ValueError(f"Node with id '{node_path}' not found in repository {repo_id}")
```

##### 4.4: Performance Optimization Implementation
- Query timeout configuration
- Result streaming for large datasets  
- Memory usage monitoring and limits
- Index utilization verification
- Query execution plan analysis

**Testing Requirements**:
- Unit tests for query function with various graph structures
- Performance tests with different repository sizes
- Edge case testing (cycles, deep hierarchies, disconnected components)
- Error condition testing (invalid inputs, database failures)

### Step 5: Workflow Creator Method Enhancement

#### Update discover_workflows() Method Signature and Logic
**Objective**: Enhance existing method with new parameter while maintaining backward compatibility

**Implementation Tasks**:

##### 5.1: Method Signature Update
```python
def discover_workflows(
    self, 
    entry_points: Optional[List[str]] = None,
    max_depth: int = 20,
    save_to_database: bool = True,
    node_path: Optional[str] = None,  # New parameter
) -> WorkflowDiscoveryResult:
    """
    Discover workflows using direct code structure analysis.
    
    This method provides two discovery modes:
    1. Full repository analysis (when node_path is None) - existing behavior
    2. Targeted analysis (when node_path is provided) - new behavior for SWE benchmarks
    
    Args:
        entry_points: Optional list of entry point IDs to analyze
        max_depth: Maximum depth for workflow traversal  
        save_to_database: Whether to save discovered workflows to database
        node_path: Optional target node ID for reverse entry point discovery.
                  When provided, discovers only entry points that can reach this node.
                  When None, maintains existing full repository discovery behavior.
                  
    Returns:
        WorkflowDiscoveryResult with discovered workflows and performance metrics
        
    Example:
        # Full repository discovery (existing behavior)
        result = creator.discover_workflows()
        
        # Targeted discovery for SWE benchmark (new behavior)  
        result = creator.discover_workflows(node_path="function_with_bug_12345")
    """
```

##### 5.2: _discover_entry_points() Method Enhancement
```python
def _discover_entry_points(self, node_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Discover entry points using hybrid approach or targeted node path analysis.
    
    This method now supports two modes:
    1. Hybrid discovery: Uses existing find_all_entry_points_hybrid (when node_path is None)
    2. Targeted discovery: Uses new find_entry_points_for_node_path (when node_path provided)
    
    Args:
        node_path: Optional target node ID for reverse entry point discovery
        
    Returns:
        List of entry point dictionaries with id, name, path, etc.
    """
    try:
        if node_path is None:
            # Existing behavior: full repository hybrid discovery
            logger.info("Discovering entry points using hybrid approach (full repository)")
            
            entry_points = find_all_entry_points_hybrid(
                db_manager=self.db_manager,
                entity_id=self.company_id,
                repo_id=self.repo_id
            )
            
            discovery_method = "hybrid_database_analysis"
            
        else:
            # New behavior: targeted discovery for specific node
            logger.info(f"Discovering entry points for target node: {node_path}")
            
            entry_points = find_entry_points_for_node_path(
                db_manager=self.db_manager,
                entity_id=self.company_id,
                repo_id=self.repo_id,
                node_path=node_path,
                max_depth=20
            )
            
            discovery_method = "targeted_upward_traversal"
        
        # Convert to standard format
        standardized_entry_points = []
        for ep in entry_points:
            standardized_entry_points.append({
                "id": ep.get("id", ""),
                "name": ep.get("name", ""),
                "path": ep.get("path", ""),
                "labels": ep.get("labels", []),
                "description": f"Entry point: {ep.get('name', 'Unknown')}",
                "discovery_method": discovery_method,
                "distance_to_target": ep.get("distance_to_target", 0),  # New field for targeted discovery
            })
        
        logger.info(f"Discovered {len(standardized_entry_points)} entry points using {discovery_method}")
        return standardized_entry_points
        
    except Exception as e:
        logger.exception(f"Error discovering entry points: {e}")
        return []
```

##### 5.3: Result Metrics Enhancement
Update WorkflowDiscoveryResult to include performance comparison metrics:
```python
return WorkflowDiscoveryResult(
    discovered_workflows=all_workflows,
    entry_points=entry_points_data,
    total_entry_points=len(entry_point_ids),
    total_workflows=len(all_workflows),
    discovery_time_seconds=discovery_time,
    warnings=warnings,
    discovery_mode="targeted" if node_path else "full_repository",  # New field
    target_node_id=node_path,  # New field
    performance_improvement_factor=self._calculate_improvement_factor(discovery_time, node_path),  # New field
)
```

**Testing Requirements**:
- Unit tests for both discovery modes
- Integration tests with real repository data
- Performance comparison tests
- Backward compatibility validation tests

### Step 6: Comprehensive Testing Implementation

#### Create Complete Test Suite for New Functionality
**Objective**: Ensure robust testing coverage for all new functionality and edge cases

**Testing Implementation Tasks**:

##### 6.1: Unit Test Suite Creation
Create comprehensive unit tests in appropriate test files:

```python
# test_workflow_creator_node_path.py
import pytest
from unittest.mock import Mock, patch
from blarify.documentation.workflow_creator import WorkflowCreator
from blarify.documentation.result_models import WorkflowDiscoveryResult

class TestWorkflowCreatorNodePath:
    """Test suite for node_path parameter functionality in WorkflowCreator."""
    
    def test_discover_workflows_with_node_path_parameter(self):
        """Test that discover_workflows accepts node_path parameter."""
        # Test implementation
        pass
        
    def test_backward_compatibility_with_none_node_path(self):
        """Test that existing behavior is maintained when node_path is None."""
        # Test implementation
        pass
        
    def test_targeted_discovery_with_valid_node_path(self):
        """Test targeted discovery with valid node_path."""
        # Test implementation
        pass
        
    def test_error_handling_with_invalid_node_path(self):
        """Test error handling with non-existent node_path."""
        # Test implementation
        pass

# test_queries_node_path.py  
class TestNodePathQueries:
    """Test suite for node path query functions."""
    
    def test_find_entry_points_for_node_path_query_structure(self):
        """Test that query has correct structure and parameters."""
        # Test implementation
        pass
        
    def test_upward_traversal_accuracy(self):
        """Test that upward traversal finds correct entry points."""
        # Test implementation
        pass
```

##### 6.2: Integration Test Implementation
```python
class TestNodePathIntegration:
    """Integration tests for end-to-end node path functionality."""
    
    @pytest.fixture
    def sample_repository_graph(self):
        """Create sample repository graph for testing."""
        # Setup test data
        pass
        
    def test_end_to_end_targeted_discovery(self, sample_repository_graph):
        """Test complete workflow from node_path to workflow results."""
        # Test implementation
        pass
        
    def test_performance_comparison(self, large_repository_graph):
        """Test performance improvement of targeted vs full discovery."""
        # Test implementation
        pass
```

##### 6.3: Performance Test Suite
```python
class TestNodePathPerformance:
    """Performance tests for node path functionality."""
    
    def test_targeted_discovery_speed(self):
        """Test that targeted discovery is significantly faster."""
        # Test implementation with timing
        pass
        
    def test_memory_usage_reduction(self):
        """Test that targeted discovery uses less memory."""
        # Test implementation with memory profiling
        pass
```

##### 6.4: Edge Case Testing
```python
class TestNodePathEdgeCases:
    """Edge case tests for node path functionality."""
    
    def test_circular_call_graphs(self):
        """Test handling of circular call relationships."""
        # Test implementation
        pass
        
    def test_deep_call_hierarchies(self):
        """Test handling of very deep call chains."""
        # Test implementation
        pass
        
    def test_disconnected_graph_components(self):
        """Test handling of nodes with no callers."""
        # Test implementation
        pass
```

### Step 7: Documentation and Code Quality

#### Update Documentation and Ensure Code Quality Standards
**Objective**: Comprehensive documentation updates and code quality validation

**Documentation Tasks**:

##### 7.1: API Documentation Updates
- Update method docstrings with new parameter descriptions
- Add usage examples for both discovery modes
- Document performance characteristics and use cases
- Update type hints and parameter descriptions

##### 7.2: Code Quality Validation
```bash
# Run complete code quality checks
poetry run ruff check  # Must pass without warnings
poetry run mypy        # Type checking
poetry run pytest --cov=blarify/documentation/workflow_creator --cov=blarify/db_managers/queries
```

##### 7.3: Performance Documentation
- Document performance benchmarks and comparisons
- Create usage guidelines for different scenarios
- Add troubleshooting guide for common issues
- Document monitoring and observability features

### Step 8: Pull Request Creation and Description

#### Create Comprehensive Pull Request
**Objective**: Create detailed PR with proper AI agent attribution and comprehensive change description

**PR Template**:
```markdown
# Add Optional Node Path Parameter to Workflow Discovery

## 🤖 AI Agent Implementation
This feature was implemented by an AI coding agent as part of the Blarify development workflow.

**Agent**: WorkflowMaster  
**Implementation Date**: [Current Date]  
**Prompt File**: `prompts/optional-node-path-workflow-discovery.md`

## Overview
Adds optional `node_path` parameter to `WorkflowCreator.discover_workflows()` method enabling targeted workflow discovery for SWE benchmark integration. When provided, performs reverse traversal to find entry points that can reach the specified target node.

## Problem Solved
- **Performance**: Reduces discovery time from 5-30 minutes to 10-60 seconds for targeted scenarios
- **Resource Usage**: 90% reduction in memory usage and database load for targeted discovery
- **SWE Integration**: Enables efficient integration with agent systems analyzing specific problematic code

## Changes Made

### Core Implementation
- ✅ Added `node_path: Optional[str] = None` parameter to `discover_workflows()`
- ✅ Created `find_entry_points_for_node_path_query()` in `queries.py`
- ✅ Updated `_discover_entry_points()` method for conditional logic
- ✅ Maintained 100% backward compatibility

### Database Queries
- ✅ Implemented upward CALLS traversal using APOC path expansion
- ✅ Added proper entry point filtering and validation
- ✅ Optimized query performance with indexing and limits

### Testing
- ✅ Comprehensive unit test suite (>90% coverage)
- ✅ Integration tests with real repository data
- ✅ Performance benchmarks demonstrating improvements
- ✅ Edge case testing (cycles, deep hierarchies, invalid inputs)

## Performance Results

| Scenario | Before | After | Improvement |
|----------|--------|-------|-------------|
| Small Repo (<1K nodes) | 30s | 3s | 10x faster |
| Medium Repo (1K-10K nodes) | 3min | 15s | 12x faster |
| Large Repo (>10K nodes) | 20min | 45s | 27x faster |

## Breaking Changes
**None** - This change is fully backward compatible. All existing code will continue to work unchanged.

## Files Modified
- `blarify/db_managers/queries.py` - New query functions
- `blarify/documentation/workflow_creator.py` - Enhanced discover_workflows method
- `tests/` - New comprehensive test suite

## Code Quality
- ✅ All ruff checks pass
- ✅ Type hints use `Optional[str]`, no `Any` types
- ✅ Comprehensive docstrings and documentation
- ✅ >90% test coverage for new code

## Usage Examples

### Existing Usage (Unchanged)
```python
# Full repository discovery - existing behavior
result = workflow_creator.discover_workflows()
```

### New Targeted Usage
```python
# Targeted discovery for SWE benchmark scenarios
result = workflow_creator.discover_workflows(node_path="problematic_function_id")
```

## Validation Checklist
- [ ] All existing tests pass
- [ ] New functionality has comprehensive tests
- [ ] Performance benchmarks demonstrate expected improvements
- [ ] Documentation is complete and accurate
- [ ] API maintains backward compatibility
- [ ] Code quality checks pass
```

### Step 9: Code Review Process

#### Invoke Code Review Agent
**Objective**: Comprehensive code review using specialized review agent

**Review Process**:
1. **Automated Review**: Invoke code-reviewer sub-agent for detailed analysis
2. **Performance Review**: Validate performance improvements and benchmarks
3. **Security Review**: Analyze new database queries for security implications
4. **Architecture Review**: Ensure changes align with existing patterns
5. **Documentation Review**: Validate completeness and accuracy of documentation

**Review Checklist**:
- [ ] Code follows established patterns and conventions
- [ ] Type hints are complete and accurate
- [ ] Error handling is comprehensive and appropriate
- [ ] Performance improvements are validated
- [ ] Security implications are considered
- [ ] Documentation is complete and helpful
- [ ] Tests provide adequate coverage
- [ ] Backward compatibility is maintained

### Step 10: Final Validation and Merge

#### Final Testing and Validation
**Objective**: Complete final validation before merge approval

**Final Validation Steps**:
1. **Regression Testing**: Run complete test suite to ensure no regressions
2. **Performance Validation**: Confirm performance improvements meet targets
3. **Integration Testing**: Test with various repository configurations
4. **Documentation Validation**: Verify all documentation is accurate and complete
5. **Code Quality Final Check**: Run all quality checks and confirm compliance

**Merge Requirements**:
- [ ] PR approved by code review agent
- [ ] All automated tests pass
- [ ] Performance benchmarks meet targets
- [ ] Documentation is complete and accurate
- [ ] No merge conflicts with target branch
- [ ] Final code quality validation passes

### Continuous Integration and Monitoring

#### Post-Merge Monitoring Setup
**Objective**: Establish monitoring and observability for new functionality

**Monitoring Implementation**:
1. **Performance Metrics**: Track discovery time improvements in production
2. **Usage Analytics**: Monitor adoption of targeted discovery feature
3. **Error Monitoring**: Set up alerts for new error conditions
4. **Resource Usage**: Monitor memory and database impact
5. **User Feedback**: Collect feedback on performance improvements

**Success Metrics Tracking**:
- Discovery time improvements (target: 90% reduction)
- Memory usage reduction (target: 90% reduction)
- Database query efficiency (target: 95% reduction)
- Feature adoption rate among SWE benchmark integrations
- Error rates and reliability metrics

This comprehensive implementation plan ensures systematic development from initial GitHub issue creation through final production monitoring, with proper validation at each step and complete documentation for future maintenance and enhancement.