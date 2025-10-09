# TDD Implementation Plan: Hierarchical Context Completion for Incremental Documentation

## Problem Statement

When using `create_documentation(target_paths=["helpers.py"])`, the system only documents nodes in the **execution path** from entry points, missing sibling methods and parent containers.

**Example File System**:
```
project/
├── helpers.py          # Target file for incremental update
│   └── Helper (class)
│       ├── validate(data)    # Called by main()
│       └── format(data)      # NOT called (sibling)
│
└── main.py
    └── main()          # Entry point - only calls Helper.validate()
```

**Current Behavior** when updating `helpers.py`:
- ✅ Documents: `Helper.validate()` (in execution path from main)
- ❌ Missing: `Helper.format()` (sibling method in same class)
- ❌ Missing: `Helper` class (parent container)
- ❌ Missing: `helpers.py` file (root file)

**Expected Behavior**:
When targeting `helpers.py` for documentation, ALL nodes in that file should be documented (complete hierarchy), not just those in the execution path from entry points.

---

## 1. Test Modification

### Location
`tests/integration/test_graphbuilder_incremental_update.py:649`

### Changes Required
- **Replace**: `test_incremental_update_updates_caller_documentation_when_file_changes`
- **With**: `test_incremental_update_documents_complete_hierarchy_when_file_changes`

### Test Structure
1. Create `helpers.py` with `Helper` class containing two methods: `validate()` and `format()`
2. Create `main.py` that only calls `Helper.validate()` (NOT `format()`)
3. Build initial graph with documentation
4. Modify `helpers.py` (change validate implementation)
5. Run incremental_update targeting only `helpers.py`

### Critical Assertions
The test must verify documentation exists for:
- `helpers.py` file (root)
- `Helper` class (parent)
- `Helper.validate()` method (in execution path)
- **`Helper.format()` method** (sibling - NOT in execution path) ← KEY ASSERTION

The last assertion will fail with current code, demonstrating the bug.

### Key Test Difference
Unlike the old test which verified callers get documented, this test verifies that **ALL hierarchical nodes in the target file** get documented, even if they're not called.

---

## 2. Expected Test Failure

**Failing Assertion**: Checking `format()` has documentation

**Why It Fails**:
1. Current flow: `_create_targeted_documentation()` discovers entry points that call into `helpers.py`
2. Finds `main()` as entry point
3. `BottomUpBatchProcessor` processes execution path: `main()` → `validate()`
4. May document parents (`Helper`, `helpers.py`) as containers of `validate()`
5. **Never discovers** `format()` because it's not in any execution path

**Expected Error**:
```
AssertionError: format() must have documentation even though NOT called!
Expected: 1 documentation node
Got: 0 documentation nodes
```

---

## 3. Implementation Strategy: Two-Phase Processing

### Phase 1 (Existing): Process Execution Paths
- Find entry points that reach `target_paths`
- Process execution path using `BottomUpBatchProcessor`
- **Result**: Documents `main()`, `validate()`, possibly `Helper` and `helpers.py` as parents

### Phase 2 (New): Complete Hierarchical Context
- Query all nodes under `target_paths` using hierarchical relationships (CONTAINS, FUNCTION_DEFINITION, CLASS_DEFINITION)
- Find nodes NOT processed in Phase 1
- Mark them by resetting `processing_status = NULL`
- Re-run `BottomUpBatchProcessor` on target files
- **Result**: Documents `format()` and any other missing siblings

### Why Mark Nodes After Phase 1?

**The marking happens BETWEEN phases**:

1. **After Phase 1 completes**: Some nodes (like `format()`) were never discovered via the execution path, so they either have:
   - No `processing_run_id` field at all, OR
   - A different `processing_run_id` from a previous run

2. **Discovering gaps**: We query for ALL hierarchical nodes under `target_paths` and compare their `processing_run_id` against the current run's ID

3. **Identifying what to process**:
   - Nodes FROM Phase 1: `processing_run_id = <current_shared_id>` (already documented)
   - Nodes NOT from Phase 1: `processing_run_id != <current_shared_id>` (need documentation)

