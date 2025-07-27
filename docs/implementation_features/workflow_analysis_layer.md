# Workflow Analysis Layer Implementation Plan

> **Parent Document**: [Semantic Documentation Layer](./semantic_documentation_layer.md)

## Overview

The Workflow Analysis Layer extends the [Semantic Documentation Layer](./semantic_documentation_layer.md) by adding **business workflow understanding** to Blarify's code analysis capabilities. While the semantic layer provides individual component descriptions, the workflow layer maps complete business processes that span multiple components, modules, and potentially async operations.

## Feature Description

### What is the Workflow Analysis Layer?

The workflow analysis layer sits on top of the existing semantic documentation infrastructure and uses the rich context already generated to identify and trace complete business workflows. It leverages:

- **Framework Detection**: Uses detected framework info to guide workflow pattern recognition
- **Main Folder Structure**: Uses architectural folders to understand component organization  
- **InformationNode Descriptions**: Uses existing semantic understanding of what each component does
- **Code Relationships**: Uses LSP relationships (CALLS, IMPORTS, etc.) to trace execution paths

### Key Capabilities

1. **Automatic Workflow Discovery**: Identifies business workflows based on component descriptions and code relationships
2. **Cross-Component Tracing**: Maps complete execution paths across multiple files and modules
3. **Async Operation Mapping**: Connects async tasks, webhooks, and events back to their triggering workflows
4. **Framework-Guided Analysis**: Uses framework knowledge to suggest typical workflow patterns

### Example Workflow Mappings

For a marketplace application, the system would identify and trace workflows like:
- **Product Creation Flow**: Form submission → validation → service layer → database → image processing task → search indexing
- **User Authentication Flow**: Login request → credential validation → session creation → redirect/response
- **Payment Processing Flow**: Cart checkout → payment gateway → order creation → inventory update → notification emails

## Technical Architecture

### Integration with Semantic Documentation Workflow

The workflow analysis extends the main workflow in `blarify/documentation/workflow.py`:

```
Current Flow:
load_codebase → detect_framework → iterate_directory_hierarchy_bottoms_up → 
group_related_knowledge → compact_to_markdown_per_folder → consolidate_final_markdown

Extended Flow:
load_codebase → detect_framework → iterate_directory_hierarchy_bottoms_up → 
discover_workflows → process_workflows → compact_to_markdown_per_folder → consolidate_final_markdown
```

### New Workflow Nodes

#### 1. `discover_workflows` Node
- **Purpose**: Analyze InformationNodes for main folders to identify business workflow patterns
- **Input**: Framework info, main folders (queries database for folder InformationNodes)
- **Process**: 
  - Query database for InformationNode of each main folder (e.g., "src", "components")
  - Use framework context to guide workflow pattern recognition
  - Use exploration tools to discover related components from folder starting points
  - Identify potential workflow entry points and business processes
- **Output**: List of discovered workflow definitions with entry points and scope

#### 2. `process_workflows` Node  
- **Purpose**: Process each discovered workflow using dedicated `WorkflowAnalysisWorkflow`
- **Input**: List of discovered workflows + all context
- **Process**: 
  - Loop through each workflow
  - Create dedicated `WorkflowAnalysisWorkflow` for each one
  - Collect all workflow analysis results
- **Output**: Complete workflow analysis results with traces and relationships

### Dedicated WorkflowAnalysisWorkflow

Following the pattern of `FolderProcessingWorkflow`, create a dedicated workflow for analyzing individual business workflows:

```python
# blarify/documentation/workflow_analysis_workflow.py

class WorkflowAnalysisState(TypedDict):
    """State management for single workflow analysis."""
    workflow_info: Dict[str, Any]           # Workflow definition to analyze
    framework_info: Dict[str, Any]          # Framework context
    available_nodes: List[Dict[str, Any]]   # InformationNodes to work with
    workflow_trace: List[Dict[str, Any]]    # Traced execution path
    async_connections: List[Dict[str, Any]] # Async operations found
    workflow_relationships: List[Dict[str, Any]] # Graph relationships to create
    error: Optional[str]

class WorkflowAnalysisWorkflow:
    """Dedicated workflow for analyzing a single business workflow."""
    
    def compile_graph(self):
        workflow = StateGraph(WorkflowAnalysisState)
        
        workflow.add_node("trace_workflow_components", self._trace_workflow_components)
        workflow.add_node("map_async_connections", self._map_async_connections)
        workflow.add_node("create_workflow_relationships", self._create_workflow_relationships)
        
        # Sequential processing
        workflow.add_edge(START, "trace_workflow_components")
        workflow.add_edge("trace_workflow_components", "map_async_connections")
        workflow.add_edge("map_async_connections", "create_workflow_relationships")
```

