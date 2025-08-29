---
title: "Add Auto-Calculation Capabilities to GetCodeByIdTool and GetNodeWorkflowsTool"
issue_number: 284
created_by: prompt-writer
date: 2025-01-29
description: "Implement auto-generation of missing documentation and workflows in Blarify tools"
---

# Add Auto-Calculation Capabilities to GetCodeByIdTool and GetNodeWorkflowsTool

## Overview

This implementation adds intelligent auto-generation capabilities to two critical Blarify tools: `GetCodeByIdTool` and `GetNodeWorkflowsTool`. When these tools detect missing documentation or workflow data, they will automatically trigger generation using the appropriate creators (DocumentationCreator and WorkflowCreator), ensuring a seamless experience for AI agents using these tools. The feature is controlled via a constructor parameter `auto_generate` (default: True) to maintain backward compatibility while enabling smart data generation.

## Problem Statement

### Current Limitations

1. **GetCodeByIdTool** currently retrieves code nodes and displays existing documentation nodes but returns "None found" when documentation is missing, requiring manual generation
2. **GetNodeWorkflowsTool** retrieves workflows but shows a warning message when no workflows exist, without attempting to generate them
3. AI agents using these tools receive incomplete results and must manually trigger generation, creating friction in the workflow
4. Missing data leads to degraded experiences when exploring codebases, particularly for new or recently modified code

### Pain Points

- AI agents (the primary users) must handle missing data scenarios manually
- Multiple round-trips are needed: query → detect missing → trigger generation → query again
- No persistent storage of generated data, leading to repeated generation for the same nodes
- Lack of unified behavior across tools for handling missing data

### Impact

- Reduced efficiency for AI agents exploring codebases
- Incomplete analysis results when documentation or workflows haven't been pre-generated
- Poor user experience when working with newly imported or updated repositories
- Wasted compute cycles when data isn't persisted after generation

## Feature Requirements

### Functional Requirements

1. **Auto-Generation Control**
   - Add `auto_generate` parameter to both tool constructors (NOT in the input schema)
   - Default value: `True` for active generation behavior
   - When `True` and data is missing, automatically trigger generation
   - When `False`, maintain current behavior (return empty/none)

2. **Silent Operation**
   - No progress bars, spinners, or user feedback during generation
   - No interactive prompts or confirmations
   - Results returned directly after generation completes
   - Log to standard Python logging for debugging only

3. **Targeted Generation**
   - Generate documentation/workflows ONLY for the requested node
   - Avoid triggering full codebase analysis
   - Use efficient, focused generation methods

4. **Data Persistence**
   - Store generated documentation/workflows in the database
   - Future queries should retrieve stored data without regeneration
   - Ensure thread-safe database operations

### Technical Requirements

1. **Dependencies**
   - Import `DocumentationCreator` from `blarify.documentation.documentation_creator`
   - Import `WorkflowCreator` from `blarify.documentation.workflow_creator`
   - Reuse existing `db_manager` and `company_id` from tool initialization

2. **Error Handling**
   - Gracefully handle generation failures
   - Return empty/none results on error (no exceptions to caller)
   - Log errors for debugging without breaking tool execution

3. **Thread Safety**
   - Ensure concurrent requests don't cause conflicts
   - Handle database session management properly
   - Avoid race conditions in generation logic

### User Stories

1. As an AI agent, when I query a node's code and documentation doesn't exist, I want it automatically generated and returned in my response
2. As an AI agent, when I request workflows for a node without existing workflows, I want them discovered and returned seamlessly
3. As a developer, I want to control auto-generation behavior through initialization parameters
4. As a system administrator, I want generated data persisted to avoid repeated computation

## Technical Analysis

### Current Implementation Review

#### GetCodeByIdTool (blarify/tools/get_code_by_id_tool.py)
- Lines 234-255: Checks for documentation nodes and displays them if available
- Returns "None found" when documentation_nodes is empty
- Already has access to db_manager and company_id
- Uses NodeSearchResultResponse model with documentation_nodes field

#### GetNodeWorkflowsTool (blarify/tools/get_node_workflows.py)
- Lines 91-107: Shows warning when no workflows found
- Has detailed warning message about missing workflow data
- Already has access to db_manager and company_id
- Uses custom queries to find workflows with BELONGS_TO_WORKFLOW relationships

