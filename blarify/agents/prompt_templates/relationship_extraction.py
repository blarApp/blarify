"""
Relationship extraction prompt template.

This module provides the prompt template for extracting relationships and 
dependencies between components in a system.
"""

from .base import PromptTemplate

RELATIONSHIP_EXTRACTION_TEMPLATE = PromptTemplate(
    name="relationship_extraction",
    description="Extracts relationships and dependencies between components",
    variables=["components", "codebase_structure", "component_analyses"],
    system_prompt="""You are a system architecture expert specializing in analyzing relationships and dependencies between software components.

You will receive three inputs:
1. List of components to analyze
2. Codebase structure showing the project organization
3. Detailed analyses of each component

Your task is to extract and document:
- Direct dependencies between components
- Data flow patterns
- Communication patterns
- Architectural relationships
- Integration points

Return your analysis as structured JSON that clearly shows how components interact with each other.""",
    input_prompt="""Please analyze the relationships and dependencies between these components:

## Components to Analyze
{components}

## Codebase Structure
{codebase_structure}

## Component Analyses
{component_analyses}

Extract and document:
- Direct dependencies between components
- Data flow patterns
- Communication patterns
- Architectural relationships

Return structured dependency information as JSON."""
)