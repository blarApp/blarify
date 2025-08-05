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

The semantic documentation layer follows a three-workflow architecture with clear separation of concerns:

```
blarify/
├── agents/                           # Agent-related functionality
│   ├── llm_provider.py              # LLM provider implementations
│   ├── prompt_templates/            # Prompt management system
│   │   ├── workflow_discovery.py   # Workflow discovery prompts
│   │   └── parent_node_analysis.py # Parent node analysis prompts
│   ├── schemas/                     # Pydantic schemas for structured output
│   │   └── workflow_discovery_schema.py
│   └── tools/                       # Agent tools infrastructure
├── documentation/                   # Documentation processing workflows
│   ├── workflow.py                 # Main orchestration workflow
│   ├── folder_processing_workflow.py  # Individual folder processing
│   ├── workflow_analysis_workflow.py  # Workflow discovery and analysis
│   ├── main_documentation_workflow.py # Final documentation generation
│   └── utils/                      # Utility classes
│       └── recursive_dfs_processor.py # Recursive DFS processing
└── db_managers/                    # Database operations
    ├── queries.py                  # Specialized queries for semantic analysis
    └── dtos/                       # Data transfer objects
        └── node_with_content_dto.py
```

### Current State Analysis

#### ✅ Already Implemented
- `InformationNode` class for semantic documentation storage
- `DocumentationExtractor` for raw documentation extraction
- `DocumentationPostProcessor` skeleton with orchestration structure
- `SemanticDocumentationAnalyzer` interface definition
- Database abstraction layer supporting custom node types

#### ✅ Three-Workflow Architecture Completed
- ✅ **FolderProcessingWorkflow**: Complete recursive DFS processing with RecursiveDFSProcessor
- ✅ **WorkflowAnalysisWorkflow**: Workflow discovery implemented, workflow processing (stub)
- ✅ **MainDocumentationWorkflow**: Documentation generation nodes (stubs for future implementation)
- ✅ **Main DocumentationWorkflow**: Orchestration with normalized node names (5/5 nodes completed)

#### ❌ Remaining Components for Full Implementation
- ❌ Workflow processing implementation in WorkflowAnalysisWorkflow
- ❌ Documentation generation implementation in MainDocumentationWorkflow
- ❌ Database schema for semantic relationships
- ❌ Integration with main GraphBuilder flow

#### ✅ Recently Completed (Three-Workflow Architecture)
- ✅ Complete three-workflow architecture implementation with independent LangGraph workflows
- ✅ Recursive DFS processing with RecursiveDFSProcessor and skeleton comment replacement
- ✅ Workflow discovery with framework-guided analysis using structured output
- ✅ Main workflow orchestration with normalized node names for better UX
- ✅ FolderProcessingWorkflow, WorkflowAnalysisWorkflow, and MainDocumentationWorkflow classes
- ✅ Utility module organization with recursive_dfs_processor moved to utils/
- ✅ Enhanced prompt templates (workflow_discovery.py, parent_node_analysis.py)
- ✅ Pydantic schemas for structured LLM output (WorkflowDiscoveryResponse)

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

#### Workflow Flow (Updated with Three-Workflow Architecture)
```
// Main orchestration workflow (normalized node names):
load_codebase → 
detect_framework (OUTPUTS: framework + main_folders) →
create_descriptions (per-folder processing) → 
get_workflows (orchestrates WorkflowAnalysisWorkflow) →
construct_general_documentation (orchestrates MainDocumentationWorkflow)

// Three independent LangGraph workflows:
1. FolderProcessingWorkflow: Recursive DFS processing of individual folders
2. WorkflowAnalysisWorkflow: discover_workflows → process_workflows
3. MainDocumentationWorkflow: group_related_knowledge → compact_to_markdown_per_folder → consolidate_final_markdown
```

**Sequential Processing Logic with Three-Workflow Architecture:**
1. **Load Codebase**: Extract complete codebase structure from graph database
2. **Framework Detection**: Single LLM call identifies framework and main architectural folders using structured output
3. **Create Descriptions**: For each main folder, run dedicated FolderProcessingWorkflow:
   - Filter and analyze leaf nodes specific to that folder using RecursiveDFSProcessor
   - Build hierarchical understanding from bottom up with skeleton comment replacement
   - Create folder-specific InformationNodes and save to database
4. **Get Workflows**: Orchestrate WorkflowAnalysisWorkflow to discover and analyze business workflows:
   - Discover workflows by analyzing all InformationNodes using framework context
   - Process each discovered workflow (stub implementation)
   - Return workflow analysis results and relationships
