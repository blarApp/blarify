from typing import List, Optional, Dict, Any, Union, TypedDict, TYPE_CHECKING, Unpack
from blarify.graph.node import NodeLabels
from .types.node import Node

if TYPE_CHECKING:
    from blarify.graph.graph_environment import GraphEnvironment


class DocumentationNodeKwargs(TypedDict, total=False):
    """Type definition for DocumentationNode kwargs."""

    level: int
    parent: Optional["Node"]
    graph_environment: Optional["GraphEnvironment"]


class DocumentationNode(Node):
    """Represents a semantic piece of documentation/knowledge extracted from the codebase.

    This node type is used to store atomic pieces of information that can be retrieved
    by LLM agents without needing to read entire documentation files.
    """

    def __init__(
        self,
        content: str,
        info_type: str,
        source_type: str,
        source_path: str,
        source_name: str,
        source_id: str,
        examples: Optional[List[Dict[str, Any]]] = None,
        source_labels: Optional[List[str]] = None,
        enhanced_content: Optional[str] = None,
        children_count: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        content_embedding: Optional[List[float]] = None,
        **kwargs: Unpack[DocumentationNodeKwargs],
    ):
        # Core semantic content
        self.content = content

        # Metadata
        self.info_type = info_type  # concept, api, pattern, example, usage, architecture, etc.
        self.source_type = source_type  # docstring, comment, readme, markdown, etc.
        self.source_path = source_path  # Original source location
        self.source_labels = source_labels or []  # Labels from source node
        self.source_name = source_name  # Name of the source node for ID generation
        self.source_id = source_id  # Unique identifier for the source node

        # Optional fields
        self.examples = examples or []
        self.enhanced_content = enhanced_content  # For parent nodes
        self.children_count = children_count  # For parent nodes
        self.metadata = metadata  # Additional metadata for tracking fallback scenarios
        self.content_embedding = content_embedding  # Vector embedding of content field

        # Use source_path as path for Node, and source_id@info as name for uniqueness
        # Set layer to documentation for documentation nodes
        super().__init__(
            label=NodeLabels.DOCUMENTATION,
            path=source_path,
            name=f"{source_id}@info",
            level=kwargs.get("level", 0),
            parent=kwargs.get("parent"),
            graph_environment=kwargs.get("graph_environment"),
            layer="documentation",
        )

    @property
    def node_repr_for_identifier(self) -> str:
        """Create a unique identifier representation for this information node."""
        return f"{self.source_id}@info"

    def as_object(self) -> dict[str, Union[str, List[str]]]:
        """Convert to dictionary for database storage."""
        obj = super().as_object()

        # Add information-specific attributes
        obj["attributes"].update(
            {
                "content": self.content,
                "info_type": self.info_type,
                "source_type": self.source_type,
                "source_path": self.source_path,
                "source_labels": self.source_labels,
                "source_node_id": self.source_id,
            }
        )

        # Add optional fields if present
        if self.enhanced_content:
            obj["attributes"]["enhanced_content"] = self.enhanced_content
        if self.children_count is not None:
            obj["attributes"]["children_count"] = self.children_count
        if self.metadata:
            # Ensure metadata is compatible with Neo4j (primitive types only)
            # Convert all values to strings to ensure Neo4j compatibility
            neo4j_metadata = {}
            for key, value in self.metadata.items():
                if value is not None:
                    neo4j_metadata[key] = str(value)
            obj["attributes"]["metadata"] = str(neo4j_metadata)
        if self.content_embedding:
            obj["attributes"]["content_embedding"] = self.content_embedding

        # Add structured data as JSON strings if present
        if self.examples:
            obj["attributes"]["examples"] = str(self.examples)

        return obj

    def mark_cycle(self) -> None:
        """Mark this node as part of a cycle."""
        original_content = self.content
        self.content = f"{original_content}\n\n**Note: This node is part of a circular dependency.**"
        self.metadata = {"has_cycle": "true"}
