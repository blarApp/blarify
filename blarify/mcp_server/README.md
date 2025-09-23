# Blarify MCP Server

The Blarify MCP (Model Context Protocol) Server exposes Blarify's powerful graph-based code analysis tools through the MCP interface, enabling integration with Claude Desktop and other MCP-compatible AI assistants.

## Features

- **11 Powerful Code Analysis Tools**: All Blarify Langchain tools available through MCP
- **Database Flexibility**: Support for both Neo4j and FalkorDB backends
- **Type-Safe**: Comprehensive type hints and strict validation
- **Async-First**: Built for performance with async/await support
- **Easy Configuration**: Environment-based configuration with sensible defaults

## Available Tools

1. **directory_explorer** - Navigate repository structure
2. **find_nodes_by_code** - Search for code by text content
3. **find_nodes_by_name_and_type** - Find nodes by name and type
4. **find_nodes_by_path** - Find nodes at specific file paths
5. **get_code_by_id** - Get detailed node information by ID
6. **get_file_context_by_id** - Get expanded file context around a node
7. **get_blame_by_id** - Get GitHub blame information
8. **get_commit_by_id** - Get commit information
9. **get_node_workflows** - Get workflow information for a node
10. **get_relationship_flowchart** - Generate Mermaid diagrams of relationships

## Installation

### Quick Setup

1. **Install Blarify**:
```bash
pip install blarify
# or
uvx install blarify
```

2. **Create a graph for your repository**:
```bash
cd /path/to/your/repository
blarify create --entity-id your-company
```

This automatically:
- Sets up a Neo4j container (if needed)
- Builds the code graph
- Saves project configuration for MCP server

3. **Configure Claude Desktop**:

Add to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**Linux**: `~/.config/claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "blarify": {
      "command": "blarify-mcp",
      "args": ["--project", "/path/to/your/repository"]
    }
  }
}
```

Or if you have only one project, simply:

```json
{
  "mcpServers": {
    "blarify": {
      "command": "blarify-mcp",
      "args": []
    }
  }
}
```

## Configuration

The MCP server automatically uses the configuration saved by `blarify create`. No environment variables or `.env` files are needed!

### Project Management

**List available projects**:
```bash
blarify-mcp --list
```

**Start server with specific project**:
```bash
blarify-mcp --project /path/to/repository
```

**Start server from within project directory** (auto-detects):
```bash
cd /path/to/repository
blarify-mcp
```

**If only one project exists**, the server will use it automatically:
```bash
blarify-mcp
```

## Usage

### Running the Server Standalone

```bash
# Auto-detect project from current directory
cd /path/to/your/repository
blarify-mcp

# Specify a project explicitly
blarify-mcp --project /path/to/your/repository

# List all available projects
blarify-mcp --list

# Using Python module directly
python -m blarify.mcp_server --project /path/to/repository
```

### Programmatic Usage

```python
import asyncio
from blarify.mcp_server.config import MCPServerConfig
from blarify.mcp_server.server import BlarifyMCPServer

async def main():
    # Load configuration from saved project
    config = MCPServerConfig.from_project("/path/to/your/repository")

    # Or auto-detect from current directory
    config = MCPServerConfig.from_project()

    # Create and run server
    server = BlarifyMCPServer(config)
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())
```

### Using with FalkorDB

```python
config = MCPServerConfig(
    db_type="falkordb",
    falkor_host="localhost",
    falkor_port=6379,
    root_path="/path/to/your/repository",
    entity_id="my_entity"
)
```

## Tool Examples

### Directory Explorer

```json
{
  "tool": "directory_explorer",
  "arguments": {
    "node_id": null  // null for root, or specific node ID
  }
}
```

### Find Nodes by Code

```json
{
  "tool": "find_nodes_by_code",
  "arguments": {
    "code_text": "def main"
  }
}
```

### Get Code by ID

```json
{
  "tool": "get_code_by_id",
  "arguments": {
    "node_id": "node_123"
  }
}
```

### Get File Context

```json
{
  "tool": "get_file_context_by_id",
  "arguments": {
    "node_id": "node_123",
    "context_lines": 10
  }
}
```

## Prerequisites

1. **Build a Code Graph**: Use the Blarify CLI to create a graph for your repository:

```bash
# Install Blarify
pip install blarify

# Build a graph for your repository (auto-spawns Neo4j if needed)
cd /path/to/your/repository
blarify create --entity-id my-company

# With documentation and workflows
blarify create --entity-id my-company --docs --workflows

# With existing Neo4j instance
blarify create --entity-id my-company \
  --neo4j-uri bolt://localhost:7687 \
  --neo4j-username neo4j \
  --neo4j-password your-password
```

2. **Start the MCP Server**: After creating the graph, start the server:

```bash
# From the same directory
blarify-mcp

# Or from anywhere
blarify-mcp --project /path/to/your/repository
```

## Troubleshooting

### Connection Issues

If you get connection errors:
1. Verify your database is running
2. Check connection credentials
3. Ensure network connectivity
4. Check firewall settings

### No Data Returned

If tools return empty results:
1. Verify graph data exists in database
2. Ensure you're using the correct project: `blarify-mcp --list`
3. Re-run `blarify create` if needed
4. Use Neo4j Browser to verify data

### Performance Issues

For better performance:
1. Ensure database has proper indexes
2. Use connection pooling (built-in)
3. Consider caching frequent queries
4. Run database on same network

## Testing

Run tests with:

```bash
# Unit tests
poetry run pytest tests/unit/mcp_server/

# Integration tests (requires Docker)
poetry run pytest tests/integration/test_mcp_server_neo4j.py

# All MCP tests
poetry run pytest -k mcp_server
```

## Architecture

The MCP server follows a clean architecture:

```
mcp_server/
├── __init__.py           # Package initialization
├── server.py             # Main server implementation
├── config.py             # Configuration management
├── tools/                # Tool adapters
│   ├── __init__.py
│   └── base.py          # Base wrapper class
└── README.md            # This file
```

### Key Components

1. **BlarifyMCPServer**: Main server class that initializes tools and handles MCP protocol
2. **MCPServerConfig**: Configuration management with validation
3. **MCPToolWrapper**: Adapter that converts Langchain tools to MCP format
4. **Database Managers**: Abstract interface for Neo4j/FalkorDB

## Contributing

When adding new tools:

1. Add the tool to `blarify/tools/`
2. Import in `server.py`
3. Add to tool initialization list
4. Update documentation
5. Add tests

## Performance Characteristics

- **Startup Time**: < 2 seconds
- **Tool Invocation Latency**: < 100ms (excluding DB query time)
- **Memory Usage**: ~50-100MB base
- **Concurrent Requests**: 10+ supported

## Security Considerations

1. **Credentials**: Never commit database credentials
2. **Network**: Use SSL/TLS for production databases
3. **Access Control**: Implement proper database user permissions
4. **Input Validation**: All inputs are validated before database queries

## License

MIT License - See LICENSE file in the root directory

## Support

For issues or questions:
- GitHub Issues: https://github.com/blarApp/blarify/issues
- Documentation: https://blar.io

## Version History

- **1.0.0** - Initial MCP server implementation
  - Support for all 10 Langchain tools
  - Neo4j and FalkorDB support
  - Comprehensive testing
  - Full type safety