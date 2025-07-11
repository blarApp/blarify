# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Blarify converts source code repositories into graph structures for LLM analysis. It supports Python, JavaScript, TypeScript, Ruby, Go, and C# through Tree-sitter and LSP integration.

## Documentation

- **Index File**: `@docs/index.md` is the file where you can go to know where to look for context in the docs
- **Installation**: See `docs/installation.md`
- **Getting Started**: See `docs/quickstart.md` 
- **API Reference**: See `docs/api-reference.md`

## Development Commands

### Package Management
```bash
poetry install          # Install dependencies
poetry add <package>    # Add dependency
```

### Code Quality
```bash
poetry run ruff check   # Lint (120 char line length)
poetry run codespell    # Spell check
poetry run isort .      # Format imports
```

### Build
```bash
poetry build           # Build package
pip install -e .       # Install for development
```

## Core Architecture

### Entry Points
- `main.py`: Four execution modes (full, diff, update, diff_with_previous)
- `prebuilt/graph_builder.py`: Simplified API for users

### Key Components
- **ProjectGraphCreator**: Core graph building
- **LspQueryHelper**: Language Server Protocol integration  
- **Database Managers**: Neo4j and FalkorDB support via abstract interface
- **Language Definitions**: Extensible support in `code_hierarchy/languages/`

### Graph Structure
Creates nodes (File, Class, Function) and relationships (Imports, Calls, Inherits) with file paths, line numbers, and diff identifiers.

## Configuration

### Environment Variables
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
ROOT_PATH=/path/to/project
```

### File Filtering
- `extensions_to_skip`: e.g., [".json", ".xml"]
- `names_to_skip`: e.g., ["__pycache__"]
- `.blarignore`: Custom ignore patterns

## Vendor Dependencies
Uses vendored `multilspy` library. Update with:
```bash
poetry run vendoring sync
```

## Testing
No test suite currently exists.

## Working with Claude Code

### Documentation First
Always check existing documentation files (`docs/*.md`) before answering questions or starting implementation. Always start in the docs/index.md 

### Planning Requirements
Before coding, create a clear written plan with:
- Specific tasks broken down into small, manageable steps
- Clear objectives for each step
- Dependencies between tasks identified

### Test-Driven Development
Follow TDD approach:
1. Write one test for the next small piece of functionality
2. Run the test (it should fail)
3. Write minimal code to make the test pass
4. Refactor if needed
5. Move to next test/functionality

This ensures code quality and prevents over-engineering.