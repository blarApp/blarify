---
title: "Refactor Blarify Tools Suite for AI Agent Usability"
issue_number:
created_by: prompt-writer
date: 2025-01-24
description: "Comprehensive refactoring of Blarify tools to make them more intuitive for AI agents while maintaining efficiency through reference IDs"
---

# Refactor Blarify Tools Suite for AI Agent Usability

## 1. Overview

This prompt guides the complete refactoring of the Blarify tools suite located in `/Users/berrazuriz/Desktop/Blar/repositories/blarify/blarify/tools/`. The refactoring aims to make tools more intuitive for AI agents by abstracting graph implementation details while keeping reference IDs as efficient handles for tool chaining.

The project Blarify converts source code repositories into graph structures for LLM analysis, supporting multiple languages through Tree-sitter and LSP integration. The tools provide programmatic access to this graph data.

## 2. Problem Statement

### Current Limitations
- **Tool redundancy**: Three tools (FindNodesByPath, FindNodesByCode, DirectoryExplorerTool) duplicate capabilities that AI agents already possess through file system access
- **Graph terminology exposure**: Current tool names and descriptions expose graph database concepts that are implementation details
- **Limited input flexibility**: Most tools only accept node_id, requiring agents to first find the ID before accessing code
- **Unintuitive naming**: Tool names like "GetCodeByIdTool" don't convey their actual value proposition
- **Inconsistent interfaces**: Some tools accept only IDs while others accept different parameters

### Impact
- AI agents struggle to understand which tool to use for specific tasks
- Redundant tools create confusion and increase maintenance burden
- The requirement to always have node_id first creates unnecessary tool chaining
- Graph terminology in descriptions makes tools less approachable

### Motivation
By refactoring these tools, we can:
- Reduce the tool suite from 13+ tools to 6 focused, powerful tools
- Enable more flexible input methods (reference_id OR file_path + symbol_name)
- Present tools with agent-friendly names and descriptions
- Maintain efficiency through reference IDs as "tool handles"

## 3. Feature Requirements

### Functional Requirements
1. **Reduced Tool Suite**: Consolidate to exactly 6 tools that cover all essential functionality
2. **Dual Input Support**: Each tool accepting node_id must also accept file_path + symbol_name combination
3. **Intuitive Naming**: Tool names should describe what they do, not how they work
4. **Reference ID Preservation**: Keep reference IDs visible as efficient handles for tool chaining
5. **Agent-Friendly Descriptions**: Remove graph terminology from tool descriptions

### Technical Requirements
- Maintain backward compatibility with existing node_id inputs
- Implement efficient lookup mechanism for file_path + symbol_name resolution
- Preserve all existing functionality in the consolidated tools
- Ensure proper error handling for both input methods
- Maintain type safety with Pydantic models

### Acceptance Criteria
- [ ] Three redundant tools are removed from the codebase
- [ ] Remaining tools are renamed to intuitive names
- [ ] All tools support dual input methods where applicable
- [ ] Tool descriptions are free of graph database terminology
- [ ] Reference IDs remain visible in outputs as tool handles
- [ ] All tests pass after refactoring
- [ ] Documentation is updated to reflect changes

## 4. Technical Analysis

### Current Implementation Review
The existing tools structure includes:
- **Database interaction layer**: Uses AbstractDbManager for graph queries
- **Pydantic models**: Input validation through BaseModel schemas
- **LangChain integration**: Tools extend BaseTool from langchain_core
- **DTO pattern**: Data transfer objects for node and edge information

### Proposed Technical Approach

#### Tool Consolidation Plan
Remove these redundant tools:
1. `find_nodes_by_path.py` - Redundant with file system access
2. `find_nodes_by_code.py` - Redundant with grep/search capabilities
3. `directory_explorer_tool.py` - Redundant with file system navigation

Keep and refactor these tools:
1. `find_nodes_by_name_and_type.py` → `find_symbols.py`
2. `search_documentation_vector_tool.py` → `search_documentation.py`
3. `get_code_by_id_tool.py` → `get_code_analysis.py`
4. `get_code_with_context_tool.py` → `get_expanded_context.py`
5. `get_blame_by_id_tool.py` → `get_blame_info.py`
6. Create new or adapt existing → `get_dependency_graph.py`

