# Blarify API Reference

This document provides a comprehensive reference for the Blarify API, covering all major classes and methods available for building and manipulating code graphs.

> **Note**: For AI agent integration using Langchain-compatible tools, see the [Tools Documentation](tools.md).

## Workflow Analysis

### find_independent_workflows

Discovers complete execution traces from entry points with edge-based flow representation.

```python
from blarify.db_managers.queries import find_independent_workflows

def find_independent_workflows(
    db_manager: AbstractDbManager, 
    entity_id: str, 
    repo_id: str, 
    entry_point_id: str
) -> List[Dict[str, Any]]
```

**Parameters:**
- `db_manager`: Database manager instance (Neo4j/FalkorDB)
- `entity_id`: Entity/company ID for filtering
- `repo_id`: Repository ID for filtering  
- `entry_point_id`: Code node ID of the entry point to analyze

**Returns:**
List of workflow dictionaries containing:
- `entryPointId/Name/Path`: Entry point details
- `endPointId/Name/Path`: Final function in call chain
- `workflowNodes`: Ordered list of functions (backward compatibility)
- `executionEdges`: **New** - Ordered list of call edges with detailed information
- `totalEdges`: Number of execution edges
- `workflowType`: Type indicator (`dfs_execution_trace_with_edges`)

**Example:**
```python
workflows = find_independent_workflows(
    db_manager=your_db_manager,
    entity_id="company_123",
    repo_id="repo_456", 
    entry_point_id="main_function_node_id"
)

for workflow in workflows:
    print(f"Workflow: {workflow['entryPointName']} -> {workflow['endPointName']}")
    for edge in workflow['executionEdges']:
        print(f"  {edge['source_name']} calls {edge['target_name']} at line {edge['start_line']}")
```

### RelationshipCreator

Creates workflow relationships for 4-layer architecture integration.

```python
from blarify.graph.relationship.relationship_creator import RelationshipCreator

# Create BELONGS_TO_WORKFLOW relationships
belongs_relationships = RelationshipCreator.create_belongs_to_workflow_relationships_for_code_nodes(
    workflow_node: Node,
    workflow_code_node_ids: List[str],
    db_manager: AbstractDbManager
) -> List[dict]

# Create WORKFLOW_STEP relationships from execution edges (preferred)
step_relationships = RelationshipCreator.create_workflow_step_relationships_from_execution_edges(
    workflow_node: Node,
    execution_edges: List[Dict[str, Any]],
    db_manager: AbstractDbManager
) -> List[dict]
```

## Core Classes

### GraphBuilder

The main entry point for building code graphs from your project.

```python
from blarify.prebuilt.graph_builder import GraphBuilder

class GraphBuilder:
    def __init__(
        self,
        root_path: str,
        extensions_to_skip: list[str] = None,
        names_to_skip: list[str] = None,
        only_hierarchy: bool = False,
        graph_environment: GraphEnvironment = None,
    )
```

**Parameters:**
- `root_path` (str): Root directory path of the project to analyze
- `extensions_to_skip` (list[str], optional): File extensions to exclude from analysis (e.g., `['.md', '.txt']`)
- `names_to_skip` (list[str], optional): Filenames/directory names to exclude from analysis (e.g., `['venv', 'tests']`)
- `only_hierarchy` (bool, optional): If True, only builds the hierarchy without relationships
- `graph_environment` (GraphEnvironment, optional): Custom graph environment

**Methods:**
- `build() -> Graph`: Builds and returns the code graph

### Graph

Represents the complete code graph with nodes and relationships.

```python
class Graph:
    def get_nodes_as_objects() -> List[dict]
    def get_relationships_as_objects() -> List[dict]
    def get_nodes_by_path(path: str) -> set[Node]
    def get_file_node_by_path(path: str) -> Optional[FileNode]
    def get_node_by_id(id: str) -> Optional[Node]
    def add_node(node: Node) -> None
    def add_nodes(nodes: List[Node]) -> None
```

**Key Methods:**
- `get_nodes_as_objects()`: Returns all nodes as serializable dictionaries
- `get_relationships_as_objects()`: Returns all relationships as serializable dictionaries
- `get_nodes_by_path(path)`: Get all nodes for a specific file path
- `filtered_graph_by_paths(paths_to_keep)`: Create a filtered graph with only specified paths

## Node Types

### Node (Base Class)

Base class for all nodes in the graph.

```python
class Node:
    label: NodeLabels
    path: str
    name: str
    level: int
    parent: Node
    graph_environment: GraphEnvironment
```

**Properties:**
- `hashed_id`: MD5 hash of the node ID
- `relative_id`: ID without graph environment prefix
- `id`: Full node identifier
- `pure_path`: File path without URI scheme
- `extension`: File extension

**Methods:**
- `as_object()`: Serialize node to dictionary
- `get_relationships()`: Get relationships originating from this node

### DefinitionNode

Base class for nodes that can contain other definitions (classes, functions).

```python
class DefinitionNode(Node):
    definition_range: Reference
    node_range: Reference
    code_text: str
    body_node: TreeSitterNode
    extra_labels: List[str]
    extra_attributes: Dict[str, str]
```

