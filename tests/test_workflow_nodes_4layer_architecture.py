"""
Tests for workflow nodes with 4-layer architecture and edge-based execution flows.

This test suite validates the implementation of issue #231, covering:
- Edge ordering in workflow queries
- Relationship creation for BELONGS_TO_WORKFLOW and WORKFLOW_STEP
- 4-layer architecture integration
- Complete specification-to-code traversal
"""

import pytest
from typing import List, Dict, Any
from unittest.mock import Mock, patch, MagicMock

from blarify.db_managers.queries import find_independent_workflows_query, find_independent_workflows
from blarify.graph.relationship.relationship_creator import RelationshipCreator
from blarify.graph.relationship.relationship_type import RelationshipType
from blarify.documentation.spec_analysis_workflow import SpecAnalysisWorkflow
from blarify.graph.node.workflow_node import WorkflowNode
from blarify.graph.graph_environment import GraphEnvironment


class TestWorkflowQueryEdgeOrdering:
    """Test suite for edge ordering in workflow queries."""

    def test_find_independent_workflows_query_includes_execution_edges(self) -> None:
        """Test that the workflow query includes executionEdges in the output."""
        query = find_independent_workflows_query()
        
        # Verify the query includes executionEdges in the returned workflow object
        assert "executionEdges" in query
        assert "executionTrace" in query  # Backward compatibility
        assert "totalEdges" in query
        
        # Verify edge ordering logic is present
        assert "order: i" in query
        assert "source_id: pathNodes[i].node_id" in query
        assert "target_id: pathNodes[i+1].node_id" in query
        
        # Verify edge ordering by call site
        assert "start_line: pathRels[i].startLine" in query
        assert "reference_character: pathRels[i].referenceCharacter" in query

    def test_find_independent_workflows_returns_edges(self) -> None:
        """Test that find_independent_workflows returns execution edges."""
        mock_db_manager = Mock()
        
        # Mock database response with execution edges
        mock_workflow_data = {
            "entryPointId": "entry123",
            "entryPointName": "main",
            "entryPointPath": "/src/main.py",
            "endPointId": "end456", 
            "endPointName": "process",
            "endPointPath": "/src/process.py",
            "workflowNodes": [
                {"id": "entry123", "name": "main", "path": "/src/main.py"},
                {"id": "mid789", "name": "validate", "path": "/src/validate.py"},
                {"id": "end456", "name": "process", "path": "/src/process.py"}
            ],
            "executionEdges": [
                {
                    "source_id": "entry123",
                    "target_id": "mid789", 
                    "relationship_type": "CALLS",
                    "order": 0,
                    "start_line": 10,
                    "reference_character": 5
                },
                {
                    "source_id": "mid789",
                    "target_id": "end456",
                    "relationship_type": "CALLS", 
                    "order": 1,
                    "start_line": 25,
                    "reference_character": 12
                }
            ],
            "totalEdges": 2,
            "workflowType": "dfs_execution_trace_with_edges"
        }
        
        mock_db_manager.query.return_value = [{"workflow": mock_workflow_data}]
        
        result = find_independent_workflows(
            db_manager=mock_db_manager,
            entity_id="test_entity",
            repo_id="test_repo", 
            entry_point_id="entry123"
        )
        
        assert len(result) == 1
        workflow = result[0]
        
        # Verify execution edges are returned
        assert "executionEdges" in workflow
        assert len(workflow["executionEdges"]) == 2
        
        # Verify edge ordering
        edges = workflow["executionEdges"]
        assert edges[0]["order"] == 0
        assert edges[1]["order"] == 1
        
        # Verify edge details
        assert edges[0]["source_id"] == "entry123"
        assert edges[0]["target_id"] == "mid789"
        assert edges[1]["source_id"] == "mid789" 
        assert edges[1]["target_id"] == "end456"


