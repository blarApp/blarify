"""Documentation layer for Blarify.

This module provides post-processing capabilities to extract and analyze
documentation from codebases, creating semantic information nodes that
can be efficiently retrieved by LLM agents.

Uses method-based orchestration for documentation creation and workflow discovery,
replacing the previous LangGraph approach with simpler, more performant patterns.
"""

# New architecture components
from .documentation_creator import DocumentationCreator
from .workflow_creator import WorkflowCreator
from .result_models import DocumentationResult, WorkflowResult, WorkflowDiscoveryResult, FrameworkDetectionResult
from .utils.bottom_up_batch_processor import BottomUpBatchProcessor, ProcessingResult
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
    # New architecture components
    "DocumentationCreator",
    "WorkflowCreator",
    "DocumentationResult",
    "WorkflowResult",
    "WorkflowDiscoveryResult",
    "FrameworkDetectionResult",
    # Core processing components
    "BottomUpBatchProcessor",
    "ProcessingResult",
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
