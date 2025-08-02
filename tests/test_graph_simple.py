"""
Simple tests for graph operations that work with current structure.
"""
import unittest
from unittest.mock import Mock
from blarify.graph.graph import Graph
from blarify.graph.node.types.node_labels import NodeLabels
from blarify.graph.relationship.relationship import Relationship
from blarify.graph.relationship.relationship_type import RelationshipType


class TestGraphSimple(unittest.TestCase):
    """Simple test suite for graph operations."""
    
    def setUp(self) -> None:
        """Set up test graph instance."""
        self.graph = Graph()  # type: ignore[misc]
        
    def test_graph_creation(self) -> None:
        """Test creating an empty graph."""
        self.assertIsInstance(self.graph, Graph)
        self.assertEqual(len(self.graph.get_nodes_as_objects()), 0)
        
    def test_add_simple_node(self) -> None:
        """Test adding a simple node to graph."""
        # Create a mock node with required properties
        node = Mock()
        node.id = "test_node_id"
        node.label = NodeLabels.FILE
        node.path = "file:///test/main.py"
        node.name = "main.py"
        node.level = 1
        node.relative_id = "test_node_id"
        node.node_repr_for_identifier = "/main.py"
        node.as_object = Mock(return_value={})
        node.get_relationships = Mock(return_value=[])
        
        # Add to graph
        self.graph.add_node(node)
        
        # Verify it was added
        retrieved = self.graph.get_node_by_id(node.id)
        self.assertEqual(retrieved, node)
        
    def test_get_node_by_id(self) -> None:
        """Test retrieving node by ID."""
        node = Mock()
        node.id = "folder_node_id"
        node.label = NodeLabels.FOLDER
        node.path = "file:///test/src"
        node.name = "src"
        node.level = 0
        node.relative_id = "folder_node_id"
        node.node_repr_for_identifier = "/src"
        node.as_object = Mock(return_value={})
        node.get_relationships = Mock(return_value=[])
        
        self.graph.add_node(node)
        
        retrieved = self.graph.get_node_by_id(node.id)
        
        self.assertEqual(retrieved, node)
        self.assertEqual(retrieved.name, "src")  # type: ignore[attr-defined]
        
    def test_get_nodes_by_label(self) -> None:
        """Test retrieving nodes by label."""
        # Add different types of nodes
        file_node = Mock()
        file_node.id = "file_node_id"
        file_node.label = NodeLabels.FILE
        file_node.path = "file:///test/main.py"
        file_node.name = "main.py"
        file_node.level = 1
        file_node.relative_id = "file_node_id"
        file_node.node_repr_for_identifier = "/main.py"
        file_node.as_object = Mock(return_value={})
        file_node.get_relationships = Mock(return_value=[])
        
        folder_node = Mock()
        folder_node.id = "folder_node_id"
        folder_node.label = NodeLabels.FOLDER
        folder_node.path = "file:///test/src"
        folder_node.name = "src"
        folder_node.level = 0
        folder_node.relative_id = "folder_node_id"
        folder_node.node_repr_for_identifier = "/src"
        folder_node.as_object = Mock(return_value={})
        folder_node.get_relationships = Mock(return_value=[])
        
        self.graph.add_node(file_node)
        self.graph.add_node(folder_node)
        
        # Get nodes by label
        file_nodes = self.graph.get_nodes_by_label(NodeLabels.FILE)
        folder_nodes = self.graph.get_nodes_by_label(NodeLabels.FOLDER)
        
        self.assertEqual(len(file_nodes), 1)
        self.assertEqual(len(folder_nodes), 1)
        self.assertIn(file_node, file_nodes)
        self.assertIn(folder_node, folder_nodes)
        
    def test_add_relationship(self) -> None:
        """Test adding relationships between nodes."""
        # Create two nodes
        parent = Mock()
        parent.id = "parent_id"
        parent.hashed_id = "hashed_parent"
        parent.label = NodeLabels.FOLDER
        parent.path = "file:///test/src"
        parent.name = "src"
        parent.level = 0
        parent.relative_id = "parent_id"
        parent.node_repr_for_identifier = "/src"
        parent.as_object = Mock(return_value={})
        parent.get_relationships = Mock(return_value=[])
        
        child = Mock()
        child.id = "child_id"
        child.hashed_id = "hashed_child"
        child.label = NodeLabels.FILE
        child.path = "file:///test/src/main.py"
        child.name = "main.py"
        child.level = 1
        child.relative_id = "child_id"
        child.node_repr_for_identifier = "/main.py"
        child.as_object = Mock(return_value={})
        child.get_relationships = Mock(return_value=[])
        
        self.graph.add_node(parent)
        self.graph.add_node(child)
        
        # Add relationship - constructor takes (start_node, end_node, rel_type)
        rel = Relationship(
            start_node=parent,
            end_node=child,
            rel_type=RelationshipType.CONTAINS
        )
        self.graph.add_references_relationships([rel])
        
        # Verify relationship exists
        relationships = self.graph.get_relationships_as_objects()
        self.assertEqual(len(relationships), 1)
        self.assertEqual(relationships[0]['sourceId'], parent.hashed_id)
        self.assertEqual(relationships[0]['targetId'], child.hashed_id)
        
    def test_get_nodes_as_objects(self) -> None:
        """Test serializing nodes to dictionaries."""
        node = Mock()
        node.id = "utils_node_id"
        node.label = NodeLabels.FILE
        node.path = "file:///test/utils.py"
        node.name = "utils.py"
        node.level = 1
        node.relative_id = "utils_node_id"
        node.node_repr_for_identifier = "/utils.py"
        node.get_relationships = Mock(return_value=[])
        
        # Mock the as_object method to return proper structure
        node.as_object = Mock(return_value={
            'type': NodeLabels.FILE.name,
            'extra_labels': [],
            'attributes': {
                'label': NodeLabels.FILE.name,
                'path': node.path,
                'name': 'utils.py',
                'level': 1
            }
        })
        
        self.graph.add_node(node)
        
        objects = self.graph.get_nodes_as_objects()
        
        self.assertEqual(len(objects), 1)
        obj = objects[0]
        
        self.assertIn('type', obj)
        self.assertIn('attributes', obj)
        self.assertEqual(obj['type'], NodeLabels.FILE.name)
        self.assertEqual(obj['attributes']['name'], 'utils.py')


