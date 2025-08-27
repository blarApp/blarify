"""DTO for documentation vector search results."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DocumentationSearchResultDto:
    """Data transfer object for documentation vector search results."""
    
    node_id: str
    title: str
    content: str
    similarity_score: float
    source_path: str
    source_labels: List[str]
    info_type: str
    enhanced_content: Optional[str] = None
    
    def __repr__(self) -> str:
        """String representation of the search result."""
        return (f"DocumentationSearchResult(node_id={self.node_id}, "
                f"title={self.title[:50]}..., score={self.similarity_score:.3f})")