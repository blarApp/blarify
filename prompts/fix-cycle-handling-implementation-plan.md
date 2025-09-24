# Implementation Plan: Fix Cycle Handling in DocumentationCreator

## Problem Statement

The bottom-up batch processor gets stuck when processing functions with cycles because the query `get_processable_nodes_with_descriptions_query` waits for ALL children (including CALLS relationships) to be completed before processing a node. In a cycle (A→B→C→A), no function can ever be marked as processable since each waits for others in the cycle to complete first.

## Solution Overview

1. Process all leaf nodes first (current implementation works fine)
2. Keep trying to process parent nodes with completed children
3. When no more parents can be processed but pending nodes remain, those remaining FUNCTION nodes must be in cycles
4. Process all remaining FUNCTION nodes as regular functions with whatever child descriptions are available
5. Continue processing parents (since completing these functions may unblock their parent classes/files)
6. Repeat steps 2-5 until no pending nodes remain

## Detailed Implementation Steps

### Step 1: Add New Query for Remaining Pending Functions

**File:** `blarify/documentation/queries/batch_processing_queries.py`

Add a new query that gets pending FUNCTION nodes without checking if their children are completed:

```python
def get_remaining_pending_functions_query() -> LiteralString:
    """
    Get all pending FUNCTION nodes with their child descriptions.

    This query is used when normal processing is blocked (likely due to cycles).
    It retrieves pending FUNCTION nodes along with descriptions from any completed children,
    without requiring ALL children to be completed.

    Key difference from get_processable_nodes_with_descriptions_query:
    - Does NOT check if all children are completed
    - Only processes FUNCTION nodes
    - Returns same structure (hier_descriptions and call_descriptions)
    """
    return """
    MATCH (root:NODE {node_id: $root_node_id})
    MATCH (root)-[:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION|CALL*0..]->(n:FUNCTION)
    WHERE (n.processing_status IS NULL OR n.processing_run_id <> $run_id) AND NOT n:DOCUMENTATION

    // Get hierarchy children (if any) - don't check completion status
    OPTIONAL MATCH (n)-[:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION]->(hier_child:NODE)
    WITH n, collect(DISTINCT hier_child) as hier_children

    // Get call children (if any) - don't check completion status
    OPTIONAL MATCH (n)-[:CALLS]->(call_child:NODE)
    WITH n, hier_children, collect(DISTINCT call_child) as call_children

    // Get descriptions from completed children only
    OPTIONAL MATCH (hier_doc:DOCUMENTATION)-[:DESCRIBES]->(hier_child)
    WHERE hier_child IN hier_children
      AND hier_child.processing_status = 'completed'
      AND hier_child.processing_run_id = $run_id
    WITH n, call_children,
         collect(DISTINCT {
             id: hier_child.node_id,
             name: hier_child.name,
             labels: labels(hier_child),
             path: hier_child.path,
             description: hier_doc.content
         }) as hier_descriptions

    OPTIONAL MATCH (call_doc:DOCUMENTATION)-[:DESCRIBES]->(call_child)
    WHERE call_child IN call_children
      AND call_child.processing_status = 'completed'
      AND call_child.processing_run_id = $run_id
    WITH n, hier_descriptions,
         collect(DISTINCT {
             id: call_child.node_id,
             name: call_child.name,
             labels: labels(call_child),
             path: call_child.path,
             description: call_doc.content
         }) as call_descriptions

    WITH n, hier_descriptions, call_descriptions
    LIMIT $batch_size

    SET n.processing_status = 'in_progress',
        n.processing_run_id = $run_id

    RETURN n.node_id as id,
           n.name as name,
           labels(n) as labels,
           n.path as path,
           n.start_line as start_line,
           n.end_line as end_line,
           coalesce(n.text, '') as content,
           hier_descriptions,
           call_descriptions
    """
```

### Step 2: Modify Bottom-Up Batch Processor

