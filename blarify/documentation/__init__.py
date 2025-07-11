"""Documentation layer for Blarify.

This module provides post-processing capabilities to extract and analyze
documentation from codebases, creating semantic information nodes that
can be efficiently retrieved by LLM agents.

Phase 2 adds LangGraph workflow capabilities for semantic analysis.
"""

from .post_processor import DocumentationPostProcessor
from .extractor import DocumentationExtractor
from .semantic_analyzer import SemanticDocumentationAnalyzer

# Phase 2 components
from .workflow import (
    DocumentationWorkflow,
    DocumentationWorkflowFactory,
    DocumentationState,
    run_documentation_workflow,
    get_codebase_analysis
)
from ..agents.llm_provider import LLMProvider
from ..agents.prompt_templates import (
    PromptTemplate,
    PromptTemplateManager,
    get_framework_detection_prompt,
    get_system_overview_prompt
)

__all__ = [
    # Phase 1 components
    "DocumentationPostProcessor",
    "DocumentationExtractor", 
    "SemanticDocumentationAnalyzer",
    
    # Phase 2 workflow components
    "DocumentationWorkflow",
    "DocumentationWorkflowFactory",
    "DocumentationState",
    "run_documentation_workflow",
    "get_codebase_analysis",
    
    # LLM providers
    "LLMProvider",
    
    # Prompt templates
    "PromptTemplate",
    "PromptTemplateManager",
    "get_framework_detection_prompt",
    "get_system_overview_prompt",
]