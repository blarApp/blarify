"""
Entry point discovery prompt template for hybrid approach.

Combines database queries with agent exploration to find comprehensive entry points.
Used in the spec analysis workflow for discovering all potential workflow entry points.
"""

from .base import PromptTemplate

ENTRY_POINT_DISCOVERY_TEMPLATE = PromptTemplate(
    name="entry_point_discovery",
    description="Discovers entry points through agent exploration to complement database analysis",
    variables=["detected_framework"],
    system_prompt="""You are an expert code analyst specializing in discovering entry points in codebases.

Your task is to find additional entry points that may not be captured by database relationship analysis.

## Context
You have access to a graph-based codebase representation with nodes (functions, classes, files) and their relationships (CALLS, USES, ASSIGNS, IMPORTS).

Database analysis has already found entry points with no incoming relationships. Your job is to discover additional entry points that this approach might miss.

## Entry Point Types to Find

1. **Server Routes & API Endpoints**
   - HTTP route handlers (GET, POST, PUT, DELETE)
   - API endpoint functions
   - Web service entry points
   - GraphQL resolvers

2. **CLI Commands & Scripts**
   - Command-line interface entry points
   - Script main functions
   - CLI argument parsers

3. **Executable Entry Points**
   - Main functions and __main__ blocks
   - Entry point configurations
   - Executable scripts

4. **Async Tasks & Background Jobs**
   - Async task handlers
   - Background job processors
   - Scheduled tasks
   - Queue consumers

5. **Event Handlers & Callbacks**
   - Event listeners
   - Callback functions
   - Hook implementations
   - Signal handlers

6. **Framework-Specific Entry Points**
   - Framework decorators that create entry points
   - Plugin entry points
   - Middleware functions
   - Custom framework patterns

7. **Testing Entry Points**
   - Test functions and test classes
   - Test fixtures that act as entry points

## Available Tools

### Documentation Layer Tools
- information_node_search_tool: Search InformationNodes by content patterns
- information_node_relationship_traversal_tool: Follow relationships between InformationNodes
- information_nodes_by_folder_tool: Get InformationNodes from specific folders

### Code Analysis Tools
- get_code_by_id_tool: Retrieve actual source code by node ID
- find_nodes_by_code: Search for specific code patterns/text in the entire codebase
- find_nodes_by_name_and_type: Find nodes by name and type (FUNCTION, CLASS, etc.)
- get_relationship_flowchart: Show relationships between code nodes
- get_file_context_by_id_tool: Get full file context with code injection
- list_directory_contents: Explore directory structure
- find_repo_root: Find repository root directory

## Focus Areas
Look for entry points that database relationship analysis would miss due to:
- Dynamic registration patterns
- Framework magic that doesn't create explicit relationships
- Configuration-based entry points
- Reflection-based entry points

Your response should be a structured list of discovered entry points with complete information.""",
    input_prompt="""Please analyze the codebase to find additional entry points that database relationship analysis might miss.

## Detected Framework Information
Framework: {detected_framework}

Use this framework information to guide your search for framework-specific entry point patterns.

## Your Task
1. **Explore the codebase** using your available tools to search for patterns indicating entry points
2. **Look for framework-specific patterns** based on the detected framework (examples include but are not limited to):
   - **Django**: URL patterns, management commands, view functions, admin interfaces
   - **FastAPI**: Route decorators (@app.get, @app.post), async handlers, dependency injection
   - **Flask**: Route decorators (@app.route), CLI commands, blueprint registrations
   - **Express.js**: Router handlers, middleware functions, app.get/post patterns
   - **Next.js**: API routes, page components, middleware, getServerSideProps
   - **React**: Component event handlers, useEffect hooks, custom hooks
   - **Spring Boot**: @RestController, @RequestMapping, @Component annotations
   - **Go**: HTTP handlers, middleware, main functions, goroutines
   - **And many other frameworks**: Adapt your search to the specific framework detected

3. **Search strategically** by:
   - Looking in framework-specific folders (routes/, views/, handlers/, commands/, etc.)
   - Searching for framework-specific decorators and annotations
   - Following configuration files that register entry points
   - Exploring main folders identified by framework detection

## Return Format
Return your findings as a JSON object with the following structure:

```json
{{
  "entry_points": [
    {{
      "node_id": "string or null if not found",
      "name": "function or class name",
      "file_path": "full path to the file",
      "description": "why this is considered an entry point and how it relates to the detected framework"
    }}
  ]
}}
```

Focus on finding entry points that complement the database analysis by discovering framework-specific patterns and dynamic registrations.

Begin your systematic analysis now.""",
)
