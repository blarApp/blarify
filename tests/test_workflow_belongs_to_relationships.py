"""
Tests for BELONGS_TO_WORKFLOW relationships functionality.

Tests the implementation of BELONGS_TO_WORKFLOW relationships from workflow
participant nodes to their containing workflows.
"""

import unittest
from unittest.mock import Mock
from typing import List, Dict, Any

from blarify.graph.relationship.relationship_creator import RelationshipCreator
from blarify.graph.relationship.relationship_type import RelationshipType
from blarify.documentation.workflow_creator import WorkflowCreator
from blarify.documentation.result_models import WorkflowResult
from blarify.graph.node.workflow_node import WorkflowNode


class TestWorkflowBelongsToRelationships(unittest.TestCase):
    """Test suite for BELONGS_TO_WORKFLOW relationships functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Mock workflow node
        self.workflow_node = Mock(spec=WorkflowNode)
        self.workflow_node.hashed_id = "workflow_123"
        self.workflow_node.name = "test_workflow"

        # Mock database manager
        self.db_manager = Mock()

        # Mock graph environment
        self.graph_environment = Mock()

        # Create WorkflowCreator instance,
        self.workflow_creator = WorkflowCreator(
            db_manager=self.db_manager,
            graph_environment=self.graph_environment,
            repo_id="test_repo",
            company_id="test_company",
        )

    def test_create_belongs_to_workflow_relationships_for_workflow_nodes_with_valid_ids(self) -> None:
        """Test creating BELONGS_TO_WORKFLOW relationships with valid node IDs."""
        # Arrange
        workflow_node_ids = ["node_1", "node_2", "node_3"]

        # Act
        relationships: List[Dict[str, str]] = RelationshipCreator.create_belongs_to_workflow_relationships_for_workflow_nodes(  # type: ignore
            workflow_node=self.workflow_node, workflow_node_ids=workflow_node_ids
        )

        # Assert
        self.assertEqual(len(relationships), 3)

        for i, relationship in enumerate(relationships):
            self.assertEqual(relationship["sourceId"], f"node_{i + 1}")
            self.assertEqual(relationship["targetId"], "workflow_123")
            self.assertEqual(relationship["type"], RelationshipType.BELONGS_TO_WORKFLOW.name)
            self.assertEqual(relationship["scopeText"], "")

    def test_create_belongs_to_workflow_relationships_for_workflow_nodes_with_empty_ids(self) -> None:
        """Test creating relationships with empty/None node IDs."""
        # Arrange
        workflow_node_ids = ["node_1", "node_2", ""]

        # Act
        relationships: List[Dict[str, str]] = RelationshipCreator.create_belongs_to_workflow_relationships_for_workflow_nodes(  # type: ignore
            workflow_node=self.workflow_node, workflow_node_ids=workflow_node_ids
        )

        # Assert - only valid IDs should create relationships
        self.assertEqual(len(relationships), 2)
        self.assertEqual(relationships[0]["sourceId"], "node_1")
        self.assertEqual(relationships[1]["sourceId"], "node_2")

    def test_create_belongs_to_workflow_relationships_for_workflow_nodes_with_empty_list(self) -> None:
        """Test creating relationships with empty node ID list."""
        # Arrange
        workflow_node_ids: List[str] = []

        # Act
        relationships: List[Dict[str, str]] = RelationshipCreator.create_belongs_to_workflow_relationships_for_workflow_nodes(  # type: ignore
            workflow_node=self.workflow_node, workflow_node_ids=workflow_node_ids
        )

        # Assert
        self.assertEqual(len(relationships), 0)

    def test_workflow_relationships_creation_includes_belongs_to_workflow(self) -> None:
        """Test that _create_workflow_relationships includes BELONGS_TO_WORKFLOW relationships."""
        # Arrange
        workflow_result = WorkflowResult(
            entry_point_id="entry_1",
            entry_point_name="main",
            entry_point_path="/path/to/main.py",
            workflow_nodes=[
                {"id": "node_1", "name": "function_1"},
                {"id": "node_2", "name": "function_2"},
                {"id": "", "name": "invalid_node"},  # Should be filtered out
            ],
            workflow_edges=[
                {
                    "caller_id": "node_1",
                    "callee_id": "node_2",
                    "relationship_type": "CALLS",
                    "depth": 1,
                    "call_line": 10,
                    "call_character": 5,
                }
            ],
        )

        # Act
        relationships: List[Dict[str, Any]] = self.workflow_creator._create_workflow_relationships(  # pyright: ignore[reportPrivateUsage]
            workflow_node=self.workflow_node, workflow_result=workflow_result
        )

        # Assert
        # Check that both WORKFLOW_STEP and BELONGS_TO_WORKFLOW relationships exist
        workflow_step_relationships = [r for r in relationships if r["type"] == RelationshipType.WORKFLOW_STEP.name]
        belongs_to_workflow_relationships = [
            r for r in relationships if r["type"] == RelationshipType.BELONGS_TO_WORKFLOW.name
        ]

        # Should have 1 WORKFLOW_STEP relationship from the edge
        self.assertEqual(len(workflow_step_relationships), 1)

        # Should have 2 BELONGS_TO_WORKFLOW relationships (node_1 and node_2, but not empty ID)
        self.assertEqual(len(belongs_to_workflow_relationships), 2)

        # Verify BELONGS_TO_WORKFLOW relationship details
        belongs_relationships_by_source = {r["sourceId"]: r for r in belongs_to_workflow_relationships}

        self.assertIn("node_1", belongs_relationships_by_source)
        self.assertIn("node_2", belongs_relationships_by_source)

        for source_id in ["node_1", "node_2"]:
            relationship = belongs_relationships_by_source[source_id]
            self.assertEqual(relationship["targetId"], "workflow_123")
            self.assertEqual(relationship["type"], RelationshipType.BELONGS_TO_WORKFLOW.name)
            self.assertEqual(relationship["scopeText"], "")

    def test_workflow_relationships_creation_with_empty_workflow_nodes(self) -> None:
        """Test _create_workflow_relationships with empty workflow_nodes."""
        # Arrange
        workflow_result = WorkflowResult(
            entry_point_id="entry_1",
            entry_point_name="main",
            entry_point_path="/path/to/main.py",
            workflow_nodes=[],  # Empty list
            workflow_edges=[],
        )

        # Act
        relationships: List[Dict[str, Any]] = self.workflow_creator._create_workflow_relationships(  # pyright: ignore[reportPrivateUsage]
            workflow_node=self.workflow_node, workflow_result=workflow_result
        )

        # Assert
        belongs_to_workflow_relationships = [
            r for r in relationships if r["type"] == RelationshipType.BELONGS_TO_WORKFLOW.name
        ]
        self.assertEqual(len(belongs_to_workflow_relationships), 0)

    def test_workflow_relationships_creation_with_no_workflow_nodes_field(self) -> None:
        """Test _create_workflow_relationships when workflow_nodes is None."""
        # Arrange
        workflow_result = WorkflowResult(
            entry_point_id="entry_1",
            entry_point_name="main",
            entry_point_path="/path/to/main.py",
            # workflow_nodes will default to empty list in WorkflowResult
        )

        # Act
        relationships: List[Dict[str, Any]] = self.workflow_creator._create_workflow_relationships(  # pyright: ignore[reportPrivateUsage]
            workflow_node=self.workflow_node, workflow_result=workflow_result
        )

        # Assert
        belongs_to_workflow_relationships = [
            r for r in relationships if r["type"] == RelationshipType.BELONGS_TO_WORKFLOW.name
        ]
        self.assertEqual(len(belongs_to_workflow_relationships), 0)

    def test_workflow_relationships_creation_with_invalid_node_structures(self) -> None:
        """Test _create_workflow_relationships with various invalid node structures."""
        # Arrange
        workflow_result = WorkflowResult(
            entry_point_id="entry_1",
            entry_point_name="main",
            entry_point_path="/path/to/main.py",
            workflow_nodes=[
                {"id": "valid_node", "name": "valid"},
                {"name": "no_id_field"},  # Missing id field
                {},  # Empty dict
                {"id": None, "name": "null_id"},  # None id
                {"id": "another_valid", "name": "valid2"},
            ],
        )

        # Act
        relationships: List[Dict[str, Any]] = self.workflow_creator._create_workflow_relationships(  # pyright: ignore[reportPrivateUsage]
            workflow_node=self.workflow_node, workflow_result=workflow_result
        )

        # Assert
        belongs_to_workflow_relationships = [
            r for r in relationships if r["type"] == RelationshipType.BELONGS_TO_WORKFLOW.name
        ]

        # Should only create relationships for nodes with valid IDs
        self.assertEqual(len(belongs_to_workflow_relationships), 2)

        source_ids = {r["sourceId"] for r in belongs_to_workflow_relationships}
        self.assertEqual(source_ids, {"valid_node", "another_valid"})

    def test_relationship_structure_format(self) -> None:
        """Test that created relationships have the correct structure format."""
        # Arrange
        workflow_node_ids = ["test_node_1"]

        # Act
        relationships: List[Dict[str, str]] = RelationshipCreator.create_belongs_to_workflow_relationships_for_workflow_nodes(  # type: ignore
            workflow_node=self.workflow_node, workflow_node_ids=workflow_node_ids
        )

        # Assert
        self.assertEqual(len(relationships), 1)
        relationship: Dict[str, str] = relationships[0]

        # Verify all required fields are present
        required_fields = {"sourceId", "targetId", "type", "scopeText"}
        self.assertEqual(set(relationship.keys()), required_fields)

        # Verify field types and values
        self.assertIsInstance(relationship["sourceId"], str)
        self.assertIsInstance(relationship["targetId"], str)
        self.assertIsInstance(relationship["type"], str)
        self.assertIsInstance(relationship["scopeText"], str)

        self.assertEqual(relationship["sourceId"], "test_node_1")
        self.assertEqual(relationship["targetId"], "workflow_123")
        self.assertEqual(relationship["type"], "BELONGS_TO_WORKFLOW")
        self.assertEqual(relationship["scopeText"], "")

    def test_integration_with_existing_workflow_step_relationships(self) -> None:
        """Test that BELONGS_TO_WORKFLOW relationships integrate properly with WORKFLOW_STEP relationships."""
        # Arrange
        workflow_result = WorkflowResult(
            entry_point_id="entry_1",
            entry_point_name="main",
            entry_point_path="/path/to/main.py",
            workflow_nodes=[
                {"id": "node_a", "name": "func_a"},
                {"id": "node_b", "name": "func_b"},
            ],
            workflow_edges=[
                {
                    "caller_id": "node_a",
                    "callee_id": "node_b",
                    "relationship_type": "CALLS",
                    "depth": 1,
                    "call_line": 15,
                    "call_character": 8,
                }
            ],
        )

        # Act
        relationships: List[Dict[str, Any]] = self.workflow_creator._create_workflow_relationships(  # pyright: ignore[reportPrivateUsage]
            workflow_node=self.workflow_node, workflow_result=workflow_result
        )

        # Assert
        # Should have both types of relationships
        workflow_step_count = sum(1 for r in relationships if r["type"] == RelationshipType.WORKFLOW_STEP.name)
        belongs_to_workflow_count = sum(
            1 for r in relationships if r["type"] == RelationshipType.BELONGS_TO_WORKFLOW.name
        )

        self.assertEqual(workflow_step_count, 1)
        self.assertEqual(belongs_to_workflow_count, 2)
        self.assertEqual(len(relationships), 3)  # Total of both types


if __name__ == "__main__":
    unittest.main()
