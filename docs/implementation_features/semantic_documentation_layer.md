# Semantic Documentation Layer Implementation Plan

## Overview

This document serves as a comprehensive implementation plan for adding a semantic documentation layer to Blarify. The semantic layer will create information nodes and relationships that help LLMs retrieve exact context needed for coding tasks, using LangGraph to orchestrate LLM agents that analyze codebases and generate semantic understanding.

## Feature Description

### What is the Semantic Documentation Layer?

The semantic documentation layer is a new component that sits on top of Blarify's existing code graph structure. It analyzes the codebase using LLM agents to create semantic InformationNode objects stored in the database that describe:

- **System Overview**: Business context, purpose, and high-level architecture
- **Component Documentation**: Detailed analysis of key components and their responsibilities  
- **API Documentation**: Function/class usage patterns and examples
- **Relationship Mapping**: Inter-component dependencies and data flow patterns

### How it Works

1. **Input**: Existing code graph with files, classes, functions, and relationships
2. **Process**: LangGraph workflow with LLM agents analyzes the code structure
3. **Output**: InformationNode objects and semantic relationships created in memory
4. **Storage**: InformationNode objects stored in the same graph database as code nodes

### Benefits

- **Precise Context Retrieval**: LLMs can get exactly the right context for coding tasks
- **Semantic Understanding**: Business logic and architecture patterns are captured
- **Efficient Navigation**: Complex codebases become more understandable
- **Agent-Friendly**: Optimized for LLM agent consumption

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
    information_nodes: Annotated[list, add]        # InformationNode objects to create
    semantic_relationships: Annotated[list, add]   # Relationships between nodes
    analyzed_nodes: Annotated[list, add]           # Analyzed code components
    repo_structure: dict                           # Repository structure info
    dependencies: dict                             # Component relationships
    root_codebase_skeleton: str                   # AST tree structure
    detected_framework: dict                       # Framework info (Django, Next.js, etc.)
    system_overview: dict                          # Business context & purpose
    doc_skeleton: dict                             # Documentation template
    key_components: list                           # Priority components to analyze