**File:** `blarify/documentation/utils/bottom_up_batch_processor.py`

#### 2.1: Update imports

Remove cycle-related imports and add the new query:

```python
# Remove these imports:
# from blarify.agents.prompt_templates import (
#     FUNCTION_WITH_CYCLE_ANALYSIS_TEMPLATE,  # Remove this
# )
# from blarify.repositories.graph_db_manager.queries import (
#     detect_function_cycles,  # Remove this
# )

# Add this import:
from blarify.documentation.queries.batch_processing_queries import (
    get_child_descriptions_query,
    get_leaf_nodes_under_node_query,
    get_remaining_pending_functions_query,  # Add this
)
```

#### 2.2: Modify `_process_node_query_based` method

Replace the existing method with the new algorithm:

```python
def _process_node_query_based(self, root_node: NodeWithContentDto) -> int:
    """Process using database queries without memory storage."""

    total_processed = 0
    max_iterations = 1000  # Safety limit

    # Phase 1: Process all leaf nodes first
    iteration = 0
    while iteration < max_iterations:
        iteration += 1

        # Try to process leaf nodes first
        leaf_count = self._process_leaf_batch(root_node)
        if leaf_count == 0:
            break
        total_processed += leaf_count
        logger.debug(f"Processed {leaf_count} leaf nodes in iteration {iteration}")

    # Phase 2: Process parent nodes and handle cycles
    iteration = 0
    consecutive_stuck_iterations = 0

    while iteration < max_iterations:
        iteration += 1

        # Try to process parent nodes with completed children
        parent_count = self._process_parent_batch(root_node)
        if parent_count > 0:
            total_processed += parent_count
            consecutive_stuck_iterations = 0  # Reset stuck counter
            logger.debug(f"Processed {parent_count} parent nodes in iteration {iteration}")
            continue

        # Check if any nodes remain
        if not self._has_pending_nodes(root_node):
            logger.debug("No pending nodes remaining")
            break

        # If we're stuck (no parents processable but nodes remain),
        # process remaining functions (likely in cycles)
        consecutive_stuck_iterations += 1

        if consecutive_stuck_iterations >= 2:
            # Process remaining functions with whatever descriptions are available
            logger.info("Detected potential cycles - processing remaining functions")
            remaining_count = self._process_remaining_functions_batch(root_node)

            if remaining_count > 0:
                total_processed += remaining_count
                consecutive_stuck_iterations = 0  # Reset after progress
                logger.debug(f"Processed {remaining_count} remaining functions")
            else:
                # No functions left, might just be the root node
                logger.debug("No remaining functions to process")
                break

    # Phase 3: Process root node if needed
    root_count = self._process_root_node(root_node)
    if root_count > 0:
        total_processed += root_count
        logger.debug("Processed root node")

    return total_processed
```

#### 2.3: Add new method `_process_remaining_functions_batch`

