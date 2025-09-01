"""Unit tests for GetBlameByIdTool."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import Mock, patch

import pytest

from blarify.tools.get_blame_by_id_tool import GetBlameByIdTool


class TestGetBlameByIdTool:
    """Test suite for GetBlameByIdTool."""

    @pytest.fixture
    def mock_db_manager(self) -> Mock:
        """Create a mock database manager."""
        return Mock()

    @pytest.fixture
    def tool(self, mock_db_manager: Mock) -> GetBlameByIdTool:
        """Create a GetBlameByIdTool instance with mocked dependencies."""
        return GetBlameByIdTool(
            db_manager=mock_db_manager,
            repo_owner="test-owner",
            repo_name="test-repo",
            github_token="test-token",
            auto_create_integration=True,
        )

    @pytest.fixture
    def sample_node_info(self) -> Dict[str, Any]:
        """Sample node information."""
        return {
            "node_name": "get_reference_type",
            "node_path": "blarify/code_hierarchy/python/lsp_query_utils.py",
            "start_line": 50,
            "end_line": 63,
            "code": """def get_reference_type(
    self, original_node: "DefinitionNode", reference: "Reference", node_referenced: "DefinitionNode"
) -> FoundRelationshipScope:
    node_in_point_reference = self._get_node_in_point_reference(node=node_referenced, reference=reference)
    found_relationship_scope = self.language_definitions.get_relationship_type(
        node=original_node, node_in_point_reference=node_in_point_reference
    )
    
    if not found_relationship_scope:
        found_relationship_scope = FoundRelationshipScope(
            node_in_scope=None, relationship_type=RelationshipType.USES
        )
    
    return found_relationship_scope""",
            "node_type": "FUNCTION",
        }

    @pytest.fixture
    def sample_blame_data(self) -> List[Dict[str, Any]]:
        """Sample blame data with multiple commits."""
        now = datetime.now(timezone.utc)
        return [
            {
                "commit_sha": "abc123def456",
                "commit_message": "feat: introduce FoundRelationshipScope",
                "commit_author": "Alice Developer",
                "commit_timestamp": (now - timedelta(days=240)).isoformat(),
                "commit_url": "https://github.com/test/repo/commit/abc123",
                "line_ranges": '[{"start": 52, "end": 52}, {"start": 54, "end": 56}, {"start": 58, "end": 63}]',
                "attribution_method": "blame",
                "pr_number": "42",
                "pr_title": "Add relationship scope feature",
                "pr_url": "https://github.com/test/repo/pull/42",
            },
            {
                "commit_sha": "def456ghi789",
                "commit_message": "refactor: replace CodeRange with Reference",
                "commit_author": "Bob Smith",
                "commit_timestamp": (now - timedelta(days=270)).isoformat(),
                "commit_url": "https://github.com/test/repo/commit/def456",
                "line_ranges": '[{"start": 50, "end": 51}, {"start": 53, "end": 53}, {"start": 57, "end": 57}]',
                "attribution_method": "blame",
                "pr_number": None,
                "pr_title": None,
                "pr_url": None,
            },
        ]

    def test_run_with_existing_blame_data(
        self,
        tool: GetBlameByIdTool,
        mock_db_manager: Mock,
        sample_node_info: Dict[str, Any],
        sample_blame_data: List[Dict[str, Any]],
    ) -> None:
        """Test getting blame for a node with existing blame data."""
        # Setup mocks
        mock_db_manager.query.side_effect = [
            [sample_node_info],  # _get_node_info query
            sample_blame_data,   # _get_existing_blame query
        ]

        # Run the tool
        result = tool._run(node_id="a" * 32)

        # Verify the output format
        assert "Git Blame for: get_reference_type (FUNCTION)" in result
        assert "File: blarify/code_hierarchy/python/lsp_query_utils.py" in result
        assert "=" * 80 in result
        
        # Check for code lines with blame info
        assert "50 | def get_reference_type(" in result
        assert "51 |" in result
        assert "52 | ) -> FoundRelationshipScope:" in result
        
        # Check for author names in blame info
        assert "Alice" in result
        assert "Bob" in result
        
        # Check for commit SHAs (abbreviated)
        assert "abc123d" in result
        assert "def456g" in result
        
        # Check summary section
        assert "Summary:" in result
        assert "Total commits: 2" in result
        assert "Primary author:" in result
        assert "Last modified:" in result
        assert "Associated Pull Requests:" in result
        assert "PR #42: Add relationship scope feature" in result

    def test_run_with_no_existing_blame_creates_integration(
        self,
        tool: GetBlameByIdTool,
        mock_db_manager: Mock,
        sample_node_info: Dict[str, Any],
        sample_blame_data: List[Dict[str, Any]],
    ) -> None:
        """Test that integration nodes are created when no blame data exists."""
        # Setup mocks
        mock_db_manager.query.side_effect = [
            [sample_node_info],  # _get_node_info query
            [],                  # _get_existing_blame query (no data)
            sample_blame_data,   # _get_existing_blame query after creation
        ]

        # Mock GitHubCreator
        with patch("blarify.tools.get_blame_by_id_tool.GitHubCreator") as MockGitHubCreator:
            mock_creator = MockGitHubCreator.return_value
            mock_result = Mock()
            mock_result.total_commits = 2
            mock_creator.create_github_integration_from_nodes.return_value = mock_result

            # Run the tool
            result = tool._run(node_id="a" * 32)

            # Verify GitHubCreator was called
            MockGitHubCreator.assert_called_once()
            mock_creator.create_github_integration_from_nodes.assert_called_once_with(
                node_ids=["a" * 32],
                save_to_database=True
            )

            # Verify the output still contains blame info
            assert "Git Blame for: get_reference_type" in result
            assert "Total commits: 2" in result

    def test_run_with_node_not_found(
        self,
        tool: GetBlameByIdTool,
        mock_db_manager: Mock,
    ) -> None:
        """Test handling when node is not found."""
        # Setup mock to return no node
        mock_db_manager.query.return_value = []

        # Run the tool
        result = tool._run(node_id="b" * 32)

        # Verify error message
        assert "Error: Node with ID" in result
        assert "not found" in result

    def test_run_with_no_code(
        self,
        tool: GetBlameByIdTool,
        mock_db_manager: Mock,
    ) -> None:
        """Test handling when node has no code."""
        node_info = {
            "node_name": "empty_function",
            "node_path": "test.py",
            "start_line": 1,
            "end_line": 1,
            "code": "",
            "node_type": "FUNCTION",
        }

        mock_db_manager.query.side_effect = [
            [node_info],  # _get_node_info query
            [],           # _get_existing_blame query
        ]

        # Run the tool
        result = tool._run(node_id="c" * 32)

        # Verify output
        assert "Git Blame for: empty_function" in result
        assert "No code available for this node" in result

    def test_format_time_ago(self, tool: GetBlameByIdTool) -> None:
        """Test time formatting."""
        now = datetime.now(timezone.utc)
        
        # Test various time differences
        assert tool._format_time_ago((now - timedelta(days=400)).isoformat()) == "1 year ago"
        assert tool._format_time_ago((now - timedelta(days=800)).isoformat()) == "2 years ago"
        assert tool._format_time_ago((now - timedelta(days=60)).isoformat()) == "2 months ago"
        assert tool._format_time_ago((now - timedelta(days=5)).isoformat()) == "5 days ago"
        assert tool._format_time_ago((now - timedelta(hours=3)).isoformat()) == "3 hours ago"
        assert tool._format_time_ago((now - timedelta(minutes=30)).isoformat()) == "30 minutes ago"
        assert tool._format_time_ago((now - timedelta(seconds=30)).isoformat()) == "Just now"
        assert tool._format_time_ago("") == "Unknown"
        assert tool._format_time_ago("invalid") == "Unknown"

    def test_calculate_author_lines(
        self,
        tool: GetBlameByIdTool,
        sample_blame_data: List[Dict[str, Any]],
    ) -> None:
        """Test calculation of lines per author."""
        author_lines = tool._calculate_author_lines(sample_blame_data)
        
        # Alice has lines 52, 54-56, 58-63 = 1 + 3 + 6 = 10 lines
        assert author_lines["Alice Developer"] == 10
        # Bob has lines 50-51, 53, 57 = 2 + 1 + 1 = 4 lines
        assert author_lines["Bob Smith"] == 4

    def test_build_line_blame_map(
        self,
        tool: GetBlameByIdTool,
        sample_blame_data: List[Dict[str, Any]],
    ) -> None:
        """Test building line-to-blame mapping."""
        line_map = tool._build_line_blame_map(sample_blame_data, start_line=50, num_lines=14)
        
        # Check specific lines
        assert line_map[50]["author"] == "Bob Smith"
        assert line_map[52]["author"] == "Alice Developer"
        assert line_map[53]["author"] == "Bob Smith"
        assert line_map[54]["author"] == "Alice Developer"
        
        # Check that all expected lines are mapped
        alice_lines = [52, 54, 55, 56, 58, 59, 60, 61, 62, 63]
        bob_lines = [50, 51, 53, 57]
        
        for line in alice_lines:
            assert line in line_map
            assert line_map[line]["author"] == "Alice Developer"
        
        for line in bob_lines:
            assert line in line_map
            assert line_map[line]["author"] == "Bob Smith"

    def test_auto_create_disabled(
        self,
        mock_db_manager: Mock,
        sample_node_info: Dict[str, Any],
    ) -> None:
        """Test that integration nodes are not created when auto_create is disabled."""
        tool = GetBlameByIdTool(
            db_manager=mock_db_manager,
            repo_owner="test-owner",
            repo_name="test-repo",
            github_token="test-token",
            auto_create_integration=False,  # Disabled
        )

        # Setup mocks
        mock_db_manager.query.side_effect = [
            [sample_node_info],  # _get_node_info query
            [],                  # _get_existing_blame query (no data)
        ]

        # Run the tool
        with patch("blarify.tools.get_blame_by_id_tool.GitHubCreator") as MockGitHubCreator:
            result = tool._run(node_id="d" * 32)

            # Verify GitHubCreator was NOT called
            MockGitHubCreator.assert_not_called()

            # Verify output shows no blame info
            assert "No blame information available" in result

    def test_github_token_from_environment(
        self,
        mock_db_manager: Mock,
    ) -> None:
        """Test that GitHub token is read from environment variable."""
        with patch.dict("os.environ", {"GITHUB_TOKEN": "env-token"}):
            tool = GetBlameByIdTool(
                db_manager=mock_db_manager,
                repo_owner="test-owner",
                repo_name="test-repo",
                github_token=None,  # Not provided
            )
            
            assert tool.github_token == "env-token"

    def test_invalid_node_id(
        self,
        mock_db_manager: Mock,
    ) -> None:
        """Test validation of node ID format."""
        tool = GetBlameByIdTool(
            db_manager=mock_db_manager,
            repo_owner="test-owner",
            repo_name="test-repo",
        )

        # Test with invalid node ID (not 32 characters)
        with pytest.raises(ValueError, match="Node id must be a 32 character"):
            tool.args_schema(node_id="short")

    def test_exception_handling(
        self,
        tool: GetBlameByIdTool,
        mock_db_manager: Mock,
    ) -> None:
        """Test exception handling in _run method."""
        # Setup mock to raise an exception
        mock_db_manager.query.side_effect = Exception("Database error")

        # Run the tool
        result = tool._run(node_id="e" * 32)

        # Verify error message
        assert "Error: Failed to get blame information" in result
        assert "Database error" in result