#### Dual Input Implementation
Create a shared input resolver that:
1. Checks if reference_id is provided
2. If not, resolves file_path + symbol_name to reference_id
3. Proceeds with existing logic using resolved reference_id

### Architecture Decisions
- Use union types in Pydantic for flexible input validation
- Implement shared utility function for ID resolution
- Maintain existing DTO structures for consistency
- Keep embedded reference IDs in code comments

### Dependencies
- Existing: langchain_core, pydantic, AbstractDbManager
- No new dependencies required

## 5. Implementation Plan

### Phase 1: Setup and Analysis (30 minutes)
- Create feature branch from main
- Analyze each tool's current functionality
- Identify shared code patterns
- Document any additional dependencies or relationships

### Phase 2: Tool Removal (45 minutes)
- Remove three redundant tool files
- Update __init__.py to remove exports
- Run tests to identify any breaking dependencies
- Fix any import errors in other parts of codebase

### Phase 3: Tool Renaming and Refactoring (2 hours)
- Rename remaining tool files
- Update class names within files
- Add dual input support to each tool
- Update tool descriptions to be agent-friendly
- Implement shared ID resolution utility

### Phase 4: Dependency Graph Tool (1 hour)
- Determine if existing tool can be adapted or new one needed
- Implement Mermaid diagram generation
- Add depth control parameter
- Support both input methods

### Phase 5: Integration and Testing (1 hour)
- Update __init__.py with new exports
- Run existing test suite
- Add tests for dual input methods
- Verify all tools work with both input types

### Phase 6: Documentation (30 minutes)
- Update tool documentation
- Create migration guide
- Update API references
- Add examples of new usage patterns

## 6. Testing Requirements

### Unit Testing Strategy
- Test both input methods for each tool
- Verify ID resolution logic
- Test error handling for invalid inputs
- Ensure backward compatibility with node_id only

### Integration Testing
- Test tool chaining using reference_ids
- Verify file_path + symbol_name resolution accuracy
- Test edge cases like non-existent symbols
- Validate Mermaid diagram generation

### Edge Cases
- Symbol names with special characters
- Multiple symbols with same name in different files
- Invalid file paths
- Malformed reference_ids
- Missing or incomplete graph data

### Test Coverage Expectations
- Maintain or improve existing coverage
- 100% coverage for new ID resolution logic
- Full coverage of both input paths

## 7. Success Criteria

### Measurable Outcomes
- Tool count reduced from 13+ to exactly 6 tools
- 100% of tools support dual input methods
- Zero graph terminology in tool descriptions
- All existing tests pass

### Quality Metrics
- Code coverage maintained above current level
- No performance regression (response time within 5% of current)
- Type safety maintained through Pydantic validation

### User Satisfaction Metrics
- AI agents can understand tool purposes from names alone
- Tool chaining works seamlessly with reference_ids
- Reduced confusion from redundant tools

## 8. Implementation Steps

### Step 1: Create GitHub Issue
```bash
# Skip due to GitHub CLI unavailability
echo "Skipping GitHub issue creation - gh CLI not available"
```

### Step 2: Create Feature Branch
```bash
git checkout main
git pull origin main
git checkout -b refactor/ai-friendly-tools-suite
```

### Step 3: Research and Analysis Phase
1. Read each tool file to understand current implementation
2. Document which tools have dependencies on removed tools
3. Identify common patterns for ID resolution
4. Check for any external dependencies on tool names

### Step 4: Remove Redundant Tools
```bash
# Remove the three redundant tool files
rm /Users/berrazuriz/Desktop/Blar/repositories/blarify/blarify/tools/find_nodes_by_path.py
rm /Users/berrazuriz/Desktop/Blar/repositories/blarify/blarify/tools/find_nodes_by_code.py
rm /Users/berrazuriz/Desktop/Blar/repositories/blarify/blarify/tools/directory_explorer_tool.py

# Update __init__.py to remove exports
# Remove lines importing and exporting these tools
```

