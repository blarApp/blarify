# Workflow Nodes with 4-Layer Architecture

This document describes the implementation of workflow nodes with 4-layer architecture and edge-based execution flows, providing complete workflow representation from business specifications to actual code execution.

## Overview

The workflow nodes implementation transforms Blarify's workflow system from returning ordered node lists to returning ordered edge lists for complete execution traces. This enables comprehensive analysis of business processes through a complete 4-layer architecture:

- **Specifications Layer**: Business specification nodes with entry points
- **Workflows Layer**: Workflow nodes representing complete execution flows  
- **Documentation Layer**: InformationNodes describing individual components
- **Code Layer**: Actual code nodes with CALLS relationships

## Architecture Pattern

```
Specifications Layer: Business spec nodes with entry points
    ↓ (BELONGS_TO_SPEC)
Workflows Layer: Workflow nodes representing complete execution flows  
    ↓ (BELONGS_TO_WORKFLOW)
Documentation Layer: InformationNodes describing individual components
    ↓ (DESCRIBES) + (WORKFLOW_STEP)
Code Layer: Actual code nodes with CALLS relationships
```

## Key Features

### 1. Edge-Based Execution Flows

The enhanced workflow query now returns execution edges in proper DFS order:

```python
from blarify.db_managers.queries import find_independent_workflows

# Get workflow with execution edges
workflows = find_independent_workflows(
    db_manager=db_manager,
    entity_id="your_entity_id",
    repo_id="your_repo_id", 
    entry_point_id="entry_point_node_id"
)

for workflow in workflows:
    print(f"Workflow: {workflow['entryPointName']} -> {workflow['endPointName']}")
    print(f"Total edges: {workflow['totalEdges']}")
    
    # Access execution edges in DFS order
    for edge in workflow['executionEdges']:
        print(f"Edge {edge['order']}: {edge['source_name']} -> {edge['target_name']}")
        print(f"  Call location: line {edge['start_line']}, char {edge['reference_character']}")
```

### 2. Workflow-Documentation Relationships

The system creates two key relationship types:

#### BELONGS_TO_WORKFLOW
Connects documentation nodes to workflow nodes:

```cypher
// Find all documentation nodes belonging to a workflow
MATCH (workflow:WORKFLOW {node_id: $workflow_id})
      <-[:BELONGS_TO_WORKFLOW]-(doc:INFORMATION)
RETURN doc.title, doc.content
```

#### WORKFLOW_STEP
Connects documentation nodes in execution order:

```cypher
// Get workflow steps in execution order
MATCH (workflow:WORKFLOW {node_id: $workflow_id})
      <-[:BELONGS_TO_WORKFLOW]-(doc:INFORMATION)
OPTIONAL MATCH (doc)-[step:WORKFLOW_STEP]->(nextDoc:INFORMATION)
WHERE step.workflow_id = $workflow_id
RETURN doc.title, step.order, nextDoc.title
ORDER BY step.order
```

## Enhanced Query Structure

The `find_independent_workflows_query()` now returns both nodes and edges:

```cypher
// Enhanced query returns execution edges with proper ordering
RETURN {
    entryPointId: pathNodes[0].node_id,
    entryPointName: pathNodes[0].name,
    entryPointPath: pathNodes[0].path,
    endPointId: last(pathNodes).node_id,
    endPointName: last(pathNodes).name,
    endPointPath: last(pathNodes).path,
    workflowNodes: executionTrace,           // Backward compatibility
    executionEdges: executionEdges,          // New edge-based data
    totalEdges: size(pathRels),
    workflowType: 'dfs_execution_trace_with_edges'
} AS workflow
```

## Complete 4-Layer Traversal Examples

### Example 1: Traverse from Specification to Code

```cypher
// Complete traversal through all 4 layers
MATCH path = (spec:INFORMATION {layer: "specifications"})
      <-[:BELONGS_TO_SPEC]-(workflow:WORKFLOW)
      <-[:BELONGS_TO_WORKFLOW]-(doc:INFORMATION)
      -[:DESCRIBES]->(code:NODE)
WHERE spec.node_id = $spec_id
RETURN path
```

### Example 2: Get Workflow Execution Flow with Documentation

```cypher
// Get complete workflow with documentation steps
MATCH (workflow:WORKFLOW {node_id: $workflow_id})
OPTIONAL MATCH (workflow)<-[:BELONGS_TO_WORKFLOW]-(doc:INFORMATION)
OPTIONAL MATCH (doc)-[step:WORKFLOW_STEP]->(nextDoc:INFORMATION)
WHERE step.workflow_id = $workflow_id
OPTIONAL MATCH (doc)-[:DESCRIBES]->(code:NODE)
RETURN workflow.title,
       doc.title as step_title,
       step.order as step_order,
       code.name as code_function,
       nextDoc.title as next_step_title
ORDER BY step.order
```

### Example 3: Business Process Analysis

```cypher
// Analyze complete business process from spec to implementation
MATCH (spec:INFORMATION {layer: "specifications", node_id: $spec_id})
MATCH (spec)<-[:BELONGS_TO_SPEC]-(workflow:WORKFLOW)
MATCH (workflow)<-[:BELONGS_TO_WORKFLOW]-(doc:INFORMATION)
MATCH (doc)-[:DESCRIBES]->(code:NODE)

// Get execution flow
OPTIONAL MATCH (doc)-[step:WORKFLOW_STEP {workflow_id: workflow.node_id}]->(nextDoc:INFORMATION)

RETURN {
    specification: spec.title,
    workflow: workflow.title,
    business_steps: collect(DISTINCT {
        step_order: step.order,
        step_title: doc.title,
        implementation: code.name,
        next_step: nextDoc.title
    })
}
```

