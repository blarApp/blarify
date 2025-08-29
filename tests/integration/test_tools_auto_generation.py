"""Integration tests for tools auto-generation functionality."""

import pytest
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from blarify.tools.get_code_by_id_tool import GetCodeByIdTool
from blarify.tools.get_node_workflows_tool import GetNodeWorkflowsTool
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from neo4j_container_manager.types import Neo4jContainerInstance
from blarify.prebuilt.graph_builder import GraphBuilder


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestToolsAutoGenerationIntegration:
    """Integration tests for auto-generation features in tools."""

    async def setup_test_graph(
        self,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
    ) -> tuple[Neo4jManager, str | None]:
        """Setup a test graph with Python code examples and return a node ID."""
        python_examples_path = test_code_examples_path / "python"
        
        # Build graph from test code
        builder = GraphBuilder(root_path=str(python_examples_path))
        graph = builder.build()
        
        # Save to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        # Get a node ID for testing (find a function node)
        query = """
        MATCH (n:FUNCTION)
        RETURN n.node_id as node_id
        LIMIT 1
        """
        result = db_manager.query(query, {})
        
        if result and len(result) > 0:
            node_id = result[0]["node_id"]
        else:
            # Fallback to any node
            query = "MATCH (n) RETURN n.node_id as node_id LIMIT 1"
            result = db_manager.query(query, {})
            node_id = result[0]["node_id"] if result else None
            
        return db_manager, node_id

    async def test_get_code_by_id_tool_with_disabled_generation(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
    ) -> None:
        """Test GetCodeByIdTool with auto-generation disabled."""
        db_manager, node_id = await self.setup_test_graph(neo4j_instance, test_code_examples_path)
        
        if not node_id:
            pytest.skip("No nodes found in test graph")
        
        try:
            # Create tool with auto-generation disabled
            tool = GetCodeByIdTool(
                db_manager=db_manager,
                company_id="default_user",  # Use the default entity ID
                auto_generate=False
            )
            
            # Run the tool
            result = tool._run(node_id)  # type: ignore[reportPrivateUsage]
            
            # Should get code but no documentation
            assert "📄 FILE:" in result or "📝 CODE:" in result
            assert node_id in result
            assert "📚 DOCUMENTATION: None found" in result
            assert "(auto-generated)" not in result
            
        finally:
            db_manager.close()

    async def test_get_code_by_id_tool_with_enabled_generation_mocked(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
    ) -> None:
        """Test GetCodeByIdTool with auto-generation enabled but mocked to avoid LLM calls."""
        db_manager, node_id = await self.setup_test_graph(neo4j_instance, test_code_examples_path)
        
        if not node_id:
            pytest.skip("No nodes found in test graph")
        
        try:
            # Create tool with auto-generation enabled
            tool = GetCodeByIdTool(
                db_manager=db_manager,
                company_id="default_user",
                auto_generate=True
            )
            
            # Mock the documentation creator to avoid actual LLM calls
            with patch.object(tool._documentation_creator, 'create_documentation') as mock_create:  # type: ignore[reportPrivateUsage]
                mock_result = Mock()
                mock_result.error = None
                mock_create.return_value = mock_result
                
                # Run the tool
                result = tool._run(node_id)  # type: ignore[reportPrivateUsage]
                
                # Should get code
                assert "📄 FILE:" in result or "📝 CODE:" in result
                assert node_id in result
                
                # Documentation generation should be attempted
                assert "📚 DOCUMENTATION:" in result
                # Since we mocked it and didn't return actual docs, should say generation attempted
                assert "None found (generation attempted)" in result
                
                # Verify the mock was called
                mock_create.assert_called_once()
                
        finally:
            db_manager.close()

    async def test_get_node_workflows_tool_with_disabled_generation(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
    ) -> None:
        """Test GetNodeWorkflowsTool with auto-generation disabled."""
        db_manager, node_id = await self.setup_test_graph(neo4j_instance, test_code_examples_path)
        
        if not node_id:
            pytest.skip("No nodes found in test graph")
        
        try:
            # Create tool with auto-generation disabled
            tool = GetNodeWorkflowsTool(
                db_manager=db_manager,
                company_id="default_user",
                auto_generate=False
            )
            
            # Run the tool
            result = tool._run(node_id)  # type: ignore[reportPrivateUsage]
            
            # Should get basic node info
            assert "🔄 WORKFLOWS FOR NODE:" in result
            assert node_id in result
            
            # Since no workflows exist and auto-generate is disabled
            if "WARNING: No workflows found" in result:
                assert "This is likely a data issue" in result
                assert "Auto-generation was attempted" not in result
            
        finally:
            db_manager.close()

    async def test_get_node_workflows_tool_with_enabled_generation_mocked(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
    ) -> None:
        """Test GetNodeWorkflowsTool with auto-generation enabled but mocked."""
        db_manager, node_id = await self.setup_test_graph(neo4j_instance, test_code_examples_path)
        
        if not node_id:
            pytest.skip("No nodes found in test graph")
        
        try:
            # Create tool with auto-generation enabled
            tool = GetNodeWorkflowsTool(
                db_manager=db_manager,
                company_id="default_user",
                auto_generate=True
            )
            
            # Mock the workflow creator to avoid actual workflow discovery
            with patch.object(tool._workflow_creator, 'discover_workflows') as mock_discover:  # type: ignore[reportPrivateUsage]
                mock_result = Mock()
                mock_result.error = None
                mock_discover.return_value = mock_result
                
                # Run the tool
                result = tool._run(node_id)  # type: ignore[reportPrivateUsage]
                
                # Should get basic node info
                assert "🔄 WORKFLOWS FOR NODE:" in result
                assert node_id in result
                
                # If no workflows found, should indicate auto-generation was attempted
                if "WARNING: No workflows found" in result:
                    assert "Auto-generation was attempted" in result
                    # Verify the mock was called
                    mock_discover.assert_called_once()
            
        finally:
            db_manager.close()

    async def test_both_tools_handle_invalid_node_id(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
    ) -> None:
        """Test that both tools handle invalid node IDs gracefully."""
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        
        invalid_node_id = "00000000000000000000000000000000"
        
        try:
            # Test GetCodeByIdTool with invalid ID
            code_tool = GetCodeByIdTool(
                db_manager=db_manager,
                company_id="default_user",
                auto_generate=True
            )
            
            # Mock to avoid actual LLM calls
            with patch.object(code_tool._documentation_creator, 'create_documentation'):  # type: ignore[reportPrivateUsage]
                result = code_tool._run(invalid_node_id)  # type: ignore[reportPrivateUsage]
                assert "No code found" in result
            
            # Test GetNodeWorkflowsTool with invalid ID  
            workflow_tool = GetNodeWorkflowsTool(
                db_manager=db_manager,
                company_id="default_user",
                auto_generate=True
            )
            
            # Mock to avoid actual workflow discovery
            with patch.object(workflow_tool._workflow_creator, 'discover_workflows'):  # type: ignore[reportPrivateUsage]
                result = workflow_tool._run(invalid_node_id)  # type: ignore[reportPrivateUsage]
                assert "not found" in result.lower()
            
        finally:
            db_manager.close()

    async def test_documentation_generation_error_handling(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
    ) -> None:
        """Test that GetCodeByIdTool handles documentation generation errors gracefully."""
        db_manager, node_id = await self.setup_test_graph(neo4j_instance, test_code_examples_path)
        
        if not node_id:
            pytest.skip("No nodes found in test graph")
        
        try:
            tool = GetCodeByIdTool(
                db_manager=db_manager,
                company_id="default_user",
                auto_generate=True
            )
            
            # Mock the documentation creator to simulate an error
            with patch.object(tool._documentation_creator, 'create_documentation') as mock_create:  # type: ignore[reportPrivateUsage]
                mock_create.side_effect = Exception("Simulated LLM error")
                
                # Run the tool - should not crash
                result = tool._run(node_id)  # type: ignore[reportPrivateUsage]
                
                # Should still get code
                assert "📄 FILE:" in result or "📝 CODE:" in result
                
                # Should indicate generation was attempted but failed
                assert "📚 DOCUMENTATION: None found (generation attempted)" in result
                
        finally:
            db_manager.close()

    async def test_workflow_generation_error_handling(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
    ) -> None:
        """Test that GetNodeWorkflowsTool handles workflow generation errors gracefully."""
        db_manager, node_id = await self.setup_test_graph(neo4j_instance, test_code_examples_path)
        
        if not node_id:
            pytest.skip("No nodes found in test graph")
        
        try:
            tool = GetNodeWorkflowsTool(
                db_manager=db_manager,
                company_id="default_user",
                auto_generate=True
            )
            
            # Mock the workflow creator to simulate an error
            with patch.object(tool._workflow_creator, 'discover_workflows') as mock_discover:  # type: ignore[reportPrivateUsage]
                mock_discover.side_effect = Exception("Simulated workflow discovery error")
                
                # Run the tool - should not crash
                result = tool._run(node_id)  # type: ignore[reportPrivateUsage]
                
                # Should still get basic info
                assert "🔄 WORKFLOWS FOR NODE:" in result
                
                # Should indicate auto-generation was attempted
                if "WARNING: No workflows found" in result:
                    assert "Auto-generation was attempted" in result
                
        finally:
            db_manager.close()