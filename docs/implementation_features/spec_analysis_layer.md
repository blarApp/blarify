# Spec Analysis Layer Implementation Plan

> **Parent Document**: [Semantic Documentation Layer](./semantic_documentation_layer.md)

## Overview

The Spec Analysis Layer extends the [Semantic Documentation Layer](./semantic_documentation_layer.md) by adding **comprehensive workflow understanding** to Blarify's code analysis capabilities. While the semantic layer provides individual component descriptions, the spec layer discovers all workflows in the codebase using a hybrid entry point discovery approach.

### Hybrid Entry Point Discovery Architecture
**Database Query + Agent Exploration with Set Union**

This approach combines the reliability of database queries with the intelligence of agent-based discovery to find comprehensive entry points that span the entire application.

## Feature Description

### What is the Hybrid Entry Point Discovery?

The spec analysis layer uses a two-phase approach to discover ALL possible entry points in a codebase, combining database reliability with agent intelligence:

**Phase 1: Database Query** - Finds functions/methods with no incoming CALLS relationships
**Phase 2: Agent Exploration** - Discovers entry points that database queries cannot find

### Entry Points the Database Query Finds:
- Functions and methods with no incoming CALLS relationships
- Basic computational entry points
- Simple function-based entry points

### Entry Points the Agent Discovers:
1. **Server Routes/Endpoints**: Web routes, API endpoints, REST handlers, GraphQL resolvers
2. **CLI Commands**: Command-line interface entry points, argument parsers, console scripts  
3. **Executable Scripts**: Main scripts, standalone executables, script entry points
4. **Async Tasks**: Background jobs, celery tasks, scheduled tasks, cron jobs, worker processes
5. **Event Handlers**: UI event handlers, message queue consumers, webhook receivers, socket handlers
6. **Framework Lifecycle**: Middleware functions, startup hooks, lifecycle methods, decorators
7. **Configuration-Driven**: Routes defined in config files, annotations, framework decorators

### Key Capabilities

1. **Comprehensive Discovery**: Finds entry points across all application patterns
2. **Framework-Aware Analysis**: Uses framework context to identify specific entry point patterns
3. **Deduplication Logic**: Combines results using set union to avoid duplicates
4. **Cross-Component Tracing**: Maps complete execution paths from all discovered entry points
5. **Agent-Based Intelligence**: Uses exploration tools to find complex entry point patterns

### Example Entry Point Discovery

For a Django marketplace application, the system would discover:
- **Database Query Finds**: Utility functions, helper methods, standalone processors
- **Agent Discovers**: 
  - URL route handlers (`/api/products/create/`)
  - Management commands (`python manage.py import_products`)
  - Celery tasks (`@task def process_image()`)
  - Webhook handlers (`/webhook/payment_complete/`)
  - Admin interface entry points
  - Background scheduled tasks

## Technical Architecture

### Integration with Semantic Documentation Workflow

The spec analysis extends the main workflow in `blarify/documentation/workflow.py` by replacing spec discovery with comprehensive workflow discovery:

```
Previous Spec-Based Flow:
load_codebase → detect_framework → create_descriptions → 
discover_specs → process_specs → construct_general_documentation

New Workflow-Based Flow:
load_codebase → detect_framework → create_descriptions → 
discover_all_entry_points → process_all_workflows → construct_general_documentation
```

This change shifts from discovering business specifications to discovering all workflows directly, providing comprehensive coverage of the entire application's execution paths.

### Hybrid Entry Point Discovery Implementation

#### 1. `discover_all_entry_points` Node
- **Purpose**: Hybrid entry point discovery using database query + agent exploration
- **Input**: Framework info, root InformationNodes
- **Phase 1 Process**: 
  - Execute database query for functions/methods with no incoming CALLS
  - Create set of known entry point IDs for deduplication
  - Convert database results to standard format
- **Phase 2 Process**:
  - Use agent with exploration tools to find additional entry points
  - Search for routes, CLI commands, async tasks, event handlers
  - Filter out duplicates using known entry point IDs set
