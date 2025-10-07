# Testing Guide: Optional repo_id Feature

## Overview

This document describes the test coverage for the optional `repo_id` feature that enables entity-wide and repo-specific scoping.

## Test Files Created

### 1. Integration Tests
**File**: `tests/integration/test_optional_repo_id.py`

Comprehensive integration tests covering:

#### Test Cases

1. **`test_entity_wide_query_returns_all_repos`**
   - Creates data in 2 different repos under same entity
   - Queries with entity-wide manager (repo_id=None)
   - Verifies results include data from both repos
   - Compares with repo-specific queries

2. **`test_repo_specific_query_filters_correctly`**
   - Gets a node from repo1
   - Queries with repo1 manager → should find it
   - Queries with repo2 manager → should NOT find it
   - Queries with entity manager → should find it
   - Validates proper filtering

3. **`test_mutation_requires_repo_id`**
   - Attempts `create_nodes()` with entity-wide manager → should raise ValueError
   - Attempts `create_edges()` with entity-wide manager → should raise ValueError
   - Attempts `detatch_delete_nodes_with_path()` with entity-wide manager → should raise ValueError
   - Validates safety constraints

4. **`test_query_method_with_optional_repo_id`**
   - Tests query() parameter injection
   - Compares entity-wide vs repo-specific counts
   - Validates proper WHERE clause filtering

5. **`test_entity_isolation_is_maintained`**
   - Creates manager with different entity_id
   - Verifies no data leakage across entities
   - Ensures entity_id is always enforced

6. **`test_backward_compatibility_with_repo_id`**
   - Tests old-style initialization with explicit repo_id
   - Verifies existing code still works
   - Validates backward compatibility

7. **`test_tool_descriptions_mention_scope`**
   - Checks all tool descriptions mention scope
   - Validates user-facing documentation

### 2. Manual Test Script
**File**: `test_optional_repo_manual.py`

Standalone script for manual validation:

1. Creates manager with repo_id (existing behavior)
2. Creates manager without repo_id (new behavior)
3. Validates mutation safety (should reject entity-wide)
4. Verifies query parameter injection

**Usage**:
```bash
python test_optional_repo_manual.py
```

## Running Tests

### Prerequisites
- Python 3.11+ (LiteralString support)
- Neo4j running (local or Docker)
- Poetry environment set up

### Run Integration Tests
```bash
# Run all optional repo_id tests
poetry run pytest tests/integration/test_optional_repo_id.py -v

# Run specific test
poetry run pytest tests/integration/test_optional_repo_id.py::TestOptionalRepoId::test_entity_wide_query_returns_all_repos -v

# Run with Neo4j integration marker
poetry run pytest -m neo4j_integration tests/integration/test_optional_repo_id.py -v
```

### Run Manual Tests
```bash
python test_optional_repo_manual.py
```

## Test Coverage

### Query Operations (✅ Covered)
- [x] Entity-wide queries with repo_id=None
- [x] Repo-specific queries with repo_id set
- [x] Query parameter injection
- [x] WHERE clause conditional filtering
- [x] Tool integration with optional repo_id

### Mutation Operations (✅ Covered)
- [x] create_nodes() requires repo_id
- [x] create_edges() requires repo_id
- [x] detatch_delete_nodes_with_path() requires repo_id
- [x] save_graph() requires repo_id (calls create methods)

### Security & Isolation (✅ Covered)
- [x] entity_id always enforced
- [x] No cross-entity data leakage
- [x] Proper repo filtering when repo_id provided
- [x] Entity-wide scope when repo_id=None

### Backward Compatibility (✅ Covered)
- [x] Existing code with repo_id still works
- [x] No breaking changes to API
- [x] Tool behavior unchanged for repo-specific usage

## Expected Test Results

### Successful Test Output
```
✅ Entity-wide query returns data from multiple repos
✅ Repo-specific query filters correctly
✅ Mutations reject entity-wide scope with clear errors
✅ Query parameter injection works correctly
✅ Entity isolation is maintained
✅ Backward compatibility preserved
✅ Tool descriptions document scope
```

### Common Test Failures & Fixes

#### ImportError: cannot import name 'LiteralString'
**Cause**: Python 3.10 doesn't support LiteralString
**Fix**: Use Python 3.11+
```bash
poetry env use python3.11
poetry install
```

#### Neo4j Connection Errors
**Cause**: Neo4j not running or wrong credentials
**Fix**: Start Neo4j and check connection settings
```bash
docker run -d -p 7687:7687 -p 7474:7474 -e NEO4J_AUTH=neo4j/password neo4j:latest
```

#### Test Data Isolation Issues
**Cause**: Previous test data not cleaned up
**Fix**: Tests use unique entity_id and repo_id per run via fixtures

## Performance Testing

### Recommended Performance Tests (TODO)

1. **Large Dataset Test**
   - Entity with 10+ repos
   - 100K+ nodes per repo
   - Compare query times: entity-wide vs repo-specific

2. **Index Effectiveness**
   - Verify entityId index is used
   - Test with and without composite (entityId, repoId) index
   - Measure query performance difference

3. **Concurrent Queries**
   - Multiple entity-wide queries in parallel
   - Multiple repo-specific queries in parallel
   - Mixed workload

### Performance Benchmarks

```python
# TODO: Add performance benchmarks
def test_entity_wide_query_performance():
    # Compare entity-wide vs repo-specific query times
    # Assert entity-wide is < 2x slower than repo-specific
    pass
```

## Test Maintenance

### Adding New Query Functions
When adding new query functions to `queries.py`:

1. Use the pattern: `MATCH (n:NODE {entityId: $entity_id}) WHERE ($repo_id IS NULL OR n.repoId = $repo_id)`
2. Add test case to `test_optional_repo_id.py`
3. Verify both entity-wide and repo-specific behavior

### Adding New Tools
When adding new tools to `blarify/tools/`:

1. Accept `db_manager: AbstractDbManager` parameter
2. Add scope description: "Scope: Searches within entity (org/company), optionally filtered by repo if db_manager has repo_id set."
3. Add test case verifying scope behavior

### Adding Mutation Methods
When adding new mutation methods to `Neo4jManager`:

1. Add validation: `if self.repo_id is None: raise ValueError("repo_id is required for ...")`
2. Add test case to verify ValueError is raised
3. Document in method docstring

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run Optional Repo ID Tests
  run: |
    poetry run pytest tests/integration/test_optional_repo_id.py -v --cov=blarify/repositories/graph_db_manager --cov-report=xml
```

### Pre-commit Hook
```bash
# Run tests before commit
poetry run pytest tests/integration/test_optional_repo_id.py -v
```

## Documentation References

- Implementation Plan: `docs/implementation_plans/repo_id_optional_plan.md`
- API Reference: `docs/api-reference.md`
- Tools Documentation: `docs/tools.md`

## Summary

✅ **Comprehensive test coverage** for optional repo_id feature
✅ **Integration tests** validate entity-wide and repo-specific behavior
✅ **Security tests** ensure entity isolation and mutation safety
✅ **Backward compatibility** tests verify no breaking changes
✅ **Manual test script** for quick validation

**Next Steps**:
1. Run tests with Python 3.11+
2. Add performance benchmarks for large datasets
3. Consider composite index for production workloads
