"""
Unit test specifically for verifying the fallback mechanism triggers correctly.

This test ensures that when a deadlock would occur, the fallback strategy is used
and produces valid documentation.
"""

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, Mock, patch

if TYPE_CHECKING:
    pass


class TestFallbackMechanism:
    """Test that fallback mechanism triggers correctly when deadlock is detected."""

    def test_fallback_triggered_on_deadlock_detection(self) -> None:
        """Test that fallback is triggered when deadlock would occur."""
        from blarify.documentation.utils.recursive_dfs_processor import BottomUpBatchProcessor
        from blarify.repositories.graph_db_manager.dtos.node_with_content_dto import NodeWithContentDto

        # Create mock dependencies
        mock_db_manager = MagicMock()
        mock_llm_provider = MagicMock()
        mock_graph_environment = MagicMock()

        # Create processor with our dependencies
        processor = BottomUpBatchProcessor(
            db_manager=mock_db_manager,
            agent_caller=mock_llm_provider,
            company_id="test_company",
            repo_id="test_repo",
            graph_environment=mock_graph_environment,
            max_workers=2,  # Low worker count to make deadlock more likely
        )

        # Create test nodes that would form a circular dependency
        node_a = NodeWithContentDto(
            id="node_a",
            name="function_a",
            labels=["FUNCTION"],
            path="file://test/module_a.py",
            content="def function_a(): return function_b()",
            start_line=1,
            end_line=1,
        )

        node_b = NodeWithContentDto(
            id="node_b",
            name="function_b",
            labels=["FUNCTION"],
            path="file://test/module_b.py",
            content="def function_b(): return function_a()",
            start_line=1,
            end_line=1,
        )

        # Mock the database to return our circular nodes
        mock_db_manager.get_node_by_id.side_effect = lambda node_id, *args, **kwargs: {  # type: ignore
            "node_a": node_a,
            "node_b": node_b,
        }.get(node_id)

        # Mock get_navigation_children to return circular dependency
        def mock_get_navigation_children(node: Any) -> list:
            if node.id == "node_a":
                return [node_b]  # A depends on B
            elif node.id == "node_b":
                return [node_a]  # B depends on A (circular!)
            return []

        # Simulate a scenario where thread 1 is processing node_a and thread 2 is processing node_b
        # Thread 1 wants to wait for node_b, Thread 2 wants to wait for node_a (deadlock!)

        # Set up the dependency tracker to simulate the deadlock scenario
        processor.dependency_tracker.register_processor("node_a", "thread_1")
        processor.dependency_tracker.register_processor("node_b", "thread_2")
        processor.dependency_tracker.register_waiter("node_b", "thread_1")  # Thread 1 waits for B

        # Now when thread 2 tries to wait for node_a, it should detect deadlock
        can_wait = processor.dependency_tracker.register_waiter("node_a", "thread_2")

        # Verify deadlock is detected
        assert can_wait is False, "Deadlock should be detected"

        # Mock the LLM response for fallback processing
        mock_llm_response = Mock()
        mock_llm_response.content = "Fallback documentation for circular dependency"
        mock_llm_provider.call_dumb_agent.return_value = mock_llm_response

        # Now test that the fallback handler is called
        with patch.object(processor, "_get_navigation_children", mock_get_navigation_children):
            # Process node_b with the fallback mechanism
            result = processor._handle_deadlock_fallback(node_b)

        # Verify fallback was used
        assert result is not None, "Fallback should produce a result"
        assert result.content == "Fallback documentation for circular dependency"
        assert hasattr(result, "metadata") and result.metadata is not None, "Fallback should include metadata"
        if result.metadata:
            assert result.metadata.get("is_fallback") is True, "Should be marked as fallback"
            assert result.metadata.get("fallback_reason") == "circular_dependency_deadlock"

        # Verify the result is cached to prevent reprocessing
        assert node_b.id in processor.deadlock_fallback_cache

    def test_fallback_with_partial_children_context(self) -> None:
        """Test fallback processing when some children are already processed."""
        from blarify.documentation.utils.recursive_dfs_processor import BottomUpBatchProcessor
        from blarify.repositories.graph_db_manager.dtos.node_with_content_dto import NodeWithContentDto
        from blarify.graph.node.documentation_node import DocumentationNode

        # Create mock dependencies
        mock_db_manager = MagicMock()
        mock_llm_provider = MagicMock()
        mock_graph_environment = MagicMock()

        processor = BottomUpBatchProcessor(
            db_manager=mock_db_manager,
            agent_caller=mock_llm_provider,
            company_id="test_company",
            repo_id="test_repo",
            graph_environment=mock_graph_environment,
            max_workers=2,
        )

        # Create a parent node with children
        parent_node = NodeWithContentDto(
            id="parent",
            name="parent_function",
            labels=["FUNCTION"],
            path="file://test/parent.py",
            content="def parent_function(): child1(); child2(); child3()",
            start_line=1,
            end_line=1,
        )

        child1 = NodeWithContentDto(
            id="child1",
            name="child1",
            labels=["FUNCTION"],
            path="file://test/child.py",
            content="def child1(): pass",
            start_line=1,
            end_line=1,
        )

        child2 = NodeWithContentDto(
            id="child2",
            name="child2",
            labels=["FUNCTION"],
            path="file://test/child.py",
            content="def child2(): pass",
            start_line=3,
            end_line=3,
        )

        # Pre-process child1 (simulating it's already done)
        processed_child1 = DocumentationNode(
            content="Child 1 does something",
            info_type="function_description",
            source_path="file://test/child.py",
            source_name="child1",
            source_labels=["FUNCTION"],
            source_id="child1",
            source_type="recursive_analysis",
            graph_environment=mock_graph_environment,
        )
        processor.node_descriptions["child1"] = processed_child1

        # Mock get_navigation_children to return both children
        with patch.object(processor, "_get_navigation_children", return_value=[child1, child2]):
            # Mock LLM response
            mock_response = Mock()
            mock_response.content = "Parent with partial context: uses child1 (documented) and child2 (unavailable)"
            mock_llm_provider.call_dumb_agent.return_value = mock_response

            # Process with fallback
            result = processor._handle_deadlock_fallback(parent_node)

        # Verify the fallback used partial context
        assert result is not None
        assert "partial context" in result.content.lower()
        if hasattr(result, "metadata") and result.metadata:
            assert result.metadata.get("is_fallback") is True
            assert result.metadata.get("partial_children_count") == 1  # Only child1 was available

        # Verify LLM was called with partial context
        mock_llm_provider.call_dumb_agent.assert_called()
        call_args = mock_llm_provider.call_dumb_agent.call_args
        input_dict = call_args[1]["input_dict"]
        assert "Child 1 does something" in input_dict.get("child_descriptions", "")

    def test_fallback_as_enhanced_leaf_when_no_children_available(self) -> None:
        """Test fallback processes node as enhanced leaf when no child context is available."""
        from blarify.documentation.utils.recursive_dfs_processor import BottomUpBatchProcessor
        from blarify.repositories.graph_db_manager.dtos.node_with_content_dto import NodeWithContentDto

        # Create mock dependencies
        mock_db_manager = MagicMock()
        mock_llm_provider = MagicMock()
        mock_graph_environment = MagicMock()

        processor = BottomUpBatchProcessor(
            db_manager=mock_db_manager,
            agent_caller=mock_llm_provider,
            company_id="test_company",
            repo_id="test_repo",
            graph_environment=mock_graph_environment,
            max_workers=2,
        )

        # Create a node that would have children but none are processed
        node = NodeWithContentDto(
            id="isolated_node",
            name="isolated_function",
            labels=["FUNCTION"],
            path="file://test/isolated.py",
            content="def isolated_function(): return complex_logic()",
            start_line=1,
            end_line=1,
        )

        # Mock get_navigation_children to return children that aren't processed
        unprocessed_child = NodeWithContentDto(
            id="unprocessed",
            name="unprocessed",
            labels=["FUNCTION"],
            path="file://test/other.py",
            content="def unprocessed(): pass",
            start_line=1,
            end_line=1,
        )

        with patch.object(processor, "_get_navigation_children", return_value=[unprocessed_child]):
            # Mock LLM response for enhanced leaf processing
            mock_response = Mock()
            mock_response.content = "Enhanced leaf analysis: function with unavailable dependencies"
            mock_llm_provider.call_dumb_agent.return_value = mock_response

            # Process with fallback
            result = processor._handle_deadlock_fallback(node)

        # Verify enhanced leaf processing was used
        assert result is not None
        assert "enhanced leaf" in result.content.lower()
        if hasattr(result, "metadata") and result.metadata:
            assert result.metadata.get("is_fallback") is True
        assert result.info_type == "enhanced_leaf_fallback"

        # Verify the node was processed without child context
        mock_llm_provider.call_dumb_agent.assert_called()
        call_args = mock_llm_provider.call_dumb_agent.call_args
        input_dict = call_args[1]["input_dict"]
        # Should have node content but no child descriptions
        assert node.content in input_dict.get("node_content", "")
        assert "child_descriptions" not in input_dict or input_dict.get("child_descriptions", "") == ""
