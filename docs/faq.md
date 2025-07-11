# FAQ - Frequently Asked Questions

This document answers common questions about Blarify, its usage, and troubleshooting.

## Table of Contents

1. [General Questions](#general-questions)
2. [Installation & Setup](#installation--setup)
3. [Usage Questions](#usage-questions)
4. [Language Support](#language-support)
5. [Database Questions](#database-questions)
6. [Performance Questions](#performance-questions)
7. [Troubleshooting](#troubleshooting)
8. [Integration Questions](#integration-questions)

## General Questions

### What is Blarify?

Blarify is a tool that converts your codebase into a graph structure, allowing you to visualize and analyze code relationships, dependencies, and architecture. It uses Language Server Protocol (LSP) and Tree-sitter for accurate code analysis.

### What can I do with Blarify?

- **Visualize code architecture** in graph databases like Neo4j or FalkorDB
- **Analyze dependencies** and find circular dependencies
- **Track code changes** and their impact
- **Understand large codebases** by exploring relationships
- **Refactor code** with confidence by understanding impacts
- **Generate documentation** from code structure

### How is Blarify different from other code analysis tools?

- **Graph-based representation**: Stores code as nodes and relationships
- **Multi-language support**: Works with Python, JavaScript, TypeScript, Ruby, Go, C#
- **LSP integration**: Uses language servers for accurate semantic analysis
- **Database storage**: Stores results in graph databases for querying
- **Change tracking**: Can track and visualize code changes over time

### Is Blarify open source?

Yes! Blarify is open source under the MIT license. You can find the source code on [GitHub](https://github.com/blarApp/blarify).

## Installation & Setup

### What are the system requirements?

- **Python**: 3.10 to 3.14
- **Operating System**: Linux, macOS, or Windows
- **Memory**: At least 2GB RAM (more for large projects)
- **Database**: Neo4j or FalkorDB for storing results

### Do I need to install a graph database?

Yes, you need either Neo4j or FalkorDB to store and visualize the graph data. FalkorDB is generally easier to set up for beginners.

### Can I use Blarify without a database?

Yes, you can build graphs and work with them in memory without saving to a database. However, you'll lose the ability to persist and query the data.

```python
# Use without database
from blarify.prebuilt.graph_builder import GraphBuilder

builder = GraphBuilder(root_path="/path/to/project")
graph = builder.build()

# Work with nodes and relationships in memory
nodes = graph.get_nodes_as_objects()
relationships = graph.get_relationships_as_objects()
```

### How do I install Blarify in a Docker container?

```dockerfile
FROM python:3.11-slim

# Install Blarify
RUN pip install blarify

# Set up your application
COPY . /app
WORKDIR /app

# Run analysis
CMD ["python", "analyze.py"]
```

## Usage Questions

### How do I analyze a specific directory?

```python
from blarify.prebuilt.graph_builder import GraphBuilder

# Analyze specific directory
builder = GraphBuilder(root_path="/path/to/specific/directory")
graph = builder.build()
```

### Can I exclude certain files or directories?

Yes, use the filtering options:

```python
builder = GraphBuilder(
    root_path="/path/to/project",
    extensions_to_skip=[".json", ".md", ".txt", ".log"],
    names_to_skip=["node_modules", "__pycache__", ".git", "venv"]
)
```

### How do I analyze only the file structure without relationships?

Use the `only_hierarchy` option for faster analysis:

```python
builder = GraphBuilder(
    root_path="/path/to/project",
    only_hierarchy=True  # Skip LSP relationship analysis
)
```

### Can I analyze a project without internet connection?

Yes, Blarify works completely offline. It only analyzes local files and doesn't require internet connectivity.

### How do I get just the file and folder structure?

```python
# Get only file and folder nodes
nodes = graph.get_nodes_as_objects()
structure_nodes = [
    node for node in nodes 
    if node["type"] in ["FILE", "FOLDER"]
]
```

## Language Support

### Which programming languages are supported?

Currently supported languages:
- **Python** (full LSP support)
- **JavaScript/TypeScript** (Tree-sitter + optional LSP)
- **Ruby** (Tree-sitter)
- **Go** (Tree-sitter)
- **C#** (Tree-sitter)
- **Java** (Tree-sitter)
- **PHP** (Tree-sitter)

### How accurate is the analysis for each language?

- **Python**: Very accurate with Jedi Language Server
- **JavaScript/TypeScript**: Good accuracy with Tree-sitter, excellent with LSP
- **Other languages**: Good structural analysis with Tree-sitter

### Can I add support for a new language?

Yes! See our [Contributing Guide](contributing.md) for details on adding language support. You'll need to:

1. Add Tree-sitter grammar dependency
2. Create language-specific definitions
3. Optionally configure LSP server
4. Add tests

### Why doesn't my TypeScript project show all relationships?

Make sure you have a TypeScript language server configured:

```bash
# Install TypeScript language server
npm install -g typescript-language-server typescript

# Or configure in your project
npm install --save-dev typescript-language-server typescript
```

### How do I improve analysis accuracy for my language?

1. **Install language server**: Adds semantic analysis
2. **Configure properly**: Ensure language server can find dependencies
3. **Include type information**: Better for strongly-typed languages
4. **Exclude generated files**: Focus on source code

## Database Questions

### Which database should I choose: Neo4j or FalkorDB?

**FalkorDB**:
- ✅ Easier to set up (Redis-compatible)
- ✅ Faster for read operations
- ✅ Lower memory usage
- ❌ Smaller ecosystem

**Neo4j**:
- ✅ Mature ecosystem
- ✅ Better tooling (Neo4j Browser, Bloom)
- ✅ Cloud options (AuraDB)
- ❌ More complex setup

**Recommendation**: Start with FalkorDB for simplicity, move to Neo4j for production.

### How do I connect to a remote database?

```python
# Remote Neo4j
from blarify.db_managers.neo4j_manager import Neo4jManager

manager = Neo4jManager(
    uri="bolt://your-server:7687",
    user="your-username",
    password="your-password",
    repo_id="my-repo",
    entity_id="my-org"
)

# Remote FalkorDB
from blarify.db_managers.falkordb_manager import FalkorDBManager

manager = FalkorDBManager(
    uri="your-server",
    port=6379,
    password="your-password",
    repo_id="my-repo",
    entity_id="my-org"
)
```

### Can I use multiple databases simultaneously?

Yes, you can save the same graph to multiple databases:

```python
nodes = graph.get_nodes_as_objects()
relationships = graph.get_relationships_as_objects()

# Save to Neo4j
neo4j_manager = Neo4jManager(repo_id="repo", entity_id="org")
neo4j_manager.save_graph(nodes, relationships)
neo4j_manager.close()

# Save to FalkorDB
falkor_manager = FalkorDBManager(repo_id="repo", entity_id="org")
falkor_manager.save_graph(nodes, relationships)
falkor_manager.close()
```

### How do I query the saved graph data?

**Neo4j (Cypher)**:
```cypher
// Find all Python files
MATCH (n:FILE) 
WHERE n.path ENDS WITH '.py' 
RETURN n.name, n.path

// Find functions with most dependencies
MATCH (f:FUNCTION)-[r]->(target)
RETURN f.name, count(r) as dependency_count
ORDER BY dependency_count DESC
LIMIT 10
```

**FalkorDB (Cypher)**:
```python
from falkordb import FalkorDB

db = FalkorDB()
graph = db.select_graph("your-repo-id")

# Query functions
result = graph.query("MATCH (f:FUNCTION) RETURN f.name LIMIT 10")
print(result.result_set)
```

## Performance Questions

### How long does analysis take?

Analysis time depends on:
- **Project size**: ~1-10 seconds per 1000 files
- **Language complexity**: Python/TypeScript slower than Go/Ruby
- **LSP enabled**: 2-5x slower but more accurate
- **System resources**: CPU and memory affect speed

### My analysis is very slow. How can I speed it up?

1. **Skip unnecessary files**:
   ```python
   builder = GraphBuilder(
       root_path="/path",
       extensions_to_skip=[".json", ".md", ".log", ".txt"],
       names_to_skip=["node_modules", "__pycache__", ".git"]
   )
   ```

2. **Use hierarchy-only mode**:
   ```python
   builder = GraphBuilder(root_path="/path", only_hierarchy=True)
   ```

3. **Exclude large directories**:
   ```python
   names_to_skip=["node_modules", "vendor", "build", "dist", "target"]
   ```

4. **Analyze in chunks**: For very large projects, analyze subdirectories separately

### How much memory does Blarify use?

Memory usage varies by project size:
- **Small projects** (< 1000 files): 50-200 MB
- **Medium projects** (1000-10000 files): 200-1000 MB  
- **Large projects** (> 10000 files): 1-5 GB

### Can I analyze very large codebases?

Yes, but consider these strategies:
- **Filter aggressively**: Skip test files, generated code
- **Analyze incrementally**: Process subdirectories separately
- **Use more memory**: Increase available RAM
- **Disable LSP**: Use Tree-sitter only for faster analysis

## Troubleshooting

### "Permission denied" errors

```bash
# On Linux/macOS, you might need:
chmod +x /path/to/blarify

# Or install in user directory:
pip install --user blarify
```

### Language server won't start

1. **Check installation**:
   ```bash
   # For Python
   pip install jedi-language-server
   
   # For TypeScript  
   npm install -g typescript-language-server
   ```

2. **Check PATH**: Ensure language servers are in your PATH
3. **Check permissions**: Language servers need execute permissions
4. **Try manual start**: Test language server independently

### "Tree-sitter parser not found" error

```bash
# Reinstall with all dependencies
pip uninstall blarify
pip install blarify

# Or install specific Tree-sitter grammars
pip install tree-sitter-python tree-sitter-javascript
```

### Database connection issues

**Neo4j**:
```bash
# Check if Neo4j is running
docker ps | grep neo4j

# Test connection
telnet localhost 7687
```

**FalkorDB**:
```bash
# Check if FalkorDB is running
docker ps | grep falkordb

# Test connection
redis-cli -p 6379 ping
```

### Out of memory errors

1. **Increase system memory**
2. **Reduce project scope**:
   ```python
   # Analyze smaller parts
   builder = GraphBuilder(
       root_path="/path/to/specific/module",
       # ... filtering options
   )
   ```
3. **Use hierarchy-only mode**
4. **Close other applications**

### Import errors

```bash
# Reinstall in clean environment
pip uninstall blarify
python -m venv fresh_env
source fresh_env/bin/activate
pip install blarify
```

## Integration Questions

### Can I use Blarify in CI/CD pipelines?

Yes! Here's a GitHub Actions example:

```yaml
name: Code Analysis
on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install Blarify
        run: pip install blarify
      - name: Analyze code
        run: python scripts/analyze.py
```

### How do I integrate with existing tools?

**Jupyter Notebooks**:
```python
# In Jupyter cell
from blarify.prebuilt.graph_builder import GraphBuilder
import matplotlib.pyplot as plt

builder = GraphBuilder(root_path=".")
graph = builder.build()
# Visualize results...
```

**VS Code Extension**: (Coming soon)

**Web Dashboards**: Export data and use with D3.js, Cytoscape.js, etc.

### Can I export data to other formats?

```python
import json
import csv

# Export to JSON
nodes = graph.get_nodes_as_objects()
with open("nodes.json", "w") as f:
    json.dump(nodes, f, indent=2)

# Export to CSV
import pandas as pd
df = pd.DataFrame(nodes)
df.to_csv("nodes.csv", index=False)

# Export relationships
relationships = graph.get_relationships_as_objects()
with open("relationships.json", "w") as f:
    json.dump(relationships, f, indent=2)
```

### How do I schedule regular analysis?

**Cron job**:
```bash
# Analyze daily at 2 AM
0 2 * * * cd /path/to/project && python analyze.py
```

**GitHub Actions with schedule**:
```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
```

### Can I compare different versions of my code?

Yes, use the diff functionality:

```python
from blarify.project_graph_diff_creator import ProjectGraphDiffCreator

# Compare current state with previous version
diff_creator = ProjectGraphDiffCreator(...)
graph_update = diff_creator.build_with_previous_node_states(previous_states)

# Get changes
nodes = graph_update.get_nodes_as_objects()
added_nodes = [n for n in nodes if "ADDED" in n.get("extra_labels", [])]
modified_nodes = [n for n in nodes if "MODIFIED" in n.get("extra_labels", [])]
```

---

## Still have questions?

- **GitHub Discussions**: [Ask a question](https://github.com/blarApp/blarify/discussions)
- **Discord**: Join our [community](https://discord.gg/s8pqnPt5AP)
- **Issues**: [Report bugs](https://github.com/blarApp/blarify/issues)
- **Email**: Contact maintainers for sensitive issues

We're here to help! 🚀
