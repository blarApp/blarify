# Semantic Documentation Layer Implementation Plan

## Overview

This document serves as a comprehensive implementation plan for adding a semantic documentation layer to Blarify. The semantic layer creates **dual-format documentation** optimized for different LLM agent consumption patterns:

1. **Fine-grained InformationNodes**: Atomic, searchable pieces stored in the graph database for precise retrieval
2. **Comprehensive Markdown Files**: Complete, narrative documentation for full-context consumption

The system uses LangGraph to orchestrate LLM agents that analyze codebases and generate semantic understanding optimized for both search and comprehensive understanding.

## Feature Description

### What is the Semantic Documentation Layer?

The semantic documentation layer is a new component that sits on top of Blarify's existing code graph structure. It analyzes the codebase using LLM agents to create **dual-format semantic documentation**:

#### **Format 1: Fine-Grained InformationNodes** (Graph Database)
Atomic, searchable pieces optimized for two search modes:
- **Located Search**: Standing at specific code points, traverse hierarchically up the graph
- **General Search**: Vector/semantic search across all information using RAG or BM25

Content includes:
- **System Overview**: Business context, purpose, and high-level architecture
- **Component Documentation**: Detailed analysis of key components and their responsibilities  
- **API Documentation**: Function/class usage patterns and examples
- **Relationship Mapping**: Inter-component dependencies and data flow patterns

#### **Format 2: Comprehensive Markdown Files** (File System)
Complete, narrative documentation optimized for full-context consumption:
- **Complete Stories**: Integrated explanations across multiple components
- **Code-Grounded**: Every statement backed by specific file paths and line numbers
- **Self-Contained**: No database dependencies, pure code references
- **Agent-Optimized**: Sized appropriately for LLM context windows

### How it Works

1. **Input**: Existing code graph with files, classes, functions, and relationships
2. **Process**: LangGraph workflow with LLM agents analyzes the code structure
3. **Output**: 
   - Fine-grained InformationNode objects with precise code references
   - Comprehensive markdown files with complete context and direct code links
4. **Storage**: 
   - InformationNodes stored in graph database with code node relationships
   - Markdown files saved to filesystem with embedded code references

### Benefits

- **Dual Search Capabilities**: Both precise hierarchical search and general semantic search
- **Complete Context**: Full narrative documentation for comprehensive understanding
- **Code Grounding**: All information traceable to specific code locations
- **Format Flexibility**: Choose InformationNodes for search, markdown for complete context
- **Agent-Friendly**: Optimized for different LLM agent consumption patterns

## Technical Architecture

### Project Structure

The semantic documentation layer follows a modular architecture with clear separation of concerns:

```
blarify/
├── agents/                  # Agent-related functionality
│   ├── llm_providers.py    # LLM provider implementations
│   ├── prompt_templates.py # Prompt management system
│   └── agent_tools.py      # Agent tools infrastructure
├── documentation/          # Documentation processing
│   ├── workflow.py         # LangGraph workflow orchestration
│   ├── post_processor.py   # Documentation post-processing
│   ├── extractor.py        # Documentation extraction
│   └── semantic_analyzer.py # Semantic analysis interface
└── db_managers/            # Database operations
    └── queries.py          # Specialized queries for semantic analysis
```

### Current State Analysis

#### ✅ Already Implemented
- `InformationNode` class for semantic documentation storage
- `DocumentationExtractor` for raw documentation extraction
- `DocumentationPostProcessor` skeleton with orchestration structure
- `SemanticDocumentationAnalyzer` interface definition
- Database abstraction layer supporting custom node types

#### ❌ Missing Components
- ❌ Database schema for semantic relationships
- ❌ Integration with main GraphBuilder flow
- 🔄 Workflow node implementations (3/10 nodes completed: load_codebase, detect_framework, generate_overview)

#### ✅ Recently Completed
- ✅ LangGraph workflow implementation
- ✅ Concrete LLM provider implementations (LangChain-based)
- ✅ Database query infrastructure
- ✅ Agent tools infrastructure (empty implementations)
- ✅ Prompt templates system

### LangGraph Workflow Architecture

