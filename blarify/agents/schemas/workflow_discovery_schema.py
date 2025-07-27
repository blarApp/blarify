"""
Pydantic schemas for workflow discovery structured outputs.

This module provides schemas for the workflow discovery process to ensure
consistent, validated responses from LLM workflow analysis.
"""

from typing import List
from pydantic import BaseModel, Field


class WorkflowDefinition(BaseModel):
    """Definition of a discovered business workflow."""
    
    name: str = Field(
        description="Clear workflow name (e.g., 'User Registration Workflow')"
    )
    description: str = Field(
        description="Brief description of what this workflow accomplishes and its business purpose"
    )
    entry_points: List[str] = Field(
        description="List of component names or endpoints that likely start this workflow",
        default_factory=list
    )
    scope: str = Field(
        description="Brief description of the workflow's boundaries and what it includes"
    )
    framework_context: str = Field(
        description="How this workflow fits within the detected framework patterns"
    )


class WorkflowDiscoveryResponse(BaseModel):
    """Response schema for workflow discovery analysis."""
    
    workflows: List[WorkflowDefinition] = Field(
        description="List of discovered business workflows in the codebase",
        default_factory=list
    )