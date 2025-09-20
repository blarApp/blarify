---
title: "CLI for Graph Building and MCP Server Enhancement"
issue_number: ""
created_by: prompt-writer
date: 2025-01-08
description: "Add CLI tool for building graphs and enhance MCP server to use repository paths as identifiers"
---

# CLI for Graph Building and MCP Server Enhancement

## Overview

This prompt guides the implementation of a CLI tool for building Blarify graphs and enhances the MCP server to use repository paths as identifiers. This will enable users to easily build graphs from the command line and simplify the MCP server configuration by using the repository path as the unique identifier.

## Problem Statement

### Current Limitations
- No CLI tool exists for building graphs - users must write Python code
- MCP server requires manual graph creation before it can be used
- Complex repository ID management with separate entity_id and repo_id
- DocumentationCreator and WorkflowCreator aren't easily accessible
- Poor user experience for getting started with Blarify

### Impact on Users
- High barrier to entry for new users
- Manual Python scripting required for basic operations
- Confusion about entity_id and repo_id relationships
- No clear workflow from repository to working MCP server
- Difficult to manage multiple repositories

### Why This Matters Now
- Users expect CLI tools for common operations
- MCP adoption requires simpler setup process
- Graph building should be a one-command operation
- Documentation and workflow generation should be easily accessible

## Feature Requirements

### Functional Requirements

1. **CLI Tool Implementation**
   - Create `blarify` command with `create` subcommand
   - Accept repository path as primary argument
   - Support entity-id parameter (required)
   - Use repository path as repo-id by default
   - Optional flags for documentation and workflow generation
   - Progress reporting during build process

2. **Graph Building Integration**
   - Use existing GraphBuilder from prebuilt module
   - Save to configured database (Neo4j/FalkorDB)
   - Support all existing graph building options
   - Handle LSP initialization and shutdown properly

3. **Documentation and Workflow Generation**
   - Optional `--docs` flag to run DocumentationCreator
   - Optional `--workflows` flag to run WorkflowCreator
   - Require OPENAI_API_KEY for documentation generation
   - Support both full and targeted documentation modes

4. **MCP Server Configuration Update**
   - Add root_path parameter to configuration
   - Use root_path as repo_id for database queries
   - Maintain backward compatibility where possible
   - Simplify configuration for end users

### Technical Requirements

1. **CLI Architecture**
   - Use argparse for command parsing
   - Follow Unix philosophy (do one thing well)
   - Support environment variables for configuration
   - Provide helpful error messages

2. **Progress Reporting**
   - Use rich library for terminal output
   - Show progress bars for long operations
   - Display statistics and summaries
   - Handle interruptions gracefully

3. **Configuration Management**
   - Read from environment variables
   - Support command-line overrides
   - Validate all required parameters
   - Store last used configuration

4. **Error Handling**
   - Check for existing graphs before building
   - Validate database connectivity
   - Handle missing API keys gracefully
   - Provide actionable error messages

## Technical Analysis

### Current Implementation Review

The existing codebase has all the components needed:
- `GraphBuilder` in `blarify/prebuilt/graph_builder.py`
- `DocumentationCreator` in `blarify/documentation/documentation_creator.py`
- `WorkflowCreator` in `blarify/documentation/workflow_creator.py`
- Database managers in `blarify/repositories/graph_db_manager/`
- MCP server in `blarify/mcp_server/`

### Proposed Technical Approach

1. **CLI Module Structure**
   ```
   blarify/
   ├── cli/
   │   ├── __init__.py
   │   ├── main.py          # Entry point with argparse
   │   └── commands/
   │       ├── __init__.py
   │       └── create.py    # Graph creation implementation
   ```

2. **Command Interface**
   ```bash
   blarify create /path/to/repo \
     --entity-id my-company \
     [--repo-id custom-id] \
     [--docs] \
     [--workflows] \
     [--neo4j-uri bolt://localhost:7687] \
     [--neo4j-username neo4j] \
     [--neo4j-password password]
   ```

3. **MCP Server Configuration**
   ```python
   class MCPServerConfig(BaseModel):
       root_path: str  # Repository path (used as repo_id)
       entity_id: str
       # ... other fields
   ```

### Architecture Decisions

1. **Use Path as Repository ID**
   - Simplifies configuration
   - Eliminates ID management complexity
   - Natural mapping between repository and graph
   - Unique identifier guaranteed by filesystem

2. **Separate CLI from MCP Server**
   - Clean separation of concerns
   - CLI builds, MCP serves
   - No graph building logic in MCP server
   - Follows Unix philosophy

