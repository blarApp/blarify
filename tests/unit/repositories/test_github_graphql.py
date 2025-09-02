"""Tests for GitHub GraphQL client functionality."""

import pytest
from unittest.mock import Mock, patch

from blarify.repositories.version_control.github import GitHub


class TestGitHubGraphQLClient:
    """Test GraphQL client methods in GitHub class."""

    def test_graphql_query_construction(self):
        """Test GraphQL query is properly constructed."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo")

        # Test blame query construction
        query, variables = github._build_blame_query("file.py", "main")  # pyright: ignore[reportPrivateUsage]

        # Verify query structure
        assert "blame(range: {startLine: $start, endLine: $end})" in query
        assert "repository(owner:$owner, name:$name)" in query
        assert "object(expression: $expr)" in query

        # Verify variables
        assert variables["owner"] == "owner"
        assert variables["name"] == "repo"
        assert variables["expr"] == "main:file.py"
        assert variables["start"] == 10
        assert variables["end"] == 20

    def test_graphql_response_parsing(self):
        """Test parsing of GraphQL blame response."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo")

        # Mock response with blame data
        response = {
            "data": {
                "repository": {
                    "object": {
                        "blame": {
                            "ranges": [
                                {
                                    "startingLine": 10,
                                    "endingLine": 15,
                                    "age": 30,
                                    "commit": {
                                        "oid": "abc123",
                                        "committedDate": "2024-01-01T00:00:00Z",
                                        "message": "Fix bug in authentication",
                                        "additions": 10,
                                        "deletions": 5,
                                        "author": {
                                            "name": "John Doe",
                                            "email": "john@example.com",
                                            "user": {"login": "johndoe"},
                                        },
                                        "committer": {
                                            "name": "John Doe",
                                            "email": "john@example.com",
                                            "user": {"login": "johndoe"},
                                        },
                                        "url": "https://github.com/owner/repo/commit/abc123",
                                        "associatedPullRequests": {
                                            "nodes": [
                                                {
                                                    "number": 123,
                                                    "title": "Fix authentication",
                                                    "url": "https://github.com/owner/repo/pull/123",
                                                    "author": {"login": "johndoe"},
                                                    "mergedAt": "2024-01-01T01:00:00Z",
                                                    "state": "MERGED",
                                                }
                                            ]
                                        },
                                    },
                                }
                            ]
                        }
                    }
                }
            }
        }

        commits = github._parse_blame_response(response)  # pyright: ignore[reportPrivateUsage]

        assert len(commits) == 1
        assert commits[0]["sha"] == "abc123"
        assert commits[0]["message"] == "Fix bug in authentication"
        assert commits[0]["author"] == "John Doe"
        assert commits[0]["line_ranges"][0]["start"] == 10
        assert commits[0]["line_ranges"][0]["end"] == 15
        assert commits[0]["pr_info"]["number"] == 123

    def test_graphql_error_handling(self):
        """Test handling of GraphQL errors."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo")

        # Test with GraphQL error response
        response = {"errors": [{"message": "Not found"}]}

        with pytest.raises(Exception) as exc_info:
            github._parse_blame_response(response)  # pyright: ignore[reportPrivateUsage]

        assert "GraphQL error" in str(exc_info.value)

    def test_graphql_query_execution(self):
        """Test execution of GraphQL queries."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo")

        # Mock the session.post method
        with patch.object(github.session, "post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {"data": {"repository": {"object": {"blame": {"ranges": []}}}}}
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            # Execute GraphQL query
            github._execute_graphql_query("query { repository { name } }", {"owner": "owner", "name": "repo"})  # pyright: ignore[reportPrivateUsage]

            # Verify the request was made correctly
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == "https://api.github.com/graphql"
            assert "query" in call_args[1]["json"]
            assert "variables" in call_args[1]["json"]

    def test_blame_query_with_default_ref(self):
        """Test blame query defaults to HEAD when ref not specified."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo")

        _, variables = github._build_blame_query("file.py")  # pyright: ignore[reportPrivateUsage]

        assert variables["expr"] == "HEAD:file.py"

    def test_multiple_blame_ranges_consolidation(self):
        """Test that multiple blame ranges for same commit are consolidated."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo")

        response = {
            "data": {
                "repository": {
                    "object": {
                        "blame": {
                            "ranges": [
                                {
                                    "startingLine": 10,
                                    "endingLine": 15,
                                    "commit": {
                                        "oid": "abc123",
                                        "committedDate": "2024-01-01T00:00:00Z",
                                        "message": "Fix bug",
                                        "author": {"name": "John", "email": "john@example.com", "user": None},
                                        "committer": {"name": "John", "email": "john@example.com", "user": None},
                                        "url": "https://github.com/owner/repo/commit/abc123",
                                        "associatedPullRequests": {"nodes": []},
                                    },
                                },
                                {
                                    "startingLine": 20,
                                    "endingLine": 25,
                                    "commit": {
                                        "oid": "abc123",  # Same commit
                                        "committedDate": "2024-01-01T00:00:00Z",
                                        "message": "Fix bug",
                                        "author": {"name": "John", "email": "john@example.com", "user": None},
                                        "committer": {"name": "John", "email": "john@example.com", "user": None},
                                        "url": "https://github.com/owner/repo/commit/abc123",
                                        "associatedPullRequests": {"nodes": []},
                                    },
                                },
                            ]
                        }
                    }
                }
            }
        }

        commits = github._parse_blame_response(response)  # pyright: ignore[reportPrivateUsage]

        # Should consolidate to single commit with multiple line ranges
        assert len(commits) == 1
        assert commits[0]["sha"] == "abc123"
        assert len(commits[0]["line_ranges"]) == 2
        assert commits[0]["line_ranges"][0]["start"] == 10
        assert commits[0]["line_ranges"][0]["end"] == 15
        assert commits[0]["line_ranges"][1]["start"] == 20
        assert commits[0]["line_ranges"][1]["end"] == 25