#### WorkflowAnalysisWorkflow Nodes

**1. `trace_workflow_components`**
- Trace execution paths using LSP relationships (CALLS, IMPORTS, etc.)
- Map component-to-component flow within the workflow
- Identify data transformations and business logic steps

**2. `map_async_connections`**  
- Identify async operations (tasks, events, webhooks) within the workflow
- Connect async operations back to their triggering components
- Map completion mechanisms and callbacks

**3. `create_workflow_relationships`**
- Generate graph relationships representing the workflow structure
- Create PARTICIPATES_IN, WORKFLOW_STEP, TRIGGERS_ASYNC relationships
- Save workflow InformationNodes and relationships to database

## Database Schema (Graph-Based)

### Workflow InformationNodes

```python
# Business workflow node:
{
    "node_id": "workflow_product_creation",
    "title": "Product Creation Workflow",
    "content": "Complete business process for creating products...",
    "info_type": "business_workflow",
    "layer": "workflows",
    "entry_points": ["ProductController.create", "api/products POST"],
    "framework_context": "Django REST API workflow"
}

# Workflow step nodes (optional, for detailed tracing):
{
    "node_id": "step_product_validation", 
    "title": "Product Input Validation Step",
    "content": "Validates product creation input parameters...",
    "info_type": "workflow_step",
    "layer": "workflows",
    "step_order": 1
}
```

### Workflow Relationships (Graph-Based)

Instead of storing traces as JSON arrays, use graph relationships:

```cypher
// Component participation in workflows
(component:INFORMATION {layer: "documentation"})
  -[:PARTICIPATES_IN]->
  (workflow:INFORMATION {layer: "workflows", info_type: "business_workflow"})

// Workflow execution flow (component to component)
(component1:INFORMATION)-[:WORKFLOW_STEP {step_order: 1, workflow_id: "product_creation"}]->(component2:INFORMATION)

// Async operations within workflows  
(trigger:INFORMATION)-[:TRIGGERS_ASYNC {workflow_id: "product_creation"}]->(async_op:INFORMATION)

// Workflow collaboration (components that work together)
(comp1:INFORMATION)-[:COLLABORATES_WITH {workflow_id: "product_creation"}]->(comp2:INFORMATION)
```

## Updated DocumentationState

```python
class DocumentationState(TypedDict):
    # Information nodes are now stored in database, not in state
    semantic_relationships: Annotated[list, add]   # Semantic relationships
    
    # New workflow analysis fields:
    discovered_workflows: List[Dict[str, Any]]      # From discover_workflows node  
    workflow_analysis_results: Annotated[list, add] # From process_workflows node
    workflow_relationships: Annotated[list, add]    # Workflow-specific relationships
```

## Query Patterns

### Workflow Discovery Queries

```cypher
// Find potential workflow entry points
MATCH (info:INFORMATION {layer: "documentation"})-[:DESCRIBES]->(code_node)
WHERE info.content =~ '.*handles.*|.*processes.*|.*endpoint.*|.*controller.*'
RETURN info.title, info.content, labels(code_node) as code_type
ORDER BY size(info.content) DESC

// Group components by architectural folders
MATCH (info:INFORMATION {layer: "documentation"})
WHERE info.source_path CONTAINS $folder_path
RETURN collect(info) as folder_components
```

### Workflow Consumption Queries

```cypher
// Find all workflows
MATCH (w:INFORMATION {layer: "workflows", info_type: "business_workflow"})
RETURN w.title, w.entry_points, w.framework_context

// Find workflow execution trace
MATCH (workflow:INFORMATION {layer: "workflows", title: "Product Creation Workflow"})
      <-[:PARTICIPATES_IN]-(components)
MATCH (components)-[step:WORKFLOW_STEP]->(next_component)
WHERE step.workflow_id = workflow.node_id
RETURN components, step.step_order, next_component
ORDER BY step.step_order

// Find async operations in a workflow
MATCH (workflow:INFORMATION {layer: "workflows"})
      <-[:PARTICIPATES_IN]-(trigger)
      -[async:TRIGGERS_ASYNC]->(async_op)
WHERE async.workflow_id = workflow.node_id
RETURN workflow.title, trigger.title, async_op.title
```

## Framework-Guided Analysis

### Framework-Specific Workflow Patterns