3. **Progressive Enhancement**
   - Basic graph building first
   - Documentation optional with flag
   - Workflows optional with flag
   - Allows incremental adoption

## Implementation Plan

### Phase 1: CLI Foundation (Day 1)
**Deliverables:**
- CLI module structure created
- Basic argparse implementation
- Entry point in pyproject.toml
- Basic command validation

**Tasks:**
1. Create `blarify/cli/` directory structure
2. Implement `main.py` with argparse
3. Create `create.py` command skeleton
4. Add `blarify` script to pyproject.toml
5. Test basic CLI invocation

### Phase 2: Graph Building Integration (Day 2)
**Deliverables:**
- Working graph building command
- Database connection and saving
- Progress reporting with rich
- Error handling

**Tasks:**
1. Integrate GraphBuilder in create command
2. Add database manager initialization
3. Implement progress reporting
4. Add error handling and validation
5. Test graph building end-to-end

### Phase 3: Documentation and Workflows (Day 3)
**Deliverables:**
- Documentation generation with --docs flag
- Workflow generation with --workflows flag
- API key validation
- LLM provider integration

**Tasks:**
1. Add --docs flag implementation
2. Integrate DocumentationCreator
3. Add --workflows flag implementation
4. Integrate WorkflowCreator
5. Add OPENAI_API_KEY validation

### Phase 4: MCP Server Updates (Day 4)
**Deliverables:**
- Updated MCPServerConfig with root_path
- Modified database initialization
- Updated environment variable mapping
- Backward compatibility handling

**Tasks:**
1. Add root_path to MCPServerConfig
2. Update database manager initialization
3. Modify environment variable parsing
4. Test MCP server with new configuration
5. Update MCP server documentation

### Phase 5: Testing and Documentation (Day 5)
**Deliverables:**
- Unit tests for CLI commands
- Integration tests
- Updated README
- Usage examples

**Tasks:**
1. Write unit tests for CLI
2. Create integration tests
3. Update main README
4. Create CLI usage guide
5. Update MCP server README

## Testing Requirements

### Unit Testing Strategy
1. **CLI Command Parsing**
   - Test argument parsing
   - Validate required parameters
   - Test optional flags
   - Error message validation

2. **Graph Building**
   - Mock GraphBuilder calls
   - Test database saving
   - Validate error handling
   - Progress reporting

3. **Configuration**
   - Environment variable loading
   - Command-line overrides
   - Validation logic
   - Default values

### Integration Testing
1. **End-to-End Graph Building**
   - Build small test repository
   - Verify database contents
   - Test with different languages
   - Validate node and relationship counts

2. **MCP Server Integration**
   - Build graph with CLI
   - Start MCP server
   - Query tools successfully
   - Verify correct graph accessed

### Manual Testing Checklist
- [ ] Build graph for Python project
- [ ] Build graph for JavaScript project
- [ ] Generate documentation successfully
- [ ] Generate workflows successfully
- [ ] MCP server accesses correct graph
- [ ] Error handling for missing parameters
- [ ] Progress reporting displays correctly

## Success Criteria

### Functional Success Metrics
- [ ] CLI command successfully builds graphs
- [ ] Documentation generation works with --docs flag
- [ ] Workflow generation works with --workflows flag
- [ ] MCP server uses root_path as repo_id

### Quality Metrics
- [ ] All tests passing
- [ ] Zero pyright errors
- [ ] Zero ruff violations
- [ ] Documentation updated

### Performance Benchmarks
- [ ] Graph building time comparable to direct API
- [ ] No performance regression in MCP server
- [ ] Progress reporting doesn't slow operations

### User Experience Metrics
- [ ] Clear command-line interface
- [ ] Helpful error messages
- [ ] Intuitive parameter names
- [ ] Good progress feedback

## Implementation Steps

### Step 1: Create CLI Module Structure
```bash
mkdir -p blarify/cli/commands
touch blarify/cli/__init__.py
touch blarify/cli/main.py
touch blarify/cli/commands/__init__.py
touch blarify/cli/commands/create.py
```

### Step 2: Implement Main CLI Entry Point
Create `blarify/cli/main.py`:
```python
import argparse
import sys
from blarify.cli.commands import create

def main():
    parser = argparse.ArgumentParser(
        prog='blarify',
        description='Blarify - Graph-based code analysis'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Build a graph')
    create.add_arguments(create_parser)
    
    args = parser.parse_args()
    
    if args.command == 'create':
        return create.execute(args)
    else:
        parser.print_help()
        return 1

if __name__ == '__main__':
    sys.exit(main())
```

