"""Documentation layer for Blarify.

This module provides post-processing capabilities to extract and analyze
documentation from codebases, creating semantic information nodes that
can be efficiently retrieved by LLM agents.

Phase 2 adds LangGraph workflow capabilities for semantic analysis.
"""

# Phase 2 components
from .workflow import DocumentationWorkflow, DocumentationState
from ..agents.llm_provider import LLMProvider
from ..agents.prompt_templates import (
    PromptTemplate,
    PromptTemplateManager,
    FRAMEWORK_DETECTION_TEMPLATE,
    SYSTEM_OVERVIEW_TEMPLATE,
    COMPONENT_ANALYSIS_TEMPLATE,
    API_DOCUMENTATION_TEMPLATE,
)

__all__ = [
    # Phase 2 workflow components
    "DocumentationWorkflow",
    "DocumentationState",
    # LLM providers
    "LLMProvider",
    # Prompt templates
    "PromptTemplate",
    "PromptTemplateManager",
    "FRAMEWORK_DETECTION_TEMPLATE",
    "SYSTEM_OVERVIEW_TEMPLATE",
    "COMPONENT_ANALYSIS_TEMPLATE",
    "API_DOCUMENTATION_TEMPLATE",
]
