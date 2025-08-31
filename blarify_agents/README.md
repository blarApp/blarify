# Blarify LangChain Agents

This directory contains LangChain-based agents that demonstrate how to use Blarify tools for intelligent code analysis and exploration.

## Overview

These agents show how to integrate Blarify's graph-based code analysis tools with LangChain to create intelligent agents that can:
- Navigate and explore code repositories
- Search for specific code patterns
- Analyze code relationships and dependencies  
- Generate documentation
- Perform lint analysis
- Validate test coverage

## Available Agents

### 1. Main Test Agent (`main_agent.py`)
A comprehensive agent that tests all available Blarify tools using LangChain's ReAct framework.

**Features:**
- Tests all Blarify tools systematically
- Uses the Blarify LLMProvider for model management
- Configurable for Neo4j or FalkorDB backends
- Comprehensive error handling

**Usage:**
```python
from main_agent import BlarifyTestAgent, AgentConfig

config = AgentConfig(
    repo_id="test",
    entity_id="test", 
    db_type="neo4j",
    model_name="o4-mini"
)

agent = BlarifyTestAgent(config)
result = agent.run("Find all Python files containing class definitions")
print(result)
```

### 2. Code Explorer Agent (`code_explorer_agent.py`)
Specialized agent for navigating and exploring codebases with advanced features.

**Features:**
- Recursive directory exploration
- Entry point detection
- Function call tracing
- File structure analysis
- Conversation memory for context retention

**Usage:**
```python
from code_explorer_agent import CodeExplorerAgent

explorer = CodeExplorerAgent(
    repo_id="test",
    entity_id="test",
    verbose=True
)

# Explore repository structure
result = explorer.explore("Show me the repository structure")

# Find entry points
result = explorer.explore("Find all main functions and entry points")

# Get exploration summary
summary = explorer.get_exploration_summary()
```

### 3. Direct Tool Tester (`test_tools_directly.py`)
A utility script that tests each Blarify tool directly without LangChain wrapping.

**Purpose:**
- Debug tool initialization issues
- Verify tool parameter signatures
- Test database connectivity
- Identify missing methods or attributes

### 4. Working Demo (`working_demo.py`)
A demonstration script showing the tools that are currently fully functional.

**Currently Working Tools:**
- `DirectoryExplorerTool` - Navigate repository structure
- `FindNodesByNameAndType` - Search for nodes by name and type
- `GetFileContextByIdTool` - Get expanded file context
- `GetRelationshipFlowchart` - Generate Mermaid diagrams

## Prerequisites

1. **Blarify Installation:**
```bash
pip install blarify
```

2. **Database Setup:**
You need either Neo4j or FalkorDB with a processed codebase:

```bash
# Neo4j
docker run -d -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password neo4j:latest

# OR FalkorDB  
docker run -d -p 6379:6379 falkordb/falkordb:latest
```

3. **Process Your Codebase:**
```python
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager

# Build graph
builder = GraphBuilder(root_path="/path/to/your/project")
graph = builder.build()

# Save to database
manager = Neo4jManager(repo_id="test", entity_id="test")
nodes = graph.get_nodes_as_objects()
relationships = graph.get_relationships_as_objects()
manager.save_graph(nodes, relationships)
```

4. **Environment Variables:**
```bash
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USERNAME="neo4j"
export NEO4J_PASSWORD="password"

# For OpenAI models (optional, Blarify provides its own LLM provider)
export OPENAI_API_KEY="your-key"
```

## Running the Agents

### Test All Tools
```bash
poetry run python main_agent.py
```

### Explore a Repository
```bash
poetry run python code_explorer_agent.py
```

### Run Working Demo
```bash
poetry run python working_demo.py
```

### Debug Tools
```bash
poetry run python test_tools_directly.py
```

## Known Issues

Some tools have compatibility issues that need fixes:

1. **FindNodesByCode**: Missing `get_nodes_by_text` method in Neo4jManager
2. **FindNodesByPath**: Missing `get_nodes_by_path` method in Neo4jManager  
3. **GetCodeByIdTool**: Parameter initialization issues with `company_id`

These issues are being addressed in upcoming Blarify updates.

## Agent Architecture

The agents use a layered architecture:

```
User Query
    ↓
LangChain Agent (ReAct/Structured Chat)
    ↓
Blarify Tools (Directory, Search, Analysis)
    ↓
Database Manager (Neo4j/FalkorDB)
    ↓
Graph Database with Code Relationships
```

## Extending the Agents

To create your own agent:

1. Import required tools from `blarify.tools`
2. Initialize a database manager
3. Create LangChain tools wrapping Blarify tools
4. Build your agent with custom prompts and logic

Example:
```python
from langchain.agents import create_structured_chat_agent
from blarify.tools import DirectoryExplorerTool
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager

# Initialize
db_manager = Neo4jManager(repo_id="my-repo", entity_id="my-company")
explorer = DirectoryExplorerTool(
    company_graph_manager=db_manager,
    company_id="my-company",
    repo_id="my-repo"
)

# Create LangChain tool
tool = explorer.get_tool()

# Build your agent...
```

## Use Cases

### 1. Code Understanding
- "Show me how the authentication system works"
- "Find all database connection code"
- "Trace the execution flow from main()"

### 2. Impact Analysis  
- "What functions call the calculate_price method?"
- "Show me all files that import the User model"
- "Find circular dependencies in the codebase"

### 3. Documentation
- "Generate documentation for the API module"
- "Find all undocumented public functions"
- "Create a dependency diagram for the service layer"

### 4. Code Quality
- "Find potential security issues in input handling"
- "Identify unused functions and dead code"
- "Check for missing error handling"

## Contributing

To contribute new agents or improve existing ones:

1. Follow the existing agent patterns
2. Add comprehensive error handling
3. Include usage examples in docstrings
4. Test with both Neo4j and FalkorDB
5. Update this README with your additions

## License

These agents are part of the Blarify project and follow the same MIT license.