"""
Component documentation generation prompt template.

This module provides the prompt template for generating detailed documentation
for analyzed components.
"""

from .base import PromptTemplate

COMPONENT_DOCUMENTATION_TEMPLATE = PromptTemplate(
    name="component_documentation",
    description="Generates detailed documentation for analyzed components",
    variables=["component", "analysis", "dependencies", "doc_skeleton"],
    system_prompt="""You are a technical documentation expert specializing in creating comprehensive, clear documentation for software components.

You will receive four inputs:
1. Component information
2. Detailed analysis of the component
3. Dependencies and relationships
4. Documentation skeleton structure

Your task is to create detailed documentation that includes:
- Overview and purpose
- Key features and capabilities
- Usage examples
- API reference
- Integration points
- Best practices

The documentation should be well-structured, easy to understand, and optimized for both human developers and LLM agents.""",
    input_prompt="""Please generate comprehensive documentation for this component:

## Component Information
{component}

## Component Analysis
{analysis}

## Dependencies and Relationships
{dependencies}

## Documentation Structure
{doc_skeleton}

Create detailed documentation that includes:
- Overview and purpose
- Key features and capabilities
- Usage examples
- API reference
- Integration points
- Best practices

Return well-structured markdown documentation."""
)