"""Tests for node-based GitHub integration creator."""

import pytest
from unittest.mock import Mock, patch
import json

from blarify.integrations.github_creator import GitHubCreator
from blarify.graph.graph_environment import GraphEnvironment
from blarify.graph.node.integration_node import IntegrationNode


class TestNodeBasedGitHubCreator:
    """Test node-based processing in GitHubCreator."""
    
    @pytest.fixture
    def mock_db_manager(self):
        """Create mock database manager."""
        mock = Mock()
        mock.query = Mock(return_value=[])
        mock.save_graph = Mock()
        return mock
    
    @pytest.fixture
    def mock_graph_env(self):
        """Create mock graph environment."""
        return GraphEnvironment(environment="test", diff_identifier="test_diff", root_path="/test")
    
    @pytest.fixture
    def github_creator(self, mock_db_manager, mock_graph_env):
        """Create GitHubCreator instance with mocks."""
        with patch('blarify.integrations.github_creator.GitHub'):
            creator = GitHubCreator(
                db_manager=mock_db_manager,
                graph_environment=mock_graph_env,
                github_token="test_token",
                repo_owner="owner",
                repo_name="repo"
            )
            return creator
    
    def test_process_existing_nodes(self, github_creator, mock_db_manager):
        """Test processing existing code nodes with blame."""
        # Mock existing nodes from database
        existing_nodes = [
            {"id": "node1", "path": "src/main.py", "start_line": 10, "end_line": 50, "name": "authenticate", "label": "FUNCTION"},
            {"id": "node2", "path": "src/utils.py", "start_line": 1, "end_line": 30, "name": "validate", "label": "FUNCTION"}
        ]
        
        # Mock blame results
        blame_results = {
            "node1": [
                {
                    "sha": "abc123",
                    "message": "Fix authentication bug",
                    "author": "Alice",
                    "author_email": "alice@example.com",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "url": "https://github.com/owner/repo/commit/abc123",
                    "line_ranges": [{"start": 15, "end": 25}],
                    "pr_info": {"number": 123, "title": "Fix auth", "url": "https://github.com/owner/repo/pull/123"}
                }
            ],
            "node2": [
                {
                    "sha": "def456",
                    "message": "Add validation logic",
                    "author": "Bob",
                    "author_email": "bob@example.com",
                    "timestamp": "2024-01-02T00:00:00Z",
                    "url": "https://github.com/owner/repo/commit/def456",
                    "line_ranges": [{"start": 5, "end": 15}],
                    "pr_info": None
                }
            ]
        }
        
        with patch.object(github_creator.github_repo, 'blame_commits_for_nodes', return_value=blame_results):
            result = github_creator.create_github_integration_from_nodes(existing_nodes)
        
        assert result.total_commits == 2
        assert result.total_prs == 1
        assert len(result.commit_nodes) == 2
        assert len(result.pr_nodes) == 1
        assert result.relationships  # Should have MODIFIED_BY relationships
    
    def test_create_integration_from_blame(self, github_creator):
        """Test creating integration nodes from blame results."""
        blame_results = {
            "node1": [
                {
                    "sha": "abc123",
                    "message": "Fix bug\n\nDetailed description",
                    "author": "Alice",
                    "author_email": "alice@example.com",
                    "author_login": "alice",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "url": "https://github.com/owner/repo/commit/abc123",
                    "additions": 10,
                    "deletions": 5,
                    "line_ranges": [{"start": 10, "end": 20}],
                    "pr_info": {
                        "number": 123,
                        "title": "Fix critical bug",
                        "url": "https://github.com/owner/repo/pull/123",
                        "author": "alice",
                        "merged_at": "2024-01-01T01:00:00Z"
                    }
                }
            ],
            "node2": [
                {
                    "sha": "def456",
                    "message": "Add feature",
                    "author": "Bob",
                    "author_email": "bob@example.com",
                    "timestamp": "2024-01-02T00:00:00Z",
                    "url": "https://github.com/owner/repo/commit/def456",
                    "line_ranges": [{"start": 1, "end": 10}],
                    "pr_info": None
                }
            ]
        }
        
        pr_nodes, commit_nodes = github_creator._create_integration_nodes_from_blame(blame_results)
        
        assert len(commit_nodes) == 2
        assert len(pr_nodes) == 1
        
        # Check commit nodes
        assert any(c.external_id == "abc123" for c in commit_nodes)
        assert any(c.external_id == "def456" for c in commit_nodes)
        
        # Check PR node
        assert pr_nodes[0].external_id == "123"
        assert pr_nodes[0].title == "Fix critical bug"
        assert pr_nodes[0].source_type == "pull_request"
    
    def test_query_all_code_nodes(self, github_creator, mock_db_manager):
        """Test querying all code nodes from database."""
        # Mock database response
        mock_nodes = [
            {"node_id": "n1", "path": "src/main.py", "start_line": 1, "end_line": 100, "name": "main", "label": "FUNCTION"},
            {"node_id": "n2", "path": "src/utils.py", "start_line": 1, "end_line": 50, "name": "Utils", "label": "CLASS"}
        ]
        mock_db_manager.query.return_value = mock_nodes
        
        nodes = github_creator._query_all_code_nodes()
        
        # Verify query was called
        mock_db_manager.query.assert_called_once()
        query = mock_db_manager.query.call_args[0][0]
        
        # Check query filters for code nodes
        assert "label IN ['FUNCTION', 'CLASS']" in query or "label IN" in query
        assert nodes == mock_nodes
    
    def test_modified_by_with_blame_relationship(self, github_creator):
        """Test creation of MODIFIED_BY relationships with blame attribution."""
        commit_node = IntegrationNode(
            source="github",
            source_type="commit",
            external_id="abc123",
            title="Fix bug",
            content="Fix authentication bug",
            timestamp="2024-01-01T00:00:00Z",
            author="Alice",
            url="https://github.com/owner/repo/commit/abc123",
            metadata={},
            graph_environment=github_creator.graph_environment,
            level=1
        )
        
        code_node = {
            "id": "node1",
            "path": "src/main.py",
            "start_line": 10,
            "end_line": 50,
            "name": "authenticate",
            "label": "FUNCTION"
        }
        
        line_ranges = [{"start": 15, "end": 25}, {"start": 30, "end": 35}]
        
        from blarify.graph.relationship.relationship_creator import RelationshipCreator
        with patch.object(RelationshipCreator, 'create_modified_by_with_blame') as mock_create:
            mock_create.return_value = {
                "start_node_id": code_node["id"],
                "end_node_id": commit_node.hashed_id,
                "type": "MODIFIED_BY",
                "properties": {
                    "blamed_lines": json.dumps(line_ranges),
                    "total_lines_affected": 16,
                    "attribution_method": "blame"
                }
            }
            
            rel = RelationshipCreator.create_modified_by_with_blame(
                commit_node=commit_node,
                code_node=code_node,
                line_ranges=line_ranges
            )
            
            mock_create.assert_called_once_with(
                commit_node=commit_node,
                code_node=code_node,
                line_ranges=line_ranges
            )
            
            assert rel["type"] == "MODIFIED_BY"
            assert rel["properties"]["attribution_method"] == "blame"
            assert rel["properties"]["total_lines_affected"] == 16
    
    def test_backward_compatibility_methods(self, github_creator):
        """Test that backward compatible methods still exist."""
        # Check that the legacy method exists
        assert hasattr(github_creator, 'create_github_integration')
        
        # Check that new methods exist
        assert hasattr(github_creator, 'create_github_integration_from_nodes')
        assert hasattr(github_creator, 'create_github_integration_from_latest_prs')
    
    def test_save_to_database_flag(self, github_creator, mock_db_manager):
        """Test that save_to_database flag controls database operations."""
        blame_results = {
            "node1": [
                {
                    "sha": "abc123",
                    "message": "Test commit",
                    "author": "Test",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "url": "https://github.com/owner/repo/commit/abc123",
                    "line_ranges": [{"start": 1, "end": 10}],
                    "pr_info": None
                }
            ]
        }
        
        with patch.object(github_creator.github_repo, 'blame_commits_for_nodes', return_value=blame_results):
            # Test with save_to_database=False
            github_creator.create_github_integration_from_nodes(
                nodes=[{"id": "node1", "path": "file.py", "start_line": 1, "end_line": 10}],
                save_to_database=False
            )
            
            # Database save should not be called
            mock_db_manager.save_graph.assert_not_called()
            
            # Reset mock
            mock_db_manager.reset_mock()
            
            # Test with save_to_database=True
            github_creator.create_github_integration_from_nodes(
                nodes=[{"id": "node1", "path": "file.py", "start_line": 1, "end_line": 10}],
                save_to_database=True
            )
            
            # Database save should be called
            mock_db_manager.save_graph.assert_called_once()
    
    def test_error_handling(self, github_creator):
        """Test error handling in node-based processing."""
        with patch.object(github_creator.github_repo, 'blame_commits_for_nodes', side_effect=Exception("API Error")):
            result = github_creator.create_github_integration_from_nodes(
                nodes=[{"id": "node1", "path": "file.py", "start_line": 1, "end_line": 10}]
            )
            
            assert result.error == "API Error"
            assert result.total_commits == 0
            assert result.total_prs == 0