---
title: "Implement MCP Server for Blarify Tools"
issue_number: ""
created_by: prompt-writer
date: 2025-01-08
description: "Create an MCP (Model Context Protocol) server to expose Blarify's Langchain-compatible tools for AI assistant integration"
---

# Implement MCP Server for Blarify Tools

## Overview

This prompt guides the implementation of a Model Context Protocol (MCP) server for Blarify, exposing the existing Langchain-compatible tools through the MCP interface. This will enable Claude Desktop and other MCP-compatible clients to interact directly with Blarify's graph-based code analysis capabilities, providing powerful code exploration and understanding features to AI assistants.

## Problem Statement

### Current Limitations
- Blarify's powerful graph-based code analysis tools are only accessible through Langchain integration
- No standardized protocol for AI assistants to access these tools outside of Langchain environments
- Limited integration options for modern AI development environments like Claude Desktop
- Tools require manual configuration and initialization for each use case

### Impact on Users
- Developers cannot easily integrate Blarify tools into their AI-powered workflows
- AI assistants lack direct access to sophisticated code graph analysis capabilities
- Teams must write custom integration code for each AI platform they use
- Reduced productivity in AI-assisted code analysis and understanding tasks

### Why This Matters Now
- MCP has emerged as the standard protocol for AI tool integration
- Claude Desktop and other platforms now support MCP servers natively
- Growing demand for AI-assisted code analysis in development workflows
- Opportunity to make Blarify's capabilities accessible to a wider audience

## Feature Requirements

### Functional Requirements

1. **MCP Server Implementation**
   - Implement stdio-based MCP server for Claude Desktop compatibility
   - Support all 11 existing Blarify tools through MCP protocol
   - Maintain backward compatibility with existing Langchain tools
   - Provide seamless tool discovery and invocation

2. **Tool Adaptation Layer**
   - Create MCP-compatible wrappers for each Langchain tool
   - Preserve all existing tool functionality and parameters
   - Handle type conversions between MCP and Langchain formats
   - Maintain tool descriptions and parameter schemas

3. **Configuration Management**
   - Support environment variable configuration (NEO4J_URI, etc.)
   - Allow repository and entity ID configuration
   - Support both Neo4j and FalkorDB backends
   - Provide sensible defaults for common use cases

4. **Error Handling**
   - Graceful handling of database connection failures
   - Clear error messages for missing configuration
   - Proper validation of tool inputs
   - Recovery mechanisms for transient failures

### Technical Requirements

1. **Dependencies**
   - Use official MCP Python SDK or FastMCP for simplified implementation
   - Maintain compatibility with Python 3.11-3.14
   - Follow existing Poetry dependency management patterns
   - Minimize additional dependencies

2. **Type Safety**
   - Comprehensive type hints for all functions and classes
   - No use of `Any` type without explicit justification
   - Nested typing for complex structures (e.g., `List[NodeSearchResultDTO]`)
   - Strict typing mode compliance with pyright

3. **Code Quality**
   - Follow existing Ruff linting rules (120 char line length)
   - Maintain existing code style and conventions
   - Comprehensive docstrings for all public APIs
   - Clean separation of concerns

4. **Testing**
   - Unit tests for all MCP server components
   - Integration tests for tool invocation through MCP
   - Mock database interactions for isolated testing
   - Test coverage > 80% for new code

### Integration Requirements

1. **Database Compatibility**
   - Work with existing AbstractDbManager interface
   - Support Neo4j
   - Maintain existing query patterns and optimizations

2. **Tool Compatibility**
   - Preserve all existing tool interfaces
   - Support all current tool parameters and options
   - Maintain existing error handling patterns

3. **Configuration Compatibility**
   - Use existing environment variable patterns
   - Support existing .env file configurations
   - Maintain backward compatibility with current setups

## Technical Analysis

### Current Implementation Review

The existing Blarify tools follow a consistent pattern:
- All tools inherit from `langchain_core.tools.BaseTool`
- Each tool has a Pydantic model for input validation
- Tools accept an `AbstractDbManager` instance for database operations
- Tools return structured data or formatted strings
- Comprehensive error handling and logging