### Proposed Technical Approach

1. **Constructor Modification**
   - Add `auto_generate: bool = True` parameter to `__init__` methods
   - Store as instance variable for use in `_run` methods
   - Maintain all existing parameters

2. **Lazy Initialization**
   - Create DocumentationCreator/WorkflowCreator instances only when needed
   - Cache creator instances to avoid repeated initialization
   - Use property pattern for lazy loading

3. **Generation Integration Points**
   - GetCodeByIdTool: After line 253, before returning "None found"
   - GetNodeWorkflowsTool: After line 91, when workflows list is empty
   - Check auto_generate flag before triggering generation

4. **Silent Generation Strategy**
   - Suppress all output from creators (no progress bars)
   - Use logging.WARNING level or higher for important messages
   - Return results directly without status messages

### Architecture and Design Decisions

1. **Why Constructor Parameter vs Input Parameter**
   - Tool configuration should be deployment-time, not runtime
   - Maintains clean separation between tool config and usage
   - Prevents AI agents from accidentally disabling generation

2. **Why Default to True**
   - Most use cases benefit from auto-generation
   - Backward compatibility for callers expecting data
   - Opt-out is available for performance-critical scenarios

3. **Why Silent Operation**
   - AI agents don't need progress feedback
   - Reduces output noise in automated workflows
   - Simplifies integration with existing systems

## Implementation Plan

### Phase 1: GetCodeByIdTool Enhancement

#### Deliverables
1. Modified constructor with auto_generate parameter
2. Lazy DocumentationCreator initialization
3. Auto-generation logic in _run method
4. Error handling and logging

#### Tasks
1. Add auto_generate parameter to __init__ method
2. Create _get_documentation_creator property method
3. Implement _generate_documentation_for_node method
4. Integrate generation in _run method after missing check
5. Add comprehensive error handling

### Phase 2: GetNodeWorkflowsTool Enhancement

#### Deliverables
1. Modified constructor with auto_generate parameter
2. Lazy WorkflowCreator initialization
3. Auto-generation logic in _run method
4. Error handling and logging

#### Tasks
1. Add auto_generate parameter to __init__ method
2. Create _get_workflow_creator property method
3. Implement _generate_workflows_for_node method
4. Integrate generation in _run method after missing check
5. Add comprehensive error handling

### Phase 3: Integration Testing

#### Deliverables
1. Unit tests for both tools with auto_generate=True
2. Unit tests for both tools with auto_generate=False
3. Integration tests with real database
4. Thread safety tests

#### Tasks
1. Create test fixtures for nodes without documentation/workflows
2. Test auto-generation triggers correctly
3. Test data persistence after generation
4. Test error scenarios and graceful degradation
5. Test concurrent requests

### Risk Assessment

1. **Performance Impact**: Generation may slow down first queries
   - Mitigation: Targeted generation, caching, async options
2. **Database Lock Contention**: Concurrent generations may conflict
   - Mitigation: Proper session management, transaction isolation
3. **Memory Usage**: Creator instances may consume memory
   - Mitigation: Lazy initialization, instance cleanup

## Testing Requirements

### Unit Testing Strategy

1. **Test Constructor Parameters**
   ```python
   def test_get_code_by_id_tool_auto_generate_default():
       tool = GetCodeByIdTool(db_manager=mock_db, company_id="test")
       assert tool.auto_generate is True
   
   def test_get_code_by_id_tool_auto_generate_disabled():
       tool = GetCodeByIdTool(db_manager=mock_db, company_id="test", auto_generate=False)
       assert tool.auto_generate is False
   ```

2. **Test Generation Trigger**
   ```python
   def test_auto_generates_documentation_when_missing():
       # Setup: Node without documentation
       # Execute: Query node with auto_generate=True
       # Assert: Documentation created and returned
   ```

3. **Test Silent Operation**
   ```python
   def test_no_output_during_generation(capsys):
       # Execute generation
       # Assert no stdout/stderr output
   ```

### Integration Testing

1. Test with real Neo4j database
2. Test with concurrent requests
3. Test persistence across tool instances
4. Test with various node types (file, class, function)

### Performance Testing

1. Measure generation time for single nodes
2. Compare query time with/without auto-generation
3. Test memory usage with multiple creator instances

