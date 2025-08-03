"""
Pydantic schemas for spec discovery structured outputs.

This module provides schemas for the spec discovery process to ensure
consistent, validated responses from LLM spec analysis.
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field


class EntryPoint(BaseModel):
    """Entry point for a specification with node information."""
    
    node_id: str = Field(
        description="The node_id from DocumentationNode (e.g., 'info_abc123')"
    )
    name: str = Field(
        description="Component name or endpoint (e.g., 'ProductController.create')"
    )
    source_node_id: str = Field(
        description="The code node ID that this documentation node describes",
        default=""
    )


class SpecDefinition(BaseModel):
    """Definition of a discovered business specification."""
    
    name: str = Field(
        description="Clear specification name (e.g., 'User Management Spec')"
    )
    description: str = Field(
        description="Brief description of what this specification encompasses and its business purpose"
    )
    entry_points: List[EntryPoint] = Field(
        description="List of entry points with their node information",
        default_factory=list
    )
    scope: str = Field(
        description="Brief description of the specification's boundaries and what it includes"
    )
    framework_context: str = Field(
        description="How this specification fits within the detected framework patterns"
    )


class SpecDiscoveryResponse(BaseModel):
    """Response schema for spec discovery analysis."""
    
    specs: List[SpecDefinition] = Field(
        description="List of discovered business specifications in the codebase",
        default_factory=list
    )