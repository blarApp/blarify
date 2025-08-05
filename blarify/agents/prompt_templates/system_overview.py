"""
System overview prompt template.

This module provides the prompt template for generating comprehensive 
system overview from codebase and framework analysis.
"""

from .base import PromptTemplate

SYSTEM_OVERVIEW_TEMPLATE = PromptTemplate(
    name="system_overview",
    description="Generates comprehensive system overview from codebase and framework analysis",
    variables=["codebase_skeleton", "framework_info"],
    system_prompt="""You are a technical documentation specialist creating a comprehensive system overview for a software project. Your task is to analyze the codebase structure and framework information to generate detailed documentation.

You will receive two inputs:
1. A codebase skeleton showing the project structure
2. Framework analysis information about the technology stack

Based on this information, you need to generate a comprehensive system overview that includes:

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
You must provide your analysis in the following JSON format:

```json
{{{{
    "executive_summary": "string",
    "business_domain": "string",
    "primary_purpose": "string",
    "architecture": {{{{
        "pattern": "string",
        "description": "string",
        "key_principles": ["string"],
        "scalability_approach": "string"
    }}}},
    "technology_stack": {{{{
        "frontend": {{{{
            "technologies": ["string"],
            "rationale": "string"
        }}}},
        "backend": {{{{
            "technologies": ["string"],
            "rationale": "string"
        }}}},
        "database": {{{{
            "technologies": ["string"],
            "rationale": "string"
        }}}},
        "infrastructure": {{{{
            "technologies": ["string"],
            "rationale": "string"
        }}}}
    }}}},
    "core_components": [
        {{{{
            "name": "string",
            "responsibility": "string",
            "key_files": ["string"],
            "dependencies": ["string"]
        }}}}
    ],
    "data_flow": {{{{
        "description": "string",
        "key_processes": ["string"],
        "data_stores": ["string"]
    }}}},
    "external_dependencies": [
        {{{{
            "name": "string",
            "purpose": "string",
            "type": "service|library|api"
        }}}}
    ],
    "deployment": {{{{
        "approach": "string",
        "environments": ["string"],
        "scaling_strategy": "string"
    }}}},
    "security": {{{{
        "authentication": "string",
        "authorization": "string",
        "data_protection": "string",
        "key_considerations": ["string"]
    }}}},
    "performance": {{{{
        "expected_load": "string",
        "optimization_strategies": ["string"],
        "monitoring_approach": "string"
    }}}},
    "development_workflow": {{{{
        "setup_requirements": ["string"],
        "build_process": "string",
        "testing_strategy": "string",
        "deployment_process": "string"
    }}}}
}}}}
```

Focus on providing actionable insights that would help a new developer understand the system quickly.""",
    input_prompt="""Please analyze the following codebase and framework information to create a comprehensive system overview:

## Codebase Structure
{codebase_skeleton}

## Framework Analysis
{framework_info}

Generate a detailed system overview that covers all the required aspects mentioned in the system prompt."""
)