# Blarify Tools Documentation

The Blarify Tools module provides Langchain-compatible tools that enable AI agents to interact with code graphs stored in Neo4j or FalkorDB. These tools abstract complex graph queries into simple, agent-friendly interfaces for exploring and analyzing codebases.

## Table of Contents

1. [Overview](#overview)
2. [Installation & Setup](#installation--setup)
3. [Available Tools](#available-tools)
4. [Usage Examples](#usage-examples)
5. [Tool Reference](#tool-reference)
6. [Integration with AI Agents](#integration-with-ai-agents)
7. [Advanced Patterns](#advanced-patterns)

## Overview

The tools module (`blarify.tools`) provides specialized interfaces for:
- **Graph Navigation**: Explore repository structure through graph relationships
- **Code Search**: Find nodes by code content, name, type, or path
- **Context Retrieval**: Get expanded code context with intelligent placeholder resolution
- **Relationship Analysis**: Visualize and understand code dependencies
- **Documentation Generation**: Auto-generate missing documentation using AI

### Key Benefits

- **Abstraction**: No need to write complex Cypher queries
- **Type Safety**: Pydantic models ensure proper input validation
- **Context Awareness**: Tools handle code collapsing/expansion automatically
- **Agent-Optimized**: Structured outputs designed for LLM consumption
- **Performance**: Efficient graph traversal with caching where appropriate

## Installation & Setup

### Prerequisites

1. A Blarify-processed codebase in Neo4j or FalkorDB
2. Langchain installed (`pip install langchain`)
3. Database connection configured

### Basic Setup

```python
from blarify.db_managers.neo4j_manager import Neo4jManager
from blarify.tools import (
    DirectoryExplorerTool,
    FindNodesByCode,
    GetCodeByIdTool,
    GetRelationshipFlowchart
)

# Initialize database manager
db_manager = Neo4jManager(
    repo_id="my-repo",
    entity_id="my-company"
)

# Initialize tools
directory_explorer = DirectoryExplorerTool(
    company_graph_manager=db_manager,
    company_id="my-company",
    repo_id="my-repo"
)

code_finder = FindNodesByCode(
    db_manager=db_manager,
    company_id="my-company",
    repo_id="my-repo",
    diff_identifier="main"
)
```

## Available Tools

### 1. DirectoryExplorerTool
Navigate repository structure via graph relationships.

**Use Cases:**
- Browse project hierarchy
- Find repository root
- List directory contents

### 2. FindNodesByCode
Search for nodes containing specific code text.

**Use Cases:**
- Find function implementations
- Locate specific algorithms
- Search for patterns or anti-patterns

### 3. FindNodesByNameAndType
Find nodes by their name and type.

**Use Cases:**
- Locate specific classes or functions
- Find all methods with certain names
- Discover test files

### 4. FindNodesByPath
Find nodes at specific file paths.

**Use Cases:**
- Navigate to known files
- Verify file existence
- Get node IDs for specific paths

### 5. GetCodeByIdTool
Retrieve detailed code and relationship information for a node.

**Use Cases:**
- Examine function implementations
- Understand node relationships
- View auto-generated documentation

### 6. GetFileContextByIdTool
Get expanded file context with child nodes injected.

**Use Cases:**
- View complete file content
- Understand code in full context
- Analyze nested structures

### 7. GetCodeWithContextTool
Combined tool for both node details and expanded file context.

**Use Cases:**
- Comprehensive code analysis
- Debugging with full context
- Code review assistance

### 8. GetRelationshipFlowchart
Generate Mermaid diagrams of node relationships.

**Use Cases:**
- Visualize dependencies
- Understand call chains
- Document architecture

### 9. GetBlameByIdTool
Get GitHub-style blame information for code nodes, showing commit info for each line.

**Use Cases:**
- Track code authorship line-by-line
- Understand when and why code was changed
- Find associated pull requests
- Identify primary code contributors

## Usage Examples

### Example 1: Exploring Repository Structure

```python
from blarify.tools import DirectoryExplorerTool

# Initialize the tool
explorer = DirectoryExplorerTool(
    company_graph_manager=db_manager,
    company_id="my-company",
    repo_id="my-repo"
)

# Get the tool for Langchain
list_directory_tool = explorer.get_tool()

# List repository root
root_contents = list_directory_tool.invoke({"node_id": None})
print(root_contents)

# Output:
# Directory listing for: /project/root (Node ID: abc123)
# ============================================================
# 
# 📁 Directories:
#   └── src/ (ID: def456)
#   └── tests/ (ID: ghi789)
# 
# 📄 Files:
#   └── README.md (ID: jkl012)
#   └── setup.py (ID: mno345)
```

### Example 2: Finding Code by Content

```python
from blarify.tools import FindNodesByCode

# Initialize the tool
code_finder = FindNodesByCode(
    db_manager=db_manager,
    company_id="my-company",
    repo_id="my-repo",
    diff_identifier="main"
)

# Search for specific code
result = code_finder._run(code="def calculate_total")

if not result["too many nodes"]:
    for node in result["nodes"]:
        print(f"Found in: {node['file_path']}")
        print(f"Node ID: {node['node_id']}")
        print(f"Code snippet: {node['code'][:100]}...")
```

### Example 3: Getting Code with Full Context

```python
from blarify.tools import GetCodeWithContextTool

# Initialize the tool
context_tool = GetCodeWithContextTool(
    db_manager=db_manager,
    company_id="my-company"
)

# Get code with expanded context
node_id = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
result = context_tool._run(node_id=node_id)

print(result)
# Output includes:
# - Code with line numbers
# - Expanded child nodes
# - Relationships (inbound/outbound)
# - Documentation if available
```

### Example 4: Generating Relationship Flowchart

```python
from blarify.tools import GetRelationshipFlowchart

# Initialize the tool
flowchart_tool = GetRelationshipFlowchart(
    company_id="my-company",
    db_manager=db_manager,
    diff_identifier="main"
)

# Generate Mermaid diagram
node_id = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
mermaid_diagram = flowchart_tool._run(node_id=node_id)

print(mermaid_diagram)
# Output:
# graph TD
#     nodeA[FunctionA] --> nodeB[FunctionB]
#     nodeB --> nodeC[FunctionC]
#     nodeA --> nodeD[FunctionD]
```

### Example 5: Getting GitHub-Style Blame Information

```python
from blarify.tools import GetBlameByIdTool

# Initialize the tool
blame_tool = GetBlameByIdTool(
    db_manager=db_manager,
    repo_owner="blarApp",
    repo_name="blarify",
    github_token=os.getenv("GITHUB_TOKEN"),
    auto_create_integration=True  # Creates integration nodes if needed
)

# Get blame for a function node
node_id = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
blame_output = blame_tool._run(node_id=node_id)

print(blame_output)
# Output:
# Git Blame for: get_reference_type (FUNCTION)
# File: blarify/code_hierarchy/python/lsp_query_utils.py
# ================================================================================
# 
# 8 months ago  alice      abc123d  feat: introduce FoundRelation...   50 | def get_reference_type(
# 9 months ago  bob        def456g  refactor: map lsp reference to...  51 |     self, original_node: "DefinitionNode", reference: "Reference", node_referenced: "DefinitionNode"
# 8 months ago  alice      abc123d  feat: introduce FoundRelation...   52 | ) -> FoundRelationshipScope:
# 9 months ago  charlie    ghi789j  refactor: replace CodeRange...     53 |     node_in_point_reference = self._get_node_in_point_reference(node=node_referenced, reference=reference)
# 8 months ago  alice      abc123d  feat: introduce FoundRelation...   54 |     found_relationship_scope = self.language_definitions.get_relationship_type(
# 9 months ago  bob        def456g  refactor: add get_relationship...  55 |         node=original_node, node_in_point_reference=node_in_point_reference
# 9 months ago  charlie    ghi789j  refactor: replace CodeRange...     56 |     )
#                                                                        57 |
# 8 months ago  alice      abc123d  feat: introduce FoundRelation...   58 |     if not found_relationship_scope:
#                                                                        59 |         found_relationship_scope = FoundRelationshipScope(
#                                                                        60 |             node_in_scope=None, relationship_type=RelationshipType.USES
#                                                                        61 |         )
#                                                                        62 |
#                                                                        63 |     return found_relationship_scope
# 
# 
# Summary:
# ----------------------------------------
# Total commits: 4
# Primary author: alice (6 lines)
# Last modified: 8 months ago by alice
# 
# Associated Pull Requests:
#   PR #42: Add relationship scope feature
#   PR #38: Refactor LSP reference handling
```

## Tool Reference

### DirectoryExplorerTool

#### Methods
- `get_tool()` - Returns Langchain-compatible tool for directory listing
- `get_find_repo_root_tool()` - Returns tool for finding repository root

#### Internal Methods
- `_find_repo_root()` - Finds the root node of the repository
- `_list_directory_children(node_id)` - Lists children of a directory node
- `_get_node_info(node_id)` - Gets basic information about a node
- `_format_directory_listing(contents, parent_node_id)` - Formats directory contents

### FindNodesByCode

#### Input Schema
```python
class Input(BaseModel):
    code: str  # Text to search for in the database
```

#### Returns
```python
{
    "nodes": List[NodeFoundByTextResponse],
    "too many nodes": bool
}
```

### GetCodeByIdTool

#### Input Schema
```python
class NodeIdInput(BaseModel):
    node_id: str  # 32-character UUID-like hash ID
```

#### Features
- Auto-generates documentation if missing (configurable)
- Displays relationships with detailed information
- Formats code with proper line numbers
- Shows node labels and metadata

### GetFileContextByIdTool

#### Key Features
- Recursively expands collapsed code sections
- Preserves proper indentation
- Handles nested placeholders
- Returns complete file context

### GetCodeWithContextTool

#### Combined Output Includes
1. **Node Details**: Labels, ID, name
2. **Code with Line Numbers**: Collapsed version with line references
3. **File Context**: Fully expanded code
4. **Relationships**: Inbound and outbound connections
5. **Documentation**: If available or auto-generated

### GetRelationshipFlowchart

#### Output Format
- Mermaid-compatible graph syntax
- Shows node relationships visually
- Includes node names and types
- Directional flow representation

### GetBlameByIdTool

#### Input Schema
```python
class NodeIdInput(BaseModel):
    node_id: str  # 32-character UUID-like hash ID
```

#### Features
- GitHub-style blame display with commit info for each line
- On-demand integration node creation if blame data doesn't exist
- Shows associated pull requests
- Calculates primary author and last modification info
- Supports configurable GitHub token and repository settings

#### Output Format
- Plain text formatted like GitHub's blame view
- Each line shows: time ago, author, commit SHA, message, line number, and code
- Summary section with statistics and PR information
- Human-readable time formatting ("8 months ago", etc.)

## Integration with AI Agents

### Langchain Integration

```python
from langchain.agents import initialize_agent, AgentType
from langchain.llms import OpenAI

# Initialize tools
tools = [
    directory_explorer.get_tool(),
    code_finder,
    context_tool,
    flowchart_tool,
    blame_tool
]

# Create agent
llm = OpenAI(temperature=0)
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

# Use agent
response = agent.run(
    "Find the main function and show me what functions it calls"
)
```

### Custom Agent Implementation

```python
class CodeAnalysisAgent:
    def __init__(self, db_manager, company_id, repo_id):
        self.tools = {
            'explore': DirectoryExplorerTool(db_manager, company_id, repo_id),
            'find_code': FindNodesByCode(db_manager, company_id, repo_id, "main"),
            'get_context': GetCodeWithContextTool(db_manager, company_id),
            'get_flowchart': GetRelationshipFlowchart(company_id, db_manager, "main")
        }
    
    def analyze_function(self, function_name: str):
        # Find the function
        nodes = self.tools['find_code']._run(code=f"def {function_name}")
        
        if nodes['nodes']:
            node_id = nodes['nodes'][0]['node_id']
            
            # Get full context
            context = self.tools['get_context']._run(node_id=node_id)
            
            # Generate flowchart
            flowchart = self.tools['get_flowchart']._run(node_id=node_id)
            
            return {
                'context': context,
                'flowchart': flowchart
            }
```

## Advanced Patterns

### Pattern 1: Recursive Dependency Analysis

```python
def analyze_dependencies(node_id: str, depth: int = 2):
    """Recursively analyze dependencies up to specified depth."""
    visited = set()
    
    def traverse(nid: str, current_depth: int):
        if nid in visited or current_depth > depth:
            return []
        
        visited.add(nid)
        node_info = get_code_tool._run(node_id=nid)
        
        dependencies = []
        # Parse outbound relations from node_info
        # Recursively traverse each dependency
        
        return dependencies
    
    return traverse(node_id, 0)
```

### Pattern 2: Code Impact Analysis

```python
def analyze_impact(changed_node_id: str):
    """Analyze what code might be affected by changes to a node."""
    # Get inbound relationships (who depends on this node)
    node_info = get_code_tool._run(node_id=changed_node_id)
    
    affected_nodes = []
    # Parse inbound relations
    # For each dependent, analyze its criticality
    
    return {
        'directly_affected': affected_nodes,
        'risk_level': calculate_risk(affected_nodes)
    }
```

### Pattern 3: Documentation Coverage Analysis

```python
def check_documentation_coverage(directory_node_id: str):
    """Check which nodes in a directory have documentation."""
    contents = directory_explorer._list_directory_children(directory_node_id)
    
    coverage = {
        'documented': [],
        'undocumented': []
    }
    
    for item in contents:
        node_info = get_code_tool._run(node_id=item['node_id'])
        # Check if documentation exists
        # Categorize accordingly
    
    return coverage
```

### Pattern 4: Test Discovery

```python
def find_tests_for_function(function_node_id: str):
    """Find test cases that test a specific function."""
    function_info = get_code_tool._run(node_id=function_node_id)
    function_name = extract_function_name(function_info)
    
    # Search for test files
    test_results = find_by_code._run(
        code=f"test_{function_name}"
    )
    
    return test_results['nodes']
```

## Best Practices

### 1. Error Handling
Always handle potential errors when tools return no results:

```python
try:
    result = tool._run(node_id=node_id)
except ValueError as e:
    print(f"Node not found: {e}")
    # Handle gracefully
```

### 2. Batch Operations
When processing multiple nodes, consider batching:

```python
def batch_analyze(node_ids: List[str]):
    results = []
    for batch in chunks(node_ids, size=10):
        # Process batch in parallel if possible
        batch_results = [tool._run(node_id=nid) for nid in batch]
        results.extend(batch_results)
    return results
```

### 3. Caching
Implement caching for frequently accessed nodes:

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_cached_node_info(node_id: str):
    return get_code_tool._run(node_id=node_id)
```

### 4. Tool Selection
Choose the right tool for the task:
- Use `FindNodesByPath` when you know the exact path
- Use `FindNodesByCode` for content-based search
- Use `GetFileContextByIdTool` when you need expanded code
- Use `GetCodeByIdTool` when you need relationships

## Troubleshooting

### Common Issues

1. **"Too many nodes found"** - Refine your search query to be more specific
2. **"Node not found"** - Verify the node_id is correct (32 characters)
3. **"No documentation found"** - Enable auto_generate in GetCodeByIdTool
4. **Empty relationships** - Ensure LSP was used during graph building

### Performance Tips

- Filter at the database level when possible
- Use specific node types in searches
- Limit depth in recursive operations
- Cache frequently accessed nodes

## Next Steps

- Explore [workflow analysis](implementation_features/workflow_nodes_4layer_architecture.md) for advanced execution trace analysis
- Learn about [semantic documentation](implementation_features/semantic_documentation_layer.md) generation
- Review the [API Reference](api-reference.md) for lower-level access
- See [Examples](examples.md) for more use cases