### Edge Cases

1. Node doesn't exist (should return error, not generate)
2. Generation fails (should return empty, not error)
3. Partial data exists (some docs, no workflows)
4. Database connection lost during generation

## Success Criteria

### Measurable Outcomes

1. **Functionality**: Both tools successfully auto-generate missing data when auto_generate=True
2. **Performance**: Generation completes within 5 seconds for typical nodes
3. **Reliability**: 100% of generation failures handled gracefully
4. **Persistence**: 100% of generated data retrievable in subsequent queries

### Quality Metrics

1. **Code Coverage**: >90% test coverage for modified code
2. **Error Rate**: <1% generation failures in production
3. **Response Time**: <10% increase in average query time
4. **Memory Usage**: <50MB additional memory per tool instance

### Performance Benchmarks

1. Single node documentation generation: <3 seconds
2. Single node workflow discovery: <2 seconds
3. Subsequent queries (cached): <100ms
4. Concurrent request handling: 10+ simultaneous

### User Satisfaction Metrics

1. AI agents receive complete data in single query
2. No manual intervention required for missing data
3. Consistent behavior across both tools
4. Clear logging for debugging issues

## Implementation Steps

### Step 1: Create GitHub Issue ✓
Issue #284 already exists: "Feature: Add Auto-Calculation Capabilities to GetCodeByIdTool and GetNodeWorkflowsTool"

### Step 2: Create Feature Branch
```bash
git checkout -b feature/auto-calculation-tools-284
```

### Step 3: Research and Planning

#### Research Tasks
1. Analyze DocumentationCreator initialization requirements
2. Analyze WorkflowCreator initialization requirements
3. Identify minimal parameters for targeted generation
4. Review existing error handling patterns in tools

### Step 4: Implement GetCodeByIdTool Changes

#### 4.1 Modify Constructor
```python
def __init__(
    self,
    db_manager: Any,
    company_id: str,
    handle_validation_error: bool = False,
    auto_generate: bool = True,  # NEW PARAMETER
):
    super().__init__(
        db_manager=db_manager,
        company_id=company_id,
        handle_validation_error=handle_validation_error,
    )
    self.auto_generate = auto_generate
    self._documentation_creator = DocumentationCreator(
            db_manager=self.db_manager,
            agent_caller=LLMProvider(),  # Default LLM provider
            graph_environment=GraphEnvironment(),  # Default environment
            company_id=self.company_id,
            repo_id=self.company_id,  # Use company_id as repo_id
            max_workers=1,  # Single thread for targeted generation
            overwrite_documentation=False
        )
```

#### 4.2 Add Generation Method
```python
def _generate_documentation_for_node(self, node_id: str) -> Optional[list[dict]]:
    """Generate documentation for a specific node."""
    try:
        if not self.auto_generate:
            return None
            
        logger.debug(f"Auto-generating documentation for node {node_id}")
        
        # Get node path for targeted generation
        node_info = self.db_manager.get_node_by_id_v2(
            node_id=node_id, 
            company_id=self.company_id
        )
        
        if not node_info:
            return None
            
        # Generate documentation for this specific node
        result = self.documentation_creator.create_documentation(
            target_paths=[node_info.node_name],
            save_to_database=True,
            generate_embeddings=False
        )
        
        # Query for the newly created documentation
        # Return documentation nodes
        return self._fetch_documentation_nodes(node_id)
        
    except Exception as e:
        logger.error(f"Failed to auto-generate documentation: {e}")
        return None
```

#### 4.4 Integrate in _run Method
Modify the documentation section (around line 234-255):
```python
# Display documentation if available
if node_result.documentation_nodes:
    # Existing code for displaying documentation
    ...
else:
    # NEW: Try auto-generation if enabled
    if self.auto_generate:
        generated_docs = self._generate_documentation_for_node(node_id)
        if generated_docs:
            node_result.documentation_nodes = generated_docs
            # Display the generated documentation
            output += "📚 DOCUMENTATION (auto-generated):\n"
            # ... format and display docs
        else:
            output += "📚 DOCUMENTATION: None found (generation attempted)\n"
    else:
        output += "📚 DOCUMENTATION: None found\n"
```

### Step 5: Implement GetNodeWorkflowsTool Changes

