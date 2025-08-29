"""Integration tests for tools auto-generation functionality."""

import pytest
from unittest.mock import Mock, patch
import tempfile
import os

from blarify.tools.get_code_by_id_tool import GetCodeByIdTool
from blarify.tools.get_node_workflows import GetNodeWorkflowsTool
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager


class TestToolsAutoGenerationIntegration:
    """Integration tests for auto-generation features in tools."""

    @pytest.fixture
    def mock_db_manager(self) -> Mock:
        """Create a mock database manager with realistic behavior."""
        mock = Mock(spec=Neo4jManager)
        
        # Setup realistic node data
        mock.get_node_by_id_v2.return_value = Mock(
            node_id="test_node_123",
            node_name="example_function.py",
            node_labels=["FILE", "PYTHON"],
            code="def example():\n    return 42",
            start_line=1,
            end_line=2,
            file_path="/test/example_function.py",
            documentation_nodes=None,
            inbound_relations=None,
            outbound_relations=None
        )
        
        mock.query.return_value = [{
            "node_id": "test_node_123",
            "name": "example_function",
            "path": "/test/example_function.py",
            "node_path": "/test/example_function.py::example_function",
            "labels": ["FUNCTION", "PYTHON"]
        }]
        
        return mock

    @pytest.fixture
    def temp_project_dir(self) -> str:
        """Create a temporary project directory with sample files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create sample Python file
            sample_file = os.path.join(tmpdir, "example.py")
            with open(sample_file, "w") as f:
                f.write("""
def example_function():
    '''A sample function for testing.'''
    return 42

class ExampleClass:
    '''A sample class for testing.'''
    
    def method(self):
        return example_function()
