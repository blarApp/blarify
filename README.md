# Blarify

Converts local code repositories into graph structures using Language Server Protocol (LSP) for semantic analysis.

## Installation

```bash
pip install blarify
```

## Usage

```python
from blarify.prebuilt.graph_builder import GraphBuilder

builder = GraphBuilder("/path/to/your/project")
graph = builder.build()

nodes = graph.get_nodes_as_objects()
relationships = graph.get_relationships_as_objects()
```

## Configuration

Create a `.env` file:

```bash
ROOT_PATH=/path/to/project/to/analyze
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

## Supported Languages

- Python
- JavaScript
- TypeScript
- Ruby
- Go
- C#
- Java
- PHP

## Node Types

- `FILE`: Source files
- `FOLDER`: Directories
- `CLASS`: Class definitions
- `FUNCTION`: Function/method definitions
- `DEFINITION`: Variables, imports, constants

## Relationship Types

- `CONTAINS`: Hierarchical containment
- `CALLS`: Function calls
- `REFERENCES`: Code references
- `INHERITS`: Class inheritance

## Database Integration

### Neo4j

```python
from blarify.db_managers.neo4j_manager import Neo4jManager

db = Neo4jManager(repo_id="project", entity_id="org")
db.save_graph(nodes, relationships)
db.close()
```

### FalkorDB

```python
from blarify.db_managers.falkordb_manager import FalkorDBManager

db = FalkorDBManager(repo_id="project", entity_id="org")
db.save_graph(nodes, relationships)
db.close()
```

## Pull Request Analysis

Add pull request changes to the graph for AI analysis:

```python
from blarify.prebuilt.graph_diff_builder import GraphDiffBuilder
from blarify.project_graph_diff_creator import FileDiff, ChangeType

diffs = [FileDiff(path="/path/to/file.py", diff_text="...", change_type=ChangeType.MODIFIED)]
builder = GraphDiffBuilder(root_path="/path/to/project", file_diffs=diffs)
graph_with_pr = builder.build()
```

## Options

```python
builder = GraphBuilder(
    root_path="/path/to/project",
    extensions_to_skip=[".json", ".md"],
    names_to_skip=["node_modules", "__pycache__"],
    only_hierarchy=True  # Skip semantic relationships for speed
)
```

## Example

<img src="https://raw.githubusercontent.com/blarApp/blarify/refs/heads/main/docs/visualisation.png"></img>
This graph was generated from the code in this repository.

## Development

```bash
poetry install
poetry run python -m blarify.main
```

## Requirements

- Python 3.10-3.14
- Neo4j or FalkorDB database

## Article

Read our article on Medium to learn more about the motivation behind this project:

[How we built a tool to turn any codebase into a graph of its relationships](https://medium.com/@v4rgas/how-we-built-a-tool-to-turn-any-code-base-into-a-graph-of-its-relationships-23c7bd130f13)

## Links

- [Documentation](docs/source/quickstart.rst)
- [Issues](https://github.com/blarApp/blarify/issues)
- [Discord](https://discord.gg/s8pqnPt5AP)