#### DocumentationState TypedDict
```python
class DocumentationState(TypedDict):
    # Fine-grained InformationNode data (for graph database)
    information_nodes: Annotated[list, add]        # Atomic InformationNode objects
    semantic_relationships: Annotated[list, add]   # Relationships between nodes
    code_references: Annotated[list, add]          # Precise code location mappings
    
    # Comprehensive markdown data (for file system)
    markdown_sections: Annotated[list, add]        # Narrative markdown content
    markdown_groupings: dict                       # Logical groupings for .md files
    markdown_files: dict                           # Final .md file contents
    
    # Shared analysis data
    analyzed_nodes: Annotated[list, add]           # Analyzed code components
    repo_structure: dict                           # Repository structure info
    dependencies: dict                             # Component relationships
    root_codebase_skeleton: str                   # AST tree structure
    detected_framework: dict                       # Framework info (Django, Next.js, etc.)
    system_overview: dict                          # Business context & purpose
    doc_skeleton: dict                             # Documentation template
    key_components: list                           # Priority components to analyze
```

#### Workflow Flow (Updated for Consolidated Framework-Guided Bottoms-Up)
```
// Parallel execution:
Branch A: load_codebase → detect_framework (NOW OUTPUTS: framework + main_folders)
Branch B: analyze_all_leaf_nodes (using dumb agent)

// Sequential execution after parallel completion:
iterate_directory_hierarchy_bottoms_up → 
group_related_knowledge → 
compact_to_markdown_per_folder →
consolidate_final_markdown
```

**Consolidated Framework-Guided Bottoms-Up Logic:**
1. **Parallel Processing**: 
   - **Branch A**: Load codebase structure and detect framework WITH main folder identification (single LLM call with structured output)
   - **Branch B**: Use dumb agent to create initial descriptions for ALL leaf nodes (functions, classes)
2. **Framework-Based Analysis**: Single node outputs both framework analysis and main folders list using structured JSON output
3. **Focused Bottoms-Up Processing**: For each main folder, perform bottoms-up hierarchical analysis using the pre-generated leaf descriptions
4. **Knowledge Grouping**: Group related InformationNodes within each folder's hierarchy
5. **Per-Folder Markdown**: Generate markdown sections for each main folder
6. **Final Consolidation**: Combine all folder-based markdown into comprehensive documentation

### Database Schema

#### Enhanced Information Nodes (Optimized for Dual Search)
- **Node Type**: `INFORMATION`
- **Core Properties**: 
  - `title`: Human-readable title
  - `content`: Main semantic content
  - `info_type`: Type (concept, api, pattern, architecture, etc.)
  - `examples`: JSON string of code examples and usage patterns
- **Search Optimization Properties**:
  - `search_keywords`: Array of keywords for vector search
  - `hierarchical_context`: Context description for located search
- **Standard Properties**:
  - `layer`: Always 'documentation'

#### Semantic Relationships
- **DESCRIBES**: InformationNode → CodeNode (precise semantic description)
- **Agent-Determined Relationships**: Other relationships are dynamically determined by LLM agents based on semantic analysis (e.g., RELATED_TO, DEPENDS_ON, EXEMPLIFIES, etc.)

## Dual-Format Consumption Patterns

### InformationNode Search Modes (Graph Database)

#### **1. Located Search Pattern**
**Use Case**: Standing at a specific code location and asking questions
**Query Flow**: 
```
code_node → DESCRIBES relationships → related_information_nodes → 
hierarchical_parent_nodes → their_information_nodes
```
**Optimization**: Fine-grained, atomic InformationNodes with precise code node relationships

#### **2. General Search Pattern**  
**Use Case**: Making general questions about the codebase
**Query Flow**:
```
question → vector_similarity_search → ranked_information_nodes
OR
question → BM25_search → ranked_information_nodes
```
**Optimization**: Rich `search_keywords` and `hierarchical_context` for semantic matching

### Markdown File Consumption (File System)

#### **Complete Context Pattern**
**Use Case**: LLM agents consuming entire documentation files for comprehensive understanding
**Consumption**: Full file read with complete narrative context
**Optimization**: 
- Self-contained stories with integrated explanations
- Direct code references (`file_path:line_start-line_end`)
- No database dependencies
- Sized for LLM context windows (3000-8000 tokens per file)

## Implementation Phases

### Phase 1: Core Infrastructure ✅ COMPLETED
**Priority**: High | **Estimated Effort**: 2-3 days