```

#### Workflow Flow
```
load_codebase → detect_framework → generate_overview → create_doc_skeleton → 
identify_key_components → analyze_component → extract_relationships → 
generate_information_nodes → analyze_cross_component → consolidate_semantic_layer
```

### Database Schema

#### Information Nodes
- **Node Type**: `INFORMATION`
- **Properties**: `title`, `content`, `info_type`, `source_type`, `source_path`, `examples`
- **Labels**: Framework-specific labels (e.g., `DJANGO_COMPONENT`, `REACT_COMPONENT`)

#### Semantic Relationships
- **DESCRIBES**: Information node describes a code node
- **RELATED_TO**: Information nodes are related to each other
- **DEPENDS_ON**: Semantic dependencies between concepts
- **EXEMPLIFIES**: Information node provides examples for code patterns

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

### Phase 3: Individual Workflow Node Implementation & Testing
**Priority**: High | **Estimated Effort**: 6-7 days

#### Overview
Phase 3 focuses on implementing and testing each individual workflow node in the DocumentationWorkflow class. The current workflow.py has placeholder implementations for most nodes. We need to complete each node with proper LLM integration and validate that the LLM responses meet quality standards for semantic documentation generation.

#### Current Node Status Analysis
- ✅ `__load_codebase` - **COMPLETED** - Loads complete codebase file tree with enhanced formatting
- ✅ `__detect_framework` - **COMPLETED** - Simplified to use only GetCodeByIdTool with ReactAgent
- ⚠️ `__generate_overview` - **NEEDS TESTING** - Implemented but requires LLM response validation
- ❌ `__create_doc_skeleton` - **NEEDS IMPLEMENTATION** - Basic structure exists, needs LLM integration
- ❌ `__identify_key_components` - **NEEDS IMPLEMENTATION** - Basic structure exists, needs LLM integration refinement
- ❌ `__analyze_component` - **NEEDS IMPLEMENTATION** - Basic structure exists, needs LLM integration refinement
- ❌ `__extract_relationships` - **NEEDS IMPLEMENTATION** - Basic structure exists, needs LLM integration refinement
- ❌ `__generate_component_docs` - **NEEDS IMPLEMENTATION** - Basic structure exists, needs LLM integration refinement
- ❌ `__analyze_cross_component` - **NEEDS IMPLEMENTATION** - Basic structure exists, needs LLM integration refinement
- ❌ `__consolidate_with_skeleton` - **NEEDS IMPLEMENTATION** - Basic structure exists, needs LLM integration refinement

#### Framework Detection Simplification (COMPLETED)

The `__detect_framework` node has been simplified based on user feedback about tool usage with certain models:

**Final Implementation:**
1. **Complete File Tree Analysis**: Receives full codebase structure from `__load_codebase`
2. **Single Tool Usage**: Uses only `GetCodeByIdTool` to read configuration files
3. **ReactAgent Architecture**: Continues using ReactAgent for better tool handling
4. **Focused Analysis**: LLM analyzes tree structure and reads config files to determine stack

**Key Benefits:**
- Simplified tool usage improves compatibility with models like O4
- Complete file tree eliminates need for directory exploration
- Config file reading provides concrete framework confirmation
- ReactAgent handles tool execution more reliably than direct binding

#### Implementation Tasks

##### Task 1: Create LLM Response Validation Testing Framework
- [ ] **Add test_node method to DocumentationWorkflow class**
  - Enable individual node testing with custom state
  - Add debugging and logging for LLM interactions
  - Create state validation helpers

- [ ] **Implement Progressive State Validation**
  - Test each node with realistic state progression
  - Validate LLM responses contain expected semantic content
  - Create quality assessment metrics for each node type

- [ ] **Create Real Codebase Testing Setup**
  - Use blarify codebase as known test case
  - Define expected outcomes for each node
  - Validate LLM responses against known characteristics

##### Task 2: Complete Node Implementations with Testing
- [ ] **Enhance and Test `__detect_framework` with Strategic Analysis**
  - **Strategic Analysis Approach**: Efficient codebase reconnaissance to guide next steps
  - **Implementation Strategy**:
    1. Analyze root structure from `__load_codebase` for initial framework clues
    2. Use `DirectoryExplorerTool` to explore 2-3 key directories (src/, app/, components/)
    3. Use `GetCodeByIdTool` to read 2-3 strategic files (config files + key source files)
    4. Provide strategic framework information to guide `__generate_overview`
  - **Expected Output**: Clear text response covering:
    - Primary language and framework
    - Project type (frontend/backend/fullstack/library)
    - Key directories for deeper analysis
    - Architecture style hints
    - Important files for next analysis step
  - **Implementation Details**: 
    - Initialize agent tools in `__detect_framework` method
    - Use tools programmatically to gather strategic information
    - Pass collected information to LLM provider for analysis
    - Update framework detection prompt to guide strategic analysis
  - **Testing**: Validate with multiple codebase types and ensure strategic information quality

- [ ] **Refine and Test `__generate_overview`**
  - Validate LLM generates business context understanding
  - Test system overview includes purpose and domain
  - Ensure response is structured and comprehensive

- [ ] **Implement and Test `__create_doc_skeleton`**
  - Create documentation structure based on detected framework
  - Generate section templates appropriate for project type
  - Validate skeleton is logical and well-organized

- [ ] **Implement and Test `__identify_key_components`**
  - Use LLM to analyze codebase and identify critical components
  - Prioritize components based on importance and usage
  - Validate component identification is accurate and complete

##### Task 3: Advanced Analysis Node Implementation
- [ ] **Implement and Test `__analyze_component`**
  - Deep semantic analysis of individual components
  - Extract component purpose, responsibilities, and usage patterns
  - Generate detailed component documentation

- [ ] **Implement and Test `__extract_relationships`**
  - Map relationships and dependencies between components
  - Create semantic relationship graph
  - Validate relationship extraction is accurate

- [ ] **Implement and Test `__generate_component_docs`**
  - Transform component analysis into structured documentation
  - Create examples and usage patterns
  - Generate API documentation for key components

##### Task 4: Final Integration and Consolidation
- [ ] **Implement and Test `__analyze_cross_component`**
  - Analyze system-wide patterns and interactions
  - Identify architectural patterns and design principles
  - Create high-level system understanding

- [ ] **Implement and Test `__consolidate_with_skeleton`**
  - Merge all generated documentation into final structure
  - Ensure consistency and completeness
  - Create final semantic documentation layer

#### Testing Strategy

##### LLM Response Quality Validation
```python
def assess_llm_output_quality(node_name: str, result: dict):
    """Quality checks for each node type"""
    quality_checks = {
        "detect_framework": [
            lambda r: "framework" in str(r).lower(),
            lambda r: any(fw in str(r).lower() for fw in ["django", "react", "next", "flask", "vue", "python"])
        ],
        "generate_overview": [
            lambda r: "business" in str(r).lower() or "purpose" in str(r).lower(),
            lambda r: len(str(r)) > 100,  # Substantial content
            lambda r: "overview" in str(r).lower() or "system" in str(r).lower()
        ],
        "identify_key_components": [
            lambda r: isinstance(r.get("key_components"), list),
            lambda r: len(r.get("key_components", [])) > 0,
            lambda r: all("path" in str(comp) for comp in r.get("key_components", []))
        ]
    }
```

##### Progressive State Testing
- Test nodes sequentially with realistic state progression
- Validate each node's contribution to overall workflow
- Ensure state consistency and data flow between nodes

##### Real Codebase Validation
- Test with blarify codebase as known baseline
- Validate expected outcomes for each node
- Ensure LLM responses are semantically correct

#### Success Criteria
- [ ] All 10 workflow nodes implemented and tested
- [ ] LLM responses pass quality validation checks
- [ ] Progressive state testing shows proper data flow
- [ ] Real codebase testing produces expected semantic documentation
- [ ] Error handling and recovery mechanisms in place
- [ ] Performance acceptable for medium-sized codebases

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

### Overall Progress
- ✅ Phase 1: Core Infrastructure (4/4 tasks completed)
- ✅ Phase 2: LangGraph Workflow Core (4/4 tasks completed)
- 🔄 Phase 3: Individual Node Implementation & Testing (2/10 nodes completed - __load_codebase and __detect_framework)
- ⏳ Phase 4: Database Integration (0/3 tasks)
- ⏳ Phase 5: Main Integration (0/3 tasks)

**Total Progress: 10/20 tasks completed (revised count)**

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