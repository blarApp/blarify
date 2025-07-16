"""
Prompt templates for the semantic documentation layer.

This module provides structured prompt templates for various LLM tasks in the
documentation workflow, including framework detection and system overview generation.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplate:
    """Base class for prompt templates."""
    name: str
    description: str
    template: str
    version: str = "1.0"
    variables: List[str] = None
    
    def __post_init__(self):
        if self.variables is None:
            self.variables = []
    
    def format(self, **kwargs) -> str:
        """Format the template with provided variables."""
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing variable {e} for template {self.name}")
            raise
        except Exception as e:
            logger.error(f"Error formatting template {self.name}: {e}")
            raise
    
    def validate_variables(self, variables: Dict[str, Any]) -> bool:
        """Validate that all required variables are provided."""
        missing = [var for var in self.variables if var not in variables]
        if missing:
            logger.error(f"Missing required variables for template {self.name}: {missing}")
            return False
        return True


# Framework Detection Templates
FRAMEWORK_DETECTION_TEMPLATE = PromptTemplate(
    name="framework_detection",
    description="Analyzes codebase structure to identify technology stack and frameworks",
    variables=[],
    template="""
You are a senior software architect analyzing a codebase structure. Your task is to identify the technology stack, frameworks, and architectural patterns used in this project.

## Analysis Instructions
Please analyze the codebase structure and provide a comprehensive assessment including:

1. **Primary Programming Language(s)**: Identify the main languages used
2. **Framework Detection**: Identify any frameworks, libraries, or platforms used
3. **Architecture Pattern**: Determine the architectural pattern (MVC, microservices, monolith, etc.)
4. **Project Type**: Classify the project type (web app, API, library, CLI tool, etc.)
5. **Technology Stack**: List the complete technology stack
6. **Development Environment**: Identify build tools, package managers, testing frameworks

## Framework Indicators to Look For
- **Web Frameworks**: Django, Flask, FastAPI, Express.js, Next.js, React, Vue.js, Angular
- **Mobile**: React Native, Flutter, Ionic, Xamarin
- **Desktop**: Electron, Tauri, PyQt, Tkinter
- **Backend**: Node.js, Spring Boot, .NET Core, Ruby on Rails
- **Database**: PostgreSQL, MySQL, MongoDB, Redis, SQLite
- **Package Managers**: npm, pip, cargo, maven, gradle
- **Build Tools**: Webpack, Vite, Rollup, Gulp, Maven, Gradle
- **Testing**: Jest, Pytest, JUnit, Mocha, Cypress

## Response Format
Provide your analysis in the following JSON format:

```json
{{
    "primary_language": "string",
    "secondary_languages": ["string"],
    "framework": {{
        "name": "string",
        "version": "string (if detectable)",
        "category": "web|mobile|desktop|backend|library|cli"
    }},
    "architecture_pattern": "string",
    "project_type": "string",
    "technology_stack": {{
        "frontend": ["string"],
        "backend": ["string"],
        "database": ["string"],
        "build_tools": ["string"],
        "testing": ["string"],
        "deployment": ["string"]
    }},
    "package_manager": "string",
    "confidence_score": 0.0-1.0,
    "reasoning": "string explaining the analysis"
}}
```

Be thorough in your analysis and provide detailed reasoning for your conclusions.
"""
)

SYSTEM_OVERVIEW_TEMPLATE = PromptTemplate(
    name="system_overview",
    description="Generates comprehensive system overview from codebase and framework analysis",
    variables=["codebase_skeleton", "framework_info"],
    template="""
You are a technical documentation specialist creating a comprehensive system overview for a software project. Your task is to analyze the codebase structure and framework information to generate detailed documentation.


## Framework Analysis
{framework_info}

## Documentation Requirements
Generate a comprehensive system overview that includes:

1. **Executive Summary**: Brief description of what the system does
2. **Architecture Overview**: High-level system architecture and design patterns
3. **Technology Stack**: Complete technology stack with rationale
4. **Core Components**: Key modules, services, and their responsibilities
5. **Data Flow**: How data moves through the system
6. **External Dependencies**: Third-party services and integrations
7. **Deployment Architecture**: How the system is deployed and scaled
8. **Security Considerations**: Authentication, authorization, and security measures
9. **Performance Characteristics**: Expected performance and scalability
10. **Development Workflow**: How developers work with this codebase

## Response Format
Provide your analysis in the following JSON format:

