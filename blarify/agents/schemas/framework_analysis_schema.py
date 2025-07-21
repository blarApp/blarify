"""
Schema for framework analysis structured output.

This module provides the Pydantic schema for the combined framework detection
and main folder identification task, ensuring consistent structured output
from the LLM analysis.
"""

from typing import List
from pydantic import BaseModel, Field


class FrameworkAnalysisResponse(BaseModel):
    """
    Structured response for combined framework analysis and main folder identification.
    
    This schema ensures the LLM returns both framework analysis text and
    a validated list of main architectural folders in a consistent format.
    """
    
    framework: str = Field(
        ..., 
        description="Complete framework and technology stack analysis including primary language, frameworks, architecture patterns, project type, and strategic insights for documentation generation"
    )
    
    main_folders: List[str] = Field(
        ...,
        min_items=3,
        max_items=10,
        description="List of 3-10 most important architectural folders identified based on the detected framework (e.g., ['models/', 'views/', 'templates/'] for Django or ['components/', 'hooks/', 'utils/'] for React)"
    )