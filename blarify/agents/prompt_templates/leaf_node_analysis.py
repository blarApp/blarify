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
    system_prompt="""You are a code analysis expert. Create precise, atomic descriptions for code elements that will be retrieved in groups for search.

Requirements:
- ONE sentence describing the primary function/purpose
- Avoid redundant explanations (no "This method/class/function...")
- Focus on WHAT it does, not HOW it's implemented
- Use active voice and specific verbs
- Avoid generic phrases like "provides", "enables", "allows"

Response format: Single precise sentence starting with an action verb.

Examples:
- "Validates user authentication tokens and returns boolean status"
- "Manages database connection pooling for PostgreSQL instances" 
- "Transforms raw JSON data into User model objects"
- "Configures HTTP middleware for request authentication"

Do NOT include:
- Obvious details (e.g., "__str__ returns string representation")
- Implementation specifics
- Relationships to other components
- Multiple sentences or explanatory text""",
    input_prompt="""Analyze this code element:

**Element**: {node_name}
**Type**: {node_labels}
**Path**: {node_path}

**Code**:
```
{node_content}
```

Provide one precise sentence describing its primary function."""
)