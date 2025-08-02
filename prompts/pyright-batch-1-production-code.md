# Pyright Batch 1: Production Code Fixes

## Objective
Fix all remaining pyright type errors in production code files to achieve zero errors.

## Target Files
Focus on these high-error production files:
- `blarify/project_graph_diff_creator.py` (29 errors)
- `blarify/project_graph_creator.py` (21 errors)  
- `blarify/stats/complexity.py` (8 errors)
- All other production files in `blarify/` directory (excluding tests/)

## Tasks

### Phase 1: High-Impact Files
1. **Fix project_graph_diff_creator.py**:
   - Add missing type annotations for return types
   - Fix Optional parameter handling
   - Add proper generic type arguments

2. **Fix project_graph_creator.py**:
   - Fix unknown return types
   - Add parameter type annotations
   - Fix Optional/None handling

3. **Fix stats/complexity.py**:
   - Add missing type annotations
   - Fix unknown variable types

### Phase 2: Remaining Production Files
4. Systematically fix all remaining production code pyright errors
5. Focus on:
   - Missing parameter type annotations
   - Unknown return types
   - Optional member access issues
   - Generic type arguments

## Acceptance Criteria
- All production code files (excluding tests/) have zero pyright errors
- No changes to test files
- All changes maintain backwards compatibility
- Regular commits with progress updates

## Strategy
- Use `pyright blarify/ --outputjson` to track progress
- Fix highest-error files first for maximum impact
- Apply consistent patterns across similar issues
- Test each fix by running pyright on affected files