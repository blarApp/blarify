"""Test GitHubCreator orchestration class."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List, Any

from blarify.graph.graph_environment import GraphEnvironment
from blarify.graph.node.integration_node import IntegrationNode


def test_github_creator_initialization():
    """Test GitHubCreator initializes correctly."""
    from blarify.integrations.github_creator import GitHubCreator
    
    mock_db_manager = Mock()
    graph_env = GraphEnvironment(
        environment="test",
        diff_identifier="0", 
        root_path="/test"
    )
    
    creator = GitHubCreator(
        db_manager=mock_db_manager,
        graph_environment=graph_env,
        github_token="test_token",
        repo_owner="owner",
        repo_name="repo"
    )
    
    assert creator.db_manager == mock_db_manager
    assert creator.graph_environment == graph_env
    assert creator.github_repo is not None


def test_create_github_integration_with_existing_code():
    """Test integration assumes code graph exists."""
    from blarify.integrations.github_creator import GitHubCreator
    
    mock_db_manager = Mock()
    graph_env = GraphEnvironment(
        environment="test",
        diff_identifier="0",
        root_path="/test"
    )
    
    # Mock existing code nodes in database
    mock_code_nodes = [
        {"node_id": "file_123", "path": "/test/src/auth.py", "label": "FILE"},
        {"node_id": "func_456", "path": "/test/src/auth.py", "label": "FUNCTION"}
    ]
    mock_db_manager.query.return_value = mock_code_nodes
    
    creator = GitHubCreator(
        db_manager=mock_db_manager,
        graph_environment=graph_env,
        github_token="test_token",
        repo_owner="owner",
        repo_name="repo"
    )
    
    # Mock GitHub API responses
    creator.github_repo = Mock()
    creator.github_repo.fetch_pull_requests.return_value = [
        {
            "number": 123,
            "title": "Fix bug",
            "description": "PR description",
            "author": "john",
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T11:00:00Z",
            "merged_at": "2024-01-15T12:00:00Z",
            "state": "closed",
            "url": "https://github.com/owner/repo/pull/123",
            "metadata": {}
        }
    ]
    
    creator.github_repo.fetch_commits.return_value = [
        {
            "sha": "abc123",
            "message": "Fix auth",
            "author": "john",
            "author_email": "john@example.com",
            "timestamp": "2024-01-15T10:00:00Z",
            "url": "https://github.com/owner/repo/commit/abc123",
            "pr_number": 123,
            "metadata": {}
        }
    ]
    
    creator.github_repo.fetch_commit_changes.return_value = [
        {
            "filename": "src/auth.py",
            "status": "modified",
            "additions": 10,
            "deletions": 5,
            "patch": "@@ -1,5 +1,10 @@\n+def new_func():\n+    pass"
        }
    ]
    
    result = creator.create_github_integration(pr_limit=10, save_to_database=False)
    
    assert result.total_prs == 1
    assert result.total_commits >= 1
    assert len(result.pr_nodes) == 1
    assert len(result.commit_nodes) >= 1


def test_process_pr_with_commits():
    """Test processing a PR creates correct nodes and relationships."""
    from blarify.integrations.github_creator import GitHubCreator
    
    mock_db_manager = Mock()
    graph_env = GraphEnvironment(
        environment="test",
        diff_identifier="0",
        root_path="/test"
    )
    
    creator = GitHubCreator(
        db_manager=mock_db_manager,
        graph_environment=graph_env,
        github_token="test",
        repo_owner="owner",
        repo_name="repo"
    )
    
    pr_data = {
        "number": 123,
        "title": "Fix bug",
        "description": "Description",
        "author": "john",
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-15T11:00:00Z",
        "merged_at": None,
        "state": "open",
        "url": "https://github.com/owner/repo/pull/123",
        "metadata": {}
    }
    
    commits_data = [
        {
            "sha": "abc123",
            "message": "Fix issue",
            "author": "john",
            "author_email": "john@example.com",
            "timestamp": "2024-01-15T10:00:00Z",
            "url": "https://github.com/owner/repo/commit/abc123",
            "pr_number": 123,
            "metadata": {}
        }
    ]
    
    creator.github_repo = Mock()
    creator.github_repo.fetch_commits.return_value = commits_data
    
    pr_node, commit_nodes = creator._process_pr(pr_data)
    
    assert pr_node.source_type == "pull_request"
    assert pr_node.external_id == "123"
    assert pr_node.title == "Fix bug"
    assert len(commit_nodes) == 1
    assert commit_nodes[0].source_type == "commit"
    assert commit_nodes[0].external_id == "abc123"


def test_map_commits_to_existing_code():
    """Test mapping commits to pre-existing code nodes."""
    from blarify.integrations.github_creator import GitHubCreator
    
    mock_db_manager = Mock()
    graph_env = GraphEnvironment(
        environment="test",
        diff_identifier="0",
        root_path="/test"
    )
    
    creator = GitHubCreator(
        db_manager=mock_db_manager,
        graph_environment=graph_env,
        github_token="test",
        repo_owner="owner",
        repo_name="repo"
    )
    
    # Create a commit node
    commit_node = IntegrationNode(
        source="github",
        source_type="commit",
        external_id="abc123",
        title="Fix auth",
        content="Commit message",
        timestamp="2024-01-15T10:00:00Z",
        author="john",
        url="https://github.com/owner/repo/commit/abc123",
        metadata={"pr_number": 123},
        graph_environment=graph_env
    )
    
    # Mock commit changes
    file_changes = [
        {
            "filename": "src/auth.py",
            "status": "modified",
            "additions": 10,
            "deletions": 5,
            "patch": "@@ -45,7 +45,15 @@\n-old\n+new"
        }
    ]
    
    creator.github_repo = Mock()
    creator.github_repo.fetch_commit_changes.return_value = file_changes
    
    # Mock finding code nodes
    mock_db_manager.query.return_value = [
        {
            "node_id": "func_123",
            "name": "authenticate",
            "label": "FUNCTION",
            "path": "/test/src/auth.py",
            "start_line": 40,
            "end_line": 50
        }
    ]
    
    relationships = creator._map_commits_to_code([commit_node])
    
    assert len(relationships) > 0
    # Should create MODIFIED_BY relationship from code to commit


def test_save_to_database_workflow():
    """Test saving nodes and relationships to database."""
    from blarify.integrations.github_creator import GitHubCreator
    
    mock_db_manager = Mock()
    graph_env = GraphEnvironment(
        environment="test",
        diff_identifier="0",
        root_path="/test"
    )
    
    creator = GitHubCreator(
        db_manager=mock_db_manager,
        graph_environment=graph_env,
        github_token="test",
        repo_owner="owner",
        repo_name="repo"
    )
    
    # Create test nodes
    pr_node = IntegrationNode(
        source="github",
        source_type="pull_request",
        external_id="123",
        title="Test PR",
        content="Description",
        timestamp="2024-01-15T10:00:00Z",
        author="john",
        url="https://github.com/owner/repo/pull/123",
        metadata={},
        graph_environment=graph_env
    )
    
    commit_node = IntegrationNode(
        source="github",
        source_type="commit",
        external_id="abc123",
        title="Test commit",
        content="Message",
        timestamp="2024-01-15T10:00:00Z",
        author="john",
        url="https://github.com/owner/repo/commit/abc123",
        metadata={"pr_number": 123},
        graph_environment=graph_env
    )
    
    # Mock saving
    creator._save_to_database([pr_node, commit_node], [])
    
    # Verify save_graph was called
    mock_db_manager.save_graph.assert_called_once()
    
    # Check that nodes were serialized
    call_args = mock_db_manager.save_graph.call_args
    nodes_arg = call_args[0][0]
    assert len(nodes_arg) == 2


def test_github_creator_error_handling():
    """Test error handling in GitHub creator."""
    from blarify.integrations.github_creator import GitHubCreator
    
    mock_db_manager = Mock()
    graph_env = GraphEnvironment(
        environment="test",
        diff_identifier="0",
        root_path="/test"
    )
    
    creator = GitHubCreator(
        db_manager=mock_db_manager,
        graph_environment=graph_env,
        github_token="test",
        repo_owner="owner",
        repo_name="repo"
    )
    
    # Mock GitHub API failure
    creator.github_repo = Mock()
    creator.github_repo.fetch_pull_requests.side_effect = Exception("API Error")
    
    # Should handle error gracefully
    result = creator.create_github_integration(pr_limit=10, save_to_database=False)
    
    assert result.total_prs == 0
    assert result.error is not None