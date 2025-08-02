import unittest
from unittest.mock import MagicMock
from blarify.graph.graph import Graph
from blarify.graph.node import Node, NodeLabels, FileNode
from blarify.graph.relationship import Relationship


class TestGraphComprehensive(unittest.TestCase):
    """Comprehensive test cases for Graph class to improve coverage."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.graph = Graph()  # type: ignore[misc]
        
    def test_has_folder_node_with_path(self) -> None:
        """Test checking if folder node exists with path."""
        # Initially no folder nodes
        self.assertFalse(self.graph.has_folder_node_with_path("/test/folder"))
        
        # Add a folder node
        mock_folder = MagicMock(spec=Node)
        mock_folder.id = "folder1"
        mock_folder.path = "/test/folder"
        mock_folder.label = NodeLabels.FOLDER
        mock_folder.relative_id = "folder1"
        
        self.graph.add_node(mock_folder)
        
        self.assertTrue(self.graph.has_folder_node_with_path("/test/folder"))
        self.assertFalse(self.graph.has_folder_node_with_path("/other/folder"))
        
    def test_add_nodes(self) -> None:
        """Test adding multiple nodes at once."""
        nodes = []
        for i in range(3):
            mock_node = MagicMock(spec=Node)
            mock_node.id = f"node{i}"
            mock_node.path = f"/test/file{i}.py"
            mock_node.label = NodeLabels.CLASS
            mock_node.relative_id = f"node{i}"
            nodes.append(mock_node)  # type: ignore[arg-type]
            
        self.graph.add_nodes(nodes)  # type: ignore[arg-type]
        
        # Verify all nodes were added
        for i in range(3):
            self.assertIsNotNone(self.graph.get_node_by_id(f"node{i}"))
            
    def test_get_file_node_by_path_none(self) -> None:
        """Test getting file node when it doesn't exist."""
        result = self.graph.get_file_node_by_path("/nonexistent/file.py")
        self.assertIsNone(result)
        
    def test_get_file_node_by_path_exists(self) -> None:
        """Test getting file node when it exists."""
        mock_file = MagicMock(spec=FileNode)
        mock_file.id = "file1"
        mock_file.path = "/test/file.py"
        mock_file.label = NodeLabels.FILE
        mock_file.relative_id = "file1"
        
        self.graph.add_node(mock_file)
        
        result = self.graph.get_file_node_by_path("/test/file.py")
        self.assertEqual(result, mock_file)
        
    def test_get_folder_node_by_path(self) -> None:
        """Test getting folder node by path."""
        mock_folder = MagicMock(spec=Node)
        mock_folder.id = "folder1"
        mock_folder.path = "/test/folder"
        mock_folder.label = NodeLabels.FOLDER
        mock_folder.relative_id = "folder1"
        
        self.graph.add_node(mock_folder)
        
        result = self.graph.get_folder_node_by_path("/test/folder")
        self.assertEqual(result, mock_folder)
        
    def test_get_node_by_relative_id_none(self) -> None:
        """Test getting node by relative ID when it doesn't exist."""
        result = self.graph.get_node_by_relative_id("nonexistent")
        self.assertIsNone(result)
        
    def test_get_node_by_relative_id_exists(self) -> None:
        """Test getting node by relative ID when it exists."""
        mock_node = MagicMock(spec=Node)
        mock_node.id = "node1"
        mock_node.path = "/test/file.py"
        mock_node.label = NodeLabels.CLASS
        mock_node.relative_id = "MyClass"
        
        self.graph.add_node(mock_node)
        
        result = self.graph.get_node_by_relative_id("MyClass")
        self.assertEqual(result, mock_node)
        
    def test_get_relationships_as_objects(self) -> None:
        """Test getting relationships as objects."""
        # Add nodes with relationships
        mock_node1 = MagicMock(spec=Node)
        mock_node1.id = "node1"
        mock_node1.path = "/test/file1.py"
        mock_node1.label = NodeLabels.CLASS
        mock_node1.relative_id = "node1"
        
        mock_node2 = MagicMock(spec=Node)
        mock_node2.id = "node2"
        mock_node2.path = "/test/file2.py"
        mock_node2.label = NodeLabels.CLASS
        mock_node2.relative_id = "node2"
        
        # Mock internal relationship
        mock_rel1 = MagicMock(spec=Relationship)
        mock_rel1.as_object.return_value = {"type": "DEFINES", "start": "node1", "end": "node2"}
        mock_node1.get_relationships.return_value = [mock_rel1]
        mock_node2.get_relationships.return_value = []
        
        self.graph.add_node(mock_node1)
        self.graph.add_node(mock_node2)
        
        # Add reference relationship
        mock_ref_rel = MagicMock(spec=Relationship)
        mock_ref_rel.as_object.return_value = {"type": "USES", "start": "node2", "end": "node1"}
        self.graph.add_references_relationships([mock_ref_rel])
        
        relationships = self.graph.get_relationships_as_objects()
        
        self.assertEqual(len(relationships), 2)
        self.assertIn({"type": "DEFINES", "start": "node1", "end": "node2"}, relationships)
        self.assertIn({"type": "USES", "start": "node2", "end": "node1"}, relationships)
        
    def test_get_relationships_from_nodes(self) -> None:
        """Test getting relationships from nodes."""
        mock_node1 = MagicMock(spec=Node)
        mock_node1.id = "node1"
        mock_node1.path = "/test/file.py"
        mock_node1.label = NodeLabels.CLASS
        mock_node1.relative_id = "node1"
        
        mock_rel1 = MagicMock(spec=Relationship)
        mock_rel2 = MagicMock(spec=Relationship)
        mock_node1.get_relationships.return_value = [mock_rel1, mock_rel2]
        
        self.graph.add_node(mock_node1)
        
        relationships = self.graph.get_relationships_from_nodes()
        
        self.assertEqual(len(relationships), 2)
        self.assertIn(mock_rel1, relationships)
        self.assertIn(mock_rel2, relationships)
        
    def test_get_all_relationships(self) -> None:
        """Test getting all relationships (nodes + references)."""
        # Add node with relationship
        mock_node = MagicMock(spec=Node)
        mock_node.id = "node1"
        mock_node.path = "/test/file.py"
        mock_node.label = NodeLabels.CLASS
        mock_node.relative_id = "node1"
        
        mock_node_rel = MagicMock(spec=Relationship)
        mock_node.get_relationships.return_value = [mock_node_rel]
        
        self.graph.add_node(mock_node)
        
        # Add reference relationship
        mock_ref_rel = MagicMock(spec=Relationship)
        self.graph.add_references_relationships([mock_ref_rel])
        
        all_relationships = self.graph.get_all_relationships()
        
        self.assertEqual(len(all_relationships), 2)
        self.assertIn(mock_node_rel, all_relationships)
        self.assertIn(mock_ref_rel, all_relationships)
        
    def test_get_nodes_as_objects(self) -> None:
        """Test getting nodes as objects."""
        mock_node1 = MagicMock(spec=Node)
        mock_node1.id = "node1"
        mock_node1.path = "/test/file1.py"
        mock_node1.label = NodeLabels.CLASS
        mock_node1.relative_id = "node1"
        mock_node1.as_object.return_value = {"id": "node1", "type": "CLASS"}
        
        mock_node2 = MagicMock(spec=Node)
        mock_node2.id = "node2"
        mock_node2.path = "/test/file2.py"
        mock_node2.label = NodeLabels.FUNCTION
        mock_node2.relative_id = "node2"
        mock_node2.as_object.return_value = {"id": "node2", "type": "FUNCTION"}
        
        self.graph.add_node(mock_node1)
        self.graph.add_node(mock_node2)
        
        objects = self.graph.get_nodes_as_objects()
        
        self.assertEqual(len(objects), 2)
        self.assertIn({"id": "node1", "type": "CLASS"}, objects)
        self.assertIn({"id": "node2", "type": "FUNCTION"}, objects)
        
    def test_filtered_graph_by_paths(self) -> None:
        """Test filtering graph by paths."""
        # Create nodes
        nodes = []
        for i in range(4):
            mock_node = MagicMock(spec=Node)
            mock_node.id = f"node{i}"
            mock_node.path = f"/test/file{i}.py"
            mock_node.label = NodeLabels.CLASS
            mock_node.relative_id = f"node{i}"
            mock_node.filter_children_by_path = MagicMock()  # type: ignore[attr-defined]
            nodes.append(mock_node)  # type: ignore[arg-type]
            self.graph.add_node(mock_node)
            
        # Create relationships
        mock_rel1 = MagicMock(spec=Relationship)
        mock_rel1.start_node = nodes[0]
        mock_rel1.end_node = nodes[1]
        
        mock_rel2 = MagicMock(spec=Relationship)
        mock_rel2.start_node = nodes[2]
        mock_rel2.end_node = nodes[3]
        
        self.graph.add_references_relationships([mock_rel1, mock_rel2])
        
        # Filter by paths
        paths_to_keep = ["/test/file0.py", "/test/file1.py"]
        filtered_graph = self.graph.filtered_graph_by_paths(paths_to_keep)
        
        # Verify filtered graph
        self.assertIsNotNone(filtered_graph.get_node_by_id("node0"))
        self.assertIsNotNone(filtered_graph.get_node_by_id("node1"))
        self.assertIsNone(filtered_graph.get_node_by_id("node2"))
        self.assertIsNone(filtered_graph.get_node_by_id("node3"))
        
        # Verify filter_children_by_path was called
        nodes[0].filter_children_by_path.assert_called_once_with(paths_to_keep)  # type: ignore[attr-defined]
        nodes[1].filter_children_by_path.assert_called_once_with(paths_to_keep)  # type: ignore[attr-defined]
        
        # Verify only relevant relationships are kept
        filtered_relationships = filtered_graph.get_all_relationships()
        self.assertEqual(len(filtered_relationships), 1)
        
    def test_filtered_graph_by_paths_with_cross_references(self) -> None:
        """Test filtering graph with cross-file references."""
        # Create nodes
        node1 = MagicMock(spec=Node)
        node1.id = "node1"
        node1.path = "/keep/file1.py"
        node1.label = NodeLabels.CLASS
        node1.relative_id = "node1"
        node1.filter_children_by_path = MagicMock()
        
        node2 = MagicMock(spec=Node)
        node2.id = "node2"
        node2.path = "/remove/file2.py"
        node2.label = NodeLabels.CLASS
        node2.relative_id = "node2"
        node2.filter_children_by_path = MagicMock()
        
        self.graph.add_node(node1)
        self.graph.add_node(node2)
        
        # Create relationship from removed node to kept node
        mock_rel = MagicMock(spec=Relationship)
        mock_rel.start_node = node2  # This node will be filtered out
        mock_rel.end_node = node1    # This node will be kept
        
        self.graph.add_references_relationships([mock_rel])
        
        # Filter by paths
        paths_to_keep = ["/keep/file1.py"]
        filtered_graph = self.graph.filtered_graph_by_paths(paths_to_keep)
        
        # Verify the relationship is still kept because end_node is in paths_to_keep
        filtered_relationships = filtered_graph.get_all_relationships()
        self.assertEqual(len(filtered_relationships), 1)
        
    def test_str_representation(self) -> None:
        """Test string representation of graph."""
        # Add nodes
        mock_node1 = MagicMock(spec=Node)
        mock_node1.id = "node1"
        mock_node1.path = "/test/file1.py"
        mock_node1.label = NodeLabels.CLASS
        mock_node1.relative_id = "node1"
        mock_node1.__str__.return_value = "Node1: Class"  # type: ignore[attr-defined]
        
        mock_node2 = MagicMock(spec=Node)
        mock_node2.id = "node2"
        mock_node2.path = "/test/file2.py"
        mock_node2.label = NodeLabels.FUNCTION
        mock_node2.relative_id = "node2"
        mock_node2.__str__.return_value = "Node2: Function"  # type: ignore[attr-defined]
        
        self.graph.add_node(mock_node1)
        self.graph.add_node(mock_node2)
        
        # Add reference relationship
        mock_rel = MagicMock(spec=Relationship)
        mock_rel.__str__.return_value = "Relationship: Node1 -> Node2"  # type: ignore[attr-defined]
        self.graph.add_references_relationships([mock_rel])
        
        graph_str = str(self.graph)
        
        self.assertIn("Node1: Class", graph_str)
        self.assertIn("Node2: Function", graph_str)
        self.assertIn("Relationship: Node1 -> Node2", graph_str)
        
    def test_empty_graph_operations(self) -> None:
        """Test operations on empty graph."""
        # Test getting from empty graph
        self.assertEqual(len(self.graph.get_nodes_by_path("/any/path")), 0)
        self.assertEqual(len(self.graph.get_nodes_by_label(NodeLabels.CLASS)), 0)
        self.assertIsNone(self.graph.get_node_by_id("any_id"))
        self.assertIsNone(self.graph.get_node_by_relative_id("any_relative_id"))
        self.assertIsNone(self.graph.get_file_node_by_path("/any/file.py"))
        
        # Test getting relationships from empty graph
        self.assertEqual(len(self.graph.get_relationships_from_nodes()), 0)
        self.assertEqual(len(self.graph.get_all_relationships()), 0)
        self.assertEqual(len(self.graph.get_relationships_as_objects()), 0)
        
        # Test string representation of empty graph
        self.assertEqual(str(self.graph), "")
        
    def test_get_all_nodes(self) -> None:
        """Test getting all nodes from graph."""
        nodes = []
        for i in range(3):
            mock_node = MagicMock(spec=Node)
            mock_node.id = f"node{i}"
            mock_node.path = f"/test/file{i}.py"
            mock_node.label = NodeLabels.CLASS
            mock_node.relative_id = f"node{i}"
            nodes.append(mock_node)  # type: ignore[arg-type]
            self.graph.add_node(mock_node)
            
        all_nodes = self.graph.get_all_nodes()
        
        self.assertEqual(len(all_nodes), 3)
        for node in nodes:  # type: ignore[attr-defined]
            self.assertIn(node, all_nodes)
    
    def test_filtered_graph_with_self_referencing_relationships(self) -> None:
        """Test filtering graph with self-referencing relationships."""
        # Create a node that has a relationship to itself
        mock_node = MagicMock(spec=Node)
        mock_node.id = "self_ref_node"
        mock_node.path = "/keep/self_ref.py"
        mock_node.label = NodeLabels.CLASS
        mock_node.relative_id = "self_ref_node"
        mock_node.filter_children_by_path = MagicMock()
        
        self.graph.add_node(mock_node)
        
        # Create self-referencing relationship
        mock_self_rel = MagicMock(spec=Relationship)
        mock_self_rel.start_node = mock_node
        mock_self_rel.end_node = mock_node  # Self-reference
        
        self.graph.add_references_relationships([mock_self_rel])
        
        # Filter by paths that include the self-referencing node
        paths_to_keep = ["/keep/self_ref.py"]
        filtered_graph = self.graph.filtered_graph_by_paths(paths_to_keep)
        
        # Verify the self-referencing relationship is preserved
        filtered_relationships = filtered_graph.get_all_relationships()
        self.assertEqual(len(filtered_relationships), 1)
        self.assertIn(mock_self_rel, filtered_relationships)
        
        # Verify the node is still present
        self.assertIsNotNone(filtered_graph.get_node_by_id("self_ref_node"))
    
    def test_filtered_graph_with_circular_references(self) -> None:
        """Test filtering graph with circular references between nodes."""
        # Create three nodes in a circular reference pattern
        node_a = MagicMock(spec=Node)
        node_a.id = "node_a"
        node_a.path = "/keep/a.py"
        node_a.label = NodeLabels.CLASS  
        node_a.relative_id = "node_a"
        node_a.filter_children_by_path = MagicMock()
        
        node_b = MagicMock(spec=Node)
        node_b.id = "node_b"
        node_b.path = "/keep/b.py"
        node_b.label = NodeLabels.CLASS
        node_b.relative_id = "node_b"
        node_b.filter_children_by_path = MagicMock()
        
        node_c = MagicMock(spec=Node)
        node_c.id = "node_c"
        node_c.path = "/discard/c.py"  # This will be filtered out
        node_c.label = NodeLabels.CLASS
        node_c.relative_id = "node_c"
        node_c.filter_children_by_path = MagicMock()
        
        self.graph.add_node(node_a)
        self.graph.add_node(node_b)
        self.graph.add_node(node_c)
        
        # Create circular relationships: A -> B -> C -> A
        rel_a_to_b = MagicMock(spec=Relationship)
        rel_a_to_b.start_node = node_a
        rel_a_to_b.end_node = node_b
        
        rel_b_to_c = MagicMock(spec=Relationship)
        rel_b_to_c.start_node = node_b
        rel_b_to_c.end_node = node_c
        
        rel_c_to_a = MagicMock(spec=Relationship)
        rel_c_to_a.start_node = node_c
        rel_c_to_a.end_node = node_a
        
        self.graph.add_references_relationships([rel_a_to_b, rel_b_to_c, rel_c_to_a])
        
        # Filter to keep only A and B (C will be discarded)
        paths_to_keep = ["/keep/a.py", "/keep/b.py"]
        filtered_graph = self.graph.filtered_graph_by_paths(paths_to_keep)
        
        # Verify only A and B nodes are kept
        self.assertIsNotNone(filtered_graph.get_node_by_id("node_a"))
        self.assertIsNotNone(filtered_graph.get_node_by_id("node_b"))
        self.assertIsNone(filtered_graph.get_node_by_id("node_c"))
        
        # Verify relationships are filtered appropriately
        filtered_relationships = filtered_graph.get_all_relationships()
        
        # Should keep all relationships because:
        # - A -> B (both nodes kept)
        # - B -> C (start node B is kept, even though end node C is discarded)
        # - C -> A (end node A is kept, even though start node C is discarded)
        # The filtering logic keeps relationships where EITHER start OR end node is in paths_to_keep
        
        self.assertEqual(len(filtered_relationships), 3)
        self.assertIn(rel_a_to_b, filtered_relationships)  # A -> B
        self.assertIn(rel_b_to_c, filtered_relationships)  # B -> C (kept because B is kept)
        self.assertIn(rel_c_to_a, filtered_relationships)  # C -> A (kept because A is kept)
    
    def test_filtered_graph_with_complex_relationship_patterns(self) -> None:
        """Test filtering with complex patterns including bidirectional relationships."""
        # Create nodes
        node1 = MagicMock(spec=Node)
        node1.id = "node1"
        node1.path = "/keep/file1.py"
        node1.label = NodeLabels.CLASS
        node1.relative_id = "node1"
        node1.filter_children_by_path = MagicMock()
        
        node2 = MagicMock(spec=Node)
        node2.id = "node2"
        node2.path = "/discard/file2.py"
        node2.label = NodeLabels.CLASS
        node2.relative_id = "node2"
        node2.filter_children_by_path = MagicMock()
        
        self.graph.add_node(node1)
        self.graph.add_node(node2)
        
        # Create bidirectional relationships
        rel_1_to_2 = MagicMock(spec=Relationship)
        rel_1_to_2.start_node = node1
        rel_1_to_2.end_node = node2
        
        rel_2_to_1 = MagicMock(spec=Relationship)
        rel_2_to_1.start_node = node2
        rel_2_to_1.end_node = node1
        
        # Add self-referencing relationship for node1
        rel_1_to_1 = MagicMock(spec=Relationship)
        rel_1_to_1.start_node = node1
        rel_1_to_1.end_node = node1
        
        self.graph.add_references_relationships([rel_1_to_2, rel_2_to_1, rel_1_to_1])
        
        # Filter to keep only node1
        paths_to_keep = ["/keep/file1.py"]
        filtered_graph = self.graph.filtered_graph_by_paths(paths_to_keep)
        
        # Verify only node1 is kept
        self.assertIsNotNone(filtered_graph.get_node_by_id("node1"))
        self.assertIsNone(filtered_graph.get_node_by_id("node2"))
        
        # Verify relationship filtering
        filtered_relationships = filtered_graph.get_all_relationships()
        
        # Should keep all relationships because filtering logic keeps relationships 
        # where EITHER start OR end node is in paths_to_keep:
        # - node1 -> node1 (self-reference, both start and end kept)
        # - node2 -> node1 (end node kept, even though start node discarded)  
        # - node1 -> node2 (start node kept, even though end node discarded)
        
        self.assertEqual(len(filtered_relationships), 3)
        self.assertIn(rel_1_to_1, filtered_relationships)  # self-reference
        self.assertIn(rel_2_to_1, filtered_relationships)  # external -> kept
        self.assertIn(rel_1_to_2, filtered_relationships)  # kept -> external


if __name__ == '__main__':
    unittest.main()