5. **Construct General Documentation**: Orchestrate MainDocumentationWorkflow for final documentation:
   - Group related knowledge within folder hierarchies
   - Generate markdown sections for each main folder including workflow documentation
   - Consolidate all folder-based and workflow markdown into comprehensive documentation

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

#### Workflow Relationships (Added by Workflow Analysis Layer)
- **PARTICIPATES_IN**: InformationNode → WorkflowNode (component participates in business workflow)
- **WORKFLOW_STEP**: InformationNode → InformationNode (execution flow between components with step_order)
- **TRIGGERS_ASYNC**: InformationNode → InformationNode (async operation triggering)
- **COLLABORATES_WITH**: InformationNode → InformationNode (components working together in workflow)

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
- ✅ ~~`__analyze_all_leaf_nodes`~~ - **REMOVED** - Replaced with recursive DFS processing for true hierarchical analysis
- ✅ ~~`__identify_main_folders_by_framework`~~ - **REMOVED** - Consolidated into `__detect_framework` for efficiency
- ✅ `__iterate_directory_hierarchy_bottoms_up` - **COMPLETED** - Implemented using RecursiveDFSProcessor for true single-branch DFS traversal
- ❌ `__discover_workflows` - **NEEDS IMPLEMENTATION** - Analyze InformationNodes to identify business workflows using framework context
- ❌ `__process_workflows` - **NEEDS IMPLEMENTATION** - Process each workflow using dedicated WorkflowAnalysisWorkflow  
- ❌ `__compact_to_markdown_per_folder` - **NEEDS IMPLEMENTATION** - Generate markdown sections for each main folder including workflow documentation
- ❌ `__consolidate_final_markdown` - **NEEDS IMPLEMENTATION** - Combine all folder-based and workflow markdown into comprehensive documentation

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

#### Recursive DFS Processing Architecture (COMPLETED)

The workflow has been completely restructured to use true recursive depth-first search (DFS) processing instead of complex LangGraph workflows. This provides natural hierarchical analysis with skeleton replacement.

**Key Changes:**
- **Removed FolderAnalysisWorkflow**: Replaced complex LangGraph workflow with simple recursive function
- **RecursiveDFSProcessor**: New dedicated class in `recursive_dfs_processor.py` for true DFS traversal
- **Single-Branch Processing**: Each folder processed one complete branch at a time
- **Skeleton Comment Replacement**: Parent nodes get enhanced content with child descriptions replacing skeleton comments

**RecursiveDFSProcessor Architecture:**
```python
class RecursiveDFSProcessor:
    def __init__(self, db_manager, agent_caller, company_id, repo_id): ...
    def process_folder(self, folder_path) -> ProcessingResult: ...
    def _process_node_recursive(self, node) -> InformationNodeDescription: ...
    def _process_leaf_node(self, node) -> InformationNodeDescription: ...
    def _process_parent_node(self, node, child_descriptions) -> InformationNodeDescription: ...
    def _replace_skeleton_comments_with_descriptions(self, content, children) -> str: ...

# Processing Flow:
1. process_folder() - Entry point for folder processing
2. _process_node_recursive() - Core recursive DFS method
3. _process_leaf_node() - Uses dumb agent for leaf analysis (same as before)
4. _process_parent_node() - NEW: Analyzes parent with enhanced content
5. _replace_skeleton_comments_with_descriptions() - NEW: Skeleton replacement
```

**Benefits:**
- **True DFS**: Processes one complete branch (leaf → parent → grandparent) before moving to siblings
- **Natural Hierarchy**: Recursion matches the tree structure perfectly
- **Enhanced Context**: Parent nodes get rich context with child descriptions embedded in their content
- **Memory Efficient**: Only holds current recursion stack, not entire tree
- **Simple Architecture**: No complex LangGraph state management, just recursive functions
- **Skeleton Replacement**: Replaces `# Code replaced for brevity, see node: xxx` with actual descriptions

#### Recursive Node Analysis Implementation (COMPLETED)

The analysis has been completely restructured to use recursive DFS processing where each node is analyzed with full hierarchical context:

**Recursive Processing Logic:**
- **DFS Traversal**: Uses `_process_node_recursive()` to traverse the tree depth-first
- **Leaf-First Processing**: Processes all children before processing parent
- **Context Propagation**: Each parent gets enhanced content with child descriptions
- **Node Caching**: Processed nodes cached to avoid reprocessing in different branches

**Database Infrastructure:**
- **NodeWithContentDto**: Enhanced Pydantic model with full node content for recursive processing
- **Query Functions**: `get_folder_node_by_path()`, `get_direct_children()` with proper path normalization
- **Path Normalization**: Strips trailing slashes to handle framework detection output correctly

