"""
Recursive DFS fallback prompt templates.

This module provides prompt templates for handling circular dependencies and deadlock
scenarios in the RecursiveDFSProcessor when processing code hierarchies with circular
references at any distance.
"""

from .base import PromptTemplate

PARENT_NODE_PARTIAL_CONTEXT_TEMPLATE = PromptTemplate(
    name="parent_node_partial_context",
    description="Analyzes parent nodes with only partially available child context due to circular dependencies",
    variables=["node_name", "node_labels", "node_path", "node_content", "child_descriptions", "fallback_note"],
    system_prompt="""You are a code analysis expert. Create descriptions for parent code elements 
that have circular dependencies, using only the available partial context from child elements.

Requirements:
- Focus on the parent element's structure and purpose
- Acknowledge incomplete child context without dwelling on it
- Extract maximum information from available children
- Maintain clarity despite missing information
- Use active voice and specific language

Response format: Clear description emphasizing what can be determined from available context.

Important: Some child elements may be missing due to circular dependencies in the codebase.
Work with the partial information available to provide the best possible analysis.""",
    input_prompt="""Analyze this parent code element with partial child context:

**Element**: {node_name}
**Type**: {node_labels}
**Path**: {node_path}

**Available Child Descriptions**:
{child_descriptions}

**Code**:
```
{node_content}
```

{fallback_note}

Provide a comprehensive description based on the available context."""
)

ENHANCED_LEAF_FALLBACK_TEMPLATE = PromptTemplate(
    name="enhanced_leaf_fallback",
    description="Analyzes nodes as enhanced leaf elements when child context is unavailable due to circular dependencies",
    variables=["node_name", "node_labels", "node_path", "node_content", "fallback_note"],
    system_prompt="""You are analyzing a code element that may have dependencies or call other functions, 
but detailed context about those dependencies is not available due to circular references.

Focus on what you can determine from the code itself:
- The element's primary purpose and responsibility
- Its structure and interface
- Observable patterns and behaviors
- Direct functionality visible in the code
- Input/output relationships if apparent

Do not speculate about missing dependency details. Work with what is directly observable.""",
    input_prompt="""Analyze the following code element:

**Name**: {node_name}
**Type**: {node_labels}
**Path**: {node_path}

**Content**:
```
{node_content}
```

{fallback_note}

Provide a description focusing on the element's purpose, structure, and any 
observable patterns, even without complete dependency information."""
)

CIRCULAR_DEPENDENCY_DETECTION_TEMPLATE = PromptTemplate(
    name="circular_dependency_detection",
    description="Documents detected circular dependencies for debugging and analysis",
    variables=["cycle_nodes", "cycle_paths", "affected_modules"],
    system_prompt="""You are documenting circular dependencies detected in a codebase.

Create a clear summary that:
- Identifies the circular dependency chain
- Explains the relationships between components
- Notes potential impacts on code analysis
- Suggests possible refactoring approaches if apparent

Be factual and technical. This documentation helps developers understand and resolve circular dependencies.""",
    input_prompt="""Document the following circular dependency:

**Cycle Components**:
{cycle_nodes}

**File Paths Involved**:
{cycle_paths}

**Affected Modules**:
{affected_modules}

Provide a technical summary of this circular dependency pattern."""
)

DEADLOCK_RECOVERY_TEMPLATE = PromptTemplate(
    name="deadlock_recovery",
    description="Documents code elements processed through deadlock recovery mechanisms",
    variables=["node_name", "node_type", "recovery_reason", "partial_context", "node_content"],
    system_prompt="""You are analyzing a code element that was processed through a deadlock recovery mechanism
due to complex circular dependencies in the codebase.

Create a description that:
- Focuses on the element's core functionality
- Uses any available partial context effectively
- Maintains accuracy despite incomplete information
- Documents what can be reliably determined

This is a recovery scenario - provide the best analysis possible with limited context.""",
    input_prompt="""Analyze this code element (processed via deadlock recovery):

**Element**: {node_name}
**Type**: {node_type}
**Recovery Reason**: {recovery_reason}

**Available Partial Context**:
{partial_context}

**Code**:
```
{node_content}
```

Generate a description focusing on observable functionality and structure."""
)