"""Unit tests for GetCodeByIdTool auto-generation functionality."""

import pytest
from unittest.mock import Mock, MagicMock, patch

from blarify.tools.get_code_by_id_tool import GetCodeByIdTool, NodeSearchResultResponse


class TestGetCodeByIdToolAutoGenerate:
    """Test suite for GetCodeByIdTool auto-generation features."""

    @pytest.fixture
    def mock_db_manager(self) -> Mock:
        """Create a mock database manager."""
        mock = Mock()
        return mock

    @pytest.fixture
    def mock_node_result(self) -> NodeSearchResultResponse:
        """Create a mock node result without documentation."""
        return NodeSearchResultResponse(
            node_id="test_node_123",
            node_name="test_function.py",
            node_labels=["FILE", "PYTHON"],
            code="def test():\n    pass",
            start_line=1,
            end_line=2,
            file_path="/test/test_function.py",
            documentation_nodes=None
        )

    @pytest.fixture
    def mock_node_result_with_docs(self) -> NodeSearchResultResponse:
        """Create a mock node result with existing documentation."""
        return NodeSearchResultResponse(
            node_id="test_node_123",
            node_name="test_function.py",
            node_labels=["FILE", "PYTHON"],
            code="def test():\n    pass",
            start_line=1,
            end_line=2,
            file_path="/test/test_function.py",
            documentation_nodes=[{
                "node_id": "doc_123",
                "node_name": "Documentation for test_function",
                "content": "This is a test function"
            }]
        )

    def test_auto_generate_default_enabled(self, mock_db_manager: Mock) -> None:
        """Test that auto_generate is enabled by default."""
        tool = GetCodeByIdTool(
            db_manager=mock_db_manager,
            company_id="test_company"
        )
        assert tool.auto_generate is True
        assert tool._documentation_creator is not None

    def test_auto_generate_explicitly_disabled(self, mock_db_manager: Mock) -> None:
        """Test that auto_generate can be explicitly disabled."""
        tool = GetCodeByIdTool(
            db_manager=mock_db_manager,
            company_id="test_company",
            auto_generate=False
        )
        assert tool.auto_generate is False
        assert tool._documentation_creator is None

    @patch('blarify.tools.get_code_by_id_tool.DocumentationCreator')
    @patch('blarify.tools.get_code_by_id_tool.LLMProvider')
    @patch('blarify.tools.get_code_by_id_tool.GraphEnvironment')
    def test_documentation_creator_initialization(
        self,
        mock_graph_env: MagicMock,
        mock_llm_provider: MagicMock,
        mock_doc_creator_class: MagicMock,
        mock_db_manager: Mock
    ) -> None:
        """Test that DocumentationCreator is properly initialized."""
        mock_doc_creator_instance = Mock()
        mock_doc_creator_class.return_value = mock_doc_creator_instance
        
        tool = GetCodeByIdTool(
            db_manager=mock_db_manager,
            company_id="test_company",
            auto_generate=True
        )
        
        # Verify DocumentationCreator was instantiated with correct parameters
        mock_doc_creator_class.assert_called_once_with(
            db_manager=mock_db_manager,
            agent_caller=mock_llm_provider.return_value,
            graph_environment=mock_graph_env.return_value,
            company_id="test_company",
            repo_id="test_company",
            max_workers=1,
            overwrite_documentation=False
        )
        assert tool._documentation_creator == mock_doc_creator_instance

    def test_no_generation_when_docs_exist(
        self,
        mock_db_manager: Mock,
        mock_node_result_with_docs: NodeSearchResultResponse
    ) -> None:
        """Test that generation is not triggered when documentation already exists."""
        mock_db_manager.get_node_by_id_v2.return_value = mock_node_result_with_docs
        
        tool = GetCodeByIdTool(
            db_manager=mock_db_manager,
            company_id="test_company",
            auto_generate=True
        )
        
        with patch.object(tool, '_generate_documentation_for_node') as mock_generate:
            result = tool._run("test_node_123")
            
            # Should not call generation method
            mock_generate.assert_not_called()
            
            # Should display existing documentation
            assert "📚 DOCUMENTATION:" in result
            assert "This is a test function" in result

    @patch('blarify.tools.get_code_by_id_tool.DocumentationCreator')
    def test_generation_triggered_when_docs_missing(
        self,
        mock_doc_creator_class: MagicMock,
        mock_db_manager: Mock,
        mock_node_result: NodeSearchResultResponse
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
        mock_db_manager.get_node_by_id_v2.side_effect = [
            mock_node_result,  # First call in _run
            mock_node_result,  # Second call in _generate_documentation_for_node
            NodeSearchResultResponse(  # Third call after generation
                **mock_node_result.model_dump(),
                documentation_nodes=[{
                    "node_id": "generated_doc_123",
                    "node_name": "Auto-generated doc",
                    "content": "Generated documentation content"
                }]
            )
        ]
        
        tool = GetCodeByIdTool(
            db_manager=mock_db_manager,
            company_id="test_company",
            auto_generate=True
        )
        
        result = tool._run("test_node_123")
        
        # Verify generation was triggered
        mock_doc_creator_instance.create_documentation.assert_called_once_with(
            target_paths=["test_function.py"],
            save_to_database=True,
            generate_embeddings=False
        )
        
        # Verify auto-generated docs are displayed
        assert "📚 DOCUMENTATION (auto-generated):" in result
        assert "Generated documentation content" in result

    def test_generation_error_handling(
        self,
        mock_db_manager: Mock,
        mock_node_result: NodeSearchResultResponse
    ) -> None:
        """Test graceful handling of generation errors."""
        mock_db_manager.get_node_by_id_v2.return_value = mock_node_result
        
        with patch('blarify.tools.get_code_by_id_tool.DocumentationCreator') as mock_doc_creator_class:
            mock_doc_creator_instance = Mock()
            mock_doc_creator_class.return_value = mock_doc_creator_instance
            
            # Simulate generation failure
            mock_doc_creator_instance.create_documentation.side_effect = Exception("Generation failed")
            
            tool = GetCodeByIdTool(
                db_manager=mock_db_manager,
                company_id="test_company",
                auto_generate=True
            )
            
            result = tool._run("test_node_123")
            
            # Should handle error gracefully
            assert "📚 DOCUMENTATION: None found (generation attempted)" in result

    def test_no_generation_when_disabled(
        self,
        mock_db_manager: Mock,
        mock_node_result: NodeSearchResultResponse
    ) -> None:
        """Test that generation is not attempted when auto_generate is False."""
        mock_db_manager.get_node_by_id_v2.return_value = mock_node_result
        
        tool = GetCodeByIdTool(
            db_manager=mock_db_manager,
            company_id="test_company",
            auto_generate=False
        )
        
        result = tool._run("test_node_123")
        
        # Should show "None found" without attempting generation
        assert "📚 DOCUMENTATION: None found" in result
        assert "(generation attempted)" not in result
        assert "(auto-generated)" not in result

    def test_generation_with_empty_result(
        self,
        mock_db_manager: Mock,
        mock_node_result: NodeSearchResultResponse
    ) -> None:
        """Test handling when generation returns empty documentation."""
        mock_db_manager.get_node_by_id_v2.side_effect = [
            mock_node_result,  # First call in _run
            mock_node_result,  # Second call in _generate_documentation_for_node
            mock_node_result   # Third call after generation (still no docs)
        ]
        
        with patch('blarify.tools.get_code_by_id_tool.DocumentationCreator') as mock_doc_creator_class:
            mock_doc_creator_instance = Mock()
            mock_doc_creator_class.return_value = mock_doc_creator_instance
            
            mock_result = Mock()
            mock_result.error = None
            mock_doc_creator_instance.create_documentation.return_value = mock_result
            
            tool = GetCodeByIdTool(
                db_manager=mock_db_manager,
                company_id="test_company",
                auto_generate=True
            )
            
            result = tool._run("test_node_123")
            
            # Should indicate generation was attempted but no docs found
            assert "📚 DOCUMENTATION: None found (generation attempted)" in result

    def test_node_not_found_during_generation(
        self,
        mock_db_manager: Mock,
        mock_node_result: NodeSearchResultResponse
    ) -> None:
        """Test handling when node is not found during generation."""
        mock_db_manager.get_node_by_id_v2.side_effect = [
            mock_node_result,  # First call in _run
            None  # Second call in _generate_documentation_for_node returns None
        ]
        
        with patch('blarify.tools.get_code_by_id_tool.DocumentationCreator') as mock_doc_creator_class:
            mock_doc_creator_instance = Mock()
            mock_doc_creator_class.return_value = mock_doc_creator_instance
            
            tool = GetCodeByIdTool(
                db_manager=mock_db_manager,
                company_id="test_company",
                auto_generate=True
            )
            
            result = tool._run("test_node_123")
            
            # Should handle missing node gracefully
            assert "📚 DOCUMENTATION: None found (generation attempted)" in result
            mock_doc_creator_instance.create_documentation.assert_not_called()