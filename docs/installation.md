# Installation Guide

This guide will help you install and set up Blarify for analyzing your codebase.

## Prerequisites

Before installing Blarify, ensure you have the following:

### System Requirements
- **Python**: Version 3.10 to 3.14 (inclusive)
- **Operating System**: Linux, macOS, or Windows
- **Memory**: At least 2GB RAM (more recommended for large codebases)
- **Disk Space**: Sufficient space for your codebase and graph data

### Graph Database
Blarify requires a graph database to store and visualize your code relationships. We support:

- **[FalkorDB](https://falkordb.com/)** (Recommended for beginners)
- **[Neo4j](https://neo4j.com/)** (Self-hosted or AuraDB)

## Installation Methods

### Method 1: Using pip (Recommended)

Install Blarify directly from PyPI:

```bash
pip install blarify
```

### Method 2: Using Poetry

If you're using Poetry for dependency management:

```bash
poetry add blarify
```

### Method 3: From Source

For development or to get the latest features:

```bash
git clone https://github.com/blarApp/blarify.git
cd blarify
pip install -e .
```

## Virtual Environment Setup

We strongly recommend using a virtual environment to avoid conflicts with other Python packages.

### Using venv

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install Blarify
pip install blarify
```

### Using conda

```bash
# Create conda environment
conda create -n blarify python=3.11
conda activate blarify

# Install Blarify
pip install blarify
```

## Database Setup

### Option 1: FalkorDB (Easiest)

FalkorDB is a Redis-compatible graph database that's easy to set up.

#### Using Docker (Recommended)

```bash
# Run FalkorDB in Docker
docker run -d --name falkordb -p 6379:6379 falkordb/falkordb:latest
```

#### Using Redis Stack

```bash
# If you have Redis Stack installed
redis-stack-server
```

#### Environment Variables for FalkorDB

Create a `.env` file in your project directory:

```env
FALKORDB_URI=localhost
FALKORDB_PORT=6379
# Optional authentication (if configured)
FALKORDB_USERNAME=your_username
FALKORDB_PASSWORD=your_password
```

### Option 2: Neo4j

#### Neo4j Desktop (Local Development)

1. Download [Neo4j Desktop](https://neo4j.com/download/)
2. Install and create a new database
3. Start the database and note the connection details

#### Neo4j AuraDB (Cloud)

1. Sign up for [Neo4j AuraDB](https://neo4j.com/product/auradb/)
2. Create a new database instance
3. Download the connection credentials

#### Environment Variables for Neo4j

Create a `.env` file in your project directory:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password

# For AuraDB, use the provided connection string
# NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
```

## Language Server Setup

Blarify uses Language Server Protocol (LSP) for advanced code analysis. Some language servers are installed automatically, while others may need manual setup.

### Automatically Supported Languages

These languages work out of the box:
- **Python** (using Jedi Language Server)
- **JavaScript/TypeScript** (using built-in Tree-sitter)
- **Ruby** (using built-in Tree-sitter)
- **Go** (using built-in Tree-sitter)
- **C#** (using built-in Tree-sitter)

### Manual Language Server Setup

For enhanced analysis of specific languages, you may want to install additional language servers:

#### JavaScript/TypeScript
```bash
npm install -g typescript-language-server typescript
```

#### Python (Alternative)
```bash
pip install python-lsp-server
```

#### Go
```bash
go install golang.org/x/tools/gopls@latest
```

#### C#
```bash
# Install via .NET SDK
dotnet tool install --global csharp-ls
```

## Verification

To verify your installation is working correctly:

### 1. Test Basic Import

```python
# test_installation.py
try:
    from blarify.prebuilt.graph_builder import GraphBuilder
    print("✅ Blarify imported successfully")
except ImportError as e:
    print(f"❌ Import failed: {e}")
```

### 2. Test Database Connection

#### For FalkorDB:
```python
# test_falkordb.py
from blarify.db_managers.falkordb_manager import FalkorDBManager

try:
    manager = FalkorDBManager(repo_id="test", entity_id="test")
    print("✅ FalkorDB connection successful")
    manager.close()
except Exception as e:
    print(f"❌ FalkorDB connection failed: {e}")
```

#### For Neo4j:
```python
# test_neo4j.py
from blarify.db_managers.neo4j_manager import Neo4jManager

try:
    manager = Neo4jManager(repo_id="test", entity_id="test")
    print("✅ Neo4j connection successful")
    manager.close()
except Exception as e:
    print(f"❌ Neo4j connection failed: {e}")
```

### 3. Test Simple Graph Building

```python
# test_graph_build.py
import tempfile
import os
from blarify.prebuilt.graph_builder import GraphBuilder

# Create a simple test file
with tempfile.TemporaryDirectory() as temp_dir:
    test_file = os.path.join(temp_dir, "test.py")
    with open(test_file, "w") as f:
        f.write("def hello():\n    return 'Hello, World!'")
    
    # Build graph
    try:
        builder = GraphBuilder(root_path=temp_dir)
        graph = builder.build()
        nodes = graph.get_nodes_as_objects()
        print(f"✅ Graph built successfully with {len(nodes)} nodes")
    except Exception as e:
        print(f"❌ Graph building failed: {e}")
```

## Troubleshooting

### Common Issues

#### 1. Python Version Compatibility
```bash
# Check Python version
python --version

# If using the wrong version, create a new environment
python3.11 -m venv .venv
```

#### 2. Permission Issues
```bash
# On Linux/macOS, you might need:
sudo pip install blarify

# Or better, use a virtual environment (recommended)
```

#### 3. Database Connection Issues

**FalkorDB Not Running:**
```bash
# Check if Docker container is running
docker ps | grep falkordb

# Restart if needed
docker restart falkordb
```

**Neo4j Connection Refused:**
- Ensure Neo4j is running
- Check firewall settings
- Verify connection URI and credentials

#### 4. Language Server Issues

**Jedi Language Server Installation:**
```bash
# Reinstall if needed
pip uninstall jedi-language-server
pip install jedi-language-server
```

**Port Conflicts:**
```bash
# Check what's using the LSP port
lsof -i :port_number

# Kill conflicting processes if necessary
```

### Getting Help

If you encounter issues:

1. **Check the logs**: Enable debug logging to see detailed error messages
2. **GitHub Issues**: Report bugs at [GitHub Issues](https://github.com/blarApp/blarify/issues)
3. **Discord Community**: Join our [Discord](https://discord.gg/s8pqnPt5AP) for community support
4. **Documentation**: Review our [API Reference](api-reference.md) and [User Guide](user-guide.md)

## Environment Configuration

### Complete .env Example

```env
# Project settings
ROOT_PATH=/path/to/your/project
ENVIRONMENT=development
DIFF_IDENTIFIER=main
REPO_ID=my-repo
COMPANY_ID=my-organization

# Database choice - use one of the following:

# FalkorDB Configuration
FALKORDB_URI=localhost
FALKORDB_PORT=6379
FALKORDB_USERNAME=
FALKORDB_PASSWORD=

# Neo4j Configuration  
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password

# Logging
LOG_LEVEL=INFO
```

### Using Environment Variables in Code

```python
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Access variables
root_path = os.getenv("ROOT_PATH")
repo_id = os.getenv("REPO_ID", "default-repo")
```

## Next Steps

After successful installation:

1. **Read the [Quickstart Guide](quickstart.md)** for your first graph
2. **Explore the [User Guide](user-guide.md)** for advanced features
3. **Check out [Examples](examples.md)** for common use cases
4. **Review the [API Reference](api-reference.md)** for detailed documentation

## Performance Optimization

For large codebases, consider:

1. **Skip unnecessary files**:
   ```python
   extensions_to_skip = ['.json', '.md', '.txt', '.log']
   names_to_skip = ['node_modules', '__pycache__', '.git', '.venv']
   ```

2. **Use appropriate database resources**:
   - Increase Neo4j memory allocation
   - Use SSD storage for better performance

3. **Monitor system resources**:
   - Watch memory usage during analysis
   - Consider analyzing in chunks for very large projects
