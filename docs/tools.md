# Blarify Tools Documentation

The Blarify Tools module provides LangChain-compatible tools that enable AI agents to interact with code graphs stored in Neo4j or FalkorDB. These tools abstract complex graph queries into simple, agent-friendly interfaces for exploring and analyzing codebases.

## Table of Contents

1. [Overview](#overview)
2. [Installation & Setup](#installation--setup)
3. [Available Tools](#available-tools)
4. [Tool Reference](#tool-reference)
5. [Usage Examples](#usage-examples)
6. [Integration with AI Agents](#integration-with-ai-agents)
7. [Best Practices](#best-practices)

## Overview

The tools module (`blarify.tools`) provides specialized interfaces for:
- **Symbol Search**: Find code elements by exact name or semantic similarity
- **Code Analysis**: Get complete code implementations with relationships
- **Context Retrieval**: Get expanded code context with intelligent placeholder resolution
- **Dependency Visualization**: Generate Mermaid diagrams showing code relationships
- **Git History**: Access GitHub-style blame information for code evolution tracking

### Key Benefits

- **Abstraction**: No need to write complex Cypher queries
- **Type Safety**: Pydantic models ensure proper input validation
- **Context Awareness**: Tools handle code collapsing/expansion automatically
- **Agent-Optimized**: Structured outputs designed for LLM consumption
- **Flexible Input**: Accept either reference IDs or file path + symbol name combinations

## Installation & Setup

### Prerequisites

1. A Blarify-processed codebase in Neo4j or FalkorDB
2. LangChain installed (`pip install langchain`)
3. Database connection configured

### Basic Setup

```python
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.tools import (
    FindSymbols,
    VectorSearch,
    GrepCode,
    GetCodeAnalysis,
    GetExpandedContext,
    GetBlameInfo,
    GetDependencyGraph
)

# Initialize database manager
db_manager = Neo4jManager(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password",
    repo_id="my-repo",
    entity_id="my-company"
)

# Initialize tools
find_symbols = FindSymbols(db_manager=db_manager)
vector_search = VectorSearch(db_manager=db_manager)
grep_code = GrepCode(db_manager=db_manager)
code_analysis = GetCodeAnalysis(db_manager=db_manager)
expanded_context = GetExpandedContext(db_manager=db_manager)
blame_info = GetBlameInfo(
    db_manager=db_manager,
    repo_owner="your-org",
    repo_name="your-repo"
)
dependency_graph = GetDependencyGraph(db_manager=db_manager)
```

## Available Tools

### 1. FindSymbols
Search for code symbols (functions, classes, files, or folders) by **exact name match**.

**Use Cases:**
- Locate specific functions or classes when you know the exact name
- Find files or folders by their exact names
- Get reference IDs for further analysis

**Key Features:**
- Exact name matching (case-sensitive)
- Returns multiple matches if symbol appears in different locations
- Provides code previews
- Returns reference IDs for navigation

### 2. VectorSearch
Perform **semantic search** over AI-generated descriptions of code scopes using vector similarity.

**Use Cases:**
- Exploratory searches when you don't know exact symbol names
- Find functionality by description (e.g., "email sending", "authentication logic")
- Discover code handling specific features or behaviors

**Key Features:**
- Semantic/fuzzy search using embeddings
- Searches over AI-generated code scope descriptions
- Configurable number of results (top_k)
- Returns relevance scores
- Requires OpenAI API key for embedding generation

### 3. GrepCode
Search for **code patterns** across the codebase using pattern matching.

**Use Cases:**
- Find function calls (e.g., where `send_email()` is called)
- Locate import statements (e.g., all pandas imports)
- Search for syntax patterns (e.g., all async functions, try blocks)
- Find variable usage or assignments
- Discover code snippets when you know what the code looks like

**Key Features:**
- Pattern-based search through code content
- Case-sensitive and case-insensitive search options
- File path filtering (glob patterns like `*.py`, `src/auth/*`)
- Returns matching code with line numbers and context
- Provides reference IDs for further analysis
- Results include surrounding code lines for context

### 4. GetCodeAnalysis
Get complete code implementation with relationships and dependencies.

**Use Cases:**
- Understand what a function does
- See which functions call this one (inbound relationships)
- See which functions this one calls (outbound relationships)
- Analyze code dependencies

**Key Features:**
- Shows complete code with line numbers
- Lists all inbound and outbound relationships
- Provides reference IDs for related symbols
- Handles collapsed code placeholders

### 4. GetExpandedContext
Get the full file context with all nested code expanded.

**Use Cases:**
- View complete file content without collapsed placeholders
- Understand code in its full surrounding context
- Analyze nested structures and their implementations

**Key Features:**
- Recursively expands all collapsed code sections
- Preserves proper indentation
- Returns complete, executable file context
- Handles circular references gracefully

### 5. GetBlameInfo
Get GitHub-style blame information showing who last modified each line of code.

**Use Cases:**
- Track code authorship line-by-line
- Understand when and why code was changed
- Find associated pull requests
- Identify primary code contributors

**Key Features:**
- GitHub-style blame display with commit info per line
- Shows time ago, author, commit SHA, and message
- Can auto-create integration nodes if needed
- Includes PR information and summary statistics
- Requires GitHub token for API access

### 6. GetDependencyGraph
Generate Mermaid diagrams showing dependencies and relationships.

**Use Cases:**
- Visualize code dependencies
- Understand call chains
- Document architecture
- Communicate code structure to others

**Key Features:**
- Generates Mermaid-compatible graph syntax
- Configurable depth of relationships
- Shows directional relationships
- Can be rendered in documentation or markdown viewers

## Tool Reference

### FindSymbols

#### Input Parameters
```python
{
    "name": str,      # Exact name of the symbol (required)
    "type": str       # One of: "FUNCTION", "CLASS", "FILE", "FOLDER" (required)
}
```

#### Returns
```python
{
    "symbols": [
        {
            "id": str,           # Reference ID (32-char handle)
            "name": str,         # Symbol name
            "type": List[str],   # Symbol types/labels
            "file_path": str,    # File location
            "code": str          # Code preview
        }
    ]
}
```

#### Example
```python
result = find_symbols._run(
    name="GraphBuilder",
    type="CLASS"
)
# Returns all classes named "GraphBuilder" with their reference IDs
```

---

### VectorSearch

#### Input Parameters
```python
{
    "query": str,     # Search query for semantic matching (required)
    "top_k": int      # Number of results to return (default: 5, max: 20)
}
```

#### Returns
Formatted string with search results including:
- Relevance scores
- Reference IDs
- File paths
- AI-generated descriptions

#### Example
```python
result = vector_search._run(
    query="email verification logic",
    top_k=5
)
# Returns top 5 code scopes related to email verification
```

#### Notes
- Requires `OPENAI_API_KEY` environment variable
- Returns "Vector search unavailable" if API key is not configured
- Minimum similarity threshold is 0.7

---

### GrepCode

#### Input Parameters
```python
{
    "pattern": str,                    # Code pattern to search for (required)
    "case_sensitive": bool,            # Case-sensitive search (default: True)
    "file_pattern": Optional[str],     # File path filter (e.g., "*.py", "src/auth/*")
    "max_results": int                 # Max results to return (default: 20, max: 50)
}
```

#### Returns
```python
{
    "matches": [
        {
            "file_path": str,          # File location
            "line_number": int,        # Line where pattern was found
            "symbol_name": str,        # Name of containing function/class
            "symbol_type": List[str],  # Types like ["FUNCTION", "CLASS"]
            "code_snippet": str,       # Code with context lines
            "id": str                  # Reference ID for further analysis
        }
    ]
}
```

#### Example
```python
# Find function calls
result = grep_code._run(pattern="send_email(")

# Case-insensitive search for imports
result = grep_code._run(
    pattern="import pandas",
    case_sensitive=False
)

# Search in specific files
result = grep_code._run(
    pattern="async def",
    file_pattern="src/api/*.py"
)
```

#### Notes
- Returns code snippets with 2 lines of context before and after the match
- File patterns support glob wildcards: `*` (any files), `**` (any directories)
- Returns "No matches found" if pattern doesn't exist in codebase

---

### GetCodeAnalysis

#### Input Parameters
Flexible input - provide either:
- `reference_id`: Reference ID (32-char handle), **OR**
- `file_path` AND `symbol_name`: File path and symbol name combination

```python
{
    "reference_id": Optional[str],   # 32-character reference ID
    "file_path": Optional[str],      # Path to file
    "symbol_name": Optional[str]     # Name of function/class/method
}
```

#### Returns
Formatted string with:
- Symbol information (ID, name, labels)
- Code with line numbers
- Inbound relationships (what calls this)
- Outbound relationships (what this calls)
- Reference IDs for all related symbols

#### Example
```python
# Using reference ID
result = code_analysis._run(
    reference_id="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
)

# Using file path + symbol name
result = code_analysis._run(
    file_path="src/services/auth.py",
    symbol_name="login_user"
)
```

---

### GetExpandedContext

#### Input Parameters
Same flexible input as GetCodeAnalysis:
```python
{
    "reference_id": Optional[str],
    "file_path": Optional[str],
    "symbol_name": Optional[str]
}
```

#### Returns
Formatted string with:
- File path
- Fully expanded source code with all nested nodes injected
- No collapsed placeholders - complete, runnable code

#### Example
```python
result = expanded_context._run(
    reference_id="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
)
# Returns complete file content with all code expanded
```

---

### GetBlameInfo

#### Input Parameters
Same flexible input as GetCodeAnalysis:
```python
{
    "reference_id": Optional[str],
    "file_path": Optional[str],
    "symbol_name": Optional[str]
}
```

#### Configuration
```python
GetBlameInfo(
    db_manager=db_manager,
    repo_owner="your-org",           # GitHub org/owner
    repo_name="your-repo",           # GitHub repo name
    github_token="ghp_...",          # Optional, defaults to GITHUB_TOKEN env var
    ref="HEAD",                      # Git ref to blame at
    auto_create_integration=True     # Auto-create integration nodes
)
```

#### Returns
Formatted string with GitHub-style blame output:
- Each line with: time ago, author, commit SHA, message, line number, code
- Summary section with total commits, primary author, last modification
- Associated pull requests

#### Example
```python
result = blame_info._run(
    file_path="src/main.py",
    symbol_name="main"
)
# Output:
# Git Blame for: main (FUNCTION)
# File: src/main.py
# ================================================================================
#
# 3 months ago  alice      abc123d  feat: add main entry point   10 | def main():
# 3 months ago  alice      abc123d  feat: add main entry point   11 |     app = create_app()
# 2 months ago  bob        def456g  fix: add error handling      12 |     try:
# ...
```

---

### GetDependencyGraph

#### Input Parameters
Flexible input plus depth parameter:
```python
{
    "reference_id": Optional[str],
    "file_path": Optional[str],
    "symbol_name": Optional[str],
    "depth": int  # Maximum depth of relationships (default: 2, range: 1-5)
}
```

#### Returns
Mermaid diagram syntax as a string:
```
graph TD
    nodeA[FunctionA] --> nodeB[FunctionB]
    nodeB --> nodeC[FunctionC]
    nodeA --> nodeD[FunctionD]
```

#### Example
```python
mermaid = dependency_graph._run(
    symbol_name="process_data",
    file_path="src/processor.py",
    depth=3
)
print(mermaid)
# Can be rendered in markdown viewers or documentation
```

## Usage Examples

### Example 1: Find and Analyze a Function

```python
# Step 1: Find the function by exact name
result = find_symbols._run(
    name="calculate_total",
    type="FUNCTION"
)

# Step 2: Get the reference ID
if result["symbols"]:
    ref_id = result["symbols"][0]["id"]

    # Step 3: Get code analysis
    analysis = code_analysis._run(reference_id=ref_id)
    print(analysis)
```

### Example 2: Exploratory Search for Feature

```python
# Search for email-related code
results = vector_search._run(
    query="email sending and verification",
    top_k=10
)
print(results)

# Results will show relevant code scopes with reference IDs
# that you can then analyze further with other tools
```

### Example 3: Search for Code Patterns

```python
# Find all function calls to authenticate
matches = grep_code._run(
    pattern="authenticate(",
    max_results=10
)

# Print matches with line numbers and context
for match in matches["matches"]:
    print(f"{match['file_path']}:{match['line_number']}")
    print(match['code_snippet'])
    print()
```

### Example 4: Understand Function Dependencies

```python
# Get dependency visualization
mermaid_diagram = dependency_graph._run(
    file_path="src/auth/login.py",
    symbol_name="authenticate_user",
    depth=2
)

print(mermaid_diagram)
# Paste into markdown viewer to see visual dependency graph
```

### Example 5: Track Code Changes

```python
# Get blame information for a function
blame_output = blame_info._run(
    file_path="src/utils/helpers.py",
    symbol_name="format_date"
)

print(blame_output)
# Shows who modified each line, when, and why
```

### Example 6: Get Complete File Context

```python
# Get fully expanded context
full_context = expanded_context._run(
    file_path="src/models/user.py",
    symbol_name="User"
)

print(full_context)
# Shows complete file with all nested code expanded
```

## Integration with AI Agents

### LangChain ReAct Agent

```python
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# Initialize all tools
tools = [
    FindSymbols(db_manager=db_manager),
    VectorSearch(db_manager=db_manager),
    GrepCode(db_manager=db_manager),
    GetCodeAnalysis(db_manager=db_manager),
    GetExpandedContext(db_manager=db_manager),
    GetBlameInfo(
        db_manager=db_manager,
        repo_owner="your-org",
        repo_name="your-repo"
    ),
    GetDependencyGraph(db_manager=db_manager)
]

# Create LLM and agent
llm = ChatOpenAI(model="gpt-4", temperature=0)
agent = create_react_agent(
    model=llm,
    tools=tools,
    state_modifier="You are a helpful code analysis assistant."
)

# Use the agent
for chunk in agent.stream(
    {"messages": [("user", "Find the authentication logic and explain how it works")]}
):
    print(chunk)
```

### MCP Server Integration

Blarify tools are also available through the Model Context Protocol (MCP) server:

```bash
# Start the MCP server
blarify-mcp --project /path/to/your/project

# Or auto-detect from current directory
cd /path/to/your/project
blarify-mcp
```

See [MCP Quick Setup Guide](mcp-quick-setup.md) for more details.

## Best Practices

### 1. Search Workflow

For optimal results, follow this workflow:

1. **Exploratory Search**: Use `VectorSearch` when you don't know exact names
   ```python
   results = vector_search._run(query="database connection logic")
   ```

2. **Exact Lookup**: Use `FindSymbols` when you know the exact name
   ```python
   symbols = find_symbols._run(name="DatabaseConnection", type="CLASS")
   ```

3. **Detailed Analysis**: Use `GetCodeAnalysis` for implementation details
   ```python
   analysis = code_analysis._run(reference_id=ref_id)
   ```

4. **Full Context**: Use `GetExpandedContext` for complete file view
   ```python
   full_code = expanded_context._run(reference_id=ref_id)
   ```

### 2. Reference ID Management

Reference IDs are 32-character hexadecimal strings that uniquely identify code symbols:

- **Store them**: Keep reference IDs for symbols you'll analyze multiple times
- **Reuse them**: Pass reference IDs to different tools for consistent analysis
- **Flexible input**: Most tools accept either reference_id OR (file_path + symbol_name)

### 3. Error Handling

Always handle potential errors:

```python
try:
    result = code_analysis._run(reference_id=ref_id)
    # Process result
except ValueError as e:
    print(f"Symbol not found: {e}")
    # Try alternative search methods
```

### 4. Performance Optimization

- **Cache results**: Store frequently accessed code analysis results
- **Limit depth**: Use lower depth values in `GetDependencyGraph` for faster results
- **Filter searches**: Be specific in `VectorSearch` queries to reduce result sets
- **Batch processing**: When analyzing multiple symbols, collect all reference IDs first

### 5. Tool Selection Guide

| Task | Recommended Tool |
|------|-----------------|
| Don't know exact name | `VectorSearch` |
| Know exact name | `FindSymbols` |
| Find function calls, imports, patterns | `GrepCode` |
| Need implementation details | `GetCodeAnalysis` |
| Need full file content | `GetExpandedContext` |
| Need visual dependencies | `GetDependencyGraph` |
| Need authorship info | `GetBlameInfo` |

## Troubleshooting

### Common Issues

**"Vector search unavailable: OPENAI_API_KEY not configured"**
- Set your OpenAI API key: `export OPENAI_API_KEY=sk-...`

**"Reference ID must be a 32 character string"**
- Ensure you're using the full reference ID, not a shortened version

**"Provide either reference_id OR (file_path AND symbol_name)"**
- You must provide either the reference_id alone, OR both file_path and symbol_name together

**"No code scopes found matching: '...'"**
- Try alternative keywords or broader search terms
- Ensure the codebase has been processed with embeddings enabled

**"Too many symbols found"**
- Make your search more specific
- Add more context to distinguish between similar symbols

### Performance Tips

- Use `FindSymbols` instead of `VectorSearch` when you know exact names (faster)
- Lower the `depth` parameter in `GetDependencyGraph` for complex codebases
- Set lower `top_k` values in `VectorSearch` for faster responses
- Ensure Neo4j/FalkorDB has proper indexes configured

## Next Steps

- Review the [API Reference](api-reference.md) for lower-level access
- See [Examples](examples.md) for more use cases
- Learn about [MCP integration](mcp-installation-guide.md) for Claude Desktop
- Explore [Quickstart Guide](quickstart.md) for getting started
