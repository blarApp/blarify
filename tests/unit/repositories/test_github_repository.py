"""Test GitHub repository implementation."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from blarify.repositories.version_control.github import GitHub


def test_github_initialization():
    """Test GitHub repository initializes with correct parameters."""
    github = GitHub(token="test_token", repo_owner="owner", repo_name="repo")
    assert github.token == "test_token"
    assert github.repo_owner == "owner"
    assert github.repo_name == "repo"
    assert github.base_url == "https://api.github.com"


def test_github_initialization_with_env_token():
    """Test GitHub uses environment variable for token if not provided."""
    with patch.dict('os.environ', {'GITHUB_TOKEN': 'env_token'}):
        github = GitHub(repo_owner="owner", repo_name="repo")
        assert github.token == "env_token"


def test_github_headers_setup():
    """Test GitHub sets up correct headers."""
    github = GitHub(token="test_token", repo_owner="owner", repo_name="repo")
    assert github.session.headers["Authorization"] == "token test_token"
    assert github.session.headers["Accept"] == "application/vnd.github.v3+json"
    assert github.session.headers["User-Agent"] == "Blarify-GitHub-Integration"


@patch('blarify.repositories.version_control.github.requests.Session')
def test_fetch_pull_requests(mock_session_class):
    """Test fetching PRs with pagination."""
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session
    
    github = GitHub(token="test", repo_owner="owner", repo_name="repo")
    github.session = mock_session
    
    # Mock response
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "number": 123,
            "title": "Fix bug",
            "body": "Description",
            "user": {"login": "john"},
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T11:00:00Z",
            "merged_at": "2024-01-15T12:00:00Z",
            "state": "closed",
            "html_url": "https://github.com/owner/repo/pull/123",
            "head": {"sha": "abc123"},
            "base": {"sha": "def456"},
            "labels": [{"name": "bug"}]
        }
    ]
    
    github._make_request = Mock(return_value=mock_response.json())
    
    prs = github.fetch_pull_requests(limit=10)
    
    assert len(prs) == 1
    assert prs[0]["number"] == 123
    assert prs[0]["title"] == "Fix bug"
    assert prs[0]["author"] == "john"
    assert prs[0]["metadata"]["labels"] == ["bug"]


def test_fetch_commits_for_pr():
    """Test fetching commits for a specific PR."""
    github = GitHub(token="test", repo_owner="owner", repo_name="repo")
    
    mock_response = [
        {
            "sha": "abc123",
            "commit": {
                "message": "Fix auth logic",
                "author": {
                    "name": "John Doe",
                    "email": "john@example.com",
                    "date": "2024-01-15T10:00:00Z"
                },
                "tree": {"sha": "tree123"}
            },
            "html_url": "https://github.com/owner/repo/commit/abc123",
            "parents": [{"sha": "parent1"}]
        }
    ]
    
    github._make_request = Mock(return_value=mock_response)
    
    commits = github.fetch_commits(pr_number=123)
    
    assert len(commits) == 1
    assert commits[0]["sha"] == "abc123"
    assert commits[0]["message"] == "Fix auth logic"
    assert commits[0]["author"] == "John Doe"
    assert commits[0]["pr_number"] == 123


def test_fetch_commit_changes():
    """Test fetching file changes for a commit."""
    github = GitHub(token="test", repo_owner="owner", repo_name="repo")
    
    mock_response = {
        "files": [
            {
                "filename": "src/auth/login.py",
                "status": "modified",
                "additions": 15,
                "deletions": 3,
                "patch": "@@ -45,7 +45,15 @@\n-old\n+new"
            }
        ]
    }
    
    github._make_request = Mock(return_value=mock_response)
    
    changes = github.fetch_commit_changes("abc123")
    
    assert len(changes) == 1
    assert changes[0]["filename"] == "src/auth/login.py"
    assert changes[0]["status"] == "modified"
    assert changes[0]["additions"] == 15
    assert changes[0]["deletions"] == 3


def test_rate_limiting_handling():
    """Test graceful handling of rate limits."""
    github = GitHub(token="test", repo_owner="owner", repo_name="repo")
    
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.headers = {'X-RateLimit-Reset': '1234567890'}
    mock_response.raise_for_status.side_effect = Exception("Rate limit")
    
    github.session.request = Mock(return_value=mock_response)
    
    with pytest.raises(Exception) as exc_info:
        github._make_request("GET", "pulls")
    
    assert "rate limit exceeded" in str(exc_info.value).lower()


def test_test_connection_success():
    """Test successful connection test."""
    github = GitHub(token="test", repo_owner="owner", repo_name="repo")
    
    github.get_repository_info = Mock(return_value={"name": "repo"})
    
    assert github.test_connection() is True


def test_test_connection_failure():
    """Test failed connection test."""
    github = GitHub(token="test", repo_owner="owner", repo_name="repo")
    
    github.get_repository_info = Mock(side_effect=Exception("Connection failed"))
    
    assert github.test_connection() is False


def test_get_repository_info():
    """Test getting repository information."""
    github = GitHub(token="test", repo_owner="owner", repo_name="repo")
    
    mock_response = Mock()
    mock_response.json.return_value = {
        "name": "repo",
        "owner": {"login": "owner"},
        "html_url": "https://github.com/owner/repo",
        "default_branch": "main",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-15T00:00:00Z",
        "description": "Test repo",
        "language": "Python",
        "size": 1000,
        "stargazers_count": 10,
        "forks_count": 5,
        "private": False
    }
    mock_response.raise_for_status = Mock()
    
    github.session.get = Mock(return_value=mock_response)
    
    info = github.get_repository_info()
    
    assert info["name"] == "repo"
    assert info["owner"] == "owner"
    assert info["default_branch"] == "main"
    assert info["metadata"]["language"] == "Python"