**Processing Methods:**
1. **Leaf Node Processing** (`_process_leaf_node`):
   - Uses existing `LEAF_NODE_ANALYSIS_TEMPLATE`
   - Calls `call_dumb_agent()` for atomic analysis
   - Creates `InformationNodeDescription` Pydantic model

2. **Parent Node Processing** (`_process_parent_node`):
   - Uses new `PARENT_NODE_ANALYSIS_TEMPLATE`
   - Calls `_replace_skeleton_comments_with_descriptions()` first
   - Processes enhanced content with child context embedded
   - Creates `InformationNodeDescription` with child count and enhanced content

**Skeleton Comment Replacement Logic:**
```python
def _replace_skeleton_comments_with_descriptions(self, content, child_descriptions):
    # Pattern: # Code replaced for brevity, see node: <node_id>
    skeleton_pattern = r'# Code replaced for brevity, see node: ([a-f0-9]+)'
    
    # Replace with formatted docstrings containing LLM descriptions
    # Maintains proper indentation and formatting
```

**Output Structure (Enhanced):**
```python
InformationNodeDescription = {
    "node_id": f"info_{node.id}",
    "title": f"Description of {node.name}",
    "content": response_content,  # LLM-generated description
    "info_type": "leaf_description" | "parent_description",
    "source_node_id": node.id,
    "source_path": node.path,
    "source_labels": node.labels,
    "source_type": "recursive_leaf_analysis" | "recursive_parent_analysis",
    "enhanced_content": enhanced_content,  # Only for parents
    "children_count": len(child_descriptions),  # Only for parents
    "layer": "documentation"
}
```

**Prompt Templates:**
- **LEAF_NODE_ANALYSIS_TEMPLATE**: Unchanged, focused on atomic functionality
- **PARENT_NODE_ANALYSIS_TEMPLATE**: NEW template for analyzing parents with enhanced content
- **Enhanced Context**: Parent template works with skeleton-replaced content

#### Implementation Tasks

##### Task 1: Recursive DFS Architecture ✅ COMPLETED
- [x] **Implement RecursiveDFSProcessor** ✅ COMPLETED
  - ✅ Created `RecursiveDFSProcessor` class with full recursive implementation
  - ✅ Implemented `NodeWithContentDto` for type-safe database queries
  - ✅ Added `get_folder_node_by_path()` and `get_direct_children()` database functions
  - ✅ Integrated with LLM provider using `call_dumb_agent` for leaf and parent processing
  - ✅ Implemented skeleton comment replacement with proper formatting
  - ✅ Created `InformationNodeDescription` Pydantic model for results

- [x] **Enhanced `__detect_framework` with Main Folder Identification** ✅ COMPLETED
  - ✅ Created FrameworkAnalysisResponse Pydantic schema for structured output
  - ✅ Enhanced framework detection prompt to include main folder identification
  - ✅ Updated `__detect_framework` to use structured output with ReactAgent
  - ✅ Consolidated framework detection and main folder identification into single LLM call
  - ✅ Removed separate `__identify_main_folders_by_framework` node for efficiency
  - ✅ Updated workflow edges to reflect consolidated approach

- [x] **Implement `__iterate_directory_hierarchy_bottoms_up` with Recursive Processing** ✅ COMPLETED
  - ✅ Replaced FolderAnalysisWorkflow with RecursiveDFSProcessor integration
  - ✅ Updated workflow node to create and use RecursiveDFSProcessor for each main folder
  - ✅ Implemented proper error handling and result conversion from Pydantic to dict
  - ✅ Added logging and progress tracking for recursive processing
  - ✅ Fixed folder path normalization to handle trailing slashes from framework detection

- [x] **Create PARENT_NODE_ANALYSIS_TEMPLATE** ✅ COMPLETED
  - ✅ Created parent node analysis prompt template with proper PromptTemplate initialization
  - ✅ Added template to prompt templates exports
  - ✅ Designed prompt to work with skeleton-replaced enhanced content
  - ✅ Added proper name, description, and variables parameters

- [x] **Fix Database Query Issues** ✅ COMPLETED
  - ✅ Fixed Neo4j syntax error: changed `length(n.path)` to `size(n.path)`
  - ✅ Added path normalization in `get_folder_node_by_path()` to strip trailing slashes
  - ✅ Ensured proper folder node matching instead of child node matching

