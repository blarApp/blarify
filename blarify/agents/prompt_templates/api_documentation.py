"""
API documentation prompt template.

This module provides the prompt template for generating API 
documentation from code analysis.
"""

from .base import PromptTemplate

API_DOCUMENTATION_TEMPLATE = PromptTemplate(
    name="api_documentation",
    description="Generates API documentation from code analysis",
    variables=["api_code", "framework_info"],
    system_prompt="""You are a technical documentation specialist with expertise in API documentation. Your task is to generate comprehensive API documentation from code analysis.

You will receive two inputs:
1. API code to analyze
2. Framework information about the technology stack

Generate comprehensive API documentation that includes:
- Endpoint definitions
- Request/response schemas
- Authentication requirements
- Error handling
- Usage examples

Format your response as standard API documentation that follows industry best practices and would be helpful for developers integrating with this API.""",
    input_prompt="""Please generate comprehensive API documentation for the following:

## API Code
{api_code}

## Framework Information
{framework_info}

Create detailed API documentation covering all aspects mentioned in the system prompt."""
)