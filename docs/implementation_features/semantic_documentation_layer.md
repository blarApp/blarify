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

### Phase 3: Component Analysis Nodes
**Priority**: Medium | **Estimated Effort**: 4-5 days

#### Tasks
- [ ] **Implement Analysis Nodes**
  - `create_doc_skeleton` - Generate documentation structure
  - `identify_key_components` - Prioritize important components
  - `analyze_component` - Deep dive into individual components
  - `extract_relationships` - Map component interactions

- [ ] **Neo4j Query Integration**
  - Add specialized Cypher queries for component analysis
  - Implement relationship traversal for dependency mapping
  - Add performance optimizations for large codebases

- [ ] **Component Prioritization Logic**
  - Framework-specific component identification
  - Business logic detection algorithms
  - Entry point and critical path analysis

### Phase 4: Documentation Generation
**Priority**: Medium | **Estimated Effort**: 3-4 days

#### Tasks
- [ ] **Final Generation Nodes**
  - `generate_information_nodes` - Create InformationNode objects from analysis
  - `analyze_cross_component` - System-wide pattern analysis
  - `consolidate_semantic_layer` - Final semantic node and relationship creation

- [ ] **Information Node Creation**
  - Convert LLM analysis into InformationNode objects
  - Create relationships between semantic and code nodes
  - Add metadata and tagging for efficient retrieval

- [ ] **Quality Assurance**
  - Add validation for generated content
  - Implement deduplication logic
  - Add content quality scoring

### Phase 5: Database Integration
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

### Phase 6: Main Integration
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
- ✅ Completed: Implemented all 10 workflow nodes (load_codebase, detect_framework, generate_overview, create_doc_skeleton, identify_key_components, analyze_component, extract_relationships, generate_component_docs, analyze_cross_component, consolidate_with_skeleton)
- ✅ Completed: Fixed import dependencies and tested workflow compilation
- ✅ Completed: Updated DocumentationState schema to focus on generated_docs output
- 📋 Next Session: Integration with main GraphBuilder and database persistence

### Overall Progress
- ✅ Phase 1: Core Infrastructure (4/4 tasks completed)
- ✅ Phase 2: LangGraph Workflow Core (4/4 tasks completed)
- ✅ Phase 3: Component Analysis Nodes (4/4 tasks completed)
- ✅ Phase 4: Documentation Generation (3/3 tasks completed)
- [ ] Phase 5: Database Integration (0/3 tasks)
- [ ] Phase 6: Main Integration (0/3 tasks)

**Total Progress: 15/19 tasks completed**

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
1. **Phase 3: Component Analysis Nodes** - Implement `identify_key_components`, `analyze_component`, `extract_relationships`
2. **Complete remaining 7 workflow nodes** - Focus on semantic relationship extraction
3. **Test workflow integration** - Validate with sample codebases
4. **Database schema design** - Plan semantic relationship storage

**Longer-term priorities:**
- Phase 4: Documentation Generation (3 nodes)
- Phase 5: Database Integration (semantic storage)
- Phase 6: Main Integration (GraphBuilder integration)

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