##### Task 2: Workflow Analysis Layer Implementation ✅ ARCHITECTURE COMPLETED
- [x] **Implement `__discover_workflows`** ✅ COMPLETED
  - ✅ Transferred to WorkflowAnalysisWorkflow._discover_workflows method
  - ✅ Analyzes all InformationNodes to identify business workflow patterns
  - ✅ Uses framework context and folder structure to guide discovery
  - ✅ Generates list of workflows with entry points and scope definitions
  - ✅ Integrated workflow discovery prompts and LLM with structured output

- [ ] **Implement `__process_workflows`** ✅ STUB COMPLETED
  - ✅ Transferred to WorkflowAnalysisWorkflow._process_workflows method (NotImplementedError stub)
  - ❌ Loop through discovered workflows (future implementation)
  - ❌ Create detailed workflow analysis for each workflow (future implementation)
  - ❌ Collect and aggregate workflow analysis results (future implementation)
  - ❌ Update state with workflow InformationNodes and relationships (future implementation)

- [x] **Create WorkflowAnalysisWorkflow Class** ✅ COMPLETED
  - ✅ Follows FolderProcessingWorkflow architectural pattern
  - ✅ Implemented WorkflowAnalysisState TypedDict
  - ✅ Created dedicated workflow for individual workflow processing
  - ✅ Added LangSmith tracking for workflow analysis visibility
  - ✅ Independent run() method for standalone execution

##### Task 3: Markdown Generation and Final Consolidation ✅ ARCHITECTURE COMPLETED
- [ ] **Implement `__compact_to_markdown_per_folder`** ✅ STUB COMPLETED
  - ✅ Transferred to MainDocumentationWorkflow._compact_to_markdown_per_folder method (NotImplementedError stub)
  - ❌ Generate comprehensive markdown sections for each main folder (future implementation)
  - ❌ Include workflow documentation alongside component documentation (future implementation)
  - ❌ Create narrative documentation with code references (file_path:line_number) (future implementation)
  - ❌ Ensure self-contained stories with integrated explanations (future implementation)
  - ❌ Size appropriately for LLM context windows (3000-8000 tokens per section) (future implementation)

- [ ] **Implement `__consolidate_final_markdown`** ✅ STUB COMPLETED
  - ✅ Transferred to MainDocumentationWorkflow._consolidate_final_markdown method (NotImplementedError stub)
  - ❌ Combine all folder-based and workflow markdown into comprehensive documentation files (future implementation)
  - ❌ Create logical groupings and cross-references between sections (future implementation)
  - ❌ Generate final markdown files for filesystem storage with workflow traces (future implementation)
  - ❌ Ensure complete coverage and consistency across all folders and workflows (future implementation)

- [x] **Create MainDocumentationWorkflow Class** ✅ COMPLETED
  - ✅ Follows three-workflow architectural pattern
  - ✅ Implemented MainDocumentationState TypedDict
  - ✅ Created dedicated workflow for final documentation generation
  - ✅ Added LangSmith tracking for documentation generation visibility
  - ✅ Independent run() method for standalone execution

#### Implementation Approach
The implementation will follow a straightforward approach:
1. Focus on completing each node's core functionality
2. Use existing prompt templates and LLM provider infrastructure
3. Implement robust error handling and logging
4. Ensure proper state management between nodes
5. Skip complex testing frameworks in favor of direct implementation

#### Success Criteria
- [x] ✅ All workflow architecture completed with three independent LangGraph workflows
- [x] ✅ WorkflowAnalysisWorkflow following FolderProcessingWorkflow architectural patterns
- [x] ✅ Main workflow orchestration with normalized node names (get_workflows, construct_general_documentation)
- [x] ✅ Independent workflow execution for testing and modularity
- [x] ✅ Proper error handling and recovery mechanisms in place
- [x] ✅ State management working correctly between workflows
- [x] ✅ LLM integration functioning for workflow discovery with structured output
- [ ] ❌ Workflow processing implementation (future work)
- [ ] ❌ Documentation generation implementation (future work)
- [ ] ❌ Workflow InformationNodes created with proper graph relationships (future work)

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

**Session 7 (Date: 2025-07-22)**
- ✅ Completed: Complete recursive DFS architecture implementation with RecursiveDFSProcessor
- ✅ Completed: Skeleton comment replacement system for enhanced parent content
- ✅ Completed: NodeWithContentDto and database query infrastructure for recursive processing
- ✅ Completed: PARENT_NODE_ANALYSIS_TEMPLATE with proper PromptTemplate initialization
- ✅ Completed: Integration of RecursiveDFSProcessor into main workflow replacing FolderAnalysisWorkflow
- ✅ Completed: Fixed Neo4j syntax errors (length → size) and path normalization issues
- ✅ Completed: Documentation updates to reflect all architectural changes
- 📋 Next Session: Implement remaining workflow nodes for knowledge grouping and markdown generation

