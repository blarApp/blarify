"""
Base classes for prompt templates.

This module provides the core PromptTemplate class and related utilities.
"""

from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
import logging
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplate:
    """Base class for prompt templates with separated system and input prompts."""

    name: str
    description: str
    system_prompt: str
    input_prompt: str
    variables: List[str] = None

    def __post_init__(self):
        if self.variables is None:
            self.variables = []

    def format_input(self, **kwargs) -> str:
        """Format the input prompt with provided variables."""
        try:
            return self.input_prompt.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing variable {e} for template {self.name}")
            raise
        except Exception as e:
            logger.error(f"Error formatting input template {self.name}: {e}")
            raise

    def get_chat_template(self, **kwargs) -> ChatPromptTemplate:
        """Get a ChatPromptTemplate with system and formatted input prompts."""
        formatted_input = self.format_input(**kwargs)
        return ChatPromptTemplate.from_messages([("system", self.system_prompt), ("human", formatted_input)])

    def get_prompts(self, **kwargs) -> Tuple[str, str]:
        """Get system prompt and formatted input prompt as a tuple."""
        return self.system_prompt, self.format_input(**kwargs)

    def validate_variables(self, variables: Dict[str, Any]) -> bool:
        """Validate that all required variables are provided."""
        missing = [var for var in self.variables if var not in variables]
        if missing:
            logger.error(f"Missing required variables for template {self.name}: {missing}")
            return False
        return True
