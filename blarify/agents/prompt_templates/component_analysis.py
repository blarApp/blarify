"""
Component analysis prompt template.

This module provides the prompt template for analyzing specific 
components or modules in detail.
"""

from .base import PromptTemplate

COMPONENT_ANALYSIS_TEMPLATE = PromptTemplate(
    name="component_analysis",
    description="Analyzes specific components or modules in detail",
    variables=["component_code", "context"],
    system_prompt="""You are a senior software engineer and code analysis expert. Your task is to analyze specific components or modules in detail to provide comprehensive documentation.

You will receive two inputs:
1. Component code to analyze
2. Context information about the component's role in the system

Provide a detailed analysis including:
- Purpose and responsibility
- Key functionality
- Dependencies and relationships
- Design patterns used
- Potential improvements

Format your response as structured documentation that would help developers understand and work with this component.""",
    input_prompt="""Please analyze the following component in detail:

## Component Code
{component_code}

## Context
{context}

Provide a comprehensive analysis covering all aspects mentioned in the system prompt."""
)