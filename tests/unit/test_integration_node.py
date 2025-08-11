"""Unit tests for IntegrationNode class."""

import pytest
from blarify.graph.node.integration_node import IntegrationNode
from blarify.graph.node.types.node_labels import NodeLabels
from blarify.graph.environment.graph_environment import GraphEnvironment


class TestIntegrationNode:
    """Unit tests for IntegrationNode."""
    
    @pytest.fixture
    def graph_environment(self):
        """Create a test graph environment."""
        return GraphEnvironment("test_entity", "test_repo", "/test/path")
    
    def test_integration_node_creation_pr(self, graph_environment):
        """Test creating an IntegrationNode for a pull request."""
        node = IntegrationNode(
            source="github",
            source_type="pull_request",
            external_id="123",
            title="Fix authentication bug",
            content="This PR fixes the authentication bug in the login module.",
            timestamp="2024-01-15T10:30:00Z",
            author="john_doe",
            url="https://github.com/repo/pull/123",
            graph_environment=graph_environment,
            metadata={"state": "open", "merged": False}
        )
        
        assert node.path == "integration://github/pull_request/123"
        assert node.label == NodeLabels.INTEGRATION
        assert node.source == "github"
        assert node.source_type == "pull_request"
        assert node.external_id == "123"
        assert node.title == "Fix authentication bug"
        assert node.author == "john_doe"
        assert node.layer == "integrations"
        assert node.metadata["state"] == "open"
    
    def test_integration_node_creation_commit(self, graph_environment):
        """Test creating an IntegrationNode for a commit."""
        node = IntegrationNode(
            source="github",
            source_type="commit",
            external_id="abc123def456",
            title="Fix: resolve authentication issue",
            content="Fixed the authentication bug by updating the token validation logic.",
            timestamp="2024-01-15T10:35:00Z",
            author="jane_smith",
            url="https://github.com/repo/commit/abc123def456",
            graph_environment=graph_environment,
            metadata={"sha": "abc123def456", "additions": 10, "deletions": 5}
        )
        
        assert node.path == "integration://github/commit/abc123def456"
        assert node.label == NodeLabels.INTEGRATION
        assert node.source == "github"
        assert node.source_type == "commit"
        assert node.external_id == "abc123def456"
        assert node.title == "Fix: resolve authentication issue"
        assert node.author == "jane_smith"
        assert node.metadata["additions"] == 10
        assert node.metadata["deletions"] == 5
    
    def test_integration_node_as_object(self, graph_environment):
        """Test converting IntegrationNode to dictionary representation."""
        node = IntegrationNode(
            source="github",
            source_type="pull_request",
            external_id="456",
            title="Add new feature",
            content="This PR adds a new feature to the system.",
            timestamp="2024-01-16T14:20:00Z",
            author="alice_dev",
            url="https://github.com/repo/pull/456",
            graph_environment=graph_environment,
            metadata={"state": "merged", "merged_at": "2024-01-16T15:00:00Z"}
        )
        
        obj = node.as_object()
        
        assert obj["source"] == "github"
        assert obj["source_type"] == "pull_request"
        assert obj["external_id"] == "456"
        assert obj["title"] == "Add new feature"
        assert obj["content"] == "This PR adds a new feature to the system."
        assert obj["timestamp"] == "2024-01-16T14:20:00Z"
        assert obj["author"] == "alice_dev"
        assert obj["url"] == "https://github.com/repo/pull/456"
        assert obj["layer"] == "integrations"
        assert obj["metadata"]["state"] == "merged"
        assert obj["path"] == "integration://github/pull_request/456"
    
    def test_integration_node_display_name_pr(self, graph_environment):
        """Test display name for PR IntegrationNode."""
        node = IntegrationNode(
            source="github",
            source_type="pull_request",
            external_id="789",
            title="Update documentation",
            content="",
            timestamp="2024-01-17T09:00:00Z",
            author="bob_writer",
            url="https://github.com/repo/pull/789",
            graph_environment=graph_environment
        )
        
        display_name = node.get_display_name()
        assert display_name == "PR #789: Update documentation"
    
    def test_integration_node_display_name_commit(self, graph_environment):
        """Test display name for commit IntegrationNode."""
        node = IntegrationNode(
            source="github",
            source_type="commit",
            external_id="1234567890abcdef",
            title="feat: add logging",
            content="",
            timestamp="2024-01-17T10:00:00Z",
            author="charlie_dev",
            url="https://github.com/repo/commit/1234567890abcdef",
            graph_environment=graph_environment
        )
        
        display_name = node.get_display_name()
        assert display_name == "Commit 1234567: feat: add logging"
    
    def test_integration_node_future_extensibility(self, graph_environment):
        """Test that IntegrationNode supports other source types for future extensibility."""
        # Test with Sentry error integration
        sentry_node = IntegrationNode(
            source="sentry",
            source_type="error",
            external_id="ERROR-12345",
            title="TypeError in authentication module",
            content="Stack trace: ...",
            timestamp="2024-01-17T11:00:00Z",
            author="system",
            url="https://sentry.io/errors/12345",
            graph_environment=graph_environment,
            metadata={"severity": "critical", "affected_users": 150}
        )
        
        assert sentry_node.path == "integration://sentry/error/ERROR-12345"
        assert sentry_node.source == "sentry"
        assert sentry_node.source_type == "error"
        
        # Test with DataDog metric integration
        datadog_node = IntegrationNode(
            source="datadog",
            source_type="metric",
            external_id="cpu_spike_001",
            title="CPU usage spike detected",
            content="CPU usage exceeded 90% for 5 minutes",
            timestamp="2024-01-17T12:00:00Z",
            author="monitoring",
            url="https://app.datadoghq.com/metrics/cpu_spike_001",
            graph_environment=graph_environment,
            metadata={"metric_value": 95.5, "duration_minutes": 5}
        )
        
        assert datadog_node.path == "integration://datadog/metric/cpu_spike_001"
        assert datadog_node.source == "datadog"
        assert datadog_node.source_type == "metric"