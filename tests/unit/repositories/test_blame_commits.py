"""Tests for GitHub blame-based commit discovery."""

from unittest.mock import patch
from typing import Dict, Any, List

from blarify.repositories.version_control.github import GitHub


class TestBlameCommitDiscovery:
    """Test blame-based commit discovery methods."""
    
    def test_blame_commits_for_range(self):
        """Test fetching commits that touched specific lines."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo")
        
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
                                        "author": {"name": "Alice", "email": "alice@example.com", "user": {"login": "alice"}},
                                        "committer": {"name": "Alice", "email": "alice@example.com", "user": {"login": "alice"}},
                                        "url": "https://github.com/owner/repo/commit/abc123",
                                        "associatedPullRequests": {"nodes": []}
                                    }
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
                                        "committer": {"name": "Bob", "email": "bob@example.com", "user": {"login": "bob"}},
                                        "url": "https://github.com/owner/repo/commit/def456",
                                        "associatedPullRequests": {"nodes": []}
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        with patch.object(github, '_execute_graphql_query', return_value=mock_response):
            commits = github.blame_commits_for_range(
                file_path="src/main.py",
                start_line=10,
                end_line=50,
                ref="HEAD"
            )
        
        assert len(commits) == 2
        assert all(c["sha"] for c in commits)
        assert all(c["line_ranges"] for c in commits)
        assert commits[0]["sha"] == "abc123"
        assert commits[0]["author"] == "Alice"
        assert commits[1]["sha"] == "def456"
        assert commits[1]["author"] == "Bob"
    
    def test_blame_with_associated_prs(self):
        """Test that blame results include PR information."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo")
        
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
                                        "committer": {"name": "Dev", "email": "dev@example.com", "user": {"login": "dev"}},
                                        "url": "https://github.com/owner/repo/commit/commit1",
                                        "associatedPullRequests": {
                                            "nodes": [
                                                {
                                                    "number": 42,
                                                    "title": "Add new feature",
                                                    "url": "https://github.com/owner/repo/pull/42",
                                                    "author": {"login": "dev"},
                                                    "mergedAt": "2024-01-01T01:00:00Z",
                                                    "state": "MERGED"
                                                }
                                            ]
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        with patch.object(github, '_execute_graphql_query', return_value=mock_response):
            commits = github.blame_commits_for_range("src/feature.py", 1, 10)
        
        assert len(commits) == 1
        assert commits[0]["pr_info"] is not None
        assert commits[0]["pr_info"]["number"] == 42
        assert commits[0]["pr_info"]["title"] == "Add new feature"
    
    def test_blame_caching(self):
        """Test that identical blame queries use cache."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo")
        
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
                                        "associatedPullRequests": {"nodes": []}
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        with patch.object(github, '_execute_graphql_query', return_value=mock_response) as mock_execute:
            # First call
            commits1 = github.blame_commits_for_range("file.py", 1, 5, "HEAD")
            # Second identical call should use cache
            commits2 = github.blame_commits_for_range("file.py", 1, 5, "HEAD")
            
            # GraphQL should only be called once due to caching
            mock_execute.assert_called_once()
            
            # Results should be identical
            assert commits1 == commits2
    
    def test_blame_commits_for_nodes(self):
        """Test batch processing of multiple nodes."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo")
        
        nodes = [
            {"id": "node1", "path": "src/main.py", "start_line": 10, "end_line": 20},
            {"id": "node2", "path": "src/main.py", "start_line": 30, "end_line": 40},
            {"id": "node3", "path": "src/utils.py", "start_line": 1, "end_line": 15}
        ]
        
        # Mock different responses for different files
        def mock_blame_response(file_path: str, start_line: int, end_line: int, ref: str = "HEAD") -> List[Dict[str, Any]]:
            if file_path == "src/main.py":
                return [
                    {
                        "sha": "commit1",
                        "message": "Main change",
                        "author": "Alice",
                        "line_ranges": [{"start": start_line, "end": end_line}],
                        "pr_info": None
                    }
                ]
            else:
                return [
                    {
                        "sha": "commit2",
                        "message": "Utils change",
                        "author": "Bob",
                        "line_ranges": [{"start": 1, "end": 15}],
                        "pr_info": None
                    }
                ]
        
        with patch.object(github, 'blame_commits_for_range', side_effect=mock_blame_response):
            results = github.blame_commits_for_nodes(nodes)
        
        assert "node1" in results
        assert "node2" in results
        assert "node3" in results
        assert results["node1"][0]["sha"] == "commit1"
        assert results["node2"][0]["sha"] == "commit1"
        assert results["node3"][0]["sha"] == "commit2"
    
    def test_merge_line_ranges_optimization(self):
        """Test that overlapping line ranges are merged for efficiency."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo")
        
        nodes = [
            {"id": "node1", "path": "file.py", "start_line": 10, "end_line": 20},
            {"id": "node2", "path": "file.py", "start_line": 15, "end_line": 25},  # Overlaps with node1
            {"id": "node3", "path": "file.py", "start_line": 21, "end_line": 30},  # Adjacent to node2
        ]
        
        merged = github._merge_line_ranges(nodes)
        
        # Should merge into a single range covering lines 10-30
        assert len(merged) == 1
        assert merged[0]["start"] == 10
        assert merged[0]["end"] == 30
        assert len(merged[0]["nodes"]) == 3
    
    def test_ranges_overlap_detection(self):
        """Test detection of overlapping line ranges."""
        github = GitHub(token="test", repo_owner="owner", repo_name="repo")
        
        # Test overlapping ranges
        assert github._ranges_overlap(
            [{"start": 10, "end": 20}],
            15, 25
        ) is True
        
        # Test non-overlapping ranges
        assert github._ranges_overlap(
            [{"start": 10, "end": 20}],
            25, 30
        ) is False
        
        # Test exact match
        assert github._ranges_overlap(
            [{"start": 10, "end": 20}],
            10, 20
        ) is True
        
        # Test contained range
        assert github._ranges_overlap(
            [{"start": 10, "end": 30}],
            15, 25
        ) is True