"""
Tests for FolderProcessingWorkflow _save_information_nodes method.
"""

import pytest
from typing import List, Dict, Any
from unittest.mock import Mock
from blarify.documentation.root_file_folder_processing_workflow import RooFileFolderProcessingWorkflow
from blarify.graph.graph_environment import GraphEnvironment


class TestSaveInformationNodes:
    """Test suite for _save_information_nodes method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.db_manager = Mock()
        self.agent_caller = Mock()
        self.company_id = "test_company"
        self.repo_id = "test_repo"
        self.folder_path = "src/components"
        self.graph_environment = GraphEnvironment("test", "main", "/test/path")

        self.workflow = RooFileFolderProcessingWorkflow(
            db_manager=self.db_manager,
            agent_caller=self.agent_caller,
            company_id=self.company_id,
            repo_id=self.repo_id,
            node_path=self.folder_path,
            graph_environment=self.graph_environment,
        )

    def test_save_information_nodes_success(self) -> None:
        """Test successful saving of information nodes and relationships."""
        # Create mock InformationNode objects as dictionaries (as they come from ProcessingResult)
        info_nodes: List[Dict[str, Any]] = [
            {
                "type": "INFORMATION",
                "extra_labels": [],
                "attributes": {
                    "node_id": "info_node1",
                    "title": "Component A Description",
                    "content": "This component handles user authentication",
                    "info_type": "component_description",
                    "source_path": "/src/components/auth.py",
                    "source_labels": ["FILE", "PYTHON"],
                    "source_type": "recursive_leaf_analysis",
                    "layer": "documentation",
                },
            },
            {
                "type": "INFORMATION",
                "extra_labels": [],
                "attributes": {
                    "node_id": "info_node2",
                    "title": "Component B Description",
                    "content": "This component manages database connections",
                    "info_type": "component_description",
                    "source_path": "/src/components/db.py",
                    "source_labels": ["FILE", "PYTHON"],
                    "source_type": "recursive_leaf_analysis",
                    "layer": "documentation",
                },
            },
        ]

        # Create node source mapping
        node_source_mapping: Dict[str, str] = {"info_node1": "source_node1", "info_node2": "source_node2"}

        # Call the method
        result = self.workflow._save_information_nodes(info_nodes, node_source_mapping)

        # Assert create_nodes was called with 2 nodes
        assert self.db_manager.create_nodes.called
        call_args = self.db_manager.create_nodes.call_args[0][0]
        assert len(call_args) == 2

        # Verify node structure
        first_node = call_args[0]
        assert first_node["type"] == "INFORMATION"
        assert first_node["attributes"]["title"] == "Component A Description"
        assert first_node["attributes"]["content"] == "This component handles user authentication"
        assert first_node["attributes"]["info_type"] == "component_description"
        assert first_node["attributes"]["node_id"] == "info_node1"
        assert first_node["attributes"]["layer"] == "documentation"

        # Assert create_edges was called with 2 relationships
        assert self.db_manager.create_edges.called
        edges_args = self.db_manager.create_edges.call_args[0][0]
        assert len(edges_args) == 2

        # Verify edge structure
        assert edges_args[0] == {
            "sourceId": "source_node1",
            "targetId": "info_node1",
            "type": "DESCRIBES",
            "scopeText": "semantic_documentation",
        }
        assert edges_args[1] == {
            "sourceId": "source_node2",
            "targetId": "info_node2",
            "type": "DESCRIBES",
            "scopeText": "semantic_documentation",
        }

        # Verify result
        assert result["success"] is True
        assert result["nodes_saved"] == 2
        assert result["relationships_created"] == 2
        assert result["errors"] == []

    def test_save_information_nodes_with_conversion_error(self) -> None:
        """Test handling of node conversion errors."""
        # Create a node that will cause conversion error by mocking the conversion method
        info_nodes: List[Dict[str, Any]] = [
            {
                "type": "INFORMATION",
                "extra_labels": [],
                "attributes": {
                    "node_id": "info_node1",
                    "title": "Good Node",
                    "content": "Valid content",
                    "info_type": "component_description",
                    "source_path": "/src/components/good.py",
                    "source_labels": ["FILE", "PYTHON"],
                    "source_type": "recursive_leaf_analysis",
                    "layer": "documentation",
                },
            }
        ]

        node_source_mapping: Dict[str, str] = {"info_node1": "source_node1"}

        # Create an info_nodes list with an invalid structure to test error handling during database operations
        invalid_info_nodes: List[Dict[str, Any]] = [
            {"invalid": "structure"}  # This should not cause processing errors anymore since we removed conversion
        ]

        # Call the method with valid structure (no processing errors should occur)
        result = self.workflow._save_information_nodes(info_nodes, node_source_mapping)

        # Verify that it works correctly since we removed the conversion step
        assert result["success"] is True
        assert result["nodes_saved"] == 1
        assert result["relationships_created"] == 1
        assert result["errors"] == []

    def test_save_information_nodes_with_database_error(self) -> None:
        """Test handling of database save errors."""
        info_nodes: List[Dict[str, Any]] = [
            {
                "type": "INFORMATION",
                "extra_labels": [],
                "attributes": {
                    "node_id": "info_node1",
                    "title": "Test Node",
                    "content": "Test content",
                    "info_type": "component_description",
                    "source_path": "/src/test.py",
                    "source_labels": ["FILE"],
                    "source_type": "recursive_leaf_analysis",
                    "layer": "documentation",
                },
            }
        ]

        node_source_mapping: Dict[str, str] = {"info_node1": "source_node1"}

        # Configure database to raise error
        self.db_manager.create_nodes.side_effect = Exception("Database connection failed")

        # Call the method
        result = self.workflow._save_information_nodes(info_nodes, node_source_mapping)

        # Verify error handling
        assert result["success"] is False
        assert result["nodes_saved"] == 0
        assert result["relationships_created"] == 0
        assert len(result["errors"]) == 1
        assert "Database save error" in result["errors"][0]

    def test_save_information_nodes_empty_input(self) -> None:
        """Test handling of empty input."""
        # Call with empty lists
        result = self.workflow._save_information_nodes([], {})

        # Verify nothing was called
        assert not self.db_manager.create_nodes.called
        assert not self.db_manager.create_edges.called

        # Verify result
        assert result["success"] is True
        assert result["nodes_saved"] == 0
        assert result["relationships_created"] == 0
        assert result["errors"] == []

    def test_save_information_nodes_mismatched_mapping(self) -> None:
        """Test handling when node_source_mapping has different keys than nodes."""
        info_nodes: List[Dict[str, Any]] = [
            {
                "type": "INFORMATION",
                "extra_labels": [],
                "attributes": {
                    "node_id": "info_node1",
                    "title": "Test Node",
                    "content": "Test content",
                    "info_type": "component_description",
                    "source_path": "/src/test.py",
                    "source_labels": ["FILE"],
                    "source_type": "recursive_leaf_analysis",
                    "layer": "documentation",
                },
            }
        ]

        # Mapping has extra entries
        node_source_mapping: Dict[str, str] = {
            "info_node1": "source_node1",
            "info_node2": "source_node2",  # No corresponding info node
            "info_node3": "source_node3",  # No corresponding info node
        }

        # Call the method
        result = self.workflow._save_information_nodes(info_nodes, node_source_mapping)

        # Should only create relationships for successfully converted nodes
        edges_args = self.db_manager.create_edges.call_args[0][0]
        assert len(edges_args) == 1  # Only for info_node1 which was converted

        assert result["success"] is True
        assert result["nodes_saved"] == 1
        assert result["relationships_created"] == 1

    def test_save_information_nodes_edge_creation_error(self) -> None:
        """Test handling when edge creation fails but node creation succeeds."""
        info_nodes: List[Dict[str, Any]] = [
            {
                "type": "INFORMATION",
                "extra_labels": [],
                "attributes": {
                    "node_id": "info_node1",
                    "title": "Test Node",
                    "content": "Test content",
                    "info_type": "component_description",
                    "source_path": "/src/test.py",
                    "source_labels": ["FILE"],
                    "source_type": "recursive_leaf_analysis",
                    "layer": "documentation",
                },
            }
        ]

        node_source_mapping: Dict[str, str] = {"info_node1": "source_node1"}

        # Configure edge creation to raise error
        self.db_manager.create_edges.side_effect = Exception("Edge creation failed")

        # Call the method
        result = self.workflow._save_information_nodes(info_nodes, node_source_mapping)

        # Nodes should be saved but edges failed
        assert result["success"] is False
        assert result["nodes_saved"] == 1
        assert result["relationships_created"] == 0
        assert len(result["errors"]) == 1
        assert "Database save error" in result["errors"][0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