- **Output**: Combined list of all discovered entry points with metadata

#### 2. `process_all_workflows` Node  
- **Purpose**: Process workflows from all discovered entry points and create 4-layer architecture
- **Input**: List of discovered entry points from hybrid discovery
- **Process**: 
  - Loop through each entry point
  - Use existing `find_independent_workflows` function for each entry point
  - Add entry point metadata to workflow results
  - Create workflow information nodes in workflows layer
  - Create BELONGS_TO_WORKFLOW relationships to documentation layer
  - Create WORKFLOW_STEP relationships for execution order
- **Output**: Complete 4-layer architecture with all workflows and relationships

### Hybrid Entry Point Discovery Architecture

```python
# blarify/documentation/spec_analysis_workflow.py

def _discover_all_entry_points(self, state: SpecAnalysisState) -> Dict[str, Any]:
    """
    Hybrid entry point discovery: Database query + Agent exploration with set union.
    """
    # STEP 1: Database Query Phase
    basic_entry_points = self.company_graph_manager.query(
        find_potential_entry_points_query(),
        {"entity_id": self.company_id, "repo_id": self.repo_id}
    )
    
    # Create set of known entry point IDs for deduplication
    known_entry_point_ids = {ep["id"] for ep in basic_entry_points}
    
    # STEP 2: Agent Exploration Phase
    # Use ReactAgent with InformationNode exploration tools
    tools = [
        InformationNodeSearchTool,
        InformationNodeRelationshipTraversalTool,
        InformationNodesByFolderTool,
    ]
    
    agent_response = self.agent_caller.call_react_agent(
        system_prompt=HYBRID_ENTRY_POINT_DISCOVERY_TEMPLATE.system_prompt,
        tools=tools,
        input_dict={
            "framework_analysis": detected_framework,
            "root_information_nodes": root_info_formatted,
        },
        input_prompt=input_prompt,
        output_schema=EntryPointDiscoveryResponse,
    )
    
    # STEP 3: Set Union - Combine results avoiding duplicates
    agent_entry_points = []
    for entry_point in agent_response.entry_points:
        if entry_point.source_node_id not in known_entry_point_ids:
            agent_entry_points.append(entry_point)
            known_entry_point_ids.add(entry_point.source_node_id)
    
    # Combine database + agent results
    all_entry_points = database_entry_points + agent_entry_points
    return {"discovered_entry_points": all_entry_points}
```

#### Database Query Function

```python
def find_potential_entry_points_query() -> str:
    """
    Reliable database query for functions/methods with no incoming CALLS.
    Finds the most obvious entry points but misses routes, CLI commands, etc.
    """
    return """
    MATCH (entry:NODE {entityId: $entity_id, repoId: $repo_id, layer: 'code'})
    WHERE (entry:FUNCTION OR entry:METHOD OR entry:CLASS)
      AND NOT ()-[:CALLS]->(entry) // No incoming calls = potential entry point
    
    RETURN entry.id as id, 
           entry.name as name, 
           entry.path as path,
           labels(entry) as labels
    ORDER BY entry.path, entry.name
    LIMIT 200
    """
```

## Database Schema (4-Layer Architecture)

### Layer Structure

```
Specifications → Workflows → Documentation → Code
```

### Node Types by Layer

#### 1. Specifications Layer
```python
# Business spec node:
{
    "node_id": "spec_abc123",
    "title": "Product Creation Spec",
    "content": "Complete business process for creating products...",
    "info_type": "business_spec",
    "layer": "specifications",
    "entry_points": [
        {
            "node_id": "info_def456",
            "name": "ProductController.create",
            "source_node_id": "node_789xyz"
        }
    ],
    "scope": "Product CRUD operations including validation and persistence",
    "framework_context": "Django REST API spec"
}
```

#### 2. Workflows Layer
```python
# Workflow node:
{
    "node_id": "workflow_ghi789",
    "title": "Workflow: ProductController.create",
    "content": "Business workflow starting from ProductController.create with 8 steps",
    "info_type": "business_workflow",
    "layer": "workflows",
    "entry_point": "node_789xyz",
    # Enhanced with entry point discovery metadata:
    "entry_point_type": "server_route",
    "entry_point_confidence": "high",
    "discovery_method": "hybrid_discovery"
}
```