### Step 5: Create Shared ID Resolution Utility
Create `/Users/berrazuriz/Desktop/Blar/repositories/blarify/blarify/tools/utils/id_resolver.py`:
```python
from typing import Optional, Tuple
from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager

def resolve_reference_id(
    db_manager: AbstractDbManager,
    reference_id: Optional[str] = None,
    file_path: Optional[str] = None,
    symbol_name: Optional[str] = None
) -> str:
    """
    Resolve a reference_id from either direct ID or file_path + symbol_name.

    Args:
        db_manager: Database manager for queries
        reference_id: Direct reference ID (32-char hash)
        file_path: Path to file containing symbol
        symbol_name: Name of symbol (function/class)

    Returns:
        Resolved reference_id

    Raises:
        ValueError: If inputs are invalid or symbol not found
    """
    if reference_id:
        return reference_id

    if not file_path or not symbol_name:
        raise ValueError("Must provide either reference_id OR (file_path AND symbol_name)")

    # Query database for node with matching file_path and name
    # Implementation depends on db_manager interface
    result = db_manager.find_node_by_path_and_name(file_path, symbol_name)
    if not result:
        raise ValueError(f"Symbol '{symbol_name}' not found in '{file_path}'")

    return result.node_id
```

### Step 6: Refactor find_symbols Tool
Rename and update `find_nodes_by_name_and_type.py` → `find_symbols.py`:
```python
class FindSymbols(BaseTool):
    name: str = "find_symbols"
    description: str = (
        "Find functions, classes, or methods by exact name. "
        "Returns a list of matching symbols with their reference IDs "
        "(efficient handles for other tools), file paths, and code previews."
    )
    # Update input schema and implementation
```

### Step 7: Refactor search_documentation Tool
Rename and update `search_documentation_vector_tool.py` → `search_documentation.py`:
```python
class SearchDocumentation(BaseTool):
    name: str = "search_documentation"
    description: str = (
        "Semantic search through AI-generated documentation for all symbols. "
        "Returns relevant symbols with reference IDs (tool handles), "
        "file paths, and documentation summaries."
    )
    # Keep existing implementation with updated naming
```

### Step 8: Refactor get_code_analysis Tool
Update `get_code_by_id_tool.py` → `get_code_analysis.py`:
```python
class FlexibleInput(BaseModel):
    reference_id: Optional[str] = Field(
        None,
        description="Reference ID (32-char handle) for the symbol"
    )
    file_path: Optional[str] = Field(
        None,
        description="Path to the file containing the symbol"
    )
    symbol_name: Optional[str] = Field(
        None,
        description="Name of the function/class/method"
    )

    @model_validator(mode='after')
    def validate_inputs(self):
        if self.reference_id:
            return self
        if not (self.file_path and self.symbol_name):
            raise ValueError("Provide either reference_id OR (file_path AND symbol_name)")
        return self

class GetCodeAnalysis(BaseTool):
    name: str = "get_code_analysis"
    description: str = (
        "Get complete code implementation with relationships and dependencies. "
        "Shows which functions call this one and which ones it calls, "
        "with reference IDs for navigation."
    )
    args_schema: type[BaseModel] = FlexibleInput
    # Update implementation to use id_resolver
```

### Step 9: Refactor get_expanded_context Tool
Update `get_code_with_context_tool.py` → `get_expanded_context.py`:
```python
class GetExpandedContext(BaseTool):
    name: str = "get_expanded_context"
    description: str = (
        "Get the full file context with expanded code for deep understanding. "
        "Includes surrounding code and embedded reference IDs for navigation."
    )
    # Add dual input support
```

### Step 10: Refactor get_blame_info Tool
Update `get_blame_by_id_tool.py` → `get_blame_info.py`:
```python
class GetBlameInfo(BaseTool):
    name: str = "get_blame_info"
    description: str = (
        "Get GitHub-style blame information showing who last modified each line. "
        "Useful for understanding code evolution and finding responsible developers."
    )
    # Add dual input support
```

### Step 11: Create/Adapt get_dependency_graph Tool
Check if GetRelationshipFlowchart exists or create new:
```python
class GetDependencyGraph(BaseTool):
    name: str = "get_dependency_graph"
    description: str = (
        "Generate a Mermaid diagram showing dependencies and relationships. "
        "Visualizes how symbols connect with configurable depth."
    )
    # Implement with dual input support and depth parameter
```

### Step 12: Update __init__.py
```python
from .find_symbols import FindSymbols
from .search_documentation import SearchDocumentation
from .get_code_analysis import GetCodeAnalysis
from .get_expanded_context import GetExpandedContext
from .get_blame_info import GetBlameInfo
from .get_dependency_graph import GetDependencyGraph

__all__ = [
    "FindSymbols",
    "SearchDocumentation",
    "GetCodeAnalysis",
    "GetExpandedContext",
    "GetBlameInfo",
    "GetDependencyGraph",
]
```