#### Tasks
- [x] **Add Dependencies** 
  - Add LangGraph to pyproject.toml
  - Add OpenAI and Anthropic SDK dependencies
  - Add typing-extensions for advanced type hints
  
- [x] **Create LLM Provider Infrastructure**
  - Create `blarify/documentation/llm_providers.py`
  - Implement `OpenAIProvider` and `AnthropicProvider` using LangChain
  - Add configuration management and API key handling
  - Implement retry logic and error handling

- [x] **Create Database Query Infrastructure**
  - Create `blarify/db_managers/queries.py`
  - Add query method to AbstractDbManager
  - Implement query method in Neo4jManager and FalkorDBManager
  - Add codebase skeleton query implementation

- [x] **Create Agent Tools Infrastructure**
  - Create `blarify/documentation/agent_tools.py`
  - Add empty implementations for future tool development
  - Set up tool registry and management system

### Phase 2: LangGraph Workflow Core ✅ COMPLETED
**Priority**: High | **Estimated Effort**: 3-4 days

#### Tasks
- [x] **Create Workflow Foundation**
  - Create `blarify/documentation/workflow.py`
  - Implement `DocumentationState` TypedDict
  - Set up LangGraph workflow structure
  - Add basic logging and progress tracking

- [x] **Implement Core Workflow Nodes**
  - `load_codebase` - Create codebase skeleton from existing Graph object
  - `detect_framework` - Analyze package files for tech stack
  - `generate_overview` - Create system understanding document
  
- [x] **Create Workflow Orchestration**
  - Set up LangGraph workflow execution
  - Implement state management between nodes
  - Add error handling and recovery mechanisms
  - Create progress tracking and logging

- [x] **Add Prompt Templates**
  - Create framework detection prompts
  - Create system overview generation prompts
  - Add template management system with `blarify/documentation/prompt_templates.py`

### Phase 3: Framework-Guided Bottoms-Up Workflow Implementation
**Priority**: High | **Estimated Effort**: 4-5 days

#### Overview
Phase 3 focuses on implementing the new framework-guided bottoms-up workflow. This approach uses parallel processing to efficiently analyze leaf nodes while detecting the framework, then performs focused hierarchical analysis based on framework-specific folder structures.

#### New Workflow Node Status Analysis  
- ✅ `__load_codebase` - **COMPLETED** - Loads complete codebase file tree with enhanced formatting
- ✅ `__detect_framework` - **COMPLETED** - Enhanced with structured output for both framework analysis AND main folder identification  
- ✅ `__analyze_all_leaf_nodes` - **COMPLETED** - Use dumb agent to create initial descriptions for ALL leaf nodes (functions, classes, files)
- ✅ ~~`__identify_main_folders_by_framework`~~ - **REMOVED** - Consolidated into `__detect_framework` for efficiency
- ❌ `__iterate_directory_hierarchy_bottoms_up` - **NEEDS IMPLEMENTATION** - Per-folder hierarchical analysis from leaves up
- ❌ `__group_related_knowledge` - **NEEDS IMPLEMENTATION** - Group related InformationNodes within each folder hierarchy
- ❌ `__compact_to_markdown_per_folder` - **NEEDS IMPLEMENTATION** - Generate markdown sections for each main folder
- ❌ `__consolidate_final_markdown` - **NEEDS IMPLEMENTATION** - Combine all folder-based markdown into comprehensive documentation

#### Framework Detection Enhancement (COMPLETED)

The `__detect_framework` node has been enhanced with structured output consolidation:

**Enhanced Implementation:**
1. **Complete File Tree Analysis**: Receives full codebase structure from `__load_codebase`
2. **Single Tool Usage**: Uses only `GetCodeByIdTool` to read configuration files
3. **ReactAgent Architecture**: Continues using ReactAgent for better tool handling
4. **Structured Output**: Single LLM call returns both framework analysis AND main folders using JSON schema
5. **Main Folder Identification**: Identifies 3-10 key architectural folders based on detected framework

**Key Benefits:**
- **Single LLM Call**: Maximum efficiency by combining framework detection and folder identification
- **Structured Output**: Guaranteed consistent format using Pydantic schema validation
- **Workflow Simplification**: Removes separate node, reducing complexity and potential failure points
- **Better Context**: Framework analysis directly informs folder identification in same context
- **Cost Optimization**: Reduces API costs compared to separate LLM calls

