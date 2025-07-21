"""
Pydantic schemas for structured LLM outputs in the agents module.

This package provides structured output schemas for various LLM tasks
to ensure consistent, validated responses from language model calls.
"""

from .framework_analysis_schema import FrameworkAnalysisResponse

__all__ = [
    "FrameworkAnalysisResponse"
]