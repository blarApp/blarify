from blarify.agents.prompt_templates.base import PromptTemplate

FRONTEND_FUNCTION_WITH_CALLS_ANALYSIS_TEMPLATE = PromptTemplate(
    name="frontend_function_with_calls_analysis",
    description="Analyzes frontend components that compose child components, focusing on visual layout and interaction flows",
    system_prompt="""You are analyzing a frontend component that composes child components. Focus on the visual layout and user interaction flows.

Create a description (4-6 sentences) that:
- Starts with "This component renders..." describing the overall visual layout
- Describes which child components are rendered and where they appear in the layout
- Explains user interaction flows between the composed elements
- Notes conditional rendering: permissions, feature flags, loading/error states
- Describes how state flows to children and how child events propagate up

Focus on:
- The overall page/section structure the user sees
- Which child components are visible and their spatial arrangement
- Interactive flows: what happens when users click, type, submit, navigate
- Loading states, error boundaries, empty states, and permission gates
- How composed children work together to form a cohesive UI experience

Avoid:
- Implementation details like hook internals or state management mechanics
- Simply listing child components without describing their visual role
- CSS or styling specifics
- Repeating the exact content of child descriptions""",
    input_prompt="""Analyze this frontend component with its composed children:

**Component**: {node_name}
**Type**: {node_labels}
**Path**: {node_path}
**Location**: Lines {start_line}-{end_line}

**Component Code**:
{node_content}

**Child Components & Dependencies**:
{child_calls_context}

Describe the visual layout this component creates, how its children are arranged, and the user interaction flows between them.""",
    variables=["node_name", "node_labels", "node_path", "start_line", "end_line", "node_content", "child_calls_context"],
)
