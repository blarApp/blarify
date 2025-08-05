"""
Cross-component analysis prompt template.

This module provides the prompt template for analyzing patterns and 
interactions across components in a system.
"""

from .base import PromptTemplate

CROSS_COMPONENT_ANALYSIS_TEMPLATE = PromptTemplate(
    name="cross_component_analysis",
    description="Analyzes patterns and interactions across components in a system",
    variables=["system_overview", "analyzed_nodes", "dependencies"],
    system_prompt="""You are a system architecture expert specializing in analyzing cross-component patterns and system-wide interactions.

You will receive three inputs:
1. System overview containing high-level system information
2. Analyzed nodes with detailed component analysis
3. Dependencies showing relationships between components

Your task is to analyze the cross-component patterns and system-wide interactions to identify:
- Common patterns across components
- System-wide architecture principles
- Integration patterns
- Data flow through the system
- Configuration and deployment patterns

Return your analysis as structured JSON that provides insights into how components work together and what architectural patterns emerge from their interactions.""",
    input_prompt="""Please analyze the cross-component patterns and system-wide interactions based on the following information:

## System Overview
{system_overview}

## Component Analysis
{analyzed_nodes}

## Dependencies
{dependencies}

Identify and analyze:
- Common patterns across components
- System-wide architecture principles
- Integration patterns
- Data flow through the system
- Configuration and deployment patterns

Return structured analysis as JSON."""
)