#### Leaf Node Analysis Implementation (COMPLETED)

The `__analyze_all_leaf_nodes` node has been successfully implemented with the following architecture:

**Leaf Node Identification Logic:**
- **Hierarchical vs LSP Relationships**: Distinguishes between hierarchical relationships (CONTAINS, FUNCTION_DEFINITION, CLASS_DEFINITION) and LSP/semantic relationships (CALLS, IMPORTS, INHERITS, etc.)
- **Leaf Node Definition**: Nodes with no outgoing hierarchical relationships, regardless of their label (can be FUNCTION, CLASS, METHOD, FILE, etc.)
- **Query Pattern**: `WHERE NOT (n)-[:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION]->()`

**Database Infrastructure:**
- **LeafNodeDto**: Pydantic model with fields: `id`, `name`, `labels`, `path`, `start_line`, `end_line`, `content`
- **Query Functions**: `get_all_leaf_nodes_query()`, `format_leaf_nodes_result()`, `get_all_leaf_nodes()`
- **Relationship Awareness**: Correctly filters out nodes that define/contain other nodes while allowing semantic connections

**LLM Processing:**
- **Batch Processing**: Processes nodes in batches of 10 for efficiency
- **Dumb Agent Usage**: Uses `call_dumb_agent()` method for simple, fast processing
- **Content Limiting**: Truncates node content to 2000 characters to avoid LLM context issues
- **Error Handling**: Creates fallback descriptions for nodes that fail analysis

**Output Structure:**
```python
info_node_description = {
    "node_id": f"info_{node.id}",
    "title": f"Description of {node.name}",
    "content": response_content,  # LLM-generated description
    "info_type": "node_description",
    "source_node_id": node.id,
    "source_path": node.path,
    "source_labels": node.labels,
    "source_type": "leaf_analysis",
    "layer": "documentation"
}
```

**Prompt Template:**
- **LEAF_NODE_ANALYSIS_TEMPLATE**: Focused on basic purpose and functionality
- **Node Type Handling**: Adapts analysis for different node types (FUNCTION, CLASS, METHOD, FILE)
- **Atomic Descriptions**: Generates independent descriptions without relationships to other components

#### Implementation Tasks

##### Task 1: Core Framework-Guided Bottoms-Up Nodes ✅ COMPLETED
- [x] **Implement `__analyze_all_leaf_nodes`** ✅ COMPLETED
  - ✅ Created LeafNodeDto with proper Pydantic structure following existing patterns
  - ✅ Implemented leaf node database queries with hierarchical relationship filtering
  - ✅ Added LEAF_NODE_ANALYSIS_TEMPLATE for atomic node descriptions
  - ✅ Integrated with LLM provider using `call_dumb_agent` for efficient processing
  - ✅ Implemented batch processing with error handling and fallback descriptions
  - ✅ Store results in `leaf_node_descriptions` state field

- [x] **Enhanced `__detect_framework` with Main Folder Identification** ✅ COMPLETED
  - ✅ Created FrameworkAnalysisResponse Pydantic schema for structured output
  - ✅ Enhanced framework detection prompt to include main folder identification
  - ✅ Updated `__detect_framework` to use structured output with ReactAgent
  - ✅ Consolidated framework detection and main folder identification into single LLM call
  - ✅ Removed separate `__identify_main_folders_by_framework` node for efficiency
  - ✅ Updated workflow edges to reflect consolidated approach

##### Task 2: Hierarchical Analysis and Knowledge Grouping
- [ ] **Implement `__iterate_directory_hierarchy_bottoms_up`**
  - For each main folder, perform hierarchical analysis from leaves up
  - Use pre-generated leaf descriptions to build folder-level understanding
  - Create InformationNodes for directory-level concepts and patterns
  - Group related leaf nodes into meaningful semantic clusters

- [ ] **Implement `__group_related_knowledge`**
  - Group related InformationNodes within each folder hierarchy
  - Identify semantic relationships between nodes (RELATED_TO, DEPENDS_ON, etc.)
  - Create relationship mappings for graph database storage
  - Organize knowledge for markdown generation

