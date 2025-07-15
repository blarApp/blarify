"""Documentation layer for Blarify.

This module provides post-processing capabilities to extract and analyze
documentation from codebases, creating semantic information nodes that
can be efficiently retrieved by LLM agents.

Phase 2 adds LangGraph workflow capabilities for semantic analysis.
"""

from .post_processor import DocumentationPostProcessor
from .extractor import DocumentationExtractor
from .semantic_analyzer import SemanticDocumentationAnalyzer, LLMProvider as SemanticLLMProvider

# Phase 2 components
from .workflow import DocumentationWorkflow, DocumentationState
from ..agents.llm_provider import LLMProvider
from ..agents.prompt_templates import (
    PromptTemplate,
    PromptTemplateManager,
    get_framework_detection_prompt,
    get_system_overview_prompt,
    get_component_analysis_prompt,
    get_api_documentation_prompt,
)

__all__ = [
    # Phase 1 components
    "DocumentationPostProcessor",
    "DocumentationExtractor",
    "SemanticDocumentationAnalyzer",
    "SemanticLLMProvider",
    # Phase 2 workflow components
    "DocumentationWorkflow",
    "DocumentationState",
    # LLM providers
    "LLMProvider",
    # Prompt templates
    "PromptTemplate",
    "PromptTemplateManager",
    "get_framework_detection_prompt",
    "get_system_overview_prompt",
    "get_component_analysis_prompt",
    "get_api_documentation_prompt",
]