#### 5.1 Modify Constructor
```python
def __init__(
    self,
    db_manager: Any,
    company_id: str,
    handle_validation_error: bool = False,
    auto_generate: bool = True,  # NEW PARAMETER
):
    super().__init__(
        db_manager=db_manager,
        company_id=company_id,
        handle_validation_error=handle_validation_error,
    )
    self.auto_generate = auto_generate
    self._workflow_creator = WorkflowCreator(
            db_manager=self.db_manager,
            graph_environment=GraphEnvironment(),
            company_id=self.company_id,
            repo_id=self.company_id  # Use company_id as repo_id
        )
```

#### 5.2 Add Generation Method
```python
def _generate_workflows_for_node(self, node_id: str, node_path: str) -> list[dict[str, Any]]:
    """Generate workflows for a specific node."""
    try:
        if not self.auto_generate:
            return []
            
        logger.debug(f"Auto-generating workflows for node {node_id}")
        
        # Generate workflows targeting this specific node
        result = self.workflow_creator.discover_workflows(
            node_path=node_path,
            max_depth=20,
            save_to_database=True
        )
        
        if result.error:
            logger.error(f"Workflow generation error: {result.error}")
            return []
            
        # Re-query for workflows after generation
        return self._get_workflows_with_chains(node_id)
        
    except Exception as e:
        logger.error(f"Failed to auto-generate workflows: {e}")
        return []
```

#### 5.4 Integrate in _run Method
Modify the workflow retrieval section (around line 91):
```python
# Get all workflows and their execution chains
workflows = self._get_workflows_with_chains(node_id)

if not workflows and self.auto_generate:
    # Try to generate workflows
    node_path = node_info.get('node_path') or node_info.get('path', '')
    if node_path:
        workflows = self._generate_workflows_for_node(node_id, node_path)
        
if not workflows:
    # Show warning (existing code)
    ...
```

### Step 6: Write Unit Tests

Create test files:
- `tests/unit/tools/test_get_code_by_id_auto_generate.py`
- `tests/unit/tools/test_get_node_workflows_auto_generate.py`

### Step 7: Write Integration Tests

Read the @docs/testing_guide.md

Create integration test:
- `tests/integration/test_tools_auto_generation.py`

### Step 8: Update Documentation

Update tool documentation to describe auto_generate parameter and behavior.

### Step 9: Create Pull Request

- Commit the way the user likes it
- Make a PR

### Step 10: Code Review

Invoke code-reviewer sub-agent to review the implementation for:
- Correctness of lazy initialization
- Thread safety of generation
- Error handling completeness
- Test coverage adequacy

## Example Usage Patterns

### Default Usage (Auto-Generation Enabled)
```python
# Tool automatically generates missing data
tool = GetCodeByIdTool(
    db_manager=neo4j_manager,
    company_id="my_company"
)
result = tool._run("abc123...")  # Will auto-generate docs if missing
```

### Performance-Critical Usage (Auto-Generation Disabled)
```python
# Tool returns quickly without generation
tool = GetCodeByIdTool(
    db_manager=neo4j_manager,
    company_id="my_company",
    auto_generate=False
)
result = tool._run("abc123...")  # Returns None if docs missing
```

### Workflow Tool Usage
```python
# Automatically discover workflows
workflow_tool = GetNodeWorkflowsTool(
    db_manager=neo4j_manager,
    company_id="my_company",
    auto_generate=True
)
workflows = workflow_tool._run("node123...")  # Discovers workflows if missing
```

## Notes for Implementation

1. **LLMProvider Initialization**: May need to handle API keys and configuration for DocumentationCreator
2. **GraphEnvironment**: Might need proper initialization with repository context
3. **Database Sessions**: Ensure proper session management to avoid connection leaks
4. **Logging Levels**: Use DEBUG for detailed traces, INFO for major operations, ERROR for failures
5. **Import Statements**: Use lazy imports inside methods to avoid circular dependencies
6. **Type Hints**: Maintain full type annotations per project standards

## Summary

This implementation adds intelligent auto-generation capabilities to two core Blarify tools, transforming them from passive query tools into active, self-healing components that ensure AI agents always receive complete data. The solution is backward-compatible, performant, and maintains the silent operation paradigm required for AI agent usage. The implementation follows Blarify's established patterns while adding significant value through automated data generation and persistence.