##### Task 3: Markdown Generation and Final Consolidation
- [ ] **Implement `__compact_to_markdown_per_folder`**
  - Generate comprehensive markdown sections for each main folder
  - Create narrative documentation with code references (file_path:line_number)
  - Ensure self-contained stories with integrated explanations
  - Size appropriately for LLM context windows (3000-8000 tokens per section)

- [ ] **Implement `__consolidate_final_markdown`**
  - Combine all folder-based markdown into comprehensive documentation files
  - Create logical groupings and cross-references between sections
  - Generate final markdown files for filesystem storage
  - Ensure complete coverage and consistency across all folders

#### Implementation Approach
The implementation will follow a straightforward approach:
1. Focus on completing each node's core functionality
2. Use existing prompt templates and LLM provider infrastructure
3. Implement robust error handling and logging
4. Ensure proper state management between nodes
5. Skip complex testing frameworks in favor of direct implementation

#### Success Criteria
- [ ] All 10 workflow nodes implemented with core functionality
- [ ] Proper error handling and recovery mechanisms in place
- [ ] State management working correctly between nodes
- [ ] LLM integration functioning for semantic analysis
- [ ] Documentation generation produces meaningful output

### Phase 4: Database Integration
**Priority**: Medium | **Estimated Effort**: 2-3 days

#### Tasks
- [ ] **Database Schema Updates**
  - Extend AbstractDbManager for InformationNode support
  - Add semantic relationship types
  - Create indexes for efficient querying

- [ ] **Persistence Layer**
  - Implement batch operations for semantic nodes
  - Add relationship creation between layers
  - Create specialized query methods

- [ ] **Migration Support**
  - Add schema migration utilities
  - Create backward compatibility layer
  - Add data validation and integrity checks

### Phase 5: Main Integration
**Priority**: Low | **Estimated Effort**: 2-3 days

#### Tasks
- [ ] **GraphBuilder Integration**
  - Add semantic processing to GraphBuilder
  - Create configuration options for LLM providers
  - Add mode selection (with/without semantic layer)

- [ ] **Main Workflow Integration**
  - Update main.py to support semantic processing
  - Add command-line options for semantic analysis
  - Create documentation processing modes

- [ ] **Testing and Validation**
  - Create comprehensive tests for workflow
  - Add integration tests with real codebases
  - Performance testing and optimization

## Progress Tracking

### Session Notes
Use this section to track progress across work sessions:

**Session 1 (Date: 2024-07-10)**
- ✅ Completed: Phase 1 - Core Infrastructure (all tasks)
- ✅ Completed: Phase 2 - LangGraph Workflow Core (first 3 nodes)
- ✅ Completed: Documentation updates
- ✅ Completed: Code reorganization (moved agentic logic to blarify/agents/)
- ✅ Completed: LLM Provider refactoring (replaced LangChain implementation with existing agent_caller)
- 📋 Next Session: Phase 3 - Component Analysis Nodes

**Session 2 (Date: 2024-07-14)**
- ✅ Completed: Created get_root_codebase_skeleton_tool.py in blarify/agents/tools/
- ✅ Completed: Updated tool exports in blarify/agents/tools/__init__.py and blarify/agents/__init__.py
- ✅ Completed: Complete replacement of workflow.py with DocumentationGeneratorWorkflow
- ✅ Completed: Basic structure for all 10 workflow nodes (load_codebase, detect_framework, generate_overview, create_doc_skeleton, identify_key_components, analyze_component, extract_relationships, generate_component_docs, analyze_cross_component, consolidate_with_skeleton)
- ✅ Completed: Fixed import dependencies and tested workflow compilation
- ✅ Completed: Updated DocumentationState schema to focus on generated_docs output
- 📋 Next Session: Individual node implementation with LLM response validation testing

**Session 3 (Date: 2024-07-18)**
- ✅ Completed: Analyzed current workflow implementation status
- ✅ Completed: Identified that only __load_codebase is fully implemented
- ✅ Completed: Redesigned Phase 3 to focus on individual node implementation and testing
- ✅ Completed: Created LLM response validation testing strategy
- ✅ Completed: Designed strategic framework detection approach using agent tools
- ✅ Completed: Updated implementation plan with framework detection enhancement strategy
- ✅ Completed: Implemented enhanced __detect_framework node with agent tools integration
- ✅ Completed: Integrated custom ReactAgent with configurable LLM providers
- ✅ Completed: Fixed ReactAgent dependencies and custom tool node implementation
- 📋 Next Session: Enhance file tree format for better framework detection context