```python
# Framework-specific workflow suggestions for discovery:
FRAMEWORK_WORKFLOWS = {
    "Django": [
        "User Authentication Flow",
        "Model CRUD Operations", 
        "Form Processing Pipeline",
        "Admin Interface Workflows",
        "API Endpoint Processing"
    ],
    "Next.js": [
        "Page Rendering Flow",
        "API Route Processing",
        "Static Generation Pipeline", 
        "Client-Side Navigation",
        "Server-Side Rendering"
    ],
    "Express.js": [
        "Request/Response Cycle",
        "Middleware Chain Execution",
        "Route Handler Processing",
        "Error Handling Flow",
        "Authentication Middleware"
    ]
}
```

## InformationNode Navigation Tools

The workflow discovery process uses specialized tools that work exclusively with the documentation layer, never exposing actual code to the LLM agents.

### Tool Architecture
- **Documentation Layer Only**: Tools return InformationNode descriptions, never code
- **Code Relationship Traversal**: Use LSP relationships (CALLS, IMPORTS, INHERITS) for accurate navigation
- **Layered Architecture**: InformationNode → DESCRIBES → Code Node → [LSP] → Target Code → DESCRIBES ← Target InformationNode

### Available Tools

#### 1. InformationNodeSearchTool
- **Purpose**: Search InformationNodes by keywords, title, or info_type
- **Input**: Search query string
- **Output**: Matching InformationNodes with descriptions, types, and source context
- **Usage**: Find components that handle specific functionality (e.g., "controller", "handler", "process")

#### 2. InformationNodeRelationshipTraversalTool
- **Purpose**: Find related InformationNodes through code relationships
- **Input**: InformationNode ID and relationship type (CALLS, IMPORTS, INHERITS)
- **Logic**: Traverse code layer relationships but surface documentation layer results
- **Output**: Related InformationNode descriptions with relationship context
- **Usage**: Discover what components call/import each other to verify workflow connections

#### 3. InformationNodesByFolderTool
- **Purpose**: Get all InformationNodes from specific folder paths
- **Input**: Folder path string
- **Output**: All InformationNodes in that folder with their descriptions
- **Usage**: Understand folder-level functionality and group related components

### Tool Usage Pattern for Workflow Discovery

```python
# Example workflow discovery process using tools:
1. Use InformationNodeSearchTool to find potential entry points:
   - Search for "controller", "handler", "endpoint", "api"
   
2. Use InformationNodeRelationshipTraversalTool to explore connections:
   - Find what each entry point calls/imports
   - Trace execution paths through component descriptions
   
3. Use InformationNodesByFolderTool to understand architectural organization:
   - Group related components by folder
   - Identify folder-specific workflow patterns

4. Combine results to identify business workflows that span multiple components
```

### Database Queries for Tools

```cypher
// InformationNodeSearchTool query
MATCH (info:INFORMATION {layer: "documentation"})
WHERE info.title CONTAINS $query OR info.content CONTAINS $query 
   OR info.info_type CONTAINS $query
RETURN info.node_id, info.title, info.content, info.info_type, 
       info.source_path, info.source_labels

// InformationNodeRelationshipTraversalTool query
MATCH (info:INFORMATION {node_id: $info_id})-[:DESCRIBES]->(code_node)
MATCH (code_node)-[rel:CALLS|IMPORTS|INHERITS]->(target_code)
MATCH (target_info:INFORMATION)-[:DESCRIBES]->(target_code)
RETURN target_info.node_id, target_info.title, target_info.content, 
       target_info.info_type, type(rel) as relationship_type,
       labels(target_code) as target_code_type, target_code.name

// InformationNodesByFolderTool query
MATCH (info:INFORMATION {layer: "documentation"})
WHERE info.source_path STARTS WITH $folder_path
RETURN info.node_id, info.title, info.content, info.info_type, 
       info.source_path, info.source_labels
ORDER BY info.source_path
```

### Folder-Specific Information Node Queries

**IMPORTANT**: The workflow discovery process queries for **only the InformationNode that describes each main folder itself**, not all nodes within the folder. This provides the starting context for exploration.