### Step 13: Run Tests and Validation
```bash
# Run linting
poetry run ruff check blarify/tools/
poetry run pyright blarify/tools/

# Run tests
poetry run pytest tests/tools/ -v

# Check for any import errors
python -c "from blarify.tools import *; print('All tools imported successfully')"
```

### Step 14: Update Documentation

1. **Update docs/tools.md** - Complete rewrite for new tool suite:
   ```markdown
   # Blarify Code Intelligence Tools

   Advanced semantic code analysis tools providing deep insights beyond text search.
   These tools use pre-computed analysis for instant, accurate results.

   ## Tool Suite Overview

   Six specialized tools for comprehensive code analysis:

   ### 1. find_symbols
   Find functions, classes, or methods by exact name.
   - **Input**: Symbol name + type (function/class/module)
   - **Output**: List with reference IDs, file paths, previews
   - **Use Case**: Locate specific code elements quickly

   ### 2. search_documentation
   Semantic search through AI-generated symbol documentation.
   - **Input**: Natural language query
   - **Output**: Relevant symbols with scores and documentation
   - **Use Case**: Find code by concept/purpose rather than name

   ### 3. get_code_analysis
   Get code implementation with relationships and dependencies.
   - **Input**: Reference ID OR file_path + symbol_name
   - **Output**: Code with line numbers + relationship list
   - **Use Case**: Understand code and its connections

   ### 4. get_expanded_context
   Get full file context with collapsed sections expanded.
   - **Input**: Reference ID OR file_path + symbol_name
   - **Output**: Complete expanded code
   - **Use Case**: See full implementation without placeholders

   ### 5. get_blame_info
   GitHub-style blame showing commit history per line.
   - **Input**: Reference ID OR file_path + symbol_name
   - **Output**: Author, commit, and PR info per line
   - **Use Case**: Track code evolution and ownership

   ### 6. get_dependency_graph
   Visual Mermaid diagram of code dependencies.
   - **Input**: Reference ID OR file_path + symbol_name
   - **Output**: Mermaid flowchart
   - **Use Case**: Visualize relationship structure

   ## Reference IDs

   Tools use reference IDs as efficient handles. When you see an ID like
   'a1b2c3d4e5f6g7h8' in any output, use it directly in other tools for
   quick access without repeating file paths and names.

   ## Removed Tools

   These tools were removed as they duplicate agent capabilities:
   - FindNodesByPath → Use file system access
   - FindNodesByCode → Use grep/search
   - DirectoryExplorerTool → Use ls/file browsing
   ```

2. Update `/Users/berrazuriz/Desktop/Blar/repositories/blarify/docs/api-reference.md`
3. Create migration guide in `/Users/berrazuriz/Desktop/Blar/repositories/blarify/docs/tools-migration.md`
4. Update any examples that reference old tool names

### Step 15: Create Pull Request
```bash
git add -A
git commit -m "refactor: make Blarify tools more intuitive for AI agents

- Remove 3 redundant tools (FindNodesByPath, FindNodesByCode, DirectoryExplorer)
- Rename remaining tools with intuitive, agent-friendly names
- Add dual input support (reference_id OR file_path + symbol_name)
- Abstract graph terminology from descriptions
- Keep reference IDs as efficient tool handles
- Consolidate to 6 focused, powerful tools

Breaking changes:
- Tool class names have changed (see migration guide)
- Removed FindNodesByPath, FindNodesByCode, DirectoryExplorerTool

Co-Authored-By: AI Agent <noreply@anthropic.com>"

git push -u origin refactor/ai-friendly-tools-suite
```

### Step 16: Code Review Process
1. Request review from team members
2. Run WorkflowManager code-reviewer sub-agent
3. Address any feedback
4. Ensure all CI/CD checks pass
5. Merge when approved

## Additional Implementation Details

### Error Handling Strategy
```python
try:
    reference_id = resolve_reference_id(
        db_manager=self.db_manager,
        reference_id=args.reference_id,
        file_path=args.file_path,
        symbol_name=args.symbol_name
    )
except ValueError as e:
    return f"Error: {str(e)}. Please provide valid inputs."
```