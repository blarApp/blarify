from blarify.agents.prompt_templates.base import PromptTemplate

FRONTEND_PARENT_NODE_ANALYSIS_TEMPLATE = PromptTemplate(
    name="frontend_parent_node_analysis",
    description="Analyzes frontend parent elements (files/modules) describing the page/view they implement",
    system_prompt="""You are analyzing a frontend file or module that implements a page, view, or UI section. Focus on the complete visual experience.

Create a description (3-5 sentences) that:
- Starts with "This [file/module] implements the..." describing the page or view
- Describes the overall visual structure and layout sections
- Lists all sections/areas visible on the page
- Mentions key interactive capabilities available to users
- Notes any route/URL this page is associated with if apparent

Focus on:
- The complete page/view this file creates for the user
- Major visual sections and their arrangement (header, sidebar, content area, footer)
- Primary user actions available on this page
- Navigation patterns and page transitions
- How child components combine to form the full page experience

Avoid:
- Verbatim repetition of child descriptions
- Implementation details like state management or data fetching internals
- File structure or import organization details
- CSS or styling specifics""",
    input_prompt="""Analyze this frontend parent element:

**Name**: {node_name}
**Type**: {node_labels}
**Path**: {node_path}

**Enhanced Content**:
{node_content}

Describe the page or view this file implements, its visual structure, and the user experience it provides.""",
    variables=["node_name", "node_labels", "node_path", "node_content"],
)