```python
# Query for main folder InformationNodes (e.g., for folders "src", "components"):
def get_main_folder_information_nodes(main_folders: List[str]) -> Dict[str, List[Dict]]:
    """
    Query database for InformationNode of each main folder.
    
    For folder "src", this returns only the InformationNode that describes 
    the "src" folder itself, not files within it.
    
    The agents then use exploration tools to discover related components.
    """
    folder_information_nodes = {}
    for folder in main_folders:
        # Query: ENDS WITH "/{folder}" to match exact folder path
        folder_nodes = get_information_nodes_by_folder(
            db_manager=db_manager,
            entity_id=entity_id, 
            repo_id=repo_id,
            folder_path=folder  # e.g., "src" -> matches "/path/to/repo/src"
        )
        
        if folder_nodes:
            folder_information_nodes[folder] = folder_nodes
            
    return folder_information_nodes
```

**Database Query Logic**:
- For folder "src", the query matches paths ending with "/src"
- This returns the InformationNode describing the "src" folder itself
- Agents use exploration tools to discover components from this starting point

## Implementation Plan

### Phase 1: Core Workflow Discovery
**Priority**: High | **Estimated Effort**: 2-3 days

#### Tasks
- [ ] **Implement `discover_workflows` Node**
  - Analyze InformationNodes grouped by architectural folders
  - Use framework context to identify typical workflow patterns
  - Generate workflow definitions with entry points and scope
  - Return list of workflows to process

- [ ] **Implement `process_workflows` Node**
  - Loop through discovered workflows
  - Create WorkflowAnalysisWorkflow instance for each workflow
  - Collect and aggregate all workflow analysis results
  - Update DocumentationState with workflow analysis results

### Phase 2: WorkflowAnalysisWorkflow Implementation  
**Priority**: High | **Estimated Effort**: 3-4 days

#### Tasks
- [ ] **Create WorkflowAnalysisWorkflow Class**
  - Follow FolderProcessingWorkflow pattern
  - Implement WorkflowAnalysisState TypedDict
  - Set up LangGraph workflow structure with 3 nodes

- [ ] **Implement Workflow Tracing Node**
  - `trace_workflow_components`: Use LSP relationships to trace execution paths
  - Map component-to-component flow within workflow scope
  - Identify data transformations and business logic steps

- [ ] **Implement Async Mapping Node**
  - `map_async_connections`: Identify async patterns in workflow
  - Connect async operations back to triggering components
  - Map completion mechanisms and callbacks

- [ ] **Implement Relationship Creation Node**
  - `create_workflow_relationships`: Generate graph relationships
  - Create PARTICIPATES_IN, WORKFLOW_STEP, TRIGGERS_ASYNC relationships
  - Save workflow InformationNodes to database with proper relationships

### Phase 3: Database Integration
**Priority**: Medium | **Estimated Effort**: 2 days

#### Tasks
- [ ] **Extend Database Schema**
  - Add workflow-specific relationship types to RelationshipType enum
  - Update database managers to support workflow relationships
  - Create indexes for efficient workflow querying

- [ ] **Implement Workflow Query Methods**
  - Add workflow discovery query methods to queries.py
  - Implement workflow consumption patterns
  - Add relationship traversal queries for workflow analysis

## Success Criteria

### Functional Requirements
- [ ] Automatically discover 3-5 main business workflows per codebase
- [ ] Create dedicated WorkflowAnalysisWorkflow for individual workflow processing
- [ ] Generate workflow InformationNodes with proper graph relationships
- [ ] Map async operations back to their triggering workflows using relationships

### Quality Requirements  
- [ ] Identified workflows correspond to actual business processes
- [ ] Workflow relationships accurately represent execution flow
- [ ] Framework-specific patterns are properly recognized
- [ ] Async connections are correctly mapped through graph relationships

### Integration Requirements
- [ ] Seamless extension of existing semantic documentation workflow
- [ ] WorkflowAnalysisWorkflow follows FolderProcessingWorkflow patterns
- [ ] Workflow relationships integrate with existing graph database schema
- [ ] Proper LangSmith tracking for individual workflow analysis

## Benefits of This Architecture

1. **Dedicated Workflow Processing**: Each workflow gets its own LangGraph workflow for better tracking and isolation
2. **Graph-Based Storage**: Uses relationships instead of JSON arrays, leveraging graph database strengths
3. **Framework-Guided Discovery**: Uses existing framework detection to guide workflow identification
4. **Rich Context Utilization**: Leverages all existing InformationNode descriptions and code relationships
5. **Scalable Processing**: Can process multiple workflows in parallel using dedicated workflows
6. **LangSmith Visibility**: Individual workflow analysis appears as separate traces in LangSmith

---

*Last Updated: 2025-07-23*  
*Status: Planning Phase - Extension of Semantic Documentation Layer*  
*Parent Document: [Semantic Documentation Layer](./semantic_documentation_layer.md)*