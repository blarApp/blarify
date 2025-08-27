"""Test IntegrationNode creation and serialization."""

from blarify.graph.graph_environment import GraphEnvironment
from blarify.graph.node.types.node_labels import NodeLabels


def test_integration_node_creation():
    """Test creating IntegrationNode with required fields."""
    from blarify.graph.node.types.integration_node import IntegrationNode

    graph_env = GraphEnvironment(environment="test", diff_identifier="0", root_path="/test")
    node = IntegrationNode(
        source="github",
        source_type="pull_request",
        external_id="123",
        title="Fix bug",
        content="Description",
        timestamp="2024-01-01T00:00:00Z",
        author="john",
        url="https://github.com/repo/pull/123",
        metadata={},
        graph_environment=graph_env,
    )

    assert node.path == "integration://github/pull_request/123"
    assert node.label == NodeLabels.INTEGRATION
    assert node.source == "github"
    assert node.source_type == "pull_request"
    assert node.external_id == "123"
    assert node.title == "Fix bug"
    assert node.author == "john"


def test_commit_node_creation():
    """Test creating commit-specific integration node."""
    from blarify.graph.node.types.integration_node import IntegrationNode

    graph_env = GraphEnvironment(environment="test", diff_identifier="0", root_path="/test")
    node = IntegrationNode(
        source="github",
        source_type="commit",
        external_id="abc123",
        title="Fix auth logic",
        content="Commit message body",
        timestamp="2024-01-01T00:00:00Z",
        author="jane",
        url="https://github.com/repo/commit/abc123",
        metadata={"pr_number": 123},
        graph_environment=graph_env,
    )

    assert node.path == "integration://github/commit/abc123"
    assert node.source_type == "commit"
    assert node.metadata["pr_number"] == 123


def test_integration_node_serialization():
    """Test IntegrationNode serialization to object."""
    from blarify.graph.node.types.integration_node import IntegrationNode

    graph_env = GraphEnvironment(environment="test", diff_identifier="0", root_path="/test")
    node = IntegrationNode(
        source="github",
        source_type="pull_request",
        external_id="456",
        title="Add feature",
        content="PR description",
        timestamp="2024-01-15T10:00:00Z",
        author="alice",
        url="https://github.com/repo/pull/456",
        metadata={"labels": ["feature", "enhancement"]},
        graph_environment=graph_env,
    )

    obj = node.as_object()

    assert obj["attributes"]["source"] == "github"
    assert obj["attributes"]["source_type"] == "pull_request"
    assert obj["attributes"]["external_id"] == "456"
    assert obj["attributes"]["title"] == "Add feature"
    assert obj["attributes"]["author"] == "alice"
    assert obj["attributes"]["path"] == "integration://github/pull_request/456"
    assert obj["attributes"]["label"] == "INTEGRATION"
    assert obj["attributes"]["layer"] == "integrations"
    assert "labels" in obj["attributes"]["metadata"]


def test_integration_node_with_different_sources():
    """Test IntegrationNode supports different source systems."""
    from blarify.graph.node.types.integration_node import IntegrationNode

    graph_env = GraphEnvironment(environment="test", diff_identifier="0", root_path="/test")

    # Sentry integration node
    sentry_node = IntegrationNode(
        source="sentry",
        source_type="error",
        external_id="12345",
        title="TypeError in user authentication",
        content="Stack trace...",
        timestamp="2024-01-15T10:00:00Z",
        author="system",
        url="https://sentry.io/organizations/org/issues/12345",
        metadata={"severity": "error", "count": 10},
        graph_environment=graph_env,
    )

    assert sentry_node.path == "integration://sentry/error/12345"
    assert sentry_node.source == "sentry"

    # DataDog integration node
    datadog_node = IntegrationNode(
        source="datadog",
        source_type="metric",
        external_id="cpu_spike_001",
        title="CPU usage spike detected",
        content="CPU usage exceeded 90%",
        timestamp="2024-01-15T10:00:00Z",
        author="monitoring",
        url="https://app.datadoghq.com/metric/cpu_spike_001",
        metadata={"threshold": 90, "duration": 300},
        graph_environment=graph_env,
    )

    assert datadog_node.path == "integration://datadog/metric/cpu_spike_001"
    assert datadog_node.source == "datadog"


def test_integration_node_hierarchy():
    """Test IntegrationNode with parent-child relationships."""
    from blarify.graph.node.types.integration_node import IntegrationNode

    graph_env = GraphEnvironment(environment="test", diff_identifier="0", root_path="/test")

    # PR as parent
    pr_node = IntegrationNode(
        source="github",
        source_type="pull_request",
        external_id="789",
        title="Refactor authentication",
        content="PR description",
        timestamp="2024-01-01T00:00:00Z",
        author="bob",
        url="https://github.com/repo/pull/789",
        metadata={},
        graph_environment=graph_env,
        level=0,
    )

    # Commit as child of PR
    commit_node = IntegrationNode(
        source="github",
        source_type="commit",
        external_id="def456",
        title="Update auth module",
        content="Commit message",
        timestamp="2024-01-01T01:00:00Z",
        author="bob",
        url="https://github.com/repo/commit/def456",
        metadata={"pr_number": 789},
        graph_environment=graph_env,
        level=1,
        parent=pr_node,
    )

    assert commit_node.level == 1
    assert commit_node.parent == pr_node
