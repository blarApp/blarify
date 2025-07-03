# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## About Blarify

Blarify is a Python library that converts local code repositories into graph structures for LLM analysis. It supports multiple programming languages (Python, JavaScript, TypeScript, Ruby, Go, C#, Java, PHP) and uses Language Server Protocol (LSP) to understand code relationships and hierarchy.

## Development Setup

**Prerequisites:**
- Python 3.10-3.14
- Poetry (package manager)
- Neo4j database (for graph storage)

**Installation:**
```bash
poetry install
```

**Environment Variables:**
Create a `.env` file with:
```
ROOT_PATH=/path/to/project/to/analyze
BLARIGNORE_PATH=/path/to/blarignore/file  # optional
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

## Common Commands

**Run the main analyzer:**
```bash
poetry run python -m blarify.main
```

**Run tests:**
```bash
# No tests currently exist in this project
```

**Code formatting and linting:**
```bash
poetry run ruff check .
poetry run ruff format .
```

**Build documentation:**
```bash
cd docs
pip install -r requirements.txt
make html
```

## Architecture Overview

### Core Components

1. **ProjectGraphCreator** (`blarify/project_graph_creator.py`): Main orchestrator that builds complete project graphs by analyzing file structure and code relationships.

2. **ProjectGraphDiffCreator** (`blarify/project_graph_diff_creator.py`): Handles incremental updates by analyzing file diffs and updating only affected parts of the graph.

3. **ProjectGraphUpdater** (`blarify/project_graph_updater.py`): Updates existing graphs when files are modified, handling deletion and recreation of affected nodes.

4. **Graph System** (`blarify/graph/`):
   - `Graph`: Core data structure storing nodes and relationships
   - `Node` types: File, Folder, Class, Function, and Definition nodes
   - `Relationship` types: Contains, Calls, References, Inherits, etc.

5. **Language Support** (`blarify/code_hierarchy/languages/`):
   - Language-specific parsers using Tree-sitter
   - LSP integration for semantic analysis
   - Supports Python, JavaScript, TypeScript, Ruby, Go, C#, Java, PHP

6. **Database Managers** (`blarify/db_managers/`):
   - `Neo4jManager`: Primary graph database implementation
   - `FalkorDbManager`: Alternative graph database support
   - Abstract interface for database operations

### Key Data Flow

1. **File Discovery**: `ProjectFilesIterator` scans project directory respecting ignore patterns
2. **Syntax Analysis**: Tree-sitter parsers extract code structure per language
3. **Semantic Analysis**: LSP servers provide references, definitions, and relationships
4. **Graph Construction**: Nodes and relationships are created and stored in `Graph` object
5. **Database Storage**: Graph is persisted to Neo4j/FalkorDB

### Node Types and Relationships

**Node Types:**
- `FILE`: Represents source code files
- `FOLDER`: Directory structure
- `CLASS`: Class definitions
- `FUNCTION`: Function/method definitions
- `DEFINITION`: Variables, imports, etc.

**Relationship Types:**
- `CONTAINS`: Folder contains file, file contains class/function
- `CALLS`: Function calls another function
- `REFERENCES`: Code references a definition
- `INHERITS`: Class inheritance relationships

## Prebuilt Classes

Use the prebuilt classes in `blarify/prebuilt/` for easy integration:

- `GraphBuilder`: Main entry point for building complete graphs
- `GraphDiffBuilder`: For incremental updates based on file diffs

## Testing

No tests currently exist in this project. To add testing capabilities, you would need to:
1. Add pytest as a dev dependency: `poetry add --group dev pytest`
2. Create test files in a `tests/` directory
3. Configure pytest in pyproject.toml if needed

## Language Server Dependencies

The system automatically manages language server installations. Each supported language has its LSP server configured in the `multilspy` vendor package.

## Database Schema

The graph database stores:
- Nodes with properties: id, label, path, name, level, content
- Relationships with properties: type, source_id, target_id
- Hierarchical structure preserving file system organization
- Code-level relationships for semantic understanding