"""
Prompt template for analyzing functions that participate in call cycles.

This template is used when processing functions that are part of recursive or
mutually recursive call patterns. The function has call relationships that
form cycles in the call graph.
"""

from blarify.agents.prompt_templates.base import PromptTemplate

# Template for analyzing functions involved in call cycles
FUNCTION_WITH_CYCLE_ANALYSIS_TEMPLATE = PromptTemplate(
    name="function_with_cycle_analysis",
    description="Analyzes functions that participate in recursive or mutually recursive call patterns",
    system_prompt="""You are analyzing a function that participates in a recursive or mutually recursive call pattern.

Create a comprehensive description that:
- Explains the function's primary purpose and responsibility
- Identifies that this function is part of a recursive/cyclic call pattern
- Describes the recursive behavior and termination conditions
- Notes the other functions involved in the cycle (if mutually recursive)
- Explains the role this function plays in the recursive algorithm
- Uses 4-6 sentences for comprehensive coverage

Start with "This function..." format.

Focus on:
- Main purpose and what recursive problem it solves  
- How the recursive pattern works (base case, recursive case)
- Termination conditions and cycle breaking logic
- Its specific role in the recursive algorithm
- Any mutual recursion relationships with other functions

Include context about:
- The recursive nature of the call pattern
- How cycles are handled or terminated  
- The function's contribution to the overall recursive solution
- Any parameters or state that control recursion depth

Avoid:
- Generic descriptions that don't mention recursion
- Implementation details like variable names
- Code syntax specifics
- Overly technical recursion theory""",
    input_prompt="""Analyze this recursive function:

**Function**: {node_name}
**Type**: {node_labels}  
**Path**: {node_path}
**Location**: Lines {start_line}-{end_line}

**Function Code**:
{node_content}

**Cycle Information**:
This function participates in a recursive call pattern with the following functions: {cycle_participants}

**Called Functions & Dependencies**:
{child_calls_context}

Provide a comprehensive description emphasizing the recursive nature, cycle behavior, and this function's role in the recursive algorithm.""",
    variables=["node_name", "node_labels", "node_path", "start_line", "end_line", "node_content", "cycle_participants", "child_calls_context"]
)