class TestWorkflowStepRelationshipCreation:
    """Test suite for WORKFLOW_STEP relationship creation from execution edges."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.mock_workflow_node = Mock()
        self.mock_workflow_node.hashed_id = "workflow_123"
        self.mock_db_manager = Mock()

    def test_create_workflow_step_relationships_from_execution_edges(self) -> None:
        """Test creation of WORKFLOW_STEP relationships from execution edges."""
        execution_edges = [
            {
                "source_id": "code1",
                "target_id": "code2",
                "order": 0,
                "start_line": 10,
                "reference_character": 5
            },
            {
                "source_id": "code2", 
                "target_id": "code3",
                "order": 1,
                "start_line": 25,
                "reference_character": 12
            }
        ]
        
        # Mock documentation node queries
        self.mock_db_manager.query.side_effect = [
            # First edge: code1 -> code2
            [{"source_doc_id": "doc1", "target_doc_id": "doc2"}],
            # Second edge: code2 -> code3  
            [{"source_doc_id": "doc2", "target_doc_id": "doc3"}]
        ]
        
        relationships = RelationshipCreator.create_workflow_step_relationships_from_execution_edges(
            workflow_node=self.mock_workflow_node,
            execution_edges=execution_edges,
            db_manager=self.mock_db_manager
        )
        
        assert len(relationships) == 2
        
        # Verify first relationship
        rel1 = relationships[0]
        assert rel1["sourceId"] == "doc1"
        assert rel1["targetId"] == "doc2"
        assert rel1["type"] == RelationshipType.WORKFLOW_STEP.name
        assert "step_order:0" in rel1["scopeText"]
        assert "workflow_id:workflow_123" in rel1["scopeText"]
        assert "edge_based:true" in rel1["scopeText"]
        
        # Verify second relationship  
        rel2 = relationships[1]
        assert rel2["sourceId"] == "doc2"
        assert rel2["targetId"] == "doc3"
        assert rel2["type"] == RelationshipType.WORKFLOW_STEP.name
        assert "step_order:1" in rel2["scopeText"]

    def test_create_workflow_step_relationships_from_empty_edges(self) -> None:
        """Test handling of empty execution edges."""
        relationships = RelationshipCreator.create_workflow_step_relationships_from_execution_edges(
            workflow_node=self.mock_workflow_node,
            execution_edges=[],
            db_manager=self.mock_db_manager
        )
        
        assert relationships == []

    def test_create_workflow_step_relationships_missing_documentation(self) -> None:
        """Test handling when documentation nodes are missing."""
        execution_edges = [
            {
                "source_id": "code1",
                "target_id": "code2", 
                "order": 0
            }
        ]
        
        # Mock empty documentation query result
        self.mock_db_manager.query.return_value = []
        
        relationships = RelationshipCreator.create_workflow_step_relationships_from_execution_edges(
            workflow_node=self.mock_workflow_node,
            execution_edges=execution_edges,
            db_manager=self.mock_db_manager
        )
        
        assert relationships == []


class TestBelongsToWorkflowRelationshipCreation:
    """Test suite for BELONGS_TO_WORKFLOW relationship creation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.mock_workflow_node = Mock()
        self.mock_workflow_node.hashed_id = "workflow_456"
        self.mock_db_manager = Mock()

    def test_create_belongs_to_workflow_relationships_for_code_nodes(self) -> None:
        """Test creation of BELONGS_TO_WORKFLOW relationships."""
        workflow_code_node_ids = ["code1", "code2", "code3"]
        
        # Mock documentation nodes query
        self.mock_db_manager.query.return_value = [
            {"doc_id": "doc1"},
            {"doc_id": "doc2"}, 
            {"doc_id": "doc3"}
        ]
        
        relationships = RelationshipCreator.create_belongs_to_workflow_relationships_for_code_nodes(
            workflow_node=self.mock_workflow_node,
            workflow_code_node_ids=workflow_code_node_ids,
            db_manager=self.mock_db_manager
        )
        
        assert len(relationships) == 3
        
        # Verify all relationships point to the workflow node
        for rel in relationships:
            assert rel["targetId"] == "workflow_456"
            assert rel["type"] == RelationshipType.BELONGS_TO_WORKFLOW.name
            assert rel["scopeText"] == ""
        
        # Verify source IDs are documentation nodes
        source_ids = [rel["sourceId"] for rel in relationships]
        assert "doc1" in source_ids
        assert "doc2" in source_ids
        assert "doc3" in source_ids