Existing tools to expose:
1. **DirectoryExplorerTool** - Navigate repository structure
2. **FindNodesByCode** - Search for code text
3. **FindNodesByNameAndType** - Find nodes by name/type
4. **FindNodesByPath** - Find nodes at paths
5. **GetCodeByIdTool** - Get node details
6. **GetFileContextByIdTool** - Get expanded file context
7. **GetCodeWithContextTool** - Combined node and context
8. **GetRelationshipFlowchart** - Generate Mermaid diagrams
9. **GetBlameByIdTool** - GitHub blame information
10. **GetCommitByIdTool** - Commit information
11. **GetNodeWorkflowsTool** - Workflow information

### Proposed Technical Approach

1. **MCP Server Architecture**
   ```
   blarify/
   ├── mcp_server/
   │   ├── __init__.py
   │   ├── server.py           # Main MCP server implementation
   │   ├── tool_adapter.py     # Langchain to MCP adapter
   │   ├── config.py           # Configuration management
   │   └── tools/              # MCP tool implementations
   │       ├── __init__.py
   │       ├── base.py         # Base MCP tool wrapper
   │       └── [tool_name].py  # Individual tool wrappers
   ```

2. **Tool Adaptation Strategy**
   - Create a base `MCPToolWrapper` class that adapts Langchain tools
   - Implement automatic schema conversion from Pydantic to MCP format
   - Handle async/sync method conversion as needed
   - Preserve all tool metadata and descriptions

3. **Configuration Approach**
   - Load configuration from environment variables
   - Support `.env` file for local development
   - Provide configuration validation on startup
   - Allow runtime configuration updates where appropriate

4. **Database Connection Management**
   - Singleton pattern for database manager instances
   - Lazy initialization of database connections
   - Connection pooling for performance
   - Graceful degradation on connection failures

### Architecture Decisions

1. **Use FastMCP for Simplified Implementation**
   - Provides higher-level abstractions over raw MCP
   - Reduces boilerplate code
   - Better error handling out of the box
   - Active community and maintenance

2. **Maintain Separation from Existing Tools**
   - Keep MCP server as a separate module
   - Avoid modifying existing Langchain tools
   - Use adapter pattern for clean separation
   - Enable independent evolution of both systems

3. **Stdio Transport for Maximum Compatibility**
   - Primary transport for Claude Desktop
   - Simple to implement and debug
   - No network configuration required
   - Secure by default (local only)

## Implementation Plan

### Phase 1: Foundation (Day 1)
**Deliverables:**
- MCP server module structure created
- Basic server implementation with stdio transport
- Configuration management system
- Database connection initialization

**Tasks:**
1. Add MCP dependencies to pyproject.toml
2. Create mcp_server module structure
3. Implement basic MCP server with hello world tool
4. Add configuration loading from environment
5. Test basic server startup and tool discovery

### Phase 2: Tool Adaptation Layer (Day 2-3)
**Deliverables:**
- Base tool wrapper implementation
- Schema conversion utilities
- First 3 tools successfully wrapped
- Unit tests for adaptation layer

**Tasks:**
1. Create MCPToolWrapper base class
2. Implement Pydantic to MCP schema conversion
3. Wrap DirectoryExplorerTool
4. Wrap GetCodeByIdTool
5. Wrap FindNodesByNameAndType
6. Write comprehensive unit tests

### Phase 3: Complete Tool Integration (Day 4-5)
**Deliverables:**
- All 11 tools wrapped and functional
- Integration tests for all tools
- Error handling improvements
- Performance optimizations

**Tasks:**
1. Wrap remaining 8 tools
2. Add integration tests for each tool
3. Implement robust error handling
4. Optimize database query patterns
5. Add caching where appropriate

### Phase 4: Testing and Documentation (Day 6)
**Deliverables:**
- Comprehensive test suite
- User documentation
- Configuration examples
- Claude Desktop integration guide

**Tasks:**
1. Write end-to-end integration tests
2. Create README for MCP server
3. Document configuration options
4. Create example Claude Desktop config
5. Add troubleshooting guide

### Phase 5: Polish and Launch (Day 7)
**Deliverables:**
- Production-ready MCP server
- Performance benchmarks
- Launch script and utilities
- PR ready for review

**Tasks:**
1. Performance profiling and optimization
2. Security review of exposed functionality
3. Create launch scripts for different platforms
4. Final testing and validation
5. Prepare comprehensive PR

## Testing Requirements

