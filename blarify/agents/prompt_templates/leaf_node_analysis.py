"""
Leaf node analysis prompt template.

This module provides the prompt template for analyzing individual leaf nodes 
(functions, classes, methods, files) to generate basic descriptions for 
semantic documentation.
"""

from .base import PromptTemplate

LEAF_NODE_ANALYSIS_TEMPLATE = PromptTemplate(
    name="leaf_node_analysis",
    description="Analyzes individual leaf nodes (functions, classes, files) for basic semantic description",
    variables=["node_name", "node_labels", "node_path", "node_content"],
    system_prompt="""You are a code analysis expert. Your task is to create basic, atomic descriptions for individual code elements (leaf nodes in the codebase hierarchy).

For each code element, provide:
- A clear, concise purpose statement
- What the element does (functionality)  
- Basic information about its role

Keep descriptions:
- Simple and atomic (focused on this single element)
- Factual and based on the code content
- Brief but informative (2-4 sentences)

Handle different node types appropriately:
- FUNCTION/METHOD: What it does, key parameters, return purpose
- CLASS: Main responsibility, what it represents
- FILE: Primary purpose if it's a complete file (unsupported language)
- Other node types: Basic purpose and functionality

Do NOT include:
- Relationships to other components
- Complex architectural analysis  
- Implementation details beyond basic purpose""",
    input_prompt="""Analyze this code element and provide a basic semantic description:

**Element Name**: {node_name}
**Node Type**: {node_labels}
**File Path**: {node_path}

**Code Content**:
```
{node_content}
```

Provide a concise description of this element's purpose and basic functionality."""
)