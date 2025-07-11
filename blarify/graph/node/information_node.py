from typing import List, Optional, Dict, Any
from blarify.graph.node import NodeLabels
from .types.definition_node import DefinitionNode


class InformationNode(DefinitionNode):
    """Represents a semantic piece of documentation/knowledge extracted from the codebase.
    
    This node type is used to store atomic pieces of information that can be retrieved
    by LLM agents without needing to read entire documentation files.
    """
    
    def __init__(
        self,
        title: str,
        content: str,
        info_type: str,
        source_type: str,
        source_path: str,
        examples: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ):
        # Core semantic content
        self.title = title
        self.content = content
        
        # Metadata
        self.info_type = info_type  # concept, api, pattern, example, usage, architecture, etc.
        self.source_type = source_type  # docstring, comment, readme, markdown, etc.
        self.source_path = source_path  # Original source location
        
        # Optional structured data
        self.examples = examples or []
        
        # Set layer to documentation for information nodes
        kwargs['layer'] = 'documentation'
        super().__init__(label=NodeLabels.INFORMATION, **kwargs)
    
    @property
    def node_repr_for_identifier(self) -> str:
        """Create a unique identifier representation for this information node."""
        return f"@{self.info_type}:{self.title}"
    
    def as_object(self) -> dict:
        """Convert to dictionary for database storage."""
        obj = super().as_object()
        
        # Add information-specific attributes
        obj["attributes"].update({
            "title": self.title,
            "content": self.content,
            "info_type": self.info_type,
            "source_type": self.source_type,
            "source_path": self.source_path,
        })
        
        # Add structured data as JSON strings if present
        if self.examples:
            obj["attributes"]["examples"] = str(self.examples)
        
        return obj
    
    def get_content_preview(self, max_length: int = 200) -> str:
        """Get a preview of the content for display purposes."""
        if len(self.content) <= max_length:
            return self.content
        return self.content[:max_length-3] + "..."
    
    def is_api_documentation(self) -> bool:
        """Check if this is API documentation."""
        return self.info_type in ["api", "function", "method", "class"]
    
    def has_examples(self) -> bool:
        """Check if this node contains code examples."""
        return len(self.examples) > 0