class TestSpecAnalysisWorkflowIntegration:
    """Test suite for SpecAnalysisWorkflow integration with edge-based workflows."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.mock_db_manager = Mock()
        self.mock_agent_caller = Mock()
        self.graph_environment = GraphEnvironment("test", "main", "/test/path")
        
        self.workflow = SpecAnalysisWorkflow(
            company_graph_manager=self.mock_db_manager,
            agent_caller=self.mock_agent_caller,
            company_id="test_company",
            repo_id="test_repo",
            graph_environment=self.graph_environment
        )

    @patch('blarify.documentation.spec_analysis_workflow.RelationshipCreator')
    def test_save_workflows_uses_execution_edges(self, mock_relationship_creator: Mock) -> None:
        """Test that _save_workflows prioritizes execution edges when available."""
        # Mock workflow data with execution edges
        workflow_data_with_edges = {
            "entryPointName": "main_function",
            "entryPointId": "main123",
            "workflowNodes": [
                {"id": "main123", "name": "main_function"},
                {"id": "validate456", "name": "validate_input"}
            ],
            "executionEdges": [
                {"source_id": "main123", "target_id": "validate456", "order": 0}
            ]
        }
        
        state = {"discovered_workflows": [workflow_data_with_edges]}
        
        # Mock relationship creator methods
        mock_relationship_creator.create_belongs_to_workflow_relationships_for_code_nodes.return_value = []
        mock_relationship_creator.create_workflow_step_relationships_from_execution_edges.return_value = [
            {"sourceId": "doc1", "targetId": "doc2", "type": "WORKFLOW_STEP"}
        ]
        
        # Mock workflow information node creation
        with patch.object(self.workflow, '_create_standalone_workflow_information_node') as mock_create_node:
            mock_info_node = Mock()
            mock_info_node.hashed_id = "workflow_info_789"
            mock_info_node.as_object.return_value = {"test": "node"}
            mock_create_node.return_value = mock_info_node
            
            result = self.workflow._save_workflows(state)
        
        # Verify edge-based relationship creation was called
        mock_relationship_creator.create_workflow_step_relationships_from_execution_edges.assert_called_once()
        
        # Verify fallback method was not called
        mock_relationship_creator.create_workflow_step_relationships_for_code_sequence.assert_not_called()
        
        # Verify result includes edge information
        assert len(result["workflow_results"]) == 1
        workflow_result = result["workflow_results"][0]
        assert workflow_result["edge_based"] is True
        assert workflow_result["edges"] == 1

    @patch('blarify.documentation.spec_analysis_workflow.RelationshipCreator') 
    def test_save_workflows_fallback_to_sequence(self, mock_relationship_creator: Mock) -> None:
        """Test that _save_workflows falls back to sequence method when no edges."""
        # Mock workflow data without execution edges
        workflow_data_no_edges = {
            "entryPointName": "legacy_function",
            "entryPointId": "legacy123", 
            "workflowNodes": [
                {"id": "legacy123", "name": "legacy_function"},
                {"id": "helper456", "name": "helper_function"}
            ]
            # No executionEdges field
        }
        
        state = {"discovered_workflows": [workflow_data_no_edges]}
        
        # Mock relationship creator methods
        mock_relationship_creator.create_belongs_to_workflow_relationships_for_code_nodes.return_value = []
        mock_relationship_creator.create_workflow_step_relationships_for_code_sequence.return_value = [
            {"sourceId": "doc1", "targetId": "doc2", "type": "WORKFLOW_STEP"}
        ]
        
        # Mock workflow information node creation
        with patch.object(self.workflow, '_create_standalone_workflow_information_node') as mock_create_node:
            mock_info_node = Mock()
            mock_info_node.hashed_id = "workflow_info_890"
            mock_info_node.as_object.return_value = {"test": "node"}
            mock_create_node.return_value = mock_info_node
            
            result = self.workflow._save_workflows(state)
        
        # Verify sequence-based relationship creation was called
        mock_relationship_creator.create_workflow_step_relationships_for_code_sequence.assert_called_once()
        
        # Verify edge-based method was not called
        mock_relationship_creator.create_workflow_step_relationships_from_execution_edges.assert_not_called()
        
        # Verify result shows no edges
        assert len(result["workflow_results"]) == 1
        workflow_result = result["workflow_results"][0]
        assert workflow_result["edge_based"] is False
        assert workflow_result["edges"] == 0


class TestWorkflowNodeCreation:
    """Test suite for WorkflowNode creation and integration."""

    def test_workflow_node_creation_with_edges(self) -> None:
        """Test WorkflowNode creation with execution edge data."""
        workflow_data = {
            "entryPointId": "entry123",
            "entryPointName": "main_entry",
            "entryPointPath": "/src/main.py",
            "endPointId": "end456",
            "endPointName": "final_process", 
            "endPointPath": "/src/process.py",
            "workflowNodes": [
                {"id": "entry123", "name": "main_entry"},
                {"id": "end456", "name": "final_process"}
            ],
            "executionEdges": [
                {"source_id": "entry123", "target_id": "end456", "order": 0}
            ]
        }
        
        graph_environment = GraphEnvironment("test", "main", "/test/path")
        
        workflow_node = WorkflowNode(
            title="Test Workflow",
            content="Test workflow with edges",
            entry_point_id=workflow_data["entryPointId"],
            entry_point_name=workflow_data["entryPointName"],
            entry_point_path=workflow_data["entryPointPath"],
            end_point_id=workflow_data["endPointId"],
            end_point_name=workflow_data["endPointName"],
            end_point_path=workflow_data["endPointPath"],
            workflow_nodes=workflow_data["workflowNodes"],
            graph_environment=graph_environment
        )
        
        # Verify WorkflowNode properties
        assert workflow_node.entry_point_id == "entry123"
        assert workflow_node.entry_point_name == "main_entry"
        assert workflow_node.end_point_id == "end456"
        assert workflow_node.end_point_name == "final_process"
        assert len(workflow_node.workflow_nodes) == 2
        
        # Verify layer is set to 'workflows'
        assert workflow_node.layer == "workflows"
        
        # Verify object serialization includes workflow data
        obj = workflow_node.as_object()
        assert obj["attributes"]["entry_point_id"] == "entry123"
        assert obj["attributes"]["steps"] == 2


class TestEdgeCaseHandling:
    """Test suite for edge cases and error conditions."""

    def test_empty_workflow_handling(self) -> None:
        """Test handling of empty workflows (entry point with no calls)."""
        mock_workflow_node = Mock()
        mock_workflow_node.hashed_id = "empty_workflow"
        mock_db_manager = Mock()
        
        # Empty execution edges
        relationships = RelationshipCreator.create_workflow_step_relationships_from_execution_edges(
            workflow_node=mock_workflow_node,
            execution_edges=[],
            db_manager=mock_db_manager
        )
        
        assert relationships == []

    def test_circular_workflow_handling(self) -> None:
        """Test handling of circular call relationships."""
        # This test verifies that circular relationships are handled gracefully
        execution_edges = [
            {"source_id": "func1", "target_id": "func2", "order": 0},
            {"source_id": "func2", "target_id": "func1", "order": 1}  # Circular
        ]
        
        mock_workflow_node = Mock()
        mock_workflow_node.hashed_id = "circular_workflow"
        mock_db_manager = Mock()
        
        # Mock documentation queries - both find docs
        mock_db_manager.query.side_effect = [
            [{"source_doc_id": "doc1", "target_doc_id": "doc2"}],
            [{"source_doc_id": "doc2", "target_doc_id": "doc1"}]
        ]
        
        relationships = RelationshipCreator.create_workflow_step_relationships_from_execution_edges(
            workflow_node=mock_workflow_node,
            execution_edges=execution_edges,
            db_manager=mock_db_manager
        )
        
        # Should create relationships for both edges
        assert len(relationships) == 2
        assert relationships[0]["sourceId"] == "doc1"
        assert relationships[0]["targetId"] == "doc2"
        assert relationships[1]["sourceId"] == "doc2"  
        assert relationships[1]["targetId"] == "doc1"

    def test_missing_code_node_ids_in_edges(self) -> None:
        """Test handling of execution edges with missing node IDs."""
        execution_edges = [
            {"source_id": "", "target_id": "code2", "order": 0},  # Missing source
            {"source_id": "code2", "target_id": "", "order": 1},  # Missing target
            {"order": 2}  # Missing both IDs
        ]
        
        mock_workflow_node = Mock()
        mock_workflow_node.hashed_id = "incomplete_workflow"
        mock_db_manager = Mock()
        
        relationships = RelationshipCreator.create_workflow_step_relationships_from_execution_edges(
            workflow_node=mock_workflow_node,
            execution_edges=execution_edges,
            db_manager=mock_db_manager
        )
        
        # Should return empty list due to missing node IDs
        assert relationships == []


class TestPerformanceValidation:
    """Test suite for performance validation of edge-based queries."""

    def test_edge_query_structure_efficiency(self) -> None:
        """Test that edge query structure is efficient."""
        query = find_independent_workflows_query()
        
        # Verify query uses efficient patterns
        assert "LIMIT 1" in query  # Limits to single path for performance
        assert "ORDER BY sortKey" in query  # Efficient ordering
        assert "NODE_PATH" in query  # Prevents infinite loops
        
        # Verify batch operations are supported in edge creation
        assert "CASE WHEN size(pathRels) > 0" in query  # Handles empty edge cases
        assert "range(0, size(pathRels)-1)" in query  # Efficient edge iteration

    def test_relationship_creation_batch_efficiency(self) -> None:
        """Test that relationship creation supports batch operations."""
        mock_workflow_node = Mock()
        mock_workflow_node.hashed_id = "batch_test"
        mock_db_manager = Mock()
        
        # Large number of execution edges to test batch handling
        execution_edges = [
            {"source_id": f"code{i}", "target_id": f"code{i+1}", "order": i}
            for i in range(100)
        ]
        
        # Mock documentation queries for all edges
        mock_db_manager.query.side_effect = [
            [{"source_doc_id": f"doc{i}", "target_doc_id": f"doc{i+1}"}]
            for i in range(100)
        ]
        
        relationships = RelationshipCreator.create_workflow_step_relationships_from_execution_edges(
            workflow_node=mock_workflow_node,
            execution_edges=execution_edges,
            db_manager=mock_db_manager
        )
        
        # Verify all relationships created
        assert len(relationships) == 100
        
        # Verify relationships maintain order
        for i, rel in enumerate(relationships):
            assert f"step_order:{i}" in rel["scopeText"]