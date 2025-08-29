"""Unit tests for GetNodeWorkflowsTool auto-generation functionality."""

import pytest
from unittest.mock import Mock, MagicMock, patch, create_autospec
from typing import Any, Dict, List

from blarify.tools.get_node_workflows_tool import GetNodeWorkflowsTool
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager


class TestGetNodeWorkflowsToolAutoGenerate:
    """Test suite for GetNodeWorkflowsTool auto-generation features."""

    @pytest.fixture
    def mock_db_manager(self) -> Mock:
        """Create a mock database manager."""
        mock = create_autospec(Neo4jManager, instance=True)
        return mock

    @pytest.fixture
    def mock_node_info(self) -> Dict[str, Any]:
        """Create mock node information."""
        return {
            "node_id": "test_node_123",
            "name": "test_function",
            "path": "/test/test_function.py",
            "node_path": "/test/test_function.py::test_function",
            "labels": ["FUNCTION", "PYTHON"],
        }

    @pytest.fixture
    def mock_workflows(self) -> List[Dict[str, Any]]:
        """Create mock workflow data."""
        return [
            {
                "workflow_id": "workflow_123",
                "workflow_name": "Test Workflow",
                "entry_point": "main",
                "exit_point": "cleanup",
                "total_steps": 5,
                "entry_path": "/test/main.py",
                "exit_path": "/test/cleanup.py",
                "workflow_description": "Test workflow description",
                "execution_chain": [
                    {
                        "node_id": "node_1",
                        "name": "main",
                        "path": "/test/main.py",
                        "is_target": False,
                        "step_order": 0,
                        "depth": 0,
                    },
                    {
                        "node_id": "test_node_123",
                        "name": "test_function",
                        "path": "/test/test_function.py",
                        "is_target": True,
                        "step_order": 1,
                        "depth": 1,
                    },
                ],
            }
        ]

    def test_auto_generate_default_enabled(self, mock_db_manager: Mock) -> None:
        """Test that auto_generate is enabled by default."""
        tool = GetNodeWorkflowsTool(db_manager=mock_db_manager, company_id="test_company")
        assert tool.auto_generate is True
        assert tool._workflow_creator is not None

    def test_auto_generate_explicitly_disabled(self, mock_db_manager: Mock) -> None:
        """Test that auto_generate can be explicitly disabled."""
        tool = GetNodeWorkflowsTool(db_manager=mock_db_manager, company_id="test_company", auto_generate=False)
        assert tool.auto_generate is False
        assert tool._workflow_creator is None

    @patch("blarify.tools.get_node_workflows_tool.WorkflowCreator")
    @patch("blarify.tools.get_node_workflows_tool.GraphEnvironment")
    def test_workflow_creator_initialization(
        self, mock_graph_env: MagicMock, mock_workflow_creator_class: MagicMock, mock_db_manager: Mock
    ) -> None:
        """Test that WorkflowCreator is properly initialized."""
        mock_workflow_creator_instance = Mock()
        mock_workflow_creator_class.return_value = mock_workflow_creator_instance

        tool = GetNodeWorkflowsTool(db_manager=mock_db_manager, company_id="test_company", auto_generate=True)

        # Verify WorkflowCreator was instantiated with correct parameters
        mock_workflow_creator_class.assert_called_once_with(
            db_manager=mock_db_manager,
            graph_environment=mock_graph_env.return_value,
        )
        assert tool._workflow_creator == mock_workflow_creator_instance

    def test_no_generation_when_workflows_exist(
        self, mock_db_manager: Mock, mock_node_info: Dict[str, Any], mock_workflows: List[Dict[str, Any]]
    ) -> None:
        """Test that generation is not triggered when workflows already exist."""
        tool = GetNodeWorkflowsTool(db_manager=mock_db_manager, company_id="test_company", auto_generate=True)

        with patch.object(tool, "_get_node_info", return_value=mock_node_info):
            with patch.object(tool, "_get_workflows_with_chains", return_value=mock_workflows):
                with patch.object(tool, "_generate_workflows_for_node") as mock_generate:
                    result = tool._run("test_node_123")

                    # Should not call generation method
                    mock_generate.assert_not_called()

                    # Should display existing workflows
                    assert "📊 WORKFLOW: Test Workflow" in result
                    assert "test_function" in result

    @patch("blarify.tools.get_node_workflows_tool.WorkflowCreator")
    def test_generation_triggered_when_workflows_missing(
        self,
        mock_workflow_creator_class: MagicMock,
        mock_db_manager: Mock,
        mock_node_info: Dict[str, Any],
        mock_workflows: List[Dict[str, Any]],
    ) -> None:
        """Test that generation is triggered when workflows are missing."""
        # Setup mock WorkflowCreator
        mock_workflow_creator_instance = Mock()
        mock_workflow_creator_class.return_value = mock_workflow_creator_instance

        # Setup mock generation result
        mock_result = Mock()
        mock_result.error = None
        mock_workflow_creator_instance.discover_workflows.return_value = mock_result

        tool = GetNodeWorkflowsTool(db_manager=mock_db_manager, company_id="test_company", auto_generate=True)

        with patch.object(tool, "_get_node_info", return_value=mock_node_info):
            with patch.object(tool, "_get_workflows_with_chains") as mock_get_workflows:
                # First call returns empty, second call (after generation) returns workflows
                mock_get_workflows.side_effect = [[], mock_workflows]

                result = tool._run("test_node_123")

                # Verify generation was triggered
                mock_workflow_creator_instance.discover_workflows.assert_called_once_with(
                    node_path="/test/test_function.py", max_depth=20, save_to_database=True
                )

                # Verify workflows are displayed after generation
                assert "📊 WORKFLOW: Test Workflow" in result
                assert "test_function" in result

    def test_generation_error_handling(self, mock_db_manager: Mock, mock_node_info: Dict[str, Any]) -> None:
        """Test graceful handling of generation errors."""
        with patch("blarify.tools.get_node_workflows_tool.WorkflowCreator") as mock_workflow_creator_class:
            mock_workflow_creator_instance = Mock()
            mock_workflow_creator_class.return_value = mock_workflow_creator_instance

            # Simulate generation failure
            mock_workflow_creator_instance.discover_workflows.side_effect = Exception("Generation failed")

            tool = GetNodeWorkflowsTool(db_manager=mock_db_manager, company_id="test_company", auto_generate=True)

            with patch.object(tool, "_get_node_info", return_value=mock_node_info):
                with patch.object(tool, "_get_workflows_with_chains", return_value=[]):
                    result = tool._run("test_node_123")

                    # Should handle error gracefully
                    assert "⚠️ WARNING: No workflows found for this node!" in result
                    assert "Auto-generation was attempted but no workflows were discovered" in result

    def test_no_generation_when_disabled(self, mock_db_manager: Mock, mock_node_info: Dict[str, Any]) -> None:
        """Test that generation is not attempted when auto_generate is False."""
        tool = GetNodeWorkflowsTool(db_manager=mock_db_manager, company_id="test_company", auto_generate=False)

        with patch.object(tool, "_get_node_info", return_value=mock_node_info):
            with patch.object(tool, "_get_workflows_with_chains", return_value=[]):
                result = tool._run("test_node_123")

                # Should show warning without attempting generation
                assert "⚠️ WARNING: No workflows found for this node!" in result
                assert "This is likely a data issue" in result
                assert "Auto-generation was attempted" not in result

    def test_generation_with_error_result(self, mock_db_manager: Mock, mock_node_info: Dict[str, Any]) -> None:
        """Test handling when generation returns an error result."""
        with patch("blarify.tools.get_node_workflows_tool.WorkflowCreator") as mock_workflow_creator_class:
            mock_workflow_creator_instance = Mock()
            mock_workflow_creator_class.return_value = mock_workflow_creator_instance

            # Setup mock generation result with error
            mock_result = Mock()
            mock_result.error = "Failed to discover workflows"
            mock_workflow_creator_instance.discover_workflows.return_value = mock_result

            tool = GetNodeWorkflowsTool(db_manager=mock_db_manager, company_id="test_company", auto_generate=True)

            with patch.object(tool, "_get_node_info", return_value=mock_node_info):
                with patch.object(tool, "_get_workflows_with_chains", return_value=[]):
                    result = tool._run("test_node_123")

                    # Should indicate generation was attempted but failed
                    assert "⚠️ WARNING: No workflows found for this node!" in result
                    assert "Auto-generation was attempted but no workflows were discovered" in result

    def test_generation_without_node_path(self, mock_db_manager: Mock) -> None:
        """Test that generation is skipped when node has no path."""
        mock_node_info_no_path = {
            "node_id": "test_node_123",
            "name": "test_function",
            "path": "",  # Empty path
            "node_path": "",  # Empty node_path
            "labels": ["FUNCTION", "PYTHON"],
        }

        tool = GetNodeWorkflowsTool(db_manager=mock_db_manager, company_id="test_company", auto_generate=True)

        with patch.object(tool, "_get_node_info", return_value=mock_node_info_no_path):
            with patch.object(tool, "_get_workflows_with_chains", return_value=[]):
                with patch.object(tool, "_generate_workflows_for_node") as mock_generate:
                    result = tool._run("test_node_123")

                    # Should not attempt generation without a path
                    mock_generate.assert_not_called()

                    # Should show warning
                    assert "⚠️ WARNING: No workflows found for this node!" in result

    def test_node_not_found(self, mock_db_manager: Mock) -> None:
        """Test handling when node is not found."""
        tool = GetNodeWorkflowsTool(db_manager=mock_db_manager, company_id="test_company", auto_generate=True)

        with patch.object(tool, "_get_node_info", return_value=None):
            result = tool._run("test_node_123")

            # Should indicate node not found
            assert "Node with ID 'test_node_123' not found in the database" in result

    def test_generate_workflows_for_node_method(
        self, mock_db_manager: Mock, mock_workflows: List[Dict[str, Any]]
    ) -> None:
        """Test the _generate_workflows_for_node method directly."""
        with patch("blarify.tools.get_node_workflows_tool.WorkflowCreator") as mock_workflow_creator_class:
            mock_workflow_creator_instance = Mock()
            mock_workflow_creator_class.return_value = mock_workflow_creator_instance

            # Setup mock generation result
            mock_result = Mock()
            mock_result.error = None
            mock_workflow_creator_instance.discover_workflows.return_value = mock_result

            tool = GetNodeWorkflowsTool(db_manager=mock_db_manager, company_id="test_company", auto_generate=True)

            with patch.object(tool, "_get_workflows_with_chains", return_value=mock_workflows):
                result = tool._generate_workflows_for_node("test_node_123", "/test/path.py")

                # Should call discover_workflows with correct parameters
                mock_workflow_creator_instance.discover_workflows.assert_called_once_with(
                    node_path="/test/path.py", max_depth=20, save_to_database=True
                )

                # Should return the workflows
                assert result == mock_workflows

    def test_generate_workflows_for_node_when_disabled(self, mock_db_manager: Mock) -> None:
        """Test that _generate_workflows_for_node returns empty when auto_generate is False."""
        tool = GetNodeWorkflowsTool(db_manager=mock_db_manager, company_id="test_company", auto_generate=False)

        result = tool._generate_workflows_for_node("test_node_123", "/test/path.py")

        # Should return empty list
        assert result == []