""")
            yield tmpdir

    @pytest.mark.integration
    def test_get_code_by_id_with_documentation_generation(
        self,
        mock_db_manager: Mock
    ) -> None:
        """Test GetCodeByIdTool with actual documentation generation flow."""
        # Create tool with auto-generation enabled
        tool = GetCodeByIdTool(
            db_manager=mock_db_manager,
            company_id="test_company",
            auto_generate=True
        )
        
        # Mock the documentation creator behavior
        with patch.object(tool._documentation_creator, 'create_documentation') as mock_create:
            # Setup successful generation
            mock_result = Mock()
            mock_result.error = None
            mock_create.return_value = mock_result
            
            # Setup database to return docs after generation
            mock_db_manager.get_node_by_id_v2.side_effect = [
                # First call - no docs
                Mock(
                    node_id="test_node_123",
                    node_name="example_function.py",
                    node_labels=["FILE", "PYTHON"],
                    code="def example():\n    return 42",
                    start_line=1,
                    end_line=2,
                    documentation_nodes=None,
                    inbound_relations=None,
                    outbound_relations=None
                ),
                # Second call in generation - same node
                Mock(
                    node_id="test_node_123",
                    node_name="example_function.py",
                    node_labels=["FILE", "PYTHON"],
                    code="def example():\n    return 42",
                    documentation_nodes=None
                ),
                # Third call after generation - with docs
                Mock(
                    node_id="test_node_123",
                    node_name="example_function.py",
                    node_labels=["FILE", "PYTHON"],
                    code="def example():\n    return 42",
                    documentation_nodes=[{
                        "node_id": "doc_generated_123",
                        "node_name": "Documentation for example_function",
                        "content": "This function returns the answer to everything: 42"
                    }]
                )
            ]
            
            # Run the tool
            result = tool._run("test_node_123")
            
            # Verify documentation generation was called
            mock_create.assert_called_once()
            
            # Verify the result contains auto-generated documentation
            assert "📚 DOCUMENTATION (auto-generated):" in result
            assert "This function returns the answer to everything: 42" in result
            assert "doc_generated_123" in result

    @pytest.mark.integration
    def test_get_node_workflows_with_workflow_generation(
        self,
        mock_db_manager: Mock
    ) -> None:
        """Test GetNodeWorkflowsTool with actual workflow generation flow."""
        # Create tool with auto-generation enabled
        tool = GetNodeWorkflowsTool(
            db_manager=mock_db_manager,
            company_id="test_company",
            auto_generate=True
        )
        
        # Mock the workflow creator behavior
        with patch.object(tool._workflow_creator, 'discover_workflows') as mock_discover:
            # Setup successful generation
            mock_result = Mock()
            mock_result.error = None
            mock_discover.return_value = mock_result
            
            # Mock _get_node_info
            with patch.object(tool, '_get_node_info') as mock_get_info:
                mock_get_info.return_value = {
                    "node_id": "test_node_123",
                    "name": "example_function",
                    "path": "/test/example_function.py",
                    "node_path": "/test/example_function.py::example_function",
                    "labels": ["FUNCTION", "PYTHON"]
                }
                
                # Mock _get_workflows_with_chains
                with patch.object(tool, '_get_workflows_with_chains') as mock_get_workflows:
                    # First call returns empty, second returns workflows after generation
                    mock_get_workflows.side_effect = [
                        [],  # No workflows initially
                        [{   # Workflows after generation
                            "workflow_id": "gen_workflow_123",
                            "workflow_name": "Generated Workflow",
                            "entry_point": "main",
                            "exit_point": "example_function",
                            "total_steps": 3,
                            "execution_chain": [
                                {
                                    "node_id": "main_123",
                                    "name": "main",
                                    "path": "/test/main.py",
                                    "is_target": False,
                                    "step_order": 0,
                                    "depth": 0
                                },
                                {
                                    "node_id": "test_node_123",
                                    "name": "example_function",
                                    "path": "/test/example_function.py",
                                    "is_target": True,
                                    "step_order": 1,
                                    "depth": 1
                                }
                            ]
                        }]
                    ]
                    
                    # Run the tool
                    result = tool._run("test_node_123")
                    
                    # Verify workflow discovery was called
                    mock_discover.assert_called_once_with(
                        node_path="/test/example_function.py",
                        max_depth=20,
                        save_to_database=True
                    )
                    
                    # Verify the result contains generated workflows
                    assert "📊 WORKFLOW: Generated Workflow" in result
                    assert "example_function" in result
                    assert "【YOU ARE HERE】" in result

    @pytest.mark.integration
    def test_both_tools_with_disabled_generation(
        self,
        mock_db_manager: Mock
    ) -> None:
        """Test both tools with auto-generation disabled."""
        # Create GetCodeByIdTool with auto-generation disabled
        code_tool = GetCodeByIdTool(
            db_manager=mock_db_manager,
            company_id="test_company",
            auto_generate=False
        )
        
        # Verify no documentation creator is initialized
        assert code_tool._documentation_creator is None
        
        # Run the tool
        code_result = code_tool._run("test_node_123")
        
        # Should show no documentation without attempting generation
        assert "📚 DOCUMENTATION: None found" in code_result
        assert "(auto-generated)" not in code_result
        assert "(generation attempted)" not in code_result
        
        # Create GetNodeWorkflowsTool with auto-generation disabled
        workflow_tool = GetNodeWorkflowsTool(
            db_manager=mock_db_manager,
            company_id="test_company",
            auto_generate=False
        )
        
        # Verify no workflow creator is initialized
        assert workflow_tool._workflow_creator is None
        
        # Mock required methods
        with patch.object(workflow_tool, '_get_node_info') as mock_get_info:
            mock_get_info.return_value = {
                "node_id": "test_node_123",
                "name": "example_function",
                "path": "/test/example_function.py",
                "labels": ["FUNCTION"]
            }
            
            with patch.object(workflow_tool, '_get_workflows_with_chains', return_value=[]):
                # Run the tool
                workflow_result = workflow_tool._run("test_node_123")
                
                # Should show warning without attempting generation
                assert "⚠️ WARNING: No workflows found for this node!" in workflow_result
                assert "This is likely a data issue" in workflow_result
                assert "Auto-generation was attempted" not in workflow_result

    @pytest.mark.integration
    def test_error_recovery_in_generation(
        self,
        mock_db_manager: Mock
    ) -> None:
        """Test that tools handle generation errors gracefully."""
        # Test GetCodeByIdTool error recovery
        code_tool = GetCodeByIdTool(
            db_manager=mock_db_manager,
            company_id="test_company",
            auto_generate=True
        )
        
        with patch.object(code_tool._documentation_creator, 'create_documentation') as mock_create:
            # Simulate generation error
            mock_create.side_effect = Exception("LLM API error")
            
            # Run the tool
            result = code_tool._run("test_node_123")
            
            # Should handle error gracefully
            assert "📚 DOCUMENTATION: None found (generation attempted)" in result
            
        # Test GetNodeWorkflowsTool error recovery
        workflow_tool = GetNodeWorkflowsTool(
            db_manager=mock_db_manager,
            company_id="test_company",
            auto_generate=True
        )
        
        with patch.object(workflow_tool._workflow_creator, 'discover_workflows') as mock_discover:
            # Simulate generation error
            mock_discover.side_effect = Exception("Graph traversal error")
            
            with patch.object(workflow_tool, '_get_node_info') as mock_get_info:
                mock_get_info.return_value = {
                    "node_id": "test_node_123",
                    "name": "example_function",
                    "path": "/test/example_function.py",
                    "labels": ["FUNCTION"]
                }
                
                with patch.object(workflow_tool, '_get_workflows_with_chains', return_value=[]):
                    # Run the tool
                    result = workflow_tool._run("test_node_123")
                    
                    # Should handle error gracefully
                    assert "⚠️ WARNING: No workflows found for this node!" in result
                    assert "Auto-generation was attempted but no workflows were discovered" in result

    @pytest.mark.integration
    def test_concurrent_tool_usage(
        self,
        mock_db_manager: Mock
    ) -> None:
        """Test that multiple tools can be used concurrently with auto-generation."""
        import threading
        
        results = {}
        errors = []
        
        def run_code_tool() -> None:
            try:
                tool = GetCodeByIdTool(
                    db_manager=mock_db_manager,
                    company_id="test_company",
                    auto_generate=True
                )
                with patch.object(tool._documentation_creator, 'create_documentation'):
                    results['code'] = tool._run("test_node_123")
            except Exception as e:
                errors.append(f"Code tool error: {e}")
        
        def run_workflow_tool() -> None:
            try:
                tool = GetNodeWorkflowsTool(
                    db_manager=mock_db_manager,
                    company_id="test_company",
                    auto_generate=True
                )
                with patch.object(tool._workflow_creator, 'discover_workflows'):
                    with patch.object(tool, '_get_node_info', return_value={"node_id": "test", "path": "/test"}):
                        with patch.object(tool, '_get_workflows_with_chains', return_value=[]):
                            results['workflow'] = tool._run("test_node_123")
            except Exception as e:
                errors.append(f"Workflow tool error: {e}")
        
        # Run tools concurrently
        thread1 = threading.Thread(target=run_code_tool)
        thread2 = threading.Thread(target=run_workflow_tool)
        
        thread1.start()
        thread2.start()
        
        thread1.join(timeout=5)
        thread2.join(timeout=5)
        
        # Verify both tools ran successfully
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert 'code' in results
        assert 'workflow' in results
        assert "📚 DOCUMENTATION:" in results['code']
        assert "WARNING: No workflows found" in results['workflow']