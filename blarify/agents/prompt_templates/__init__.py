"""
Prompt templates package for the semantic documentation layer.

This package provides structured prompt templates for various LLM tasks in the
documentation workflow, organized as individual modules for better maintainability.
"""

from .base import PromptTemplate
from .template_manager import PromptTemplateManager, template_manager
from .framework_detection import FRAMEWORK_DETECTION_TEMPLATE
from .system_overview import SYSTEM_OVERVIEW_TEMPLATE
from .component_analysis import COMPONENT_ANALYSIS_TEMPLATE
from .api_documentation import API_DOCUMENTATION_TEMPLATE
from .component_identification import COMPONENT_IDENTIFICATION_TEMPLATE
from .cross_component_analysis import CROSS_COMPONENT_ANALYSIS_TEMPLATE
from .relationship_extraction import RELATIONSHIP_EXTRACTION_TEMPLATE
from .component_documentation import COMPONENT_DOCUMENTATION_TEMPLATE
from .documentation_consolidation import DOCUMENTATION_CONSOLIDATION_TEMPLATE
from .leaf_node_analysis import LEAF_NODE_ANALYSIS_TEMPLATE
from .parent_node_analysis import PARENT_NODE_ANALYSIS_TEMPLATE
from .function_with_calls_analysis import FUNCTION_WITH_CALLS_ANALYSIS_TEMPLATE
from .spec_discovery import SPEC_DISCOVERY_TEMPLATE

__all__ = [
    "PromptTemplate",
    "PromptTemplateManager", 
    "template_manager",
    "FRAMEWORK_DETECTION_TEMPLATE",
    "SYSTEM_OVERVIEW_TEMPLATE", 
    "COMPONENT_ANALYSIS_TEMPLATE",
    "API_DOCUMENTATION_TEMPLATE",
    "COMPONENT_IDENTIFICATION_TEMPLATE",
    "CROSS_COMPONENT_ANALYSIS_TEMPLATE",
    "RELATIONSHIP_EXTRACTION_TEMPLATE",
    "COMPONENT_DOCUMENTATION_TEMPLATE",
    "DOCUMENTATION_CONSOLIDATION_TEMPLATE",
    "LEAF_NODE_ANALYSIS_TEMPLATE",
    "PARENT_NODE_ANALYSIS_TEMPLATE",
    "FUNCTION_WITH_CALLS_ANALYSIS_TEMPLATE",
    "SPEC_DISCOVERY_TEMPLATE"
]