**Session 4 (Date: 2024-07-18)**
- ✅ Completed: Enhanced database query to retrieve complete file tree (removed maxLevel limitation)
- ✅ Completed: Updated file tree formatting to use FOLDER/FILE labels with node IDs
- ✅ Completed: Updated framework detection prompt to emphasize complete tree analysis
- ✅ Completed: Maintained ReactAgent and tools for selective deeper exploration
- 📋 Next Session: Continue with remaining workflow node implementations

**Session 5 (Date: 2024-07-18)**
- ✅ Completed: Simplified __detect_framework by removing DirectoryExplorerTool
- ✅ Completed: Updated framework detection prompt to focus on file tree + GetCodeByIdTool only
- ✅ Completed: Maintained ReactAgent usage for better tool handling with models like O4
- ✅ Completed: Created test scripts to validate simplified framework detection
- 📋 Next Session: Continue with __generate_overview node implementation and testing

**Session 6 (Date: 2024-07-18)**
- ✅ Completed: Analyzed dual-format documentation requirements based on consumption patterns
- ✅ Completed: Designed InformationNode structure for hierarchical and vector search optimization
- ✅ Completed: Designed comprehensive markdown files for complete context consumption
- ✅ Completed: Updated implementation plan with dual-granularity approach
- ✅ Completed: Enhanced DocumentationState to support both InformationNodes and markdown generation
- ✅ Completed: Updated workflow flow to include markdown generation nodes
- ✅ Completed: Simplified database schema focusing on core properties and agent-determined relationships
- 📋 Next Session: Implement enhanced InformationNode structure and continue with workflow nodes

### Overall Progress
- ✅ Phase 1: Core Infrastructure (4/4 tasks completed)
- ✅ Phase 2: LangGraph Workflow Core (4/4 tasks completed)
- 🔄 Phase 3: Framework-Guided Bottoms-Up Workflow (3/6 nodes completed - __load_codebase, __detect_framework, __analyze_all_leaf_nodes)
- ⏳ Phase 4: Database Integration (0/3 tasks)
- ⏳ Phase 5: Main Integration (0/3 tasks)

**Total Progress: 11/17 tasks completed (updated for new workflow)**

## Technical Specifications

### File Structure

#### New Files Created
```
blarify/db_managers/
└── queries.py              # Database query functions

blarify/documentation/
└── workflow.py              # LangGraph workflow implementation (DocumentationGeneratorWorkflow)

blarify/agents/
├── llm_provider.py          # LLM provider (renamed from agent_caller)
├── prompt_templates.py      # Prompt management system
├── agent_tools.py           # Agent tools infrastructure
└── tools/
    └── get_root_codebase_skeleton_tool.py  # Tool for accessing codebase structure
```

#### New Files to Create
```
blarify/documentation/
└── workflow_nodes.py        # Individual workflow node implementations (for remaining 7 nodes)

blarify/agents/
└── (additional agent tools and utilities in future phases)
```

#### Files to Modify
```
blarify/documentation/
├── post_processor.py        # Integrate LangGraph workflow
├── semantic_analyzer.py     # Complete implementation
└── __init__.py             # Export new classes

blarify/prebuilt/
└── graph_builder.py        # Add semantic processing option

blarify/db_managers/
├── neo4j_manager.py        # Support InformationNode
├── falkordb_manager.py     # Support InformationNode
└── db_manager.py           # Add semantic methods

pyproject.toml              # Add new dependencies
```

### LLM Provider Interface

```python
class LLMProvider(Protocol):
    def analyze(self, prompt: str, context: Dict[str, Any]) -> str:
        """Analyze content using the LLM."""
        pass
    
    def generate_structured(self, prompt: str, schema: Dict) -> Dict:
        """Generate structured output matching schema."""
        pass
```

### Workflow Node Template

```python
def workflow_node(state: DocumentationState) -> Dict[str, Any]:
    """Template for workflow nodes."""
    # 1. Extract required inputs from state
    # 2. Perform node-specific analysis
    # 3. Return dictionary with state updates
    # 4. Handle errors gracefully
    return {"new_field": "value"}
```