```json
{{
    "executive_summary": "string",
    "business_domain": "string",
    "primary_purpose": "string",
    "architecture": {{
        "pattern": "string",
        "description": "string",
        "key_principles": ["string"],
        "scalability_approach": "string"
    }},
    "technology_stack": {{
        "frontend": {{
            "technologies": ["string"],
            "rationale": "string"
        }},
        "backend": {{
            "technologies": ["string"],
            "rationale": "string"
        }},
        "database": {{
            "technologies": ["string"],
            "rationale": "string"
        }},
        "infrastructure": {{
            "technologies": ["string"],
            "rationale": "string"
        }}
    }},
    "core_components": [
        {{
            "name": "string",
            "responsibility": "string",
            "key_files": ["string"],
            "dependencies": ["string"]
        }}
    ],
    "data_flow": {{
        "description": "string",
        "key_processes": ["string"],
        "data_stores": ["string"]
    }},
    "external_dependencies": [
        {{
            "name": "string",
            "purpose": "string",
            "type": "service|library|api"
        }}
    ],
    "deployment": {{
        "approach": "string",
        "environments": ["string"],
        "scaling_strategy": "string"
    }},
    "security": {{
        "authentication": "string",
        "authorization": "string",
        "data_protection": "string",
        "key_considerations": ["string"]
    }},
    "performance": {{
        "expected_load": "string",
        "optimization_strategies": ["string"],
        "monitoring_approach": "string"
    }},
    "development_workflow": {{
        "setup_requirements": ["string"],
        "build_process": "string",
        "testing_strategy": "string",
        "deployment_process": "string"
    }}
}}
```

Focus on providing actionable insights that would help a new developer understand the system quickly.
"""
)

# Additional specialized templates
COMPONENT_ANALYSIS_TEMPLATE = PromptTemplate(
    name="component_analysis",
    description="Analyzes specific components or modules in detail",
    variables=["component_code", "context"],
    template="""
Analyze the following component in detail:

## Component Code
{component_code}

## Context
{context}

Provide a detailed analysis including:
- Purpose and responsibility
- Key functionality
- Dependencies and relationships
- Design patterns used
- Potential improvements

Format your response as structured documentation.
"""
)

API_DOCUMENTATION_TEMPLATE = PromptTemplate(
    name="api_documentation",
    description="Generates API documentation from code analysis",
    variables=["api_code", "framework_info"],
    template="""
Generate comprehensive API documentation for the following code:

## API Code
{api_code}

## Framework Information
{framework_info}

Include:
- Endpoint definitions
- Request/response schemas
- Authentication requirements
- Error handling
- Usage examples

Format as standard API documentation.
"""
)


class PromptTemplateManager:
    """Manages prompt templates and their lifecycle."""
    
    def __init__(self):
        self.templates: Dict[str, PromptTemplate] = {}
        self._initialize_templates()
    
    def _initialize_templates(self):
        """Initialize all available templates."""
        templates = [
            FRAMEWORK_DETECTION_TEMPLATE,
            SYSTEM_OVERVIEW_TEMPLATE,
            COMPONENT_ANALYSIS_TEMPLATE,
            API_DOCUMENTATION_TEMPLATE
        ]
        
        for template in templates:
            self.templates[template.name] = template
    
    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """Get a template by name."""
        return self.templates.get(name)
    
    def list_templates(self) -> List[str]:
        """List all available template names."""
        return list(self.templates.keys())
    
    def add_template(self, template: PromptTemplate) -> None:
        """Add a new template."""
        self.templates[template.name] = template
    
    def remove_template(self, name: str) -> bool:
        """Remove a template by name."""
        if name in self.templates:
            del self.templates[name]
            return True
        return False
    
    def format_template(self, name: str, **kwargs) -> str:
        """Format a template with provided variables."""
        template = self.get_template(name)
        if not template:
            raise ValueError(f"Template {name} not found")
        
        if not template.validate_variables(kwargs):
            raise ValueError(f"Invalid variables for template {name}")
        
        return template.format(**kwargs)
    
    def validate_template_variables(self, name: str, variables: Dict[str, Any]) -> bool:
        """Validate variables for a template."""
        template = self.get_template(name)
        if not template:
            return False
        return template.validate_variables(variables)


# Convenience functions for common operations
def get_framework_detection_prompt() -> str:
    """Get formatted framework detection prompt."""
    manager = PromptTemplateManager()
    return manager.get_template("framework_detection")


def get_system_overview_prompt(codebase_skeleton: str, framework_info: str) -> str:
    """Get formatted system overview prompt."""
    manager = PromptTemplateManager()
    return manager.format_template(
        "system_overview", 
        codebase_skeleton=codebase_skeleton, 
        framework_info=framework_info
    )


def get_component_analysis_prompt(component_code: str, context: str) -> str:
    """Get formatted component analysis prompt."""
    manager = PromptTemplateManager()
    return manager.format_template(
        "component_analysis", 
        component_code=component_code, 
        context=context
    )


def get_api_documentation_prompt(api_code: str, framework_info: str) -> str:
    """Get formatted API documentation prompt."""
    manager = PromptTemplateManager()
    return manager.format_template(
        "api_documentation", 
        api_code=api_code, 
        framework_info=framework_info
    )


# Global template manager instance
template_manager = PromptTemplateManager()