class TestNodeLabels(unittest.TestCase):
    """Test node label types."""
    
    def test_node_labels_exist(self) -> None:
        """Test that expected node labels exist."""
        # Basic labels
        self.assertTrue(hasattr(NodeLabels, 'FILE'))
        self.assertTrue(hasattr(NodeLabels, 'FOLDER'))
        self.assertTrue(hasattr(NodeLabels, 'CLASS'))
        self.assertTrue(hasattr(NodeLabels, 'FUNCTION'))
        
        # Filesystem labels
        self.assertTrue(hasattr(NodeLabels, 'FILESYSTEM_FILE'))
        self.assertTrue(hasattr(NodeLabels, 'FILESYSTEM_DIRECTORY'))
        
        # Documentation labels
        self.assertTrue(hasattr(NodeLabels, 'DOCUMENTATION_FILE'))
        self.assertTrue(hasattr(NodeLabels, 'CONCEPT'))
        self.assertTrue(hasattr(NodeLabels, 'DOCUMENTED_ENTITY'))
        
        # Description label
        self.assertTrue(hasattr(NodeLabels, 'DESCRIPTION'))


class TestRelationshipTypes(unittest.TestCase):
    """Test relationship types."""
    
    def test_relationship_types_exist(self) -> None:
        """Test that expected relationship types exist."""
        # Basic relationships
        self.assertTrue(hasattr(RelationshipType, 'CONTAINS'))
        self.assertTrue(hasattr(RelationshipType, 'IMPORTS'))
        self.assertTrue(hasattr(RelationshipType, 'USES'))
        
        # Filesystem relationships
        self.assertTrue(hasattr(RelationshipType, 'FILESYSTEM_CONTAINS'))
        self.assertTrue(hasattr(RelationshipType, 'IMPLEMENTS'))
        
        # Documentation relationships
        self.assertTrue(hasattr(RelationshipType, 'CONTAINS_CONCEPT'))
        self.assertTrue(hasattr(RelationshipType, 'DESCRIBES_ENTITY'))
        self.assertTrue(hasattr(RelationshipType, 'DOCUMENTS'))
        
        # Description relationships
        self.assertTrue(hasattr(RelationshipType, 'REFERENCED_BY_DESCRIPTION'))


if __name__ == '__main__':
    unittest.main()