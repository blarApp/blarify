"""
Prompt template for analyzing functions with call stack context.

This template is used when processing functions in the call stack navigation mode.
The function has outgoing CALLS and USES relationships, and the descriptions of
the called/used functions are provided as context.
"""

from blarify.agents.prompt_templates.base import PromptTemplate

# Template for analyzing functions with call context
FUNCTION_WITH_CALLS_ANALYSIS_TEMPLATE = PromptTemplate(
    name="function_with_calls_analysis",
    description="Analyzes functions with context from the functions they call and dependencies they use",
    system_prompt="""You are analyzing a function with context from the functions it calls and dependencies it uses.

Create a comprehensive description that:
- Explains the function's primary purpose and responsibility
- Describes how it orchestrates its child function calls
- Mentions the specific functions it calls and their roles
- Explains the overall execution flow and logic
- Notes any dependencies it uses and their purpose
- Uses 4-6 sentences for comprehensive coverage

Start with "This function..." format.

Focus on:
- Main purpose and what problem it solves
- How it coordinates called functions to achieve its goal
- The execution flow and control logic
- Key dependencies and their roles
- Its place in the larger call stack architecture

Include context about:
- Which functions are called and when
- How the results of called functions are used
- The logical flow between different calls
- Any error handling or control flow patterns

Avoid:
- Simply listing called functions without context
- Repeating the exact content of child descriptions
- Implementation details like variable names
- Code syntax specifics""",
    input_prompt="""Analyze this function with call context:

**Function**: {node_name}
**Type**: {node_labels}  
**Path**: {node_path}
**Location**: Lines {start_line}-{end_line}

**Function Code**:
{node_content}

**Called Functions & Dependencies**:
{child_calls_context}

Provide a comprehensive description of what this function does, how it orchestrates its calls, and its role in the execution flow.""",
    variables=["node_name", "node_labels", "node_path", "start_line", "end_line", "node_content", "child_calls_context"]
)