### Database Schema Changes

#### Information Node Properties
- `node_id`: Unique identifier
- `title`: Human-readable title
- `content`: Main content text
- `info_type`: Type of information (concept, api, pattern, etc.)
- `source_type`: Source of information (docstring, comment, etc.)
- `source_path`: Original file path
- `examples`: JSON string of code examples
- `framework`: Detected framework (Django, React, etc.)
- `layer`: Always 'documentation'

#### Relationship Types
- `DESCRIBES`: InformationNode → CodeNode
- `RELATED_TO`: InformationNode → InformationNode
- `DEPENDS_ON`: InformationNode → InformationNode
- `EXEMPLIFIES`: InformationNode → CodeNode

## Success Criteria

### Functional Requirements
- [ ] LangGraph workflow successfully analyzes codebases
- [ ] Information nodes are created with proper semantic content
- [ ] Relationships are established between semantic and code layers
- [ ] Database persistence works correctly
- [ ] Integration with existing Blarify workflows

### Performance Requirements
- [ ] Processes medium codebases (1K-10K files) in reasonable time
- [ ] Memory usage remains manageable
- [ ] Database queries are optimized
- [ ] LLM API calls are efficient and cached when possible

### Quality Requirements
- [ ] Generated documentation is accurate and useful
- [ ] Code examples are valid and relevant
- [ ] Relationships are semantically correct
- [ ] System handles errors gracefully

## Dependencies

### External Dependencies
- **langgraph**: Workflow orchestration
- **langchain**: Core LangChain framework
- **langchain-openai**: OpenAI integration
- **langchain-anthropic**: Anthropic integration
- **openai**: OpenAI API integration
- **anthropic**: Anthropic API integration
- **typing-extensions**: Advanced type hints

### Internal Dependencies
- **blarify.graph**: Node and relationship classes
- **blarify.db_managers**: Database persistence
- **blarify.documentation**: Existing documentation extraction

## Risk Mitigation

### Technical Risks
- **LLM API Rate Limits**: Implement exponential backoff and caching
- **Large Codebase Performance**: Add batch processing and streaming
- **Database Performance**: Optimize queries and add indexes
- **Integration Complexity**: Maintain backward compatibility

### Implementation Risks
- **Scope Creep**: Stick to defined phases and success criteria
- **Quality Control**: Add comprehensive testing at each phase
- **Documentation**: Keep implementation docs updated
- **Time Management**: Track progress and adjust scope if needed

## Next Steps

**Priority for next session:**
1. **Phase 3: Individual Node Implementation & Testing** - Create testing framework and implement nodes sequentially
2. **LLM Response Validation** - Focus on quality assessment and semantic correctness
3. **Progressive State Testing** - Validate data flow between nodes
4. **Real Codebase Testing** - Use blarify as baseline for validation

**Longer-term priorities:**
- Phase 4: Database Integration (semantic storage)
- Phase 5: Main Integration (GraphBuilder integration)

## Implementation Notes

### Lessons Learned
- LangChain integration provides better LLM abstraction than direct API calls
- Database query infrastructure crucial for workflow nodes
- Agent tools infrastructure needed early for LangGraph integration
- Prompt templates system essential for consistent LLM interactions

### Architecture Decisions
- Used existing agent_caller (renamed to LLMProvider) instead of LangChain custom implementation
- Implemented abstract query method for database flexibility
- Created comprehensive state management with TypedDict
- Built workflow as sequential nodes with error handling
- Separated agentic logic into dedicated blarify/agents/ module

### Performance Considerations
- Database queries optimized with APOC procedures
- LLM calls include retry logic and error handling
- Codebase skeleton generation uses hierarchical formatting
- Workflow state management keeps memory usage controlled

### Database Query Infrastructure
- `query(cypher_query: str, parameters: dict) -> List[dict]` method added to AbstractDbManager
- Codebase skeleton query implementation with hierarchical formatting
- Helper functions for result formatting and structure generation
- Neo4j and FalkorDB implementations with proper error handling

---

*Last Updated: 2024-07-14*
*Status: Implementation Phase - 15/19 tasks completed*
*Next Session Priority: Phase 5 - Database Integration*