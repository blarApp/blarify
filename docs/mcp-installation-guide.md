# Blarify MCP Server Installation Guide

This guide explains how to install and configure the Blarify MCP (Model Context Protocol) Server for use with Claude Desktop and other MCP-compatible AI assistants.

## Prerequisites

Before installing the MCP server, ensure you have:

1. **Python 3.11-3.14** installed
2. **Docker** (optional, for running Neo4j locally)
3. **Neo4j or FalkorDB** database with Blarify graph data
4. **pip** or **poetry** package manager

## Installation Methods

### Method 1: Install from PyPI (Recommended)

Once Blarify is published to PyPI:

```bash
pip install blarify
```

Or with specific extras:

```bash
pip install "blarify[mcp]"
```

### Method 2: Install from GitHub

Install directly from the repository:

```bash
pip install git+https://github.com/blarApp/blarify.git@feature/mcp-server-implementation
```

### Method 3: Install from Source

Clone and install locally:

```bash
# Clone the repository
git clone https://github.com/blarApp/blarify.git
cd blarify

# Install with poetry
poetry install

# Or install with pip
pip install -e .
```

## Configuration

### Step 1: Set Up Environment Variables

Create a `.env` file in your project directory or set environment variables:

```bash
# Neo4j Configuration
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USERNAME="neo4j"
export NEO4J_PASSWORD="your-password"
export REPOSITORY_ID="your-repo-id"
export ENTITY_ID="your-entity-id"
export DB_TYPE="neo4j"

# Optional: FalkorDB Configuration
# export DB_TYPE="falkordb"
# export FALKOR_HOST="localhost"
# export FALKOR_PORT="6379"
```

### Step 2: Populate Your Database

Before using the MCP server, you need to build and save a code graph:

```python
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager

# Build the graph
builder = GraphBuilder(root_path="/path/to/your/code")
graph = builder.build()

# Save to Neo4j
db_manager = Neo4jManager(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="your-password",
    repo_id="your-repo-id",
    entity_id="your-entity-id"
)

db_manager.save_graph(
    graph.get_nodes_as_objects(),
    graph.get_relationships_as_objects()
)
db_manager.close()
```

### Step 3: Test the Installation

Verify the MCP server is installed correctly:

```bash
# Test the server can start
python -m blarify.mcp_server --help

# Run the server in test mode
python -m blarify.mcp_server
```

## Claude Desktop Integration

### Step 1: Locate Claude Desktop Config

Find your Claude Desktop configuration file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/claude/claude_desktop_config.json`

### Step 2: Add Blarify MCP Server

Edit the configuration file to add Blarify:

```json
{
  "mcpServers": {
    "blarify": {
      "command": "python",
      "args": ["-m", "blarify.mcp_server"],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "your-password",
        "REPOSITORY_ID": "your-repo",
        "ENTITY_ID": "your-entity",
        "DB_TYPE": "neo4j"
      }
    }
  }
}
```

### Step 3: Restart Claude Desktop

1. Completely quit Claude Desktop
2. Start Claude Desktop again
3. The Blarify tools should now be available

### Step 4: Verify Integration

In Claude Desktop, you can verify the tools are loaded by asking:
- "What MCP tools are available?"
- "Can you explore the directory structure of my code?"

## Running Neo4j with Docker

If you don't have Neo4j installed, you can run it with Docker:

```bash
# Run Neo4j container
docker run -d \
  --name neo4j-blarify \
  -p 7474:7474 \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# Wait for Neo4j to start (about 10-20 seconds)
sleep 20

# Now you can use bolt://localhost:7687 as your NEO4J_URI
```

## Alternative: Using with Poetry

If you're developing with Blarify:

```bash
# Install dependencies
poetry install

# Run the MCP server
poetry run python -m blarify.mcp_server
```

## Standalone Script Installation

For users who want a simple script-based approach:

```bash
# Create a startup script
cat > ~/bin/blarify-mcp << 'EOF'
#!/usr/bin/env python
import os
import sys

# Add your configuration here
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USERNAME", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "password")
os.environ.setdefault("REPOSITORY_ID", "default")
os.environ.setdefault("ENTITY_ID", "default")

from blarify.mcp_server import main
main()
EOF

# Make it executable
chmod +x ~/bin/blarify-mcp

# Now use this in Claude Desktop config:
{
  "mcpServers": {
    "blarify": {
      "command": "~/bin/blarify-mcp"
    }
  }
}
```

## Troubleshooting

### Common Issues

#### 1. Module Not Found Error

```
ModuleNotFoundError: No module named 'blarify'
```

**Solution**: Ensure Blarify is installed in the Python environment:
```bash
pip list | grep blarify
# If not found:
pip install blarify
```

#### 2. FastMCP Not Found

```
ModuleNotFoundError: No module named 'fastmcp'
```

**Solution**: Install the FastMCP dependency:
```bash
pip install fastmcp>=2.12.0
```

#### 3. Database Connection Failed

```
Error: Could not connect to Neo4j
```

**Solution**: 
- Verify Neo4j is running: `docker ps` or check Neo4j Browser at http://localhost:7474
- Check credentials are correct
- Ensure firewall allows connection to port 7687

#### 4. No Tools Available in Claude

**Solution**:
- Check Claude Desktop logs for errors
- Verify the configuration file syntax is correct (valid JSON)
- Ensure Python path in config points to correct Python with Blarify installed

### Checking Logs

Claude Desktop logs can help debug issues:

**macOS**: 
```bash
tail -f ~/Library/Logs/Claude/mcp-server-blarify.log
```

**Windows**: Check Event Viewer or:
```powershell
Get-Content "$env:APPDATA\Claude\Logs\mcp-server-blarify.log" -Tail 50 -Wait
```

## Available Tools

Once installed, these tools become available in Claude Desktop:

1. **directory_explorer** - Navigate repository structure
2. **find_nodes_by_code** - Search for code by text
3. **find_nodes_by_name_and_type** - Find nodes by name/type
4. **find_nodes_by_path** - Find nodes at file paths
5. **get_code_by_id** - Get node details
6. **get_file_context_by_id** - Get expanded file context
7. **get_blame_by_id** - GitHub blame information
8. **get_commit_by_id** - Commit information
9. **get_node_workflows** - Workflow information
10. **get_relationship_flowchart** - Generate Mermaid diagrams

## Example Usage in Claude Desktop

Once configured, you can ask Claude:

```
"Can you explore the structure of my repository?"
"Find all functions that contain 'process_data'"
"Show me the code for the main function"
"Generate a flowchart of function calls from the entry point"
```

## Updating the MCP Server

To update to the latest version:

```bash
# With pip
pip install --upgrade blarify

# With poetry
poetry update blarify

# From source
git pull origin main
poetry install
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/blarApp/blarify/issues
- Documentation: https://blar.io/docs
- Discord: [Join our community](https://discord.gg/blarify)

## Next Steps

After installation:
1. Build your code graph with GraphBuilder
2. Configure your database connection
3. Test with Claude Desktop
4. Explore your codebase with natural language!