4. **Marking for processing**: For gap nodes, reset `processing_status = NULL` and `processing_run_id = NULL`
   - This makes them eligible for `BottomUpBatchProcessor` to pick up
   - The batch processor's queries look for nodes with `NULL` or `pending` status

5. **Phase 2 processes them**: When we re-run the batch processor on the target file, it finds these NULL-status nodes and documents them

**Key Insight**: We use a shared `processing_run_id` across both phases. This allows us to distinguish between "already processed in THIS run" vs "not processed yet".

---

## 4. Implementation Steps

### Step 1: Create Hierarchical Node Discovery Query

**File**: `blarify/repositories/graph_db_manager/queries.py`
**Location**: After `find_entry_points_for_files_paths()`

**Add Two Functions**:

1. **`get_all_hierarchical_nodes_under_paths_query()` -> LiteralString**
   - Returns Cypher query that finds file nodes matching `file_paths`
   - Traverses via `FUNCTION_DEFINITION|CLASS_DEFINITION*1..` relationships
   - Returns all descendant nodes (file, classes, methods, nested classes)
   - Uses DISTINCT to avoid duplicates

2. **`get_all_hierarchical_nodes_under_paths(db_manager, file_paths)` -> List[Dict]**
   - Executes the query with proper parameters
   - Formats results into list of dicts with: id, name, labels, path, node_path
   - Logs number of nodes found

**Note**: Only traverse HIERARCHICAL relationships, not CALLS

---

### Step 2: Create Hierarchical Completion Method

**File**: `blarify/documentation/documentation_creator.py`
**Location**: After `_discover_entry_points()` method

**Add Method**: `_complete_hierarchical_context(self, target_paths: List[str], processing_run_id: str) -> int`

**Purpose**: Mark all hierarchical nodes under target_paths that weren't processed in Phase 1

**Logic**:
1. Call `get_all_hierarchical_nodes_under_paths()` to get all nodes in hierarchy
2. For each node, run an embedded query to check and mark:
   - Check: `WHERE (n.processing_status IS NULL OR n.processing_run_id <> $run_id)`
   - Mark: `SET n.processing_status = NULL, n.processing_run_id = NULL`
   - Skip: `AND NOT n:DOCUMENTATION`
3. Count and return number of marked nodes

**Returns**: Number of nodes marked for completion

---

### Step 3: Integrate Two-Phase Processing

**File**: `blarify/documentation/documentation_creator.py`
**Method**: `_create_targeted_documentation()` (around line 230)

**Modifications**:
1. **At start**: Generate `processing_run_id = str(uuid.uuid4())`
2. **Phase 1**: Pass `processing_run_id` to all `BottomUpBatchProcessor` instances when processing entry points
3. **Between phases**: Call `marked_count = self._complete_hierarchical_context(target_paths, processing_run_id)`
4. **Phase 2**: If `marked_count > 0`, create new processors for each target_path with same `processing_run_id`
5. **Aggregate**: Collect results from both phases

**Import Addition**: Add `import uuid` at top of file

---

### Step 4: Update BottomUpBatchProcessor Constructor

**File**: `blarify/documentation/utils/bottom_up_batch_processor.py`
**Location**: Constructor `__init__` (around line 95)

**Check if `processing_run_id` exists**:
- If it's auto-generated in constructor, modify to accept optional parameter
- Add: `processing_run_id: Optional[str] = None`
- Use: `self.processing_run_id = processing_run_id or str(uuid.uuid4())`

---

### Step 5: Update Imports

**File**: `blarify/documentation/documentation_creator.py`
**Location**: Import section (around lines 13-26)

**Add**:
```python
import uuid  # Add if not present

from ..repositories.graph_db_manager.queries import (
    # ... existing imports ...
    get_all_hierarchical_nodes_under_paths,  # NEW
    get_node_by_path,  # NEW (if not already imported)
)
```

---

### Step 6: Run Tests and Verify

**Before implementation**:
```bash
poetry run pytest tests/integration/test_graphbuilder_incremental_update.py::TestGraphBuilderIncrementalUpdate::test_incremental_update_documents_complete_hierarchy_when_file_changes -v
# Should FAIL
```

