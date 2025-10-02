# Blarify Quickstart

Welcome to Blarify! This guide will help you get started using Blarify to visualize your codebase.

## Prerequisites

- Python (>=3.10,<=3.14)
- A graph database instance (we recommend using [FalkorDB](https://falkordb.com/) or [AuraDB](https://neo4j.com/product/auradb/))

## Installation

First set up your virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

Install the Blarify repository:
```bash
pip install blarify
```

## Usage

```python
PATH_TO_YOUR_PROJECT = "/path/to/your/project/"
```

Import GraphBuilder from the prebuilt module

```python
from blarify.prebuilt.graph_builder import GraphBuilder
```

Create the graph builder

You can skip files or directories by passing them in the extensions_to_skip or names_to_skip parameters

I highly recommend skipping everything that is not a code file as this will make the graph much more readable and way faster to build

```python
graph_builder = GraphBuilder(root_path=PATH_TO_YOUR_PROJECT, extensions_to_skip=[".json"], names_to_skip=["__pycache__"])
```

Build the graph

```python
graph = graph_builder.build()
```

This will return a graph object that contains all the nodes and relationships in your codebase

To save them and visualize them in a graph database you can get the nodes and relationships as objects

```python
relationships = graph.get_relationships_as_objects()
nodes = graph.get_nodes_as_objects()
```

this will return a list of dictionaries with the following structure

### Relationship
```python
{
    "sourceId": "hashed_id_of_start_node", # Unique identifier for the start node
    "targetId": "hashed_id_of_end_node", # Unique identifier for the end node
    "type": "relationship_type", # Type of the relationship
    "scopeText": "scope_text", # Text that the relationship is based on
}
```

### Node
```python
{
    "type": "node_type", # File, Class, Function, etc
    "extra_labels": [], # Additional labels for the node
    "attributes": {
        "label": "node_type, # Same as type
        "path": "file://path/to/file", # Path to the file that contains the node
        "node_id": "node_id", # Unique identifier for the node, hashed node path
        "node_path": "path/to/node", # Path to the within the file
        "name": "node_name", # Name of the node
        "level": "node_level", # Level of the node within the file structure
        "hashed_id": "node_id", # Same as node_id
        "diff_identifier": "diff_identifier", # Identifier for the node, this is used when using the PR feature

        # The following attributes may not be present in all nodes
        "start_line": "start_line", # Start line of the node within the file
        "end_line": "end_line", # End line of the node within the file
        "text": "node_text", # Text of the node within the file
    },
}
```

## Complete Examples

### Simple Example (Manual Save)

For maximum control over the graph building and saving process:

```python
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager

# Build the graph
graph_builder = GraphBuilder(
    root_path="/path/to/your/project",
    extensions_to_skip=[".json"],
    names_to_skip=["__pycache__"]
)
graph = graph_builder.build(save_to_db=False)

# Get nodes and relationships
nodes = graph.get_nodes_as_objects()
relationships = graph.get_relationships_as_objects()

# Save manually to database
db_manager = Neo4jManager(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password",
    repo_id="my-repo",
    entity_id="my-org"
)
db_manager.save_graph(nodes, relationships)
db_manager.close()
```

### Automated Pipeline (Recommended)

For a streamlined experience with automatic saving, workflows, and documentation:

```python
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager

# Initialize database manager
db_manager = Neo4jManager(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password",
    repo_id="my-repo",
    entity_id="my-org"
)

# Build with integrated pipeline
builder = GraphBuilder(
    root_path="/path/to/your/project",
    extensions_to_skip=[".json", ".xml"],
    names_to_skip=["__pycache__", "node_modules"],
    db_manager=db_manager,
    generate_embeddings=True  # Enable embeddings for documentation
)

# Build with workflows and documentation
# Everything is automatically saved to the database!
graph = builder.build(
    save_to_db=True,              # Auto-save to database
    create_workflows=True,         # Discover execution workflows
    create_documentation=True      # Generate LLM documentation
)

db_manager.close()
```

### Using FalkorDB

```python
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.repositories.graph_db_manager.falkordb_manager import FalkorDBManager

db_manager = FalkorDBManager(
    host="localhost",
    port=6379,
    repo_id="my-repo",
    entity_id="my-org"
)

builder = GraphBuilder(
    root_path="/path/to/your/project",
    db_manager=db_manager,
    generate_embeddings=True
)

graph = builder.build(
    create_workflows=True,
    create_documentation=True
)

db_manager.close()
```

### Incremental Update

For efficient updates when only specific files have changed:

```python
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.project_graph_updater import UpdatedFile
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager

# Initialize database manager
db_manager = Neo4jManager(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password",
    repo_id="my-repo",
    entity_id="my-org"
)

# Create builder instance
builder = GraphBuilder(
    root_path="/path/to/your/project",
    extensions_to_skip=[".json", ".xml"],
    names_to_skip=["__pycache__", "node_modules"],
    db_manager=db_manager,
    generate_embeddings=True
)

# Specify which files to update
updated_files = [
    UpdatedFile(path="/path/to/your/project/src/main.py"),
    UpdatedFile(path="/path/to/your/project/src/utils.py")
]

# Incrementally update only those files
# Workflows and documentation will be regenerated automatically
graph = builder.incremental_update(
    updated_files=updated_files,
    save_to_db=True,
    create_workflows=True,
    create_documentation=True
)

db_manager.close()
```

## Next Steps

- **Workflows**: Discover execution traces through your codebase
- **Documentation**: Generate AI-powered documentation for your code
- **MCP Server**: Use `blarify-mcp` to integrate with Claude Desktop
- **Tools**: Check the [Tools Documentation](tools.md) for AI agent integration




