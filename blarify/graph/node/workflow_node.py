from typing import List, Optional, Dict, Any
from blarify.graph.node import NodeLabels
from .types.node import Node


class WorkflowNode(Node):
    """Represents a workflow extracted from the codebase.

    This node type is used to store workflow information including entry points,
    endpoints, and execution paths that can be retrieved by LLM agents.
    """

    def __init__(
        self,
        title: str,
        content: str,
        entry_point_id: str,
        entry_point_name: str,
        entry_point_path: str,
        end_point_id: str,
        end_point_name: str,
        end_point_path: str,
        workflow_nodes: List[Dict[str, Any]],
        source_type: str = "workflow_analysis",
        source_path: str = "",
        source_name: str = "",
        source_labels: Optional[List[str]] = None,
        enhanced_content: Optional[str] = None,
        **kwargs,
    ):
        # Core workflow content
        self.title = title
        self.content = content

        # Workflow-specific metadata
        self.entry_point_id = entry_point_id
        self.entry_point_name = entry_point_name
        self.entry_point_path = entry_point_path
        self.end_point_id = end_point_id
        self.end_point_name = end_point_name
        self.end_point_path = end_point_path
        self.workflow_nodes = workflow_nodes or []
        
        # Metadata
        self.source_type = source_type  # workflow_analysis, etc.
        self.source_path = source_path or f"file:///workflows/{entry_point_name.replace(' ', '_').lower()}"
        self.source_labels = source_labels or ["WORKFLOW"]
        self.source_name = source_name or f"workflow_{entry_point_id}_{end_point_id}"
        
        # Optional fields
        self.enhanced_content = enhanced_content
        
        # Use source_path as path for Node, and source_name@workflow as name
        # Set layer to workflows for workflow nodes
        super().__init__(
            label=NodeLabels.WORKFLOW, 
            path=self.source_path,
            name=f"{self.source_name}@workflow",
            level=kwargs.get('level', 0),
            parent=kwargs.get('parent'),
            graph_environment=kwargs.get('graph_environment'),
            layer="workflows"
        )

    
    @property
    def node_repr_for_identifier(self) -> str:
        """Create a unique identifier representation for this workflow node."""
        return f"{self.source_name}@workflow"

    def as_object(self) -> dict:
        """Convert to dictionary for database storage."""
        obj = super().as_object()

        # Add workflow-specific attributes
        obj["attributes"].update(
            {
                "title": self.title,
                "content": self.content,
                "entry_point_id": self.entry_point_id,
                "entry_point_name": self.entry_point_name,
                "entry_point_path": self.entry_point_path,
                "end_point_id": self.end_point_id,
                "end_point_name": self.end_point_name,
                "end_point_path": self.end_point_path,
                "source_type": self.source_type,
                "source_path": self.source_path,
                "source_labels": self.source_labels,
                "steps": len(self.workflow_nodes),
            }
        )
        
        # Add optional fields if present
        if self.enhanced_content:
            obj["attributes"]["enhanced_content"] = self.enhanced_content

        # Add structured data as JSON strings if present
        if self.workflow_nodes:
            obj["attributes"]["workflow_nodes"] = str(self.workflow_nodes)

        return obj

    def get_content_preview(self, max_length: int = 200) -> str:
        """Get a preview of the content for display purposes."""
        if len(self.content) <= max_length:
            return self.content
        return self.content[: max_length - 3] + "..."

    def get_workflow_summary(self) -> str:
        """Get a summary of the workflow."""
        return f"Workflow from {self.entry_point_name} to {self.end_point_name} with {len(self.workflow_nodes)} steps"

    def has_valid_endpoints(self) -> bool:
        """Check if this workflow has valid entry and end points."""
        return bool(self.entry_point_id and self.end_point_id)

    def get_step_count(self) -> int:
        """Get the number of steps in this workflow."""
        return len(self.workflow_nodes)