#### 3. Documentation Layer
```python
# Existing InformationNode:
{
    "node_id": "info_def456",
    "title": "Product Creation Controller",
    "content": "Handles product creation requests...",
    "layer": "documentation",
    "source_node_id": "node_789xyz"
}
```

#### 4. Code Layer
```python
# Existing code nodes with id, name, path, etc.
```

### Relationships in 4-Layer Architecture

```cypher
// Layer connections
(spec:INFORMATION {layer: "specifications"})
  <-[:BELONGS_TO_SPEC]-
  (workflow:INFORMATION {layer: "workflows"})
  <-[:BELONGS_TO_WORKFLOW]-
  (doc:INFORMATION {layer: "documentation"})
  -[:DESCRIBES]->
  (code:NODE {layer: "code"})

// Workflow execution steps
(doc1:INFORMATION {layer: "documentation"})
  -[:WORKFLOW_STEP {order: 0, workflow_id: "workflow_123"}]->
  (doc2:INFORMATION {layer: "documentation"})
  -[:WORKFLOW_STEP {order: 1, workflow_id: "workflow_123"}]->
  (doc3:INFORMATION {layer: "documentation"})

// Multiple workflows per spec
(spec:INFORMATION)
  <-[:BELONGS_TO_SPEC]-(workflow1:INFORMATION)
(spec:INFORMATION)
  <-[:BELONGS_TO_SPEC]-(workflow2:INFORMATION)
```

## Updated DocumentationState

```python
class DocumentationState(TypedDict):
    # Information nodes are now stored in database, not in state
    semantic_relationships: Annotated[list, add]   # Semantic relationships
    
    # New spec analysis fields:
    discovered_specs: List[Dict[str, Any]]      # From discover_specs node  
    spec_analysis_results: Annotated[list, add] # From process_specs node
    spec_relationships: Annotated[list, add]    # Spec-specific relationships
```

## Query Patterns

### Spec Discovery Queries

```cypher
// Find potential spec entry points
MATCH (info:INFORMATION {layer: "documentation"})-[:DESCRIBES]->(code_node)
WHERE info.content =~ '.*handles.*|.*processes.*|.*endpoint.*|.*controller.*'
RETURN info.title, info.content, labels(code_node) as code_type
ORDER BY size(info.content) DESC

// Group components by architectural folders
MATCH (info:INFORMATION {layer: "documentation"})
WHERE info.source_path CONTAINS $folder_path
RETURN collect(info) as folder_components
```

### 4-Layer Consumption Queries

```cypher
// Find all specs
MATCH (spec:INFORMATION {layer: "specifications", info_type: "business_spec"})
RETURN spec.title, spec.entry_points, spec.framework_context

// Find workflows for a spec
MATCH (spec:INFORMATION {layer: "specifications", node_id: $spec_id})
      <-[:BELONGS_TO_SPEC]-(workflow:INFORMATION {layer: "workflows"})
RETURN workflow.title, workflow.entry_point

// Get complete workflow trace through documentation layer
MATCH (workflow:INFORMATION {layer: "workflows", node_id: $workflow_id})
      <-[:BELONGS_TO_WORKFLOW]-(doc:INFORMATION {layer: "documentation"})
OPTIONAL MATCH (doc)-[step:WORKFLOW_STEP]->(nextDoc:INFORMATION)
WHERE step.workflow_id = workflow.node_id
RETURN doc, step.order, nextDoc
ORDER BY step.order

// Traverse from spec to code through all layers
MATCH path = (spec:INFORMATION {layer: "specifications"})
      <-[:BELONGS_TO_SPEC]-(workflow:INFORMATION {layer: "workflows"})
      <-[:BELONGS_TO_WORKFLOW]-(doc:INFORMATION {layer: "documentation"})
      -[:DESCRIBES]->(code:NODE {layer: "code"})
WHERE spec.node_id = $spec_id
RETURN path
```

