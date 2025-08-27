from typing import Any, Dict
from blarify.graph.graph_environment import GraphEnvironment
from blarify.graph.node.types.integration_node import IntegrationNode


class PullRequestNode(IntegrationNode):
    """Represents a pull request node in the graph."""

    def __init__(
        self,
        external_id: str,
        title: str,
        description: str,
        timestamp: str,
        author: str,
        url: str,
        metadata: Dict[str, Any],
        graph_environment: GraphEnvironment,
    ):
        super().__init__(
            source="github",
            source_type="pull_request",
            external_id=external_id,
            title=title,
            content=description,
            timestamp=timestamp,
            author=author,
            url=url,
            metadata=metadata,
            graph_environment=graph_environment,
        )
