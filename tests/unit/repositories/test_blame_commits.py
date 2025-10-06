"""Tests for GitHub blame-based commit discovery."""

from unittest.mock import patch
from typing import List

from blarify.repositories.graph_db_manager.dtos.code_node_dto import CodeNodeDto
from blarify.repositories.version_control.dtos.blame_commit_dto import BlameCommitDto
from blarify.repositories.version_control.dtos.blame_line_range_dto import BlameLineRangeDto
from blarify.repositories.version_control.github import GitHub


class TestBlameCommitDiscovery:
    """Test blame-based commit discovery methods."""

    def test_blame_commits_for_range(self):
        """Test fetching commits that touched specific lines."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo", ref="HEAD")

        # Mock GraphQL response
        mock_response = {
            "data": {
                "repository": {
                    "object": {
                        "blame": {
                            "ranges": [
                                {
                                    "startingLine": 10,
                                    "endingLine": 20,
                                    "commit": {
                                        "oid": "abc123",
                                        "committedDate": "2024-01-01T00:00:00Z",
                                        "message": "Implement authentication",
                                        "additions": 15,
                                        "deletions": 5,
                                        "author": {
                                            "name": "Alice",
                                            "email": "alice@example.com",
                                            "user": {"login": "alice"},
                                        },
                                        "committer": {
                                            "name": "Alice",
                                            "email": "alice@example.com",
                                            "user": {"login": "alice"},
                                        },
                                        "url": "https://github.com/owner/repo/commit/abc123",
                                        "associatedPullRequests": {"nodes": []},
                                    },
                                },
                                {
                                    "startingLine": 21,
                                    "endingLine": 50,
                                    "commit": {
                                        "oid": "def456",
                                        "committedDate": "2024-01-02T00:00:00Z",
                                        "message": "Add validation",
                                        "additions": 30,
                                        "deletions": 10,
                                        "author": {"name": "Bob", "email": "bob@example.com", "user": {"login": "bob"}},
                                        "committer": {
                                            "name": "Bob",
                                            "email": "bob@example.com",
                                            "user": {"login": "bob"},
                                        },
                                        "url": "https://github.com/owner/repo/commit/def456",
                                        "associatedPullRequests": {"nodes": []},
                                    },
                                },
                            ]
                        }
                    }
                }
            }
        }

        with (
            patch.object(github, "_execute_graphql_query", return_value=mock_response),
            patch.object(
                github,
                "_fetch_commit_details_batch",
                return_value={
                    "abc123": {
                        "message": "Implement authentication",
                        "author": "Alice",
                        "author_email": "alice@example.com",
                        "author_login": "alice",
                        "timestamp": "2024-01-01T00:00:00Z",
                        "url": "https://github.com/owner/repo/commit/abc123",
                        "additions": 15,
                        "deletions": 5,
                        "pr_info": None,
                    },
                    "def456": {
                        "message": "Add validation",
                        "author": "Bob",
                        "author_email": "bob@example.com",
                        "author_login": "bob",
                        "timestamp": "2024-01-02T00:00:00Z",
                        "url": "https://github.com/owner/repo/commit/def456",
                        "additions": 30,
                        "deletions": 10,
                        "pr_info": None,
                    },
                },
            ),
        ):
            commits = github.blame_commits_for_range(file_path="src/main.py", start_line=10, end_line=50)

        assert len(commits) == 2
        assert all(commit.sha for commit in commits)
        assert all(commit.line_ranges for commit in commits)
        assert commits[0].sha == "abc123"
        assert commits[0].author == "Alice"
        assert commits[1].sha == "def456"
        assert commits[1].author == "Bob"

    def test_blame_with_associated_prs(self):
        """Test that blame results include PR information."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo", ref="HEAD")

        mock_response = {
            "data": {
                "repository": {
                    "object": {
                        "blame": {
                            "ranges": [
                                {
                                    "startingLine": 1,
                                    "endingLine": 10,
                                    "commit": {
                                        "oid": "commit1",
                                        "committedDate": "2024-01-01T00:00:00Z",
                                        "message": "Feature implementation",
                                        "author": {"name": "Dev", "email": "dev@example.com", "user": {"login": "dev"}},
                                        "committer": {
                                            "name": "Dev",
                                            "email": "dev@example.com",
                                            "user": {"login": "dev"},
                                        },
                                        "url": "https://github.com/owner/repo/commit/commit1",
                                        "associatedPullRequests": {
                                            "nodes": [
                                                {
                                                    "number": 42,
                                                    "title": "Add new feature",
                                                    "url": "https://github.com/owner/repo/pull/42",
                                                    "author": {"login": "dev"},
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

        with (
            patch.object(github, "_execute_graphql_query", return_value=mock_response),
            patch.object(
                github,
                "_fetch_commit_details_batch",
                return_value={
                    "commit1": {
                        "message": "Feature implementation",
                        "author": "Dev",
                        "author_email": "dev@example.com",
                        "author_login": "dev",
                        "timestamp": "2024-01-01T00:00:00Z",
                        "url": "https://github.com/owner/repo/commit/commit1",
                        "additions": None,
                        "deletions": None,
                        "pr_info": {
                            "number": 42,
                            "title": "Add new feature",
                            "url": "https://github.com/owner/repo/pull/42",
                            "author": "dev",
                            "mergedAt": "2024-01-01T01:00:00Z",
                            "state": "MERGED",
                            "bodyText": "",
                        },
                    }
                },
            ),
        ):
            commits = github.blame_commits_for_range("src/feature.py", 1, 10)

        assert len(commits) == 1
        assert commits[0].pr_info is not None
        assert commits[0].pr_info.number == 42
        assert commits[0].pr_info.title == "Add new feature"

    def test_blame_caching(self):
        """Test that identical blame queries use cache."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo", ref="HEAD")

        mock_response = {
            "data": {
                "repository": {
                    "object": {
                        "blame": {
                            "ranges": [
                                {
                                    "startingLine": 1,
                                    "endingLine": 5,
                                    "commit": {
                                        "oid": "cached",
                                        "committedDate": "2024-01-01T00:00:00Z",
                                        "message": "Cached commit",
                                        "author": {"name": "Cache", "email": "cache@example.com", "user": None},
                                        "committer": {"name": "Cache", "email": "cache@example.com", "user": None},
                                        "url": "https://github.com/owner/repo/commit/cached",
                                        "associatedPullRequests": {"nodes": []},
                                    },
                                }
                            ]
                        }
                    }
                }
            }
        }

        with (
            patch.object(github, "_execute_graphql_query", return_value=mock_response) as mock_execute,
            patch.object(
                github,
                "_fetch_commit_details_batch",
                return_value={
                    "cached": {
                        "message": "Cached commit",
                        "author": "Cache",
                        "author_email": "cache@example.com",
                        "author_login": None,
                        "timestamp": "2024-01-01T00:00:00Z",
                        "url": "https://github.com/owner/repo/commit/cached",
                        "additions": None,
                        "deletions": None,
                        "pr_info": None,
                    }
                },
            ) as mock_fetch_details,
        ):
            # First call
            commits1 = github.blame_commits_for_range("file.py", 1, 5)
            # Second identical call should use cache
            commits2 = github.blame_commits_for_range("file.py", 1, 5)

            # GraphQL and detail fetch should run only once due to caching
            mock_execute.assert_called_once()
            mock_fetch_details.assert_called_once()

            # Results should be identical
            assert commits1 == commits2

    def test_blame_commits_for_nodes(self):
        """Test batch processing of multiple nodes."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo")

        nodes = [
            CodeNodeDto(
                id="node1",
                name="Node1",
                label="FUNCTION",
                path="src/main.py",
                start_line=9,
                end_line=19,
            ),
            CodeNodeDto(
                id="node2",
                name="Node2",
                label="FUNCTION",
                path="src/main.py",
                start_line=29,
                end_line=39,
            ),
            CodeNodeDto(
                id="node3",
                name="Node3",
                label="FUNCTION",
                path="src/utils.py",
                start_line=0,
                end_line=14,
            ),
        ]

        # Mock different responses for different files
        def mock_blame_response(file_path: str, start_line: int, end_line: int) -> List[BlameCommitDto]:
            if file_path == "src/main.py":
                return [
                    BlameCommitDto(
                        sha="commit1",
                        message="Main change",
                        author="Alice",
                        author_email=None,
                        author_login=None,
                        timestamp="2024-01-02T00:00:00Z",
                        url="https://github.com/owner/repo/commit/commit1",
                        additions=None,
                        deletions=None,
                        line_ranges=[BlameLineRangeDto(start=start_line, end=end_line)],
                        pr_info=None,
                    )
                ]
            else:
                return [
                    BlameCommitDto(
                        sha="commit2",
                        message="Utils change",
                        author="Bob",
                        author_email=None,
                        author_login=None,
                        timestamp="2024-01-03T00:00:00Z",
                        url="https://github.com/owner/repo/commit/commit2",
                        additions=None,
                        deletions=None,
                        line_ranges=[BlameLineRangeDto(start=1, end=15)],
                        pr_info=None,
                    )
                ]

        with patch.object(github, "blame_commits_for_range", side_effect=mock_blame_response):
            results = github.blame_commits_for_nodes(nodes)

        assert "node1" in results
        assert "node2" in results
        assert "node3" in results
        assert results["node1"][0].sha == "commit1"
        assert results["node2"][0].sha == "commit1"
        assert results["node3"][0].sha == "commit2"

    def test_merge_line_ranges_optimization(self):
        """Test that overlapping line ranges are merged for efficiency."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo")

        nodes = [
            CodeNodeDto(id="node1", name="Node1", label="FUNCTION", path="file.py", start_line=9, end_line=19),
            CodeNodeDto(id="node2", name="Node2", label="FUNCTION", path="file.py", start_line=14, end_line=24),
            CodeNodeDto(id="node3", name="Node3", label="FUNCTION", path="file.py", start_line=20, end_line=29),
        ]

        merged = github._merge_line_ranges(nodes)  # pyright: ignore[reportPrivateUsage]

        # Should merge into a single range covering lines 10-30
        assert len(merged) == 1
        assert merged[0]["start"] == 10
        assert merged[0]["end"] == 30
        assert len(merged[0]["nodes"]) == 3

    def test_ranges_overlap_detection(self):
        """Test detection of overlapping line ranges."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo")

        # Test overlapping ranges
        assert github._ranges_overlap([{"start": 10, "end": 20}], 15, 25) is True  # pyright: ignore[reportPrivateUsage]

        # Test non-overlapping ranges
        assert github._ranges_overlap([{"start": 10, "end": 20}], 25, 30) is False  # pyright: ignore[reportPrivateUsage]

        # Test exact match
        assert github._ranges_overlap([{"start": 10, "end": 20}], 10, 20) is True  # pyright: ignore[reportPrivateUsage]

        # Test contained range
        assert github._ranges_overlap([{"start": 10, "end": 30}], 15, 25) is True  # pyright: ignore[reportPrivateUsage]