## Framework-Guided Analysis

### Framework-Specific Spec Patterns

```python
# Framework-specific spec suggestions for discovery:
FRAMEWORK_WORKFLOWS = {
    "Django": [
        "User Authentication Flow",
        "Model CRUD Operations", 
        "Form Processing Pipeline",
        "Admin Interface Specs",
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

The spec discovery process uses specialized tools that work exclusively with the documentation layer, never exposing actual code to the LLM agents.

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
- **Usage**: Discover what components call/import each other to verify spec connections

#### 3. InformationNodesByFolderTool
- **Purpose**: Get all InformationNodes from specific folder paths
- **Input**: Folder path string
- **Output**: All InformationNodes in that folder with their descriptions
- **Usage**: Understand folder-level functionality and group related components

### Tool Usage Pattern for Spec Discovery

```python
# Example spec discovery process using tools:
1. Use InformationNodeSearchTool to find potential entry points:
   - Search for "controller", "handler", "endpoint", "api"
   
2. Use InformationNodeRelationshipTraversalTool to explore connections:
   - Find what each entry point calls/imports
   - Trace execution paths through component descriptions
   
3. Use InformationNodesByFolderTool to understand architectural organization:
   - Group related components by folder
   - Identify folder-specific spec patterns

4. Combine results to identify business specs that span multiple components
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

**IMPORTANT**: The spec discovery process queries for **only the InformationNode that describes each main folder itself**, not all nodes within the folder. This provides the starting context for exploration.

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

## Implementation Status

### ✅ Completed
- **4-Layer Architecture Design**: Specifications → Workflows → Documentation → Code
- **Database Schema**: Added BELONGS_TO_SPEC, BELONGS_TO_WORKFLOW, DESCRIBES relationships
- **Spec Discovery**: Implemented with node ID capture for entry points
- **Spec Processing**: Creates spec nodes, finds workflows, creates all relationships
- **Query Methods**: Added all necessary Cypher queries for 4-layer architecture
- **Integration**: SpecAnalysisWorkflow fully integrated with main workflow

### 🚧 Future Enhancements
- **Async Operation Mapping**: Connect async tasks back to workflows
- **Cross-Workflow Analysis**: Identify shared components between workflows
- **Workflow Visualization**: Generate visual workflow diagrams
- **Performance Optimization**: Batch relationship creation for large specs

## Success Criteria

### Functional Requirements
- [ ] Automatically discover 3-5 main business specs per codebase
- [ ] Create dedicated SpecAnalysisSpec for individual spec processing
- [ ] Generate spec InformationNodes with proper graph relationships
- [ ] Map async operations back to their triggering specs using relationships

### Quality Requirements  
- [ ] Identified specs correspond to actual business processes
- [ ] Spec relationships accurately represent execution flow
- [ ] Framework-specific patterns are properly recognized
- [ ] Async connections are correctly mapped through graph relationships

### Integration Requirements
- [ ] Seamless extension of existing semantic documentation spec
- [ ] SpecAnalysisSpec follows FolderProcessingSpec patterns
- [ ] Spec relationships integrate with existing graph database schema
- [ ] Proper LangSmith tracking for individual spec analysis

## Benefits of This Architecture

1. **Dedicated Spec Processing**: Each spec gets its own LangGraph spec for better tracking and isolation
2. **Graph-Based Storage**: Uses relationships instead of JSON arrays, leveraging graph database strengths
3. **Framework-Guided Discovery**: Uses existing framework detection to guide spec identification
4. **Rich Context Utilization**: Leverages all existing InformationNode descriptions and code relationships
5. **Scalable Processing**: Can process multiple specs in parallel using dedicated specs
6. **LangSmith Visibility**: Individual spec analysis appears as separate traces in LangSmith

---

*Last Updated: 2025-07-28*  
*Status: Implementation Complete - 4-Layer Architecture Fully Functional*  
*Parent Document: [Semantic Documentation Layer](./semantic_documentation_layer.md)*