### Unit Testing Strategy
1. **Server Components**
   - Test server initialization and configuration
   - Test tool registration and discovery
   - Test message handling and routing
   - Mock all external dependencies

2. **Tool Wrappers**
   - Test schema conversion accuracy
   - Test parameter validation
   - Test error handling
   - Test response formatting

3. **Configuration**
   - Test environment variable loading
   - Test configuration validation
   - Test default value handling
   - Test error cases

### Integration Testing
1. **End-to-End Tool Invocation**
   - Test each tool through MCP protocol
   - Verify correct database queries executed
   - Validate response formats
   - Test error propagation

2. **Database Integration**
   - Test with Neo4j container
   - Test with FalkorDB container
   - Test connection failure scenarios
   - Test query timeout handling

3. **Claude Desktop Integration**
   - Manual testing with Claude Desktop
   - Test all tools in real scenarios
   - Verify performance characteristics
   - Document any limitations

### Performance Testing
1. **Benchmarks**
   - Measure tool invocation latency
   - Test concurrent tool requests
   - Profile memory usage
   - Identify bottlenecks

2. **Load Testing**
   - Test with multiple concurrent clients
   - Test with large result sets
   - Test connection pool behavior
   - Measure resource consumption

### Edge Cases and Error Scenarios
1. **Configuration Errors**
   - Missing required environment variables
   - Invalid database credentials
   - Malformed configuration values
   - Network connectivity issues

2. **Tool Input Validation**
   - Invalid node IDs
   - Malformed search queries
   - Out of range parameters
   - SQL injection attempts

3. **Runtime Errors**
   - Database connection loss
   - Query timeouts
   - Memory exhaustion
   - Unexpected data formats

## Success Criteria

### Functional Success Metrics
- [ ] All 11 Blarify tools accessible through MCP protocol
- [ ] Claude Desktop can discover and invoke all tools
- [ ] No regression in existing Langchain tool functionality
- [ ] Clean startup with proper configuration validation

### Quality Metrics
- [ ] Test coverage > 80% for new code
- [ ] Zero pyright errors in strict mode
- [ ] Zero ruff linting violations
- [ ] All tests passing in CI/CD pipeline

### Performance Benchmarks
- [ ] Tool invocation latency < 100ms (excluding database query time)
- [ ] Server startup time < 2 seconds
- [ ] Memory footprint < 100MB base usage
- [ ] Support for 10+ concurrent tool invocations

### User Experience Metrics
- [ ] Clear, actionable error messages
- [ ] Comprehensive documentation with examples
- [ ] Simple configuration process
- [ ] Intuitive tool descriptions and parameters

## Implementation Steps

### Step 1: GitHub Issue Creation
Create a GitHub issue for tracking this implementation:
```bash
gh issue create \
  --title "Feature: Implement MCP Server for Blarify Tools" \
  --body "## Problem Statement
Blarify's powerful graph-based code analysis tools need to be exposed through the Model Context Protocol (MCP) to enable integration with Claude Desktop and other AI assistants.

## Requirements
- Implement stdio-based MCP server
- Wrap all 11 existing Langchain tools
- Maintain backward compatibility
- Support Neo4j and FalkorDB backends
- Comprehensive testing and documentation

## Technical Approach
- Use FastMCP for implementation
- Adapter pattern for tool wrapping
- Environment-based configuration
- Comprehensive type safety

## Success Criteria
- All tools accessible through MCP
- Claude Desktop integration working
- 80%+ test coverage
- Performance benchmarks met

*Note: This issue was created by an AI agent on behalf of the repository owner.*" \
  --label "enhancement,feature"
```

### Step 2: Branch Creation
Create feature branch for development:
```bash
git checkout -b feature/mcp-server-implementation
```

### Step 3: Research and Planning
1. Review MCP protocol documentation
2. Analyze FastMCP examples and best practices
3. Study existing Blarify tool implementations
4. Identify potential integration challenges
5. Create detailed technical design document

### Step 4: Foundation Implementation
1. Add MCP dependencies to pyproject.toml:
   ```toml
   fastmcp = "^0.3.0"
   mcp = "^1.0.0"
   ```
2. Create mcp_server module structure
3. Implement basic server with configuration
4. Add database connection management
5. Test basic functionality

