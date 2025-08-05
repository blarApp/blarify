"""
Template manager for prompt templates.

This module provides the PromptTemplateManager class for managing
and accessing prompt templates.
"""

from typing import Dict, Any, Optional, List
import logging

from .base import PromptTemplate
from .framework_detection import FRAMEWORK_DETECTION_TEMPLATE
from .system_overview import SYSTEM_OVERVIEW_TEMPLATE
from .component_analysis import COMPONENT_ANALYSIS_TEMPLATE
from .api_documentation import API_DOCUMENTATION_TEMPLATE
from .leaf_node_analysis import LEAF_NODE_ANALYSIS_TEMPLATE

logger = logging.getLogger(__name__)


class PromptTemplateManager:
    """Manages prompt templates and their lifecycle."""
    
    def __init__(self):
        self.templates: Dict[str, PromptTemplate] = {}
        self._initialize_templates()
    
    def _initialize_templates(self):
        """Initialize all available templates."""
        templates = [
            FRAMEWORK_DETECTION_TEMPLATE,
            SYSTEM_OVERVIEW_TEMPLATE,
            COMPONENT_ANALYSIS_TEMPLATE,
            API_DOCUMENTATION_TEMPLATE,
            LEAF_NODE_ANALYSIS_TEMPLATE
        ]
        
        for template in templates:
            self.templates[template.name] = template
    
    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """Get a template by name."""
        return self.templates.get(name)
    
    def list_templates(self) -> List[str]:
        """List all available template names."""
        return list(self.templates.keys())
    
    def add_template(self, template: PromptTemplate) -> None:
        """Add a new template."""
        self.templates[template.name] = template
    
    def remove_template(self, name: str) -> bool:
        """Remove a template by name."""
        if name in self.templates:
            del self.templates[name]
            return True
        return False
    
    def format_template(self, name: str, **kwargs) -> str:
        """Format a template with provided variables."""
        template = self.get_template(name)
        if not template:
            raise ValueError(f"Template {name} not found")
        
        if not template.validate_variables(kwargs):
            raise ValueError(f"Invalid variables for template {name}")
        
        return template.format(**kwargs)
    
    def validate_template_variables(self, name: str, variables: Dict[str, Any]) -> bool:
        """Validate variables for a template."""
        template = self.get_template(name)
        if not template:
            return False
        return template.validate_variables(variables)


# Global template manager instance
template_manager = PromptTemplateManager()


# Convenience functions for common operations
def get_framework_detection_prompt() -> PromptTemplate:
    """Get framework detection prompt template."""
    return template_manager.get_template("framework_detection")


def get_system_overview_prompt(codebase_skeleton: str, framework_info: str) -> str:
    """Get formatted system overview prompt."""
    return template_manager.format_template(
        "system_overview", 
        codebase_skeleton=codebase_skeleton, 
        framework_info=framework_info
    )


def get_component_analysis_prompt(component_code: str, context: str) -> str:
    """Get formatted component analysis prompt."""
    return template_manager.format_template(
        "component_analysis", 
        component_code=component_code, 
        context=context
    )


def get_api_documentation_prompt(api_code: str, framework_info: str) -> str:
    """Get formatted API documentation prompt."""
    return template_manager.format_template(
        "api_documentation", 
        api_code=api_code, 
        framework_info=framework_info
    )


def get_leaf_node_analysis_prompt(node_name: str, node_labels: list, node_path: str, node_content: str) -> str:
    """Get formatted leaf node analysis prompt."""
    return template_manager.format_template(
        "leaf_node_analysis",
        node_name=node_name,
        node_labels=node_labels,
        node_path=node_path,
        node_content=node_content
    )


# Chat template convenience functions
def get_framework_detection_chat_template(**kwargs):
    """Get framework detection chat template."""
    template = template_manager.get_template("framework_detection")
    return template.get_chat_template(**kwargs)


def get_system_overview_chat_template(codebase_skeleton: str, framework_info: str):
    """Get system overview chat template."""
    template = template_manager.get_template("system_overview")
    return template.get_chat_template(codebase_skeleton=codebase_skeleton, framework_info=framework_info)


def get_component_analysis_chat_template(component_code: str, context: str):
    """Get component analysis chat template."""
    template = template_manager.get_template("component_analysis")
    return template.get_chat_template(component_code=component_code, context=context)


def get_api_documentation_chat_template(api_code: str, framework_info: str):
    """Get API documentation chat template."""
    template = template_manager.get_template("api_documentation")
    return template.get_chat_template(api_code=api_code, framework_info=framework_info)