### Step 3: Implement Create Command
Create `blarify/cli/commands/create.py`:
```python
import os
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.documentation.documentation_creator import DocumentationCreator
from blarify.documentation.workflow_creator import WorkflowCreator

def add_arguments(parser):
    parser.add_argument('path', help='Repository path')
    parser.add_argument('--entity-id', required=True, help='Entity identifier')
    parser.add_argument('--repo-id', help='Repository identifier (defaults to path)')
    parser.add_argument('--docs', action='store_true', help='Generate documentation')
    parser.add_argument('--workflows', action='store_true', help='Generate workflows')
    # Database configuration
    parser.add_argument('--neo4j-uri', default=os.getenv('NEO4J_URI'))
    parser.add_argument('--neo4j-username', default=os.getenv('NEO4J_USERNAME'))
    parser.add_argument('--neo4j-password', default=os.getenv('NEO4J_PASSWORD'))

def execute(args):
    console = Console()
    
    # Use path as repo_id if not specified
    repo_id = args.repo_id or args.path
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Build graph
        task = progress.add_task("Building graph...", total=None)
        builder = GraphBuilder(root_path=args.path)
        graph = builder.build()
        
        # Save to database
        progress.update(task, description="Saving to database...")
        db_manager = Neo4jManager(
            uri=args.neo4j_uri,
            username=args.neo4j_username,
            password=args.neo4j_password,
            repo_id=repo_id,
            entity_id=args.entity_id
        )
        db_manager.save_graph(
            graph.get_nodes_as_objects(),
            graph.get_relationships_as_objects()
        )
        
        # Generate documentation if requested
        if args.docs:
            progress.update(task, description="Generating documentation...")
            # Implementation here
        
        # Generate workflows if requested
        if args.workflows:
            progress.update(task, description="Generating workflows...")
            # Implementation here
        
        db_manager.close()
    
    console.print(f"[green]✓[/green] Graph built successfully!")
    return 0
```

### Step 4: Update pyproject.toml
```toml
[tool.poetry.scripts]
blarify = "blarify.cli.main:main"
blarify-mcp = "blarify.mcp_server:main"
```

### Step 5: Update MCP Server Configuration
Update `blarify/mcp_server/config.py`:
```python
class MCPServerConfig(BaseModel):
    # Database configuration
    neo4j_uri: str = Field(...)
    neo4j_username: str = Field(...)
    neo4j_password: str = Field(...)
    
    # Repository configuration
    root_path: str = Field(
        description="Repository path (used as repo_id)"
    )
    entity_id: str = Field(
        description="Entity identifier"
    )
    
    # Remove old repository_id field
```

### Step 6: Update MCP Server Database Initialization
Update `blarify/mcp_server/server.py`:
```python
def _initialize_db_manager(self) -> AbstractDbManager:
    if self.config.db_type == "neo4j":
        return Neo4jManager(
            uri=self.config.neo4j_uri,
            user=self.config.neo4j_username,
            password=self.config.neo4j_password,
            repo_id=self.config.root_path,  # Use root_path as repo_id
            entity_id=self.config.entity_id,
        )
```

## Risk Assessment and Mitigation

### Technical Risks
1. **Path as ID Issues**
   - Risk: Long paths might cause issues
   - Mitigation: Hash paths if too long
   
2. **Backward Compatibility**
   - Risk: Breaking existing setups
   - Mitigation: Support old config temporarily

### Operational Risks
1. **User Confusion**
   - Risk: Users confused by new workflow
   - Mitigation: Clear documentation and examples

2. **API Key Management**
   - Risk: Missing API keys for documentation
   - Mitigation: Clear error messages

## Dependencies and Prerequisites

### Required Dependencies
- All existing Blarify dependencies
- rich (already in dependencies)
- argparse (built-in)

### Development Prerequisites
- Python 3.11-3.14
- Docker for database testing
- OPENAI_API_KEY for documentation testing

## Future Enhancements

### Short-term
- Add `blarify update` command for incremental updates
- Add `blarify status` command to check graph status
- Support for .blarify.yml configuration file

### Long-term
- Web UI for graph building
- Cloud-based graph storage
- Automated graph updates on git push

## Conclusion

This implementation will significantly improve the Blarify user experience by providing a simple CLI for graph building and simplifying the MCP server configuration. The use of repository paths as identifiers eliminates complexity while maintaining uniqueness. With comprehensive testing and documentation, this feature will make Blarify more accessible to new users while maintaining power for advanced use cases.