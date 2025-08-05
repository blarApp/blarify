"""
Documentation consolidation prompt template.

This module provides the prompt template for consolidating all documentation
into a final comprehensive guide.
"""

from .base import PromptTemplate

DOCUMENTATION_CONSOLIDATION_TEMPLATE = PromptTemplate(
    name="documentation_consolidation",
    description="Consolidates all documentation into a final comprehensive guide",
    variables=["doc_skeleton", "component_docs", "system_patterns", "system_overview"],
    system_prompt="""You are a documentation expert specializing in creating final, comprehensive system documentation that integrates all component documentation and system analysis.

You will receive four inputs:
1. Documentation skeleton structure
2. Component documentation
3. System patterns and architecture
4. System overview

Your task is to create a final, well-organized documentation that:
- Follows the skeleton structure
- Integrates all component documentation
- Includes system-wide patterns
- Provides clear navigation
- Is optimized for LLM agent consumption

The final documentation should be comprehensive yet accessible, providing both high-level understanding and detailed technical information.""",
    input_prompt="""Please consolidate all documentation into a final comprehensive guide:

## Documentation Structure
{doc_skeleton}

## Component Documentation
{component_docs}

## System Patterns and Architecture
{system_patterns}

## System Overview
{system_overview}

Create a final, well-organized documentation that:
- Follows the skeleton structure
- Integrates all component documentation
- Includes system-wide patterns
- Provides clear navigation
- Is optimized for LLM agent consumption

Return the final consolidated documentation."""
)