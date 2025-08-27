"""Integration node for external tool data (GitHub, Sentry, DataDog, etc.)."""

from typing import Dict, Any, Optional
import json

from blarify.graph.node.types.node import Node
from blarify.graph.node.types.node_labels import NodeLabels
from blarify.graph.graph_environment import GraphEnvironment


class IntegrationNode(Node):
    """Node representing external tool integration data.

    Supports various external tools like GitHub (PRs, commits),
    Sentry (errors), DataDog (metrics), etc. Uses a synthetic
    path format: integration://source/source_type/external_id
    """

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
        metadata: Dict[str, Any],
        graph_environment: GraphEnvironment,
        level: int = 0,
        parent: Optional[Node] = None,
    ):
        """Initialize IntegrationNode.

        Args:
            source: Source system (github, sentry, datadog, etc.)
            source_type: Type within source (pull_request, commit, error, metric)
            external_id: External system's ID for this item
            title: Title or summary of the item
            content: Full content/description
            timestamp: ISO format timestamp
            author: Author or creator
            url: Web URL to view the item
            metadata: Additional system-specific data
            graph_environment: Graph environment configuration
            level: Hierarchy level (0 for root)
            parent: Parent node if hierarchical
        """
        # Create synthetic path
        synthetic_path = f"integration://{source}/{source_type}/{external_id}"

        # Initialize base Node
        super().__init__(
            label=NodeLabels.INTEGRATION,
            path=synthetic_path,
            name=title,
            level=level,
            parent=parent,
            graph_environment=graph_environment,
            layer="integrations",
        )

        # Store integration-specific attributes
        self.source = source
        self.source_type = source_type
        self.external_id = external_id
        self.title = title
        self.content = content
        self.timestamp = timestamp
        self.author = author
        self.url = url
        self.metadata = metadata

    def as_object(self) -> Dict[str, Any]:
        """Serialize IntegrationNode to dictionary.

        Returns:
            Dictionary representation for database storage
        """
        base_obj = super().as_object()

        # Add integration-specific attributes
        base_obj["attributes"].update(
            {
                "source": self.source,
                "source_type": self.source_type,
                "external_id": self.external_id,
                "title": self.title,
                "content": self.content,
                "timestamp": self.timestamp,
                "author": self.author,
                "url": self.url,
                "metadata": json.dumps(self.metadata) if self.metadata else "{}",
                "layer": "integrations",
            }
        )

        return base_obj

    @property
    def node_repr_for_identifier(self) -> str:
        """Return representation for identifier generation."""
        return f"{self.source}_{self.source_type}_{self.external_id}"

    def __repr__(self) -> str:
        """String representation of IntegrationNode."""
        return (
            f"IntegrationNode(source={self.source}, type={self.source_type}, id={self.external_id}, title={self.title})"
        )