**Session 8 (Date: 2025-07-23)**
- ✅ Completed: Redesigned workflow architecture to include dedicated workflow analysis layer
- ✅ Completed: Created workflow_analysis_layer.md implementation plan
- ✅ Completed: Updated main workflow flow to include discover_workflows and process_workflows nodes
- ✅ Completed: Designed WorkflowAnalysisWorkflow following FolderProcessingWorkflow pattern
- ✅ Completed: Updated database schema to use graph relationships instead of JSON arrays for workflow traces
- ✅ Completed: Updated task structure to reflect new workflow-focused approach
- 📋 Next Session: Implement discover_workflows node and WorkflowAnalysisWorkflow class

**Session 9 (Date: 2025-07-24)**
- ✅ Completed: Complete three-workflow architecture implementation
- ✅ Completed: WorkflowAnalysisWorkflow class with workflow discovery implementation
- ✅ Completed: MainDocumentationWorkflow class with documentation generation stubs
- ✅ Completed: Main workflow orchestration with normalized node names
- ✅ Completed: Independent workflow execution capabilities for testing
- ✅ Completed: File organization with utils/ folder for shared utilities
- ✅ Completed: Enhanced prompt templates and Pydantic schemas for structured output
- ✅ Completed: Updated documentation to reflect three-workflow architecture
- 📋 Next Session: Implement workflow processing and documentation generation functionality

### Overall Progress
- ✅ Phase 1: Core Infrastructure (4/4 tasks completed)
- ✅ Phase 2: LangGraph Workflow Core (4/4 tasks completed)
- ✅ Phase 3: Three-Workflow Architecture (5/5 main workflow nodes completed with orchestration)
- ✅ Phase 3: FolderProcessingWorkflow (Complete recursive DFS implementation)
- ✅ Phase 3: WorkflowAnalysisWorkflow (Architecture completed, workflow discovery implemented)
- ✅ Phase 3: MainDocumentationWorkflow (Architecture completed, documentation generation stubs)
- ⏳ Phase 4: Database Integration (0/3 tasks)
- ⏳ Phase 5: Main Integration (0/3 tasks)

**Total Progress: 19/22 tasks completed (three-workflow architecture fully implemented)**

## Technical Specifications

### File Structure

#### New Files Created (Three-Workflow Architecture)
```
blarify/db_managers/
├── queries.py              # Database query functions with recursive DFS support
└── dtos/
    ├── leaf_node_dto.py        # DTO for leaf nodes (existing)
    └── node_with_content_dto.py  # DTO for nodes with full content for recursive processing

blarify/documentation/
├── workflow.py              # Main orchestration workflow (DocumentationWorkflow)
├── folder_processing_workflow.py  # Individual folder processing workflow
├── workflow_analysis_workflow.py  # Workflow discovery and analysis workflow
├── main_documentation_workflow.py # Final documentation generation workflow
└── utils/
    └── recursive_dfs_processor.py  # Complete recursive DFS processor with skeleton replacement

blarify/agents/
├── llm_provider.py          # LLM provider (renamed from agent_caller)
├── prompt_templates/
│   ├── base.py              # Base PromptTemplate dataclass
│   ├── framework_detection.py  # Framework detection template
│   ├── leaf_node_analysis.py   # Leaf node analysis template (existing)
│   ├── parent_node_analysis.py  # Parent node analysis template
│   └── workflow_discovery.py   # Workflow discovery template
├── schemas/
│   └── workflow_discovery_schema.py  # Pydantic schemas for workflow discovery
└── tools/
    └── get_root_codebase_skeleton_tool.py  # Tool for accessing codebase structure
```

#### Future Implementation Files (Next Phase)
```
blarify/agents/
├── prompt_templates/
│   ├── workflow_tracing.py         # Workflow component tracing template
│   ├── async_mapping.py            # Async operation mapping template
│   ├── knowledge_grouping.py       # Knowledge grouping template
│   └── markdown_generation.py      # Markdown generation template
└── tools/
    └── workflow_exploration_tools.py  # Tools for exploring workflow relationships
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

*Last Updated: 2025-07-24*
*Status: Three-Workflow Architecture Complete - 19/22 tasks completed*
*Next Session Priority: Implement workflow processing and documentation generation functionality*

## Related Documents

- **[Workflow Analysis Layer](./workflow_analysis_layer.md)**: Detailed implementation plan for the workflow analysis extension