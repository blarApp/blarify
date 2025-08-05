# Architecture Overview

This document provides a comprehensive overview of Blarify's architecture, design patterns, and internal components.

## Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [Core Components](#core-components)
3. [Data Flow](#data-flow)
4. [Language Support](#language-support)
5. [Database Abstraction](#database-abstraction)
6. [Graph Representation](#graph-representation)
7. [Language Server Integration](#language-server-integration)
8. [Extension Points](#extension-points)

## High-Level Architecture

Blarify follows a modular architecture designed for extensibility and maintainability:

```
┌─────────────────────────────────────────────────────────────┐
│                    Blarify Architecture                     │
├─────────────────────────────────────────────────────────────┤
│  User Interface Layer                                      │
│  ┌─────────────────┐  ┌─────────────────┐                 │
│  │  GraphBuilder   │  │   CLI Tools     │                 │
│  └─────────────────┘  └─────────────────┘                 │
├─────────────────────────────────────────────────────────────┤
│  Core Analysis Layer                                       │
│  ┌─────────────────┐  ┌─────────────────┐                 │
│  │ ProjectGraph    │  │ ProjectGraph    │                 │
│  │   Creator       │  │ DiffCreator     │                 │
│  └─────────────────┘  └─────────────────┘                 │
├─────────────────────────────────────────────────────────────┤
│  Language Processing Layer                                 │
│  ┌─────────────────┐  ┌─────────────────┐                 │
│  │ TreeSitter      │  │ LSP Query       │                 │
│  │   Helper        │  │   Helper        │                 │
│  └─────────────────┘  └─────────────────┘                 │
├─────────────────────────────────────────────────────────────┤
│  Graph Management Layer                                    │
│  ┌─────────────────┐  ┌─────────────────┐                 │
│  │    Graph        │  │  Node Factory   │                 │
│  │   Objects       │  │  & Utilities    │                 │
│  └─────────────────┘  └─────────────────┘                 │
├─────────────────────────────────────────────────────────────┤
│  Data Persistence Layer                                    │
│  ┌─────────────────┐  ┌─────────────────┐                 │
│  │   Neo4j         │  │   FalkorDB      │                 │
│  │  Manager        │  │   Manager       │                 │
│  └─────────────────┘  └─────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. GraphBuilder (Entry Point)

The `GraphBuilder` class serves as the main entry point for users:

```python
# Simplified GraphBuilder structure
class GraphBuilder:
    def __init__(self, root_path, extensions_to_skip, names_to_skip, ...):
        self.root_path = root_path
        self.file_iterator = ProjectFilesIterator(...)
        self.lsp_helper = LspQueryHelper(...)
    
    def build(self) -> Graph:
        # Orchestrates the entire graph building process
        return ProjectGraphCreator(...).build()
```

**Responsibilities:**
- Configuration management
- Component initialization
- High-level orchestration

### 2. ProjectGraphCreator (Core Engine)

The heart of the analysis engine:

```python
class ProjectGraphCreator:
    def build(self) -> Graph:
        # 1. Create code hierarchy (file structure + definitions)
        self._create_code_hierarchy()
        
        # 2. Create relationships from LSP references
        self._create_relationships_from_references_for_files()
        
        return self.graph
    
    def _create_code_hierarchy(self):
        # Uses TreeSitter to parse code structure
        
    def _create_relationships_from_references_for_files(self):
        # Uses LSP to find code references and relationships
```

**Responsibilities:**
- Code hierarchy creation
- Relationship discovery
- Graph assembly

### 3. ProjectGraphDiffCreator (Change Analysis)

Extends `ProjectGraphCreator` for change tracking:

```python
class ProjectGraphDiffCreator(ProjectGraphCreator):
    def build_with_previous_node_states(self, previous_states) -> GraphUpdate:
        # 1. Build current graph
        self._create_code_hierarchy()
        
        # 2. Compare with previous state
        self.mark_updated_and_added_nodes_as_diff()
        
        # 3. Create change relationships
        self.create_relationships_from_previous_node_states(previous_states)
        
        return GraphUpdate(self.graph, self.external_relationship_store)
```

**Responsibilities:**
- Change detection
- Diff relationship creation
- Version comparison

## Data Flow

The data flows through Blarify in the following sequence:

```
1. File Discovery
   ├── ProjectFilesIterator scans directory
   ├── Applies filtering rules (extensions, names)
   └── Generates file list

2. Code Hierarchy Creation
   ├── TreeSitterHelper parses each file
   ├── Language-specific definitions extract structures
   ├── NodeFactory creates node objects
   └── Graph stores hierarchical relationships

3. Reference Analysis
   ├── LspQueryHelper queries language servers
   ├── Finds references for each definition
   ├── RelationshipCreator builds relationships
   └── Graph stores reference relationships

4. Data Serialization
   ├── Nodes converted to dictionary format
   ├── Relationships converted to dictionary format
   └── Ready for database storage

5. Database Persistence
   ├── Database manager receives data
   ├── Batch operations for performance
   └── Data stored in graph database
```

### Detailed Flow Diagram

```
File System → ProjectFilesIterator → File Objects
     ↓
TreeSitterHelper → Language Definitions → Node Objects
     ↓
Graph (Hierarchy) ← NodeFactory ← TreeSitter AST
     ↓
LspQueryHelper → References → RelationshipCreator
     ↓
Graph (Complete) → Serialization → Database Manager
     ↓
Graph Database (Neo4j/FalkorDB)
```

## Language Support

Blarify uses a two-tier approach for language support:

### Tier 1: TreeSitter (Syntax Analysis)

All supported languages use TreeSitter for basic syntax parsing:

```python
class TreeSitterHelper:
    def __init__(self, language_definitions: LanguageDefinitions):
        self.language_definitions = language_definitions
        self.parser = self._setup_parser()
    
    def create_hierarchy_for_file(self, file: File) -> List[Node]:
        # Parse file with TreeSitter
        tree = self.parser.parse(file.content)
        
        # Extract definitions using language-specific rules
        return self._extract_definitions(tree.root_node, file)
```

**Supported Languages:**
- Python
- JavaScript/TypeScript  
- Ruby
- Go
- C#
- Java
- PHP

### Tier 2: LSP (Semantic Analysis)

For deeper analysis, Blarify uses Language Server Protocol:

```python
class LspQueryHelper:
    def get_paths_where_node_is_referenced(self, node: Node) -> List[Reference]:
        # Query LSP server for references
        references = self.lsp_client.find_references(
            uri=node.path,
            position=node.definition_range.start
        )
        return references
```

**Enhanced Support:**
- Python (via Jedi Language Server)
- JavaScript/TypeScript (configurable)
- Others can be added via LSP servers

### Language Definition Pattern

Each language implements the `LanguageDefinitions` interface:

```python
class PythonDefinitions(LanguageDefinitions):
    @staticmethod
    def get_query_for_definitions() -> str:
        return """
        (function_def name: (identifier) @function.name) @function.definition
        (class_def name: (identifier) @class.name) @class.definition
        """
    
    @staticmethod
    def get_relationship_type(node, reference_node) -> FoundRelationshipScope:
        # Language-specific relationship detection
        return FoundRelationshipScope(reference_node, RelationshipType.CALLS)
```

## Database Abstraction

Blarify provides a unified interface for different graph databases:

### Database Manager Interface

```python
class AbstractDbManager:
    def save_graph(self, nodes: List[dict], edges: List[dict]):
        """Save complete graph to database"""
        
    def create_nodes(self, nodeList: List[dict]):
        """Create nodes in batch"""
        
    def create_edges(self, edgesList: List[dict]):
        """Create relationships in batch"""
        
    def detatch_delete_nodes_with_path(self, path: str):
        """Delete nodes by path"""
        
    def close(self):
        """Close database connection"""
```

### Neo4j Implementation

```python
class Neo4jManager(AbstractDbManager):
    def save_graph(self, nodes, edges):
        # Uses APOC procedures for batch operations
        self.create_nodes(nodes)
        self.create_edges(edges)
    
    def create_nodes(self, nodeList):
        # Cypher query with APOC for performance
        query = """
        CALL apoc.periodic.iterate(
            "UNWIND $nodeList AS node RETURN node",
            "CALL apoc.merge.node(...)",
            {batchSize: 100, parallel: false}
        )
        """
```

### FalkorDB Implementation

```python
class FalkorDBManager(AbstractDbManager):
    def save_graph(self, nodes, edges):
        # Uses FalkorDB's native graph operations
        graph = self.db.select_graph(self.repo_id)
        self._batch_create_nodes(graph, nodes)
        self._batch_create_edges(graph, edges)
```

## Graph Representation

### Node Hierarchy

Blarify uses an inheritance hierarchy for different node types:

```
Node (Base)
├── FolderNode (Directories)
├── FileNode (Source files)
└── DefinitionNode (Code definitions)
    ├── ClassNode (Class definitions)
    ├── FunctionNode (Function/method definitions)
    └── DeletedNode (For diff tracking)
```

### Node Structure

```python
class Node:
    # Core attributes
    label: NodeLabels          # NODE, FILE, CLASS, FUNCTION, etc.
    path: str                  # file:// URI
    name: str                  # Display name
    level: int                 # Nesting level
    parent: Node               # Parent in hierarchy
    graph_environment: GraphEnvironment  # Context information
    
    # Computed properties
    @property
    def id(self) -> str:
        return str(self.graph_environment) + self._identifier()
    
    @property
    def hashed_id(self) -> str:
        return md5(self.id.encode()).hexdigest()
```

### Relationship Types

```python
class RelationshipType(Enum):
    # Hierarchy relationships
    CONTAINS = "CONTAINS"              # Folder contains file
    FUNCTION_DEFINITION = "FUNCTION_DEFINITION"  # File defines function
    CLASS_DEFINITION = "CLASS_DEFINITION"        # File defines class
    
    # Code relationships
    CALLS = "CALLS"                    # Function calls function
    IMPORTS = "IMPORTS"                # File imports from file
    INHERITS = "INHERITS"              # Class inherits from class
    USES = "USES"                      # General usage relationship
    
    # Change tracking
    MODIFIED = "MODIFIED"              # Node was modified
    DELETED = "DELETED"                # Node was deleted
```

## Language Server Integration

### LSP Client Architecture

```python
class LspQueryHelper:
    def __init__(self, root_uri: str):
        self.root_uri = root_uri
        self.language_servers = {}
        self.websocket_client = None
    
    def start(self):
        # Initialize language servers for detected languages
        self._detect_languages()
        self._start_language_servers()
        self._establish_websocket_connection()
    
    def get_paths_where_node_is_referenced(self, node: Node) -> List[Reference]:
        # Query appropriate language server
        server = self._get_server_for_file(node.path)
        return server.find_references(node.definition_range)
```

### Language Server Lifecycle

```
1. Detection
   ├── Scan project for language files
   ├── Determine required language servers
   └── Check if servers are available

2. Initialization
   ├── Start language server processes
   ├── Send initialize request
   ├── Wait for initialized notification
   └── Configure workspace

3. Usage
   ├── Send textDocument/references requests
   ├── Process reference responses
   ├── Convert LSP positions to internal format
   └── Create relationship objects

4. Cleanup
   ├── Send shutdown request
   ├── Send exit notification
   ├── Close connections
   └── Terminate processes
```

## Extension Points

Blarify is designed to be extensible at several levels:

### 1. Language Support

Add new languages by implementing the `LanguageDefinitions` interface:

```python
class NewLanguageDefinitions(LanguageDefinitions):
    @staticmethod
    def get_query_for_definitions() -> str:
        # TreeSitter query for extracting definitions
        return "(function_declaration) @function"
    
    @staticmethod
    def get_relationship_type(node, reference) -> FoundRelationshipScope:
        # Logic for determining relationship types
        return FoundRelationshipScope(reference, RelationshipType.CALLS)
```

### 2. Database Backends

Add new database support by extending `AbstractDbManager`:

```python
class CustomDbManager(AbstractDbManager):
    def save_graph(self, nodes, edges):
        # Custom database implementation
        pass
```

### 3. Analysis Pipeline

Extend analysis by creating custom graph creators:

```python
class CustomGraphCreator(ProjectGraphCreator):
    def build(self) -> Graph:
        graph = super().build()
        # Add custom analysis
        self._add_custom_metrics(graph)
        return graph
    
    def _add_custom_metrics(self, graph):
        # Custom analysis logic
        pass
```

### 4. Node Types

Add custom node types for domain-specific analysis:

```python
class CustomNode(DefinitionNode):
    custom_attribute: str
    
    def as_object(self) -> dict:
        obj = super().as_object()
        obj["attributes"]["custom_attribute"] = self.custom_attribute
        return obj
```

## Performance Considerations

### Memory Management

- **Streaming Processing**: Files are processed one at a time to manage memory
- **Lazy Loading**: Node relationships are computed on-demand
- **Garbage Collection**: Explicit cleanup of LSP resources

### Optimization Strategies

1. **Filtering**: Early filtering reduces processing overhead
2. **Batch Operations**: Database operations are batched for efficiency
3. **Connection Pooling**: Database connections are reused
4. **Caching**: LSP responses can be cached for repeated queries

### Scalability Patterns

- **Horizontal Scaling**: Multiple instances can analyze different parts
- **Incremental Analysis**: Only changed files need reprocessing
- **Parallel Processing**: Language servers can run concurrently

This architecture provides a solid foundation for analyzing codebases while remaining flexible and extensible for future enhancements.