**After implementation**:
```bash
# Should PASS
poetry run pytest tests/integration/test_graphbuilder_incremental_update.py::TestGraphBuilderIncrementalUpdate::test_incremental_update_documents_complete_hierarchy_when_file_changes -v

# Check no regressions
poetry run pytest tests/integration/test_graphbuilder_incremental_update.py -v

# Full test suite
poetry run pytest tests/

# Type checking
poetry run pyright blarify/documentation/ blarify/repositories/graph_db_manager/queries.py

# Linting
poetry run ruff check blarify/documentation/ blarify/repositories/graph_db_manager/queries.py
```

---

## 5. Algorithm Overview

```
complete_hierarchical_documentation(target_paths):
    // Step 1: Initialize with shared run ID
    processing_run_id = generate_uuid()

    // Step 2: Phase 1 - Process execution paths
    entry_points = discover_entry_points(target_paths)
    for entry_point in entry_points:
        process_node(entry_point, run_id=processing_run_id)
        // Nodes in execution path now marked with processing_run_id

    // Step 3: Discover hierarchical gaps
    all_nodes = query_hierarchical_nodes(target_paths)

    marked = 0
    for node in all_nodes:
        if node.processing_run_id != processing_run_id:
            // This node wasn't in execution path - mark it
            reset_processing_status(node)
            marked++

    // Step 4: Phase 2 - Process gaps
    if marked > 0:
        for target_path in target_paths:
            process_node(target_path, run_id=processing_run_id)
            // Picks up NULL-status nodes and documents them

    return results
```

---

## 6. Edge Cases to Handle

### 1. Target Path is a Class (not a File)
**Example**: `target_paths = ["helpers.py::Helper"]`
**Solution**: Modify query to support both FILE and CLASS labels

### 2. Target Path is a Method
**Example**: `target_paths = ["helpers.py::Helper::validate"]`
**Solution**: Traverse UP to find parent file/class, document entire hierarchy

### 3. Hierarchy Contains Cycles
**Solution**: No changes needed - existing cycle detection in BottomUpBatchProcessor handles this

### 4. Nodes Already Have Documentation
**Solution**: `overwrite_documentation` flag already controls this

### 5. Target Path is a Folder
**Example**: `target_paths = ["src/helpers/"]`
**Solution**: Modify query to handle FOLDER nodes, traverse to all contained files

### 6. Large Hierarchies (1000+ nodes)
**Solution**: Process target_paths one at a time, use batching for node marking

---

## 7. Success Criteria

- [ ] New test passes
- [ ] Test demonstrates: `format()` method has documentation (sibling not in execution path)
- [ ] Parent classes documented (Helper class)
- [ ] Root files documented (helpers.py)
- [ ] No regression in existing tests
- [ ] Code passes `pyright` type checking
- [ ] Code passes `ruff` linting
- [ ] Logs show "Phase 1" and "Phase 2" execution messages

---

## 8. Implementation Checklist

### Query Implementation
- [ ] Add `get_all_hierarchical_nodes_under_paths_query()` to queries.py
- [ ] Add `get_all_hierarchical_nodes_under_paths()` helper function
- [ ] Test query returns file, class, and all methods for a given file path

### Method Implementation
- [ ] Add `_complete_hierarchical_context()` to DocumentationCreator
- [ ] Verify marking logic correctly identifies gaps

### Integration
- [ ] Modify `_create_targeted_documentation()` for two-phase approach
- [ ] Add shared `processing_run_id` generation
- [ ] Pass `processing_run_id` to all BottomUpBatchProcessor instances
- [ ] Update BottomUpBatchProcessor constructor to accept `processing_run_id`
- [ ] Add imports: `uuid`, query functions

### Testing
- [ ] Replace old test with new test
- [ ] Verify test FAILS before implementation
- [ ] Implement all changes
- [ ] Verify test PASSES after implementation
- [ ] Run full test suite (no regressions)
- [ ] Run pyright and ruff checks

---

## Estimated Effort

- **Development**: 4-6 hours
- **Testing & Verification**: 2 hours
- **Total**: 6-8 hours

**Risk Level**: Low (minimal changes, leverages existing infrastructure)
**Value**: High (fixes critical gap in incremental documentation)