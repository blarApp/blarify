## Code Review Memory - 2025-08-05

### PR #242: Fix workflow discovery DFS path sequencing gaps

#### What I Learned
- Bridge edge pattern addresses DFS path sequencing gaps by creating synthetic connections between consecutive paths
- _create_bridge_edges() maintains database integrity by creating edges only in memory (never stored)
- Bridge edges have identical structure to CALLS edges for uniform LLM processing
- Path boundary detection uses depth=0 and entry point ID reoccurrence to identify new DFS paths
- Step ordering is crucial for continuous execution trace reconstruction

#### Patterns to Watch
- Bridge edges should always have call_line=None and call_character=None since they're synthetic
- Functions creating synthetic data should be prefixed with underscore (_create_bridge_edges)
- Complex query functions should be split into query generation and execution components
- Integration tests should verify compatibility with existing data structures (WorkflowResult)
- Bridge edge creation is O(n) complexity and scales linearly with path count

#### Architecture Insights
- DFS traversal creates independent paths that need synthetic connections for continuity
- LLM agents require continuous execution traces for complete workflow understanding
- Database integrity preserved by keeping synthetic data in memory only
- Step ordering provides the sequence needed for timeline reconstruction
EOF < /dev/null
## Code Review Memory - 2025-08-07

### PR #253: Implement GraphBuilder Integration Tests with Testing Documentation

#### What I Learned
- Integration testing framework uses pytest with neo4j_container_manager for isolated database environments
- GraphAssertions utility class provides standardized Cypher query methods for validation
- Test code examples are organized by language in tests/code_examples/ directory
- APOC plugin support is enabled in Neo4j container configuration for advanced queries
- LSP helper had critical bug in attribute name: language_to_lsp_server vs language_to_lsp_servers
- Async test configuration requires asyncio_mode = "auto" in pytest settings
- Threading issues in LSP context manager exit handling needed proper cleanup for multiple instances

#### Patterns to Watch
- Integration tests should use shared fixtures from conftest.py for consistency
- Test code examples should be minimal but representative of real-world usage
- Graph validation should use parameterized assertions for different node types and relationships
- Neo4j container lifecycle management ensures clean test isolation
- LSP server instance management requires careful handling of multiple server contexts per language
- Test documentation should include clear contributor guidelines and troubleshooting sections

#### Architecture Insights
- GraphBuilder integration requires end-to-end testing from source code parsing to database persistence
- Multi-language support testing uses parameterized pytest fixtures for DRY principles
- Neo4j container integration with APOC plugin enables advanced graph operations in tests
- LSP helper supports multiple server instances per language for parallel processing
- Test structure separates basic functionality, language-specific features, and edge cases for maintainability
- Graph assertions abstract Cypher query complexity for test readability

#### Critical Bug Fixes Identified
- Fixed LSP helper typo: language_to_lsp_server → language_to_lsp_servers (line 905)
- Fixed threading issue in LSP context manager exit handling for multiple instances
- Added proper async test configuration with asyncio_mode = "auto"
- Fixed node label capitalization consistency throughout test suite

EOF < /dev/null