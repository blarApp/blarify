"""Test integration relationship creation."""

import pytest
import json
from unittest.mock import Mock

from blarify.graph.relationship.relationship_creator import RelationshipCreator
from blarify.graph.relationship.relationship_type import RelationshipType
from blarify.graph.graph_environment import GraphEnvironment
from blarify.graph.node.integration_node import IntegrationNode
from blarify.graph.node.function_node import FunctionNode


def test_create_integration_sequence_relationships():
    """Test PR → INTEGRATION_SEQUENCE → Commit relationships."""
    graph_env = GraphEnvironment(
        environment="test",
        diff_identifier="0",
        root_path="/test"
    )
    
    pr_node = IntegrationNode(
        source="github",
        source_type="pull_request",
        external_id="123",
        title="Fix bug",
        content="Description",
        timestamp="2024-01-15T10:00:00Z",
        author="john",
        url="https://github.com/repo/pull/123",
        metadata={},
        graph_environment=graph_env
    )
    
    commit_nodes = [
        IntegrationNode(
            source="github",
            source_type="commit",
            external_id="abc123",
            title="First commit",
            content="Message",
            timestamp="2024-01-15T10:00:00Z",
            author="john",
            url="https://github.com/repo/commit/abc123",
            metadata={"pr_number": 123},
            graph_environment=graph_env
        ),
        IntegrationNode(
            source="github",
            source_type="commit",
            external_id="def456",
            title="Second commit",
            content="Message",
            timestamp="2024-01-15T11:00:00Z",
            author="john",
            url="https://github.com/repo/commit/def456",
            metadata={"pr_number": 123},
            graph_environment=graph_env
        )
    ]
    
    relationships = RelationshipCreator.create_integration_sequence_relationships(
        pr_node, commit_nodes
    )
    
    assert len(relationships) == 2
    assert relationships[0].rel_type == RelationshipType.INTEGRATION_SEQUENCE
    assert relationships[0].start_node == pr_node
    assert relationships[0].end_node == commit_nodes[0]
    assert relationships[0].attributes["order"] == 0
    
    assert relationships[1].rel_type == RelationshipType.INTEGRATION_SEQUENCE
    assert relationships[1].start_node == pr_node
    assert relationships[1].end_node == commit_nodes[1]
    assert relationships[1].attributes["order"] == 1


def test_create_modified_by_relationships():
    """Test Code ← MODIFIED_BY ← Commit relationships."""
    graph_env = GraphEnvironment(
        environment="test",
        diff_identifier="0",
        root_path="/test"
    )
    
    commit_node = IntegrationNode(
        source="github",
        source_type="commit",
        external_id="abc123",
        title="Fix auth",
        content="Commit message",
        timestamp="2024-01-15T10:00:00Z",
        author="john",
        url="https://github.com/repo/commit/abc123",
        metadata={"pr_number": 123},
        graph_environment=graph_env
    )
    
    # Mock code nodes
    mock_function_node = Mock()
    mock_function_node.hashed_id = "func_123"
    mock_function_node.name = "authenticate"
    mock_function_node.path = "/test/src/auth.py"
    mock_function_node.label = "FUNCTION"
    
    file_changes = [
        {
            "filename": "src/auth.py",
            "status": "modified",
            "additions": 10,
            "deletions": 5,
            "patch": "@@ -45,7 +45,15 @@\n-old\n+new",
            "line_ranges": [
                {
                    "type": "addition",
                    "start": 45,
                    "end": 60
                }
            ]
        }
    ]
    
    relationships = RelationshipCreator.create_modified_by_relationships(
        commit_node, [mock_function_node], file_changes
    )
    
    assert len(relationships) == 1
    assert relationships[0].rel_type == RelationshipType.MODIFIED_BY
    assert relationships[0].start_node == mock_function_node
    assert relationships[0].end_node == commit_node
    
    # Check relationship properties
    props = relationships[0].attributes
    assert props["lines_added"] == 10
    assert props["lines_deleted"] == 5
    assert props["change_type"] == "modified"
    assert props["file_path"] == "src/auth.py"
    assert props["node_type"] == "FUNCTION"
    assert props["commit_sha"] == "abc123"
    assert props["pr_number"] == 123


def test_hierarchical_modified_by():
    """Test MODIFIED_BY creates relationships at the most specific level."""
    graph_env = GraphEnvironment(
        environment="test",
        diff_identifier="0",
        root_path="/test"
    )
    
    commit_node = IntegrationNode(
        source="github",
        source_type="commit",
        external_id="abc123",
        title="Update function",
        content="Message",
        timestamp="2024-01-15T10:00:00Z",
        author="john",
        url="https://github.com/repo/commit/abc123",
        metadata={},
        graph_environment=graph_env
    )
    
    # Mock hierarchical code nodes
    mock_function = Mock()
    mock_function.hashed_id = "func_123"
    mock_function.name = "process_data"
    mock_function.path = "/test/src/processor.py"
    mock_function.label = "FUNCTION"
    mock_function.start_line = 45
    mock_function.end_line = 60
    
    mock_class = Mock()
    mock_class.hashed_id = "class_456"
    mock_class.name = "DataProcessor"
    mock_class.path = "/test/src/processor.py"
    mock_class.label = "CLASS"
    mock_class.start_line = 10
    mock_class.end_line = 100
    
    mock_file = Mock()
    mock_file.hashed_id = "file_789"
    mock_file.name = "processor.py"
    mock_file.path = "/test/src/processor.py"
    mock_file.label = "FILE"
    
    file_changes = [
        {
            "filename": "src/processor.py",
            "status": "modified",
            "additions": 5,
            "deletions": 2,
            "patch": "@@ -50,2 +50,5 @@",
            "line_ranges": [{"type": "addition", "start": 50, "end": 55}]
        }
    ]
    
    # Should create relationship to most specific node (function)
    relationships = RelationshipCreator.create_modified_by_relationships(
        commit_node, [mock_function, mock_class, mock_file], file_changes
    )
    
    # Should only create one relationship to the most specific node
    assert len(relationships) == 1
    assert relationships[0].start_node == mock_function
    assert relationships[0].attributes["node_specificity_level"] == 1  # Function level


def test_create_affects_relationships():
    """Test Commit → AFFECTS → Workflow relationships."""
    graph_env = GraphEnvironment(
        environment="test",
        diff_identifier="0",
        root_path="/test"
    )
    
    commit_nodes = [
        IntegrationNode(
            source="github",
            source_type="commit",
            external_id="abc123",
            title="Update workflow",
            content="Message",
            timestamp="2024-01-15T10:00:00Z",
            author="john",
            url="https://github.com/repo/commit/abc123",
            metadata={},
            graph_environment=graph_env
        )
    ]
    
    # Mock workflow nodes
    mock_workflow = Mock()
    mock_workflow.hashed_id = "workflow_123"
    mock_workflow.title = "Data Processing Workflow"
    
    relationships = RelationshipCreator.create_affects_relationships(
        commit_nodes, [mock_workflow]
    )
    
    assert len(relationships) == 1
    assert relationships[0].rel_type == RelationshipType.AFFECTS
    assert relationships[0].start_node == commit_nodes[0]
    assert relationships[0].end_node == mock_workflow