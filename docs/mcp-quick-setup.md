# Blarify MCP - Quick Setup

## The Simplest Way: Using uvx (Recommended)

Just add this to your Claude Desktop config:

```json
{
  "mcpServers": {
    "blarify": {
      "command": "uvx",
      "args": ["blarify-mcp"],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "your-password"
      }
    }
  }
}
```

That's it! `uvx` will handle the installation automatically.

## Alternative: Using pip

If you prefer pip:

```bash
pip install blarify
```

Then configure Claude Desktop:

```json
{
  "mcpServers": {
    "blarify": {
      "command": "blarify-mcp",
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "your-password"
      }
    }
  }
}
```

## Quick Database Setup

If you need a Neo4j database quickly:

```bash
docker run -d \
  -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

## Build Your Code Graph

```python
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager

# Build and save
builder = GraphBuilder(root_path="/your/code")
graph = builder.build()

db = Neo4jManager(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)
db.save_graph(
    graph.get_nodes_as_objects(),
    graph.get_relationships_as_objects()
)
db.close()
```

## That's All!

Restart Claude Desktop and you're ready to explore your code with natural language.

## Comparison with Other MCP Tools

| Tool | Installation |
|------|-------------|
| filesystem | `"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem"]` |
| github | `"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"]` |
| **blarify** | `"command": "uvx", "args": ["blarify-mcp"]` |

Just as simple as any other MCP tool!