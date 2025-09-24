"""Unit tests for GetCodeAnalysis auto-generation functionality."""

import pytest
from unittest.mock import Mock, MagicMock, patch

from blarify.tools.get_code_analysis import GetCodeAnalysis
from blarify.repositories.graph_db_manager.dtos.node_search_result_dto import NodeSearchResultDTO
from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager


class TestGetCodeAnalysisAutoGenerate:
    """Test suite for GetCodeAnalysis auto-generation features."""

    @pytest.fixture
    def mock_db_manager(self) -> Mock:
        """Create a mock database manager that properly inherits from AbstractDbManager."""
        # Create a mock that properly inherits from AbstractDbManager
        mock = Mock(spec=AbstractDbManager)
        # Configure the mock to have the required methods with default return values
        mock.get_node_by_id = Mock(return_value=None)  # Default to returning None
        mock.query = Mock(return_value=[])  # Default to returning empty list
        return mock

    @pytest.fixture
    def mock_node_result(self) -> NodeSearchResultDTO:
        """Create a mock node result without documentation."""
        return NodeSearchResultDTO(
            node_id="test_node_123",
            node_name="test_function.py",
            node_labels=["FILE", "PYTHON"],
            node_path="test_function.py",
            code="def test():\n    pass",
            start_line=1,
            end_line=2,
            file_path="/test/test_function.py",
            documentation=None,
        )

    @pytest.fixture
    def mock_node_result_with_docs(self) -> NodeSearchResultDTO:
        """Create a mock node result with existing documentation."""
        return NodeSearchResultDTO(
            node_id="test_node_123",
            node_name="test_function.py",
            node_labels=["FILE", "PYTHON"],
            node_path="test_function.py",
            code="def test():\n    pass",
            start_line=1,
            end_line=2,
            file_path="/test/test_function.py",
            documentation="This is a test function",
        )

    def test_auto_generate_default_enabled(self, mock_db_manager: Mock) -> None:
        """Test that auto_generate is enabled by default."""
        tool = GetCodeAnalysis(db_manager=mock_db_manager)
        assert tool.auto_generate_documentation is True
        assert tool._documentation_creator is not None  # type: ignore[reportPrivateUsage]

    def test_auto_generate_explicitly_disabled(self, mock_db_manager: Mock) -> None:
        """Test that auto_generate can be explicitly disabled."""
        tool = GetCodeAnalysis(db_manager=mock_db_manager, auto_generate_documentation=False)
        assert tool.auto_generate_documentation is False
        # DocumentationCreator is still created even when auto_generate is disabled

    @patch("blarify.tools.get_code_by_id_tool.DocumentationCreator")
    @patch("blarify.tools.get_code_by_id_tool.LLMProvider")
    @patch("blarify.tools.get_code_by_id_tool.GraphEnvironment")
    def test_documentation_creator_initialization(
        self,
        mock_graph_env: MagicMock,
        mock_llm_provider: MagicMock,
        mock_doc_creator_class: MagicMock,
        mock_db_manager: Mock,
    ) -> None:
        """Test that DocumentationCreator is properly initialized."""
        mock_doc_creator_instance = Mock()
        mock_doc_creator_class.return_value = mock_doc_creator_instance

        tool = GetCodeAnalysis(db_manager=mock_db_manager, auto_generate_documentation=True)

        # Verify DocumentationCreator was instantiated with correct parameters
        mock_doc_creator_class.assert_called_once_with(
            db_manager=mock_db_manager,
            agent_caller=mock_llm_provider.return_value,
            graph_environment=mock_graph_env.return_value,
            max_workers=20,
            overwrite_documentation=False,
        )
        assert tool._documentation_creator == mock_doc_creator_instance  # type: ignore[reportPrivateUsage]

    def test_no_generation_when_docs_exist(
        self, mock_db_manager: Mock, mock_node_result_with_docs: NodeSearchResultDTO
    ) -> None:
        """Test that generation is not triggered when documentation already exists."""
        mock_db_manager.get_node_by_id.return_value = mock_node_result_with_docs

        tool = GetCodeAnalysis(db_manager=mock_db_manager, auto_generate_documentation=True)

        with patch.object(tool, "_generate_documentation_for_node") as mock_generate:
            result = tool._run("test_node_123")  # type: ignore[reportPrivateUsage]  # type: ignore[reportPrivateUsage]

            # Should not call generation method
            mock_generate.assert_not_called()

            # Should display existing documentation
            assert "📚 DOCUMENTATION:" in result
            assert "This is a test function" in result

    @patch("blarify.tools.get_code_by_id_tool.DocumentationCreator")
    def test_generation_triggered_when_docs_missing(
        self, mock_doc_creator_class: MagicMock, mock_db_manager: Mock, mock_node_result: NodeSearchResultDTO
    ) -> None:
        """Test that generation is triggered when documentation is missing."""
        # Setup mock DocumentationCreator
        mock_doc_creator_instance = Mock()
        mock_doc_creator_class.return_value = mock_doc_creator_instance

        # Setup mock generation result
        mock_result = Mock()
        mock_result.error = None
        mock_doc_creator_instance.create_documentation.return_value = mock_result

        # Setup database responses
        updated_result = mock_node_result.model_copy(update={"documentation": "Generated documentation content"})

        mock_db_manager.get_node_by_id.side_effect = [
            mock_node_result,  # First call in _run
            updated_result,  # Second call in _generate_documentation_for_node after generation
        ]

        tool = GetCodeAnalysis(db_manager=mock_db_manager, auto_generate_documentation=True)

        result = tool._run("test_node_123")  # type: ignore[reportPrivateUsage]

        # Verify generation was triggered
        mock_doc_creator_instance.create_documentation.assert_called_once_with(
            target_paths=["test_function.py"], save_to_database=True, generate_embeddings=False
        )

        # Verify auto-generated docs are displayed
        assert "📚 DOCUMENTATION:" in result
        assert "Generated documentation content" in result

    def test_generation_error_handling(self, mock_db_manager: Mock, mock_node_result: NodeSearchResultDTO) -> None:
        """Test graceful handling of generation errors."""
        mock_db_manager.get_node_by_id.return_value = mock_node_result

        with patch("blarify.tools.get_code_by_id_tool.DocumentationCreator") as mock_doc_creator_class:
            mock_doc_creator_instance = Mock()
            mock_doc_creator_class.return_value = mock_doc_creator_instance

            # Simulate generation failure
            mock_doc_creator_instance.create_documentation.side_effect = Exception("Generation failed")

            tool = GetCodeAnalysis(db_manager=mock_db_manager, auto_generate_documentation=True)

            result = tool._run("test_node_123")  # type: ignore[reportPrivateUsage]  # type: ignore[reportPrivateUsage]

            # Should handle error gracefully
            assert "📚 DOCUMENTATION: None found (generation attempted)" in result

    def test_no_generation_when_disabled(self, mock_db_manager: Mock, mock_node_result: NodeSearchResultDTO) -> None:
        """Test that generation is not attempted when auto_generate is False."""
        mock_db_manager.get_node_by_id.return_value = mock_node_result

        tool = GetCodeAnalysis(db_manager=mock_db_manager, auto_generate_documentation=False)

        result = tool._run("test_node_123")  # type: ignore[reportPrivateUsage]

        # Should show "None found" without attempting generation
        assert "📚 DOCUMENTATION: None found" in result
        assert "(generation attempted)" not in result
        assert "(auto-generated)" not in result

    def test_generation_with_empty_result(self, mock_db_manager: Mock, mock_node_result: NodeSearchResultDTO) -> None:
        """Test handling when generation returns empty documentation."""
        mock_db_manager.get_node_by_id.side_effect = [
            mock_node_result,  # First call in _run
            mock_node_result,  # Second call in _generate_documentation_for_node
            mock_node_result,  # Third call after generation (still no docs)
        ]

        with patch("blarify.tools.get_code_by_id_tool.DocumentationCreator") as mock_doc_creator_class:
            mock_doc_creator_instance = Mock()
            mock_doc_creator_class.return_value = mock_doc_creator_instance

            mock_result = Mock()
            mock_result.error = None
            mock_doc_creator_instance.create_documentation.return_value = mock_result

            tool = GetCodeAnalysis(db_manager=mock_db_manager, auto_generate_documentation=True)

            result = tool._run("test_node_123")  # type: ignore[reportPrivateUsage]  # type: ignore[reportPrivateUsage]

            # Should indicate generation was attempted but no docs found
            assert "📚 DOCUMENTATION: None found (generation attempted)" in result

    def test_node_not_found_during_generation(
        self, mock_db_manager: Mock, mock_node_result: NodeSearchResultDTO
    ) -> None:
        """Test handling when node is not found during generation."""
        mock_db_manager.get_node_by_id.return_value = mock_node_result

        with patch("blarify.tools.get_code_by_id_tool.DocumentationCreator") as mock_doc_creator_class:
            mock_doc_creator_instance = Mock()
            mock_doc_creator_class.return_value = mock_doc_creator_instance
            
            # Make create_documentation succeed but the node still has no documentation
            mock_result = Mock()
            mock_result.error = None
            mock_doc_creator_instance.create_documentation.return_value = mock_result

            tool = GetCodeAnalysis(db_manager=mock_db_manager, auto_generate_documentation=True)

            result = tool._run("test_node_123")  # type: ignore[reportPrivateUsage]  # type: ignore[reportPrivateUsage]

            # Should handle missing node gracefully
            assert "📚 DOCUMENTATION: None found (generation attempted)" in result
            # Generation was attempted
            mock_doc_creator_instance.create_documentation.assert_called_once()