**Methods:**
- `relate_node_as_define_relationship(node)`: Add a child definition
- `add_extra_label(label)`: Add an extra label for change tracking
- `is_code_text_equivalent(code_text)`: Check if code text has changed

### Specific Node Types

#### FileNode
Represents a source code file.

#### FolderNode
Represents a directory in the project.

#### ClassNode
Represents a class definition.

#### FunctionNode
Represents a function/method definition.

#### DeletedNode
Represents a deleted node (used in diff mode).

## Database Managers

### Neo4jManager

Manages connections and operations with Neo4j databases.

```python
class Neo4jManager:
    def __init__(
        self,
        repo_id: str = None,
        entity_id: str = None,
        max_connections: int = 50,
        uri: str = None,
        user: str = None,
        password: str = None,
    )
```

**Methods:**
- `save_graph(nodes, edges)`: Save complete graph to Neo4j
- `create_nodes(nodeList)`: Create nodes in batch
- `create_edges(edgesList)`: Create relationships in batch
- `detatch_delete_nodes_with_path(path)`: Delete nodes by path
- `close()`: Close database connection

### FalkorDBManager

Manages connections and operations with FalkorDB databases.

```python
class FalkorDBManager:
    def __init__(
        self,
        repo_id: str = None,
        entity_id: str = None,
        uri: str = None,
        user: str = None,
        password: str = None,
    )
```

**Methods:**
- `save_graph(nodes, edges)`: Save complete graph to FalkorDB
- `create_nodes(nodeList)`: Create nodes in batch
- `create_edges(edgesList)`: Create relationships in batch
- `detatch_delete_nodes_with_path(path)`: Delete nodes by path
- `close()`: Close database connection

## Relationships

### Relationship

Represents a relationship between two nodes.

```python
class Relationship:
    start_node: Node
    end_node: Node
    rel_type: RelationshipType
    scope_text: str
```

**Methods:**
- `as_object()`: Serialize relationship to dictionary format

### RelationshipType

Enumeration of available relationship types:
- `CONTAINS`: Folder contains file/subfolder
- `FUNCTION_DEFINITION`: Node defines a function
- `CLASS_DEFINITION`: Node defines a class
- `CALLS`: Function calls another function
- `IMPORTS`: File imports from another file
- `INHERITS`: Class inherits from another class
- `MODIFIED`: Node was modified (diff mode)
- `DELETED`: Node was deleted (diff mode)

## Graph Environment

### GraphEnvironment

Defines the context for graph creation.

```python
@dataclass
class GraphEnvironment:
    environment: str
    diff_identifier: str
    root_path: str
```

## Utilities

### ProjectFilesIterator

Iterates through project files with filtering capabilities.

```python
class ProjectFilesIterator:
    def __init__(
        self,
        root_path: str,
        blarignore_path: str = None,
        extensions_to_skip: List[str] = None,
        names_to_skip: List[str] = None
    )
```

### LspQueryHelper

Handles Language Server Protocol queries for code analysis.

```python
class LspQueryHelper:
    def __init__(self, root_uri: str)
    def start()
    def get_paths_where_node_is_referenced(node: Node)
    def shutdown_exit_close()
```

## Data Formats

### Node Object Format

```python
{
    "type": "node_type",  # FILE, CLASS, FUNCTION, etc.
    "extra_labels": [],   # Additional labels for change tracking
    "attributes": {
        "label": "node_type",
        "path": "file://path/to/file",
        "node_id": "hashed_node_id",
        "node_path": "full_node_path",
        "name": "node_name",
        "level": 0,
        "hashed_id": "hashed_node_id",
        "diff_identifier": "diff_id",
        # Additional attributes for definition nodes:
        "start_line": 10,
        "end_line": 20,
        "text": "source_code_text",
        "stats_max_indentation": 4,
        "stats_min_indentation": 0,
        "stats_average_indentation": 2.5,
        "stats_sd_indentation": 1.2,
        "stats_methods_defined": 3  # For class nodes
    }
}
```

### Relationship Object Format

```python
{
    "sourceId": "source_node_hashed_id",
    "targetId": "target_node_hashed_id", 
    "type": "relationship_type",
    "scopeText": "contextual_scope_text"
}
```

## Error Handling

### Common Exceptions

- `FileExtensionNotSupported`: Raised when trying to analyze unsupported file types
- `ValueError`: Raised for invalid path formats or configuration
- `neo4j.exceptions.ServiceUnavailable`: Database connection issues

## Environment Variables

The following environment variables can be used for configuration:

### Neo4j Configuration
- `NEO4J_URI`: Neo4j database URI
- `NEO4J_USERNAME`: Neo4j username
- `NEO4J_PASSWORD`: Neo4j password

### FalkorDB Configuration
- `FALKORDB_URI`: FalkorDB host (default: localhost)
- `FALKORDB_PORT`: FalkorDB port (default: 6379)
- `FALKORDB_USERNAME`: FalkorDB username
- `FALKORDB_PASSWORD`: FalkorDB password

### General Configuration
- `ROOT_PATH`: Default root path for analysis
- `ENVIRONMENT`: Graph environment name
- `DIFF_IDENTIFIER`: Identifier for diff/PR mode
- `COMPANY_ID`: Entity/organization identifier
- `REPO_ID`: Repository identifier