### Step 5: Tool Adaptation
1. Create base wrapper class
2. Implement schema conversion utilities
3. Wrap each tool systematically
4. Add comprehensive error handling
5. Write unit tests for each wrapper

### Step 6: Integration Testing
1. Set up test database containers
2. Create integration test suite
3. Test each tool end-to-end
4. Verify Claude Desktop compatibility
5. Document any limitations

### Step 7: Documentation
1. Create MCP server README
2. Document configuration options
3. Provide Claude Desktop setup guide
4. Add troubleshooting section
5. Include example usage scenarios

### Step 8: Performance Optimization
1. Profile server performance
2. Optimize database queries
3. Implement caching where beneficial
4. Reduce memory footprint
5. Document performance characteristics

### Step 9: Code Review Preparation
1. Run pyright in strict mode
2. Run ruff for linting
3. Ensure all tests pass
4. Update documentation
5. Create comprehensive PR description

### Step 10: Pull Request Creation
Create PR with detailed description:
```bash
gh pr create \
  --title "feat: Implement MCP Server for Blarify Tools" \
  --body "## Summary
- Implements Model Context Protocol (MCP) server for Blarify
- Exposes all 11 existing Langchain tools through MCP
- Enables Claude Desktop integration

## Changes
- Added `blarify/mcp_server/` module with complete implementation
- Created tool adapters for all existing tools
- Added comprehensive test suite
- Included documentation and configuration examples

## Testing
- Unit tests for all components
- Integration tests with database backends
- Manual testing with Claude Desktop
- Performance benchmarks included

## Documentation
- README for MCP server usage
- Claude Desktop configuration guide
- API documentation for tool wrappers

*Note: This PR was created by an AI agent*"
```

### Step 11: Code Review Process
1. Invoke code-reviewer sub-agent for thorough review
2. Address all review feedback
3. Ensure CI/CD pipeline passes
4. Update documentation as needed
5. Merge upon approval

## Risk Assessment and Mitigation

### Technical Risks
1. **MCP Protocol Changes**
   - Risk: MCP specification evolves incompatibly
   - Mitigation: Pin MCP SDK version, monitor updates
   
2. **Performance Degradation**
   - Risk: MCP overhead impacts tool performance
   - Mitigation: Implement caching, optimize hot paths
   
3. **Database Connection Issues**
   - Risk: Connection pooling causes resource exhaustion
   - Mitigation: Implement proper connection management

### Integration Risks
1. **Tool Compatibility**
   - Risk: Some tools don't map cleanly to MCP
   - Mitigation: Design flexible adapter pattern
   
2. **Schema Conversion Complexity**
   - Risk: Complex Pydantic schemas hard to convert
   - Mitigation: Implement robust conversion utilities

### Operational Risks
1. **Configuration Complexity**
   - Risk: Users struggle with setup
   - Mitigation: Provide clear documentation and examples
   
2. **Debugging Difficulties**
   - Risk: Hard to debug MCP communication
   - Mitigation: Implement comprehensive logging

## Dependencies and Prerequisites

### Required Dependencies
- `fastmcp` or `mcp` Python package
- Existing Blarify dependencies (neo4j, langchain, etc.)
- Python 3.11-3.14 runtime

### Development Prerequisites
- Docker for running test databases
- Poetry for dependency management
- Git for version control
- Testing frameworks (pytest, pytest-asyncio)

### Knowledge Prerequisites
- Understanding of MCP protocol
- Familiarity with Langchain tools
- Knowledge of Blarify architecture
- Experience with async Python programming

## Future Enhancements

### Short-term (Post-MVP)
- Add tool result caching for performance
- Implement batch tool invocation support
- Add metrics and monitoring
- Create tool composition capabilities

### Medium-term
- Support for WebSocket transport
- Tool versioning and compatibility management
- Dynamic tool discovery from graph
- Custom tool creation interface

### Long-term
- Multi-tenant support with isolation
- Tool marketplace integration
- AI-powered tool suggestions
- Automated tool generation from code patterns

## Conclusion

This MCP server implementation will significantly expand Blarify's reach by making its powerful code analysis tools accessible to modern AI assistants. The careful adaptation of existing tools ensures backward compatibility while opening new integration possibilities. With comprehensive testing and documentation, this feature will provide a robust foundation for AI-assisted code analysis workflows.