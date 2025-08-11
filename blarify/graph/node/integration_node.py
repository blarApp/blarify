"""Integration node for external tool data (GitHub PRs, commits, etc.)."""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from blarify.graph.node.node import Node
from blarify.graph.node.types.node_labels import NodeLabels
from blarify.graph.environment.graph_environment import GraphEnvironment


@dataclass
class IntegrationNode(Node):
    """
    Node representing external tool integration data (PRs, commits, etc.).
    
    This class supports integration with external tools like GitHub, providing
    a consistent interface for storing PR and commit data in the graph.
    """
    
    source: str  # e.g., "github", "sentry", "datadog"
    source_type: str  # e.g., "pull_request", "commit", "error", "metric"
    external_id: str  # External system's ID for this entity
    title: str  # Title or summary
    content: str  # Description, commit message, etc.
    timestamp: str  # ISO format timestamp
    author: str  # Author username or identifier
    url: str  # Link to external resource
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional tool-specific data
    
    def __init__(
        self,
        source: str,
        source_type: str,
        external_id: str,
        title: str,
        content: str,
        timestamp: str,
        author: str,
        url: str,
        graph_environment: GraphEnvironment,
        metadata: Optional[Dict[str, Any]] = None,
        level: int = 0,
        parent: Optional[Node] = None,
    ):
        """
        Initialize an IntegrationNode.
        
        Args:
            source: Source system (e.g., "github")
            source_type: Type of entity (e.g., "pull_request", "commit")
            external_id: ID in the external system
            title: Title or summary
            content: Full content/description
            timestamp: ISO format timestamp
            author: Author identifier
            url: URL to external resource
            graph_environment: Graph environment
            metadata: Additional tool-specific data
            level: Hierarchy level (default 0)
            parent: Parent node if applicable
        """
        # Create synthetic path for integration entities
        synthetic_path = f"integration://{source}/{source_type}/{external_id}"
        
        super().__init__(
            label=NodeLabels.INTEGRATION,
            path=synthetic_path,
            name=title,
            level=level,
            parent=parent,
            graph_environment=graph_environment,
            layer="integrations"
        )
        
        self.source = source
        self.source_type = source_type
        self.external_id = external_id
        self.title = title
        self.content = content
        self.timestamp = timestamp
        self.author = author
        self.url = url
        self.metadata = metadata or {}
        
    def as_object(self) -> Dict[str, Any]:
        """
        Convert IntegrationNode to dictionary representation.
        
        Returns:
            Dictionary with all node properties for database storage
        """
        obj = super().as_object()
        obj.update({
            "source": self.source,
            "source_type": self.source_type,
            "external_id": self.external_id,
            "title": self.title,
            "content": self.content,
            "timestamp": self.timestamp,
            "author": self.author,
            "url": self.url,
            "metadata": self.metadata,
            "layer": "integrations"
        })
        return obj
    
    def get_display_name(self) -> str:
        """Get a display-friendly name for this integration node."""
        if self.source_type == "pull_request":
            return f"PR #{self.external_id}: {self.title}"
        elif self.source_type == "commit":
            # Show first 7 chars of SHA
            short_sha = self.external_id[:7] if len(self.external_id) > 7 else self.external_id
            return f"Commit {short_sha}: {self.title}"
        else:
            return f"{self.source_type} {self.external_id}: {self.title}"
    
    def __repr__(self) -> str:
        """String representation of IntegrationNode."""
        return (
            f"IntegrationNode(source='{self.source}', "
            f"type='{self.source_type}', "
            f"id='{self.external_id}', "
            f"title='{self.title[:30]}...')"
        )