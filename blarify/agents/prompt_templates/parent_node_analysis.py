"""
Prompt template for analyzing parent nodes with enhanced content.

This template is used when processing parent nodes in the recursive DFS traversal.
The skeleton comments in the parent's content have already been replaced with
detailed descriptions of the child elements.
"""

from blarify.agents.prompt_templates.base import PromptTemplate

# Template for analyzing parent nodes with child context embedded
PARENT_NODE_ANALYSIS_TEMPLATE = PromptTemplate(
    name="parent_node_analysis",
    description="Analyzes parent code elements with enhanced content where skeleton comments have been replaced with child descriptions",
    system_prompt="""You are analyzing a parent code element with enhanced content where skeleton comments have been replaced with child descriptions.

Create a substantial summary that:
- Describes what the parent code structure handles/manages
- Summarizes the key functionality provided by its children
- Explains the organizational pattern and structure
- Mentions specific capabilities without repeating full child descriptions
- Uses 3-5 sentences for comprehensive coverage

Start with "This [class/module/package] handles..." or "This [type] manages..." format.

Focus on:
- Primary responsibilities and domain
- Key child components and their roles
- How the structure organizes functionality
- Overall purpose in the codebase architecture

Avoid:
- Verbatim repetition of child descriptions
- Overly generic language
- Implementation minutiae""",
    input_prompt="""Analyze this parent element:

**Name**: {node_name}
**Type**: {node_labels}  
**Path**: {node_path}

**Enhanced Content**:
{node_content}

Provide a substantial description of what this parent element handles, including summaries of its key child functionality and overall architectural purpose.""",
    variables=["node_name", "node_labels", "node_path", "node_content"]
)
