# Pyright Batch 4: Remaining Test Files

## Objective
Fix pyright type errors in all remaining test files to achieve zero errors.

## Target Files
Focus on remaining test files:
- `tests/test_graph_comprehensive.py` (15 errors)
- `tests/test_documentation_extraction.py` (14 errors)
- `tests/test_graph_operations.py` (13 errors)
- `tests/test_llm_description_nodes.py` (12 errors)
- `tests/test_filesystem_nodes.py` (12 errors)
- All other remaining test files with fewer errors

## Tasks

### Phase 1: Medium-Error Test Files
1. **Fix test_graph_comprehensive.py**:
   - Add missing parameter type annotations
   - Fix graph mock object types
   - Add proper node type hints

2. **Fix test_documentation_extraction.py**:
   - Add missing parameter types
   - Fix documentation mock types
   - Add proper extraction method type hints

3. **Fix test_graph_operations.py**:
   - Add missing parameter type annotations
   - Fix graph operation mock types
   - Add proper operation method type hints

### Phase 2: Final Cleanup
4. **Fix remaining test files**:
   - test_llm_description_nodes.py
   - test_filesystem_nodes.py
   - test_graph_fixed.py
   - test_graph_simple.py
   - test_documentation_nodes.py
   - test_conditional_imports_integration.py
   - Any other remaining test files

## Acceptance Criteria
- ALL test files have zero pyright errors
- Complete test suite type safety achieved
- No changes to production code
- Test functionality preserved
- Final verification that total error count is 0

## Strategy
- Use `pyright tests/ --outputjson` to track overall progress
- Apply systematic parameter type annotations
- Use consistent patterns from previous batches
- Final verification: `pyright --outputjson` shows 0 errors total