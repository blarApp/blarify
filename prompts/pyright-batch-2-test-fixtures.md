# Pyright Batch 2: Test Fixtures and High-Error Test Files

## Objective
Fix pyright type errors in test fixtures and the highest-error test files.

## Target Files
Focus on these high-error test files:
- `tests/test_tree_sitter_helper.py` (54 errors)
- `tests/test_gitignore_integration.py` (32 errors)
- `tests/test_project_file_explorer.py` (31 errors)
- `tests/fixtures/node_factories.py` (17 errors)

## Tasks

### Phase 1: Test Fixtures
1. **Fix tests/fixtures/node_factories.py**:
   - Add missing parameter type annotations
   - Fix mock object type annotations
   - Add proper return type hints

### Phase 2: High-Error Test Files
2. **Fix test_tree_sitter_helper.py**:
   - Add missing parameter types to test methods
   - Fix mock object type annotations
   - Add proper fixture type hints

3. **Fix test_gitignore_integration.py**:
   - Add missing parameter type annotations
   - Fix test method signatures
   - Add proper type hints for test data

4. **Fix test_project_file_explorer.py**:
   - Add missing parameter types
   - Fix test setup method annotations
   - Add proper assertion type hints

## Acceptance Criteria
- All targeted test files have zero pyright errors
- No changes to production code
- Test functionality preserved
- Regular commits with progress updates

## Strategy
- Use `pyright tests/test_tree_sitter_helper.py tests/test_gitignore_integration.py tests/test_project_file_explorer.py tests/fixtures/node_factories.py --outputjson` to track progress
- Focus on systematic parameter type additions
- Use consistent typing patterns for test methods
- Fix highest-error files first for maximum impact