```python
def _process_remaining_functions_batch(self, root_node: NodeWithContentDto) -> int:
    """
    Process remaining FUNCTION nodes that may be in cycles.

    This method processes functions without requiring all their children to be completed,
    using whatever child descriptions are available.
    """
    # Get remaining functions from database
    query = get_remaining_pending_functions_query()
    params = {
        "run_id": self.processing_run_id,
        "batch_size": self.batch_size,
        "root_node_id": root_node.id,
    }

    batch_results = self.db_manager.query(query, params)
    if not batch_results:
        return 0

    logger.debug(f"Processing {len(batch_results)} remaining functions (potential cycles)")

    # Process batch with thread pool
    documentation_nodes = []
    with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
        futures = []

        for node_data in batch_results:
            # Extract node info
            node = NodeWithContentDto(
                id=node_data["id"],
                name=node_data["name"],
                labels=node_data["labels"],
                path=node_data["path"],
                start_line=node_data.get("start_line"),
                end_line=node_data.get("end_line"),
                content=node_data.get("content", ""),
            )

            # Extract child descriptions (may be incomplete due to cycles)
            hier_descriptions = node_data.get("hier_descriptions", [])
            call_descriptions = node_data.get("call_descriptions", [])

            # Convert descriptions to DocumentationNode-like objects for processing
            child_descriptions = []
            for desc in hier_descriptions + call_descriptions:
                if desc and desc.get("description"):
                    # Create minimal DocumentationNode for child context
                    child_doc = DocumentationNode(
                        content=desc["description"],
                        info_type="child_description",
                        source_path=desc.get("path", ""),
                        source_name=desc.get("name", ""),
                        source_id=desc.get("id", ""),
                        source_labels=desc.get("labels", []),
                        source_type="child",
                        graph_environment=self.graph_environment,
                    )
                    child_descriptions.append(child_doc)

            # Reuse _process_parent_node for processing (no special cycle handling)
            future = executor.submit(self._process_parent_node, node, child_descriptions)
            futures.append((future, node.id))

        # Harvest results
        for future in as_completed([f[0] for f in futures]):
            try:
                doc_node = future.result(timeout=30)
                if doc_node:
                    documentation_nodes.append(doc_node)
            except Exception as e:
                logger.error(f"Error processing remaining function: {e}")

    # Save batch immediately
    if documentation_nodes:
        self._save_documentation_batch(documentation_nodes)

    return len(batch_results)
```

#### 2.4: Simplify `_process_parent_node` method

Remove all cycle detection logic:

```python
def _process_parent_node(
    self, node: NodeWithContentDto, child_descriptions: List[DocumentationNode]
) -> Optional[DocumentationNode]:
    """
    Process a parent node with child descriptions.

    Args:
        node: The parent node DTO to process
        child_descriptions: List of child documentation nodes

    Returns:
        DocumentationNode with generated description
    """
    try:
        # Check if it's a function with calls
        is_function_with_calls = "FUNCTION" in node.labels and child_descriptions

        if is_function_with_calls:
            # Use function calls context for functions
            child_calls_context = self._create_function_calls_context(child_descriptions)

            # Always use FUNCTION_WITH_CALLS_ANALYSIS_TEMPLATE (no cycle checking)
            system_prompt, input_prompt = FUNCTION_WITH_CALLS_ANALYSIS_TEMPLATE.get_prompts()
            prompt_dict = {
                "node_name": node.name,
                "node_labels": " | ".join(node.labels),
                "node_path": node.path,
                "start_line": str(node.start_line) if node.start_line else "Unknown",
                "end_line": str(node.end_line) if node.end_line else "Unknown",
                "node_content": node.content or "",
                "child_calls_context": child_calls_context,
            }
        else:
            # Parent node (class, file, folder)
            system_prompt, input_prompt = PARENT_NODE_ANALYSIS_TEMPLATE.get_prompts()

            # Create enhanced content based on node type
            if "FOLDER" in node.labels:
                enhanced_content = self._create_child_descriptions_summary(child_descriptions)
            else:
                # For files and code nodes with actual content, replace skeleton comments
                enhanced_content = self._replace_skeleton_comments_with_descriptions(
                    node.content, child_descriptions
                )

            prompt_dict = {
                "node_name": node.name,
                "node_labels": " | ".join(node.labels),
                "node_path": node.path,
                "node_content": enhanced_content,
            }

        # Generate description using LLM
        description = self.agent_caller.call_dumb_agent(
            system_prompt=system_prompt, input_dict=prompt_dict, input_prompt=input_prompt
        )

        # Create DocumentationNode
        doc_node = DocumentationNode(
            content=description,
            info_type="parent_analysis",
            source_type="code",
            source_path=node.path,
            source_name=node.name,
            source_id=node.id,
            source_labels=node.labels,
            children_count=len(child_descriptions),
            graph_environment=self.graph_environment,
        )

        return doc_node

    except Exception as e:
        logger.error(f"Error processing parent node {node.name}: {e}")
        # Create fallback documentation
        return DocumentationNode(
            content=f"Error processing {node.name}: {str(e)}",
            info_type="error",
            source_type="code",
            source_path=node.path,
            source_name=node.name,
            source_id=node.id,
            source_labels=node.labels,
            metadata={"error": str(e)},
            graph_environment=self.graph_environment,
        )
```

