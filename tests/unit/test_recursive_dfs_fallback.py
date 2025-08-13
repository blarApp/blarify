"""
Unit tests for fallback strategies in RecursiveDFSProcessor following TDD approach.

These tests are written first (TDD) to define the behavior we expect
from the fallback mechanisms before implementation.
"""

import pytest
from unittest.mock import Mock, patch

from blarify.documentation.utils.recursive_dfs_processor import RecursiveDFSProcessor
from blarify.graph.node.documentation_node import DocumentationNode
from blarify.db_managers.dtos.node_with_content_dto import NodeWithContentDto


class TestRecursiveDFSFallbackStrategies:
    """Unit tests for fallback strategies following TDD approach."""
    
    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock database manager."""
        mock = Mock()
        mock.get_node_by_id = Mock(return_value=None)
        return mock
    
    @pytest.fixture  
    def mock_llm_provider(self):
        """Create a mock LLM provider."""
        mock = Mock()
        # Return object with content attribute
        mock.call_dumb_agent = Mock(return_value=Mock(content="Mock description"))
        return mock
    
    @pytest.fixture
    def mock_graph_environment(self):
        """Create a mock graph environment."""
        mock = Mock()
        mock.generate_node_id = Mock(side_effect=lambda path, labels: f"id_{path}")
        return mock
    
    @pytest.fixture
    def processor(self, mock_db_manager, mock_llm_provider, mock_graph_environment):
        """Create a RecursiveDFSProcessor instance for testing."""
        return RecursiveDFSProcessor(
            db_manager=mock_db_manager,
            agent_caller=mock_llm_provider,
            company_id="test_company",
            repo_id="test_repo",
            graph_environment=mock_graph_environment,
            max_workers=5
        )
    
    def test_handle_deadlock_fallback_with_partial_children(self, processor):
        """Test fallback handling when some children are already processed."""
        # Given - Create test nodes
        parent_node = NodeWithContentDto(
            id="parent_id",
            name="parent_func",
            path="file://test/parent.py",
            labels=["Function"],
            content="def parent_func(): pass",
            children=[],
            properties={}
        )
        
        # Create child node DTO
        child_node = NodeWithContentDto(
            id="child1_id",
            name="child1_func",
            path="file://test/child1.py",
            labels=["Function"],
            content="def child1_func(): pass",
            children=[],
            properties={}
        )
        
        # Pre-populate some child descriptions in cache
        child1_doc = DocumentationNode(
            title="Child 1",
            content="Child 1 description",
            info_type="function_description",
            source_path="file://test/child1.py",
            source_name="child1_func",
            source_labels=["Function"],
            source_id="child1_id",
            source_type="function",
            graph_environment=processor.graph_environment
        )
        processor.node_descriptions["child1_id"] = child1_doc
        
        # Mock _get_navigation_children to return our child
        with patch.object(processor, '_get_navigation_children', return_value=[child_node]):
            # When - Call fallback handler
            result = processor._handle_deadlock_fallback(parent_node)
        
        # Then - Verify fallback processing
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.get("is_fallback") is True
        assert result.metadata.get("fallback_reason") == "circular_dependency_deadlock"
        assert result.metadata.get("partial_children_count") == 1
        
    def test_handle_deadlock_fallback_no_children(self, processor):
        """Test fallback handling when no child context is available."""
        # Given - Node with no processed children
        node = NodeWithContentDto(
            id="node_id",
            name="test_func",
            path="file://test/file.py",
            labels=["Function"],
            content="def test_func(): pass",
            children=[],
            properties={}
        )
        
        # When - Call fallback handler
        result = processor._handle_deadlock_fallback(node)
        
        # Then - Verify enhanced leaf processing
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.get("is_fallback") is True
        assert result.metadata.get("fallback_reason") == "circular_dependency_deadlock"
        assert result.info_type == "enhanced_leaf_fallback"
        
    def test_timeout_fallback_mechanism(self, processor):
        """Test that timeout triggers fallback processing."""
        # Given - Node that will timeout
        node = NodeWithContentDto(
            id="timeout_node",
            name="timeout_func",
            path="file://test/timeout.py",
            labels=["Function"],
            content="def timeout_func(): pass",
            children=[],
            properties={}
        )
        
        # Set a very short timeout for testing
        processor.fallback_timeout_seconds = 0.1
        
        # When - Call timeout handler
        result = processor._handle_timeout_fallback(node)
        
        # Then - Verify fallback was used
        assert result is not None
        assert result.metadata is not None
        assert result.metadata.get("is_fallback") is True
        
    def test_fallback_cache_prevents_reprocessing(self, processor):
        """Test that fallback cache prevents duplicate processing."""
        # Given - Node to process
        node = NodeWithContentDto(
            id="cached_node",
            name="cached_func",
            path="file://test/cached.py",
            labels=["Function"],
            content="def cached_func(): pass",
            children=[],
            properties={}
        )
        
        # When - Call fallback handler twice
        result1 = processor._handle_deadlock_fallback(node)
        
        # Record the LLM call count
        initial_call_count = processor.agent_caller.call_dumb_agent.call_count
        
        result2 = processor._handle_deadlock_fallback(node)
        
        # Then - Verify caching worked
        assert result1 is result2  # Same object returned
        assert processor.agent_caller.call_dumb_agent.call_count == initial_call_count  # No additional LLM calls
        assert "cached_node" in processor.deadlock_fallback_cache
        
    def test_process_parent_node_with_partial_context(self, processor):
        """Test processing parent nodes with only partial child context."""
        # Given - Parent node and partial children
        parent_node = NodeWithContentDto(
            id="parent_id",
            name="ParentClass",
            path="file://test/parent.py",
            labels=["Class"],
            content="class ParentClass:\n    def method1(self): pass\n    def method2(self): pass",
            children=[],
            properties={}
        )
        
        available_children = [
            DocumentationNode(
                title="Method 1",
                content="This method does something",
                info_type="function_description",
                source_path="file://test/parent.py",
                source_name="method1",
                source_labels=["Function"],
                source_id="method1_id",
                source_type="function",
                graph_environment=processor.graph_environment
            )
        ]
        
        # When - Process with partial context
        result = processor._process_parent_node_with_partial_context(
            parent_node, available_children, is_fallback=True
        )
        
        # Then - Verify proper handling
        assert result is not None
        assert result.info_type == "parent_description_fallback"
        assert result.metadata["is_fallback"] is True
        assert result.metadata["partial_children_count"] == 1
        assert result.metadata["fallback_reason"] == "circular_dependency_deadlock"
        
    def test_process_node_as_enhanced_leaf(self, processor):
        """Test processing nodes as enhanced leaves when context unavailable."""
        # Given - Node to process as enhanced leaf
        node = NodeWithContentDto(
            id="leaf_node",
            name="complex_func",
            path="file://test/complex.py",
            labels=["Function"],
            content="def complex_func(x, y):\n    result = x + y\n    return result * 2",
            children=[],
            properties={}
        )
        
        # When - Process as enhanced leaf
        result = processor._process_node_as_enhanced_leaf(node, is_fallback=True)
        
        # Then - Verify enhanced processing
        assert result is not None
        assert result.info_type == "enhanced_leaf_fallback"
        assert result.source_type == "enhanced_leaf_analysis_fallback"
        assert result.metadata["is_fallback"] is True
        assert result.metadata["fallback_reason"] == "circular_dependency_deadlock"