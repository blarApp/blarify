# Pyright Batch 3: Core Test Files

## Objective
Fix pyright type errors in core test files for graph, filesystem, and LLM functionality.

## Target Files
Focus on these core test files:
- `tests/test_code_complexity.py` (28 errors)
- `tests/test_filesystem_operations.py` (27 errors)
- `tests/test_description_generator.py` (24 errors)
- `tests/test_lsp_helper.py` (21 errors)

## Tasks

### Phase 1: Core Functionality Tests
1. **Fix test_code_complexity.py**:
   - Add missing parameter type annotations
   - Fix test setup method types
   - Add proper mock object type hints

2. **Fix test_filesystem_operations.py**:
   - Add missing parameter types to test methods
   - Fix filesystem mock type annotations
   - Add proper file operation type hints

3. **Fix test_description_generator.py**:
   - Add missing parameter type annotations
   - Fix LLM mock object types
   - Add proper generator method type hints

4. **Fix test_lsp_helper.py**:
   - Add missing parameter types
   - Fix LSP server mock types
   - Add proper helper method type hints

## Acceptance Criteria
- All targeted test files have zero pyright errors
- No changes to production code  
- Test functionality preserved
- Regular commits with progress updates

## Strategy
- Use `pyright tests/test_code_complexity.py tests/test_filesystem_operations.py tests/test_description_generator.py tests/test_lsp_helper.py --outputjson` to track progress
- Apply consistent typing patterns for test methods
- Focus on parameter type annotations first
- Fix mock object types systematically