"""
Pydantic schemas for entry point discovery results.

Defines structured output schemas for hybrid entry point discovery approach,
ensuring consistent data format from agent exploration.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class EntryPoint(BaseModel):
    """
    Represents a discovered entry point in the codebase.
    
    Entry points are functions, classes, or code patterns that serve as
    starting points for execution workflows.
    """
    
    node_id: Optional[str] = Field(
        default=None,
        description="Graph node ID if available from relationship traversal"
    )
    
    name: str = Field(
        description="Name of the function, class, or entry point identifier"
    )
    
    file_path: str = Field(
        description="Full file path where the entry point is defined"
    )
    
    description: str = Field(
        description="Human-readable explanation of why this is considered an entry point"
    )


class EntryPointDiscoveryResult(BaseModel):
    """
    Complete result of entry point discovery analysis.
    
    Contains all discovered entry points from agent exploration.
    """
    
    discovered_entry_points: List[EntryPoint] = Field(
        description="List of all entry points discovered through agent exploration",
        default_factory=list
    )


class HybridEntryPointResult(BaseModel):
    """
    Combined result from both database and agent entry point discovery.
    
    Represents the final unified set of entry points from hybrid discovery approach.
    """
    
    database_entry_points: List[dict] = Field(
        description="Entry points found through database relationship analysis",
        default_factory=list
    )
    
    agent_discovered_entry_points: List[EntryPoint] = Field(
        description="Additional entry points found through agent exploration",
        default_factory=list
    )
    
    combined_entry_points: List[dict] = Field(
        description="Unified set of all entry points after deduplication",
        default_factory=list
    )