#### 2.5: Remove `_format_cycle_participants` method

Delete this method entirely as it's no longer needed.

### Step 3: Remove Cycle Detection from queries.py

**File:** `blarify/repositories/graph_db_manager/queries.py`

Remove these two functions:
- `get_function_cycle_detection_query()`
- `detect_function_cycles()`

### Step 4: Remove Cycle Analysis Template

**File:** `blarify/agents/prompt_templates/__init__.py`

Remove the import and export:

```python
# Remove this import:
# from .function_with_cycle_analysis import FUNCTION_WITH_CYCLE_ANALYSIS_TEMPLATE

# Remove from __all__:
# "FUNCTION_WITH_CYCLE_ANALYSIS_TEMPLATE",
```

Also delete the file: `blarify/agents/prompt_templates/function_with_cycle_analysis.py`

### Step 5: Update Import in batch_processing_queries.py

**File:** `blarify/documentation/queries/__init__.py`

Add the new query to exports:

```python
from .batch_processing_queries import (
    get_leaf_nodes_batch_query,
    get_processable_nodes_with_descriptions_query,
    mark_nodes_completed_query,
    check_pending_nodes_query,
    get_leaf_nodes_under_node_query,
    get_child_descriptions_query,
    get_remaining_pending_functions_query,  # Add this
)

# Add to __all__ if it exists
```

## Testing Strategy

### 1. Unit Tests for New Query

Create tests to verify that `get_remaining_pending_functions_query`:
- Returns pending FUNCTION nodes
- Includes descriptions from completed children only
- Doesn't require all children to be completed
- Properly sets processing status

### 2. Update Integration Tests for Cycle Processing

**File:** `tests/integration/test_cycle_detection.py`

Update existing tests to verify the new approach:
- Simple cycle: A→B→A
- Complex cycle: A→B→C→D→B
- Multiple independent cycles
- Functions with both cycle and non-cycle calls
- Nested cycles within classes
- Ensure documentation is generated for all nodes including those in cycles

## Benefits of This Approach

1. **Simplicity**: No special cycle handling logic - all functions treated uniformly
2. **Robustness**: Can't get stuck on cycles since we force processing after detection
3. **Completeness**: All nodes eventually get processed with best available information
4. **Maintainability**: Less code, fewer edge cases, simpler to understand
5. **Scalability**: Works with any cycle complexity without special cases

## Migration Notes

1. The change is backward compatible - existing documentation won't be affected
2. Re-running documentation on projects with cycles will now complete successfully
3. The quality of documentation for cyclic functions may improve since they'll have partial context instead of being stuck

## Documentation Updates

### Update Internal Documentation

**File:** `docs/documentation-creator.md`

Update the documentation to reflect the new cycle handling approach:

1. Remove references to cycle detection and special handling
2. Update the processing pipeline section to describe the new three-phase approach:
   - Phase 1: Process leaf nodes
   - Phase 2: Iteratively process parents and handle stuck cycles
   - Phase 3: Process root node
3. Remove mentions of:
   - FUNCTION_WITH_CYCLE_ANALYSIS_TEMPLATE
   - detect_function_cycles
   - _format_cycle_participants
4. Add explanation of how cycles are naturally handled by processing remaining functions when stuck
5. Update the "Key Features" section to reflect the simplified approach

**Key points to emphasize:**
- Cycles are handled implicitly rather than explicitly detected
- All functions are treated uniformly (no special cycle templates)
- The system can't deadlock because it forces processing of remaining functions
- Better maintainability due to simpler logic