## Relationship Creation

### Programmatic Relationship Creation

```python
from blarify.graph.relationship.relationship_creator import RelationshipCreator

# Create BELONGS_TO_WORKFLOW relationships
belongs_relationships = RelationshipCreator.create_belongs_to_workflow_relationships_for_code_nodes(
    workflow_node=workflow_node,
    workflow_code_node_ids=code_node_ids,
    db_manager=db_manager
)

# Create WORKFLOW_STEP relationships from execution edges (preferred)
step_relationships = RelationshipCreator.create_workflow_step_relationships_from_execution_edges(
    workflow_node=workflow_node,
    execution_edges=execution_edges,
    db_manager=db_manager
)

# Fallback: Create from code sequence
step_relationships = RelationshipCreator.create_workflow_step_relationships_for_code_sequence(
    workflow_node=workflow_node,
    workflow_code_node_ids=code_node_ids,
    db_manager=db_manager
)

# Batch create relationships
db_manager.create_edges(belongs_relationships + step_relationships)
```

## Performance Considerations

### Query Optimization

1. **Limit Path Expansion**: The query uses `LIMIT 1` to get the first (lexicographically smallest) execution path
2. **Efficient Ordering**: Uses `ORDER BY sortKey` for DFS-by-callsite ordering
3. **Prevent Loops**: Uses `NODE_PATH` uniqueness to prevent infinite recursion
4. **Batch Operations**: Relationship creation supports batch processing

### Memory Usage

The edge-based approach maintains similar memory usage to the node-based approach while providing richer execution flow information.

## Integration with Spec Analysis Workflow

The `SpecAnalysisWorkflow` automatically uses edge-based relationships when available:

```python
# In _save_workflows method
execution_edges = workflow_data.get("executionEdges", [])
if execution_edges:
    # Use edge-based relationship creation
    workflow_step_relationships = (
        RelationshipCreator.create_workflow_step_relationships_from_execution_edges(
            workflow_node=workflow_info_node,
            execution_edges=execution_edges,
            db_manager=self.company_graph_manager,
        )
    )
else:
    # Fallback to sequence-based method
    workflow_step_relationships = (
        RelationshipCreator.create_workflow_step_relationships_for_code_sequence(
            workflow_node=workflow_info_node,
            workflow_code_node_ids=workflow_code_node_ids,
            db_manager=self.company_graph_manager,
        )
    )
```

## Workflow Data Structure

### Enhanced Workflow Object

```python
{
    "entryPointId": "entry_node_id",
    "entryPointName": "main_function",
    "entryPointPath": "/src/main.py",
    "endPointId": "end_node_id",
    "endPointName": "final_function",
    "endPointPath": "/src/final.py",
    "workflowNodes": [
        {
            "id": "node_id",
            "name": "function_name",
            "path": "/src/file.py",
            "call_order": 0,
            "execution_step": 1
        }
        // ... more nodes
    ],
    "executionEdges": [
        {
            "source_id": "source_node_id",
            "target_id": "target_node_id",
            "relationship_type": "CALLS",
            "order": 0,
            "start_line": 25,
            "reference_character": 12,
            "source_name": "caller_function",
            "target_name": "called_function",
            "source_path": "/src/caller.py",
            "target_path": "/src/called.py"
        }
        // ... more edges
    ],
    "totalEdges": 5,
    "workflowType": "dfs_execution_trace_with_edges"
}
```

## Migration Guide

### For Existing Code

If you have existing code that uses the workflow system:

1. **Query Results**: Existing `workflowNodes` array is still available for backward compatibility
2. **New Features**: Access `executionEdges` array for detailed execution flow information
3. **Relationship Creation**: The system automatically chooses the best relationship creation method

### Example Migration

```python
# Before: Using only nodes
for node in workflow["workflowNodes"]:
    print(f"Step {node['execution_step']}: {node['name']}")

# After: Using edges for better flow representation
for edge in workflow["executionEdges"]:
    print(f"Edge {edge['order']}: {edge['source_name']} calls {edge['target_name']}")
    print(f"  Location: {edge['source_path']}:{edge['start_line']}")
```

## Error Handling

### Edge Cases Handled

1. **Empty Workflows**: Entry points with no calls return empty edge arrays
2. **Circular Calls**: Handled gracefully with NODE_PATH uniqueness
3. **Missing Documentation**: System continues with available relationships
4. **Deep Call Stacks**: Limited to 20 levels for performance

### Error Recovery

```python
try:
    workflows = find_independent_workflows(db_manager, entity_id, repo_id, entry_point_id)
    for workflow in workflows:
        if workflow.get("executionEdges"):
            # Process edge-based workflow
            process_edge_workflow(workflow)
        else:
            # Fallback to node-based processing
            process_node_workflow(workflow)
except Exception as e:
    logger.error(f"Workflow processing failed: {e}")
    # Handle gracefully
```

## Benefits

### For Developers

1. **Complete Execution Traces**: See exactly how functions call each other
2. **Call Site Information**: Know where each call originates from
3. **Business Context**: Connect code execution to business processes
4. **Performance Insights**: Understand execution flow for optimization

### For Architects

1. **4-Layer Visibility**: Trace from business requirements to implementation
2. **Process Documentation**: Automated workflow documentation generation
3. **Impact Analysis**: Understand how changes affect business processes
4. **Compliance**: Document execution flows for regulatory requirements

## Future Enhancements

- **Parallel Execution Analysis**: Track concurrent workflow execution
- **Performance Metrics**: Add execution timing to edges
- **Dynamic Workflows**: Support for runtime workflow modification
- **Workflow Visualization**: Generate interactive workflow diagrams