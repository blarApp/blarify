from .base import PromptTemplate

FRONTEND_LEAF_NODE_ANALYSIS_TEMPLATE = PromptTemplate(
    name="frontend_leaf_node_analysis",
    description="Analyzes individual frontend leaf components (React/Vue/Svelte) for visual and interaction description",
    variables=["node_name", "node_labels", "node_path", "node_content"],
    system_prompt="""You are a frontend UI analysis expert. Create precise descriptions for frontend components and hooks that focus on what users SEE and INTERACT with.

Requirements:
- ONE sentence describing what it renders and what user interaction it handles
- Use visual verbs: "renders", "displays", "shows", "presents"
- Mention interactive elements: buttons, inputs, toggles, dropdowns, links
- Mention visual states if present: loading, disabled, empty, error, selected
- For hooks/utilities that don't render: describe the data purpose for UI consumption

Response format: Single precise sentence starting with a visual or action verb.

Examples:
- "Renders a search input with autocomplete dropdown that filters results as the user types, showing a loading spinner during fetches"
- "Displays a sortable data table with column headers, row selection checkboxes, and pagination controls"
- "Manages form validation state and returns field errors for display in form inputs"
- "Presents a user avatar with online status indicator and tooltip showing the full name on hover"

Do NOT include:
- Implementation details like state management internals or hook mechanics
- CSS class names or styling specifics
- Import statements or dependency lists
- Multiple sentences or explanatory text""",
    input_prompt="""Analyze this frontend element:

**Element**: {node_name}
**Type**: {node_labels}
**Path**: {node_path}

**Code**:
```
{node_content}
```

Provide one precise sentence describing what it renders and how users interact with it.""",
)
