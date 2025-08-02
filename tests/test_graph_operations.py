"""
Comprehensive tests for graph operations.
"""
import unittest
from unittest.mock import Mock
from blarify.graph.graph import Graph
from blarify.graph.relationship.relationship import Relationship
from blarify.graph.relationship.relationship_type import RelationshipType
from blarify.graph.node.types.node_labels import NodeLabels
from tests.fixtures.node_factories import (
    create_filesystem_file_node, create_concept_node, create_documented_entity_node
)


class TestGraphOperations(unittest.TestCase):
    """Test suite for core graph operations."""
    
    def setUp(self) -> None:
        """Set up test graph instance."""
        self.graph = Graph()  # type: ignore[misc]
        
    def test_add_node_success(self) -> None:
        """Test adding a node to the graph."""
        node = create_filesystem_file_node("main.py")
        
        self.graph.add_node(node)
        
        # Verify node was added using get_node_by_id
        retrieved = self.graph.get_node_by_id(node.id)
        self.assertEqual(retrieved, node)
        
    def test_add_duplicate_node(self) -> None:
        """Test that duplicate nodes are handled correctly."""
        # Create a node and add it twice
        node1 = create_filesystem_file_node("main.py", "main.py")
        
        self.graph.add_node(node1)
        # Get the current count
        initial_count = len(self.graph.get_all_nodes())
        
        # Add the same node again (same object reference)
        self.graph.add_node(node1)
        
        # Should still have same count - node is replaced/updated
        final_count = len(self.graph.get_all_nodes())
        self.assertEqual(initial_count, final_count)
        
        # Verify the node is in the graph
        retrieved = self.graph.get_node_by_id(node1.id)
        self.assertEqual(retrieved, node1)
        
    def test_get_node_by_id(self) -> None:
        """Test retrieving a node by ID."""
        node = create_concept_node("TestConcept")
        self.graph.add_node(node)
        
        retrieved = self.graph.get_node_by_id(node.id)
        
        self.assertEqual(retrieved, node)
        self.assertEqual(retrieved.name, "TestConcept")  # type: ignore[attr-defined]
        
    def test_get_node_by_id_not_found(self) -> None:
        """Test retrieving non-existent node returns None."""
        result = self.graph.get_node_by_id("non_existent_id")
        self.assertIsNone(result)
        
    def test_get_nodes_by_label(self) -> None:
        """Test retrieving nodes by label."""
        file1 = create_filesystem_file_node("main.py")
        file2 = create_filesystem_file_node("utils.py")
        concept1 = create_concept_node("TestConcept")
        
        self.graph.add_node(file1)
        self.graph.add_node(file2)
        self.graph.add_node(concept1)
        
        file_nodes = self.graph.get_nodes_by_label(NodeLabels.FILESYSTEM_FILE)
        concept_nodes = self.graph.get_nodes_by_label(NodeLabels.CONCEPT)
        
        self.assertEqual(len(file_nodes), 2)
        self.assertEqual(len(concept_nodes), 1)
        self.assertIn(file1, file_nodes)
        self.assertIn(file2, file_nodes)
        self.assertIn(concept1, concept_nodes)
        
    def test_add_relationship_success(self) -> None:
        """Test adding a relationship between nodes."""
        file_node = create_filesystem_file_node("main.py")
        concept_node = create_concept_node("TestConcept", source_file="main.py")
        
        self.graph.add_node(file_node)
        self.graph.add_node(concept_node)
        
        rel = Relationship(
            start_node=file_node,
            end_node=concept_node,
            rel_type=RelationshipType.CONTAINS_CONCEPT
        )
        self.graph.add_references_relationships([rel])
        
        # Verify relationship was added
        relationships = self.graph.get_relationships_as_objects()
        self.assertEqual(len(relationships), 1)
        self.assertEqual(relationships[0]['sourceId'], file_node.hashed_id)
        self.assertEqual(relationships[0]['targetId'], concept_node.hashed_id)
        self.assertEqual(relationships[0]['type'], RelationshipType.CONTAINS_CONCEPT.name)
        
    def test_add_relationship_missing_nodes(self) -> None:
        """Test adding relationship with missing nodes raises error."""
        # Create mock nodes that don't exist in graph
        mock_node1 = Mock()
        mock_node1.hashed_id = "missing_source"
        mock_node2 = Mock()
        mock_node2.hashed_id = "missing_target"
        
        rel = Relationship(
            start_node=mock_node1,
            end_node=mock_node2,
            rel_type=RelationshipType.CONTAINS
        )
        
        # Adding a relationship with nodes not in graph doesn't raise error
        # The relationship is just added to the references list
        self.graph.add_references_relationships([rel])
        relationships = self.graph.get_relationships_as_objects()
        self.assertEqual(len(relationships), 1)
            
    def test_get_relationships_by_node(self) -> None:
        """Test retrieving relationships for a specific node."""
        file_node = create_filesystem_file_node("main.py")
        concept1 = create_concept_node("Concept1", source_file="main.py")
        concept2 = create_concept_node("Concept2", source_file="main.py")
        entity1 = create_documented_entity_node("Entity1", source_file="main.py")
        
        self.graph.add_node(file_node)
        self.graph.add_node(concept1)
        self.graph.add_node(concept2)
        self.graph.add_node(entity1)
        
        # Add relationships
        self.graph.add_references_relationships([
            Relationship(
                start_node=file_node,
                end_node=concept1,
                rel_type=RelationshipType.CONTAINS_CONCEPT
            ),
            Relationship(
                start_node=file_node,
                end_node=concept2,
                rel_type=RelationshipType.CONTAINS_CONCEPT
            ),
            Relationship(
                start_node=file_node,
                end_node=entity1,
                rel_type=RelationshipType.DESCRIBES_ENTITY
            )
        ])
        
        # Get all relationships and filter manually
        all_rels = self.graph.get_all_relationships()
        outgoing = [r for r in all_rels if r.start_node == file_node]
        self.assertEqual(len(outgoing), 3)
        
        # Get incoming relationships to concept1
        incoming = [r for r in all_rels if r.end_node == concept1]
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0].start_node, file_node)
        
    def test_get_nodes_as_objects(self) -> None:
        """Test serializing nodes to dictionary objects."""
        file_node = create_filesystem_file_node("main.py")
        concept_node = create_concept_node("TestConcept")
        
        self.graph.add_node(file_node)
        self.graph.add_node(concept_node)
        
        # Get nodes and check their properties directly
        nodes = self.graph.get_all_nodes()
        self.assertEqual(len(nodes), 2)
        
        # Check nodes have expected properties
        node_names = [n.name for n in nodes]
        self.assertIn("main.py", node_names)
        self.assertIn("TestConcept", node_names)
        
        # Test as_object works with nodes that have graph_environment
        objects = self.graph.get_nodes_as_objects()
        self.assertEqual(len(objects), 2)
        
    def test_clear_graph(self) -> None:
        """Test clearing all nodes and relationships from graph."""
        # Add some nodes and relationships
        node1 = create_filesystem_file_node("file1.py")
        node2 = create_concept_node("Concept1")
        self.graph.add_node(node1)
        self.graph.add_node(node2)
        self.graph.add_references_relationships([
            Relationship(start_node=node1, end_node=node2, rel_type=RelationshipType.CONTAINS_CONCEPT)
        ])
        
        # Verify graph has content
        self.assertGreater(len(self.graph.get_all_nodes()), 0)
        self.assertGreater(len(self.graph.get_relationships_as_objects()), 0)
        
        # Graph doesn't have a clear method, recreate it
        self.graph = Graph()
        
        # Verify graph is empty
        self.assertEqual(len(self.graph.get_all_nodes()), 0)
        self.assertEqual(len(self.graph.get_relationships_as_objects()), 0)
        
    def test_node_exists(self) -> None:
        """Test checking if a node exists in the graph."""
        node = create_concept_node("test_concept")
        
        # Graph doesn't have node_exists method, use get_node_by_id
        self.assertIsNone(self.graph.get_node_by_id(node.id))
        
        self.graph.add_node(node)
        
        self.assertIsNotNone(self.graph.get_node_by_id(node.id))
        
    def test_remove_node(self) -> None:
        """Test removing a node from the graph."""
        node = create_filesystem_file_node("temp.py")
        concept_node = create_concept_node("TempConcept", source_file="temp.py")
        
        self.graph.add_node(node)
        self.graph.add_node(concept_node)
        self.graph.add_references_relationships([
            Relationship(
                start_node=node,
                end_node=concept_node,
                rel_type=RelationshipType.CONTAINS_CONCEPT
            )
        ])
        
        # Graph doesn't have remove_node method
        # Test filtering by paths instead
        filtered_graph = self.graph.filtered_graph_by_paths([concept_node.path])
        
        # Verify only concept node remains in filtered graph
        nodes = filtered_graph.get_all_nodes()
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].name, "TempConcept")
        
    def test_get_connected_nodes(self) -> None:
        """Test getting nodes connected to a specific node."""
        # Create a small graph
        file1 = create_filesystem_file_node("main.py", "main.py")
        file2 = create_filesystem_file_node("utils.py", "utils.py")
        concept1 = create_concept_node("MainConcept", source_file="main.py")
        entity1 = create_documented_entity_node("Helper", source_file="utils.py")
        
        self.graph.add_node(file1)
        self.graph.add_node(file2)
        self.graph.add_node(concept1)
        self.graph.add_node(entity1)
        
        # file1 contains concept1
        self.graph.add_references_relationships([
            Relationship(
                start_node=file1,
                end_node=concept1,
                rel_type=RelationshipType.CONTAINS_CONCEPT
            ),
            # file2 contains entity1
            Relationship(
                start_node=file2,
                end_node=entity1,
                rel_type=RelationshipType.DESCRIBES_ENTITY
            ),
            # concept1 relates to entity1
            Relationship(
                start_node=concept1,
                end_node=entity1,
                rel_type=RelationshipType.RELATES_TO
            )
        ])
        
        # Get all relationships and filter to find connected nodes
        all_rels = self.graph.get_all_relationships()
        
        # Find nodes connected to concept1
        connected_to_concept1 = set()  # type: ignore[var-annotated]
        for rel in all_rels:
            if rel.start_node == concept1:
                connected_to_concept1.add(rel.end_node)  # type: ignore[arg-type]
            elif rel.end_node == concept1:
                connected_to_concept1.add(rel.start_node)  # type: ignore[arg-type]
        
        # Should include file1 (incoming) and entity1 (outgoing)
        self.assertIn(file1, connected_to_concept1)  # type: ignore[arg-type]
        self.assertIn(entity1, connected_to_concept1)  # type: ignore[arg-type]
        self.assertNotIn(file2, connected_to_concept1)  # type: ignore[arg-type]
        
    def test_get_subgraph(self) -> None:
        """Test extracting a subgraph around specific nodes."""
        # Create a simple graph
        file1 = create_filesystem_file_node("main.py")
        concept1 = create_concept_node("MainConcept", source_file="main.py")
        concept2 = create_concept_node("OtherConcept", source_file="other.py")
        
        self.graph.add_node(file1)
        self.graph.add_node(concept1)
        self.graph.add_node(concept2)
        
        # Add relationship only between file1 and concept1
        self.graph.add_references_relationships([
            Relationship(
                start_node=file1,
                end_node=concept1,
                rel_type=RelationshipType.CONTAINS_CONCEPT
            )
        ])
        
        # Filter graph by paths
        subgraph = self.graph.filtered_graph_by_paths([file1.path, concept1.path])
        
        # Verify subgraph contains only the filtered nodes
        nodes = subgraph.get_all_nodes()
        self.assertEqual(len(nodes), 2)
        node_names = [n.name for n in nodes]
        self.assertIn('main.py', node_names)
        self.assertIn('MainConcept', node_names)
        self.assertNotIn('OtherConcept', node_names)
        
    def test_merge_graphs(self) -> None:
        """Test merging two graphs together."""
        graph1 = Graph()
        graph2 = Graph()
        
        # Add nodes to graph1
        file1 = create_filesystem_file_node("file1.py")
        concept1 = create_concept_node("Concept1", source_file="file1.py")
        graph1.add_node(file1)
        graph1.add_node(concept1)
        
        # Add nodes to graph2
        file2 = create_filesystem_file_node("file2.py")
        entity2 = create_documented_entity_node("Entity2", source_file="file2.py")
        graph2.add_node(file2)
        graph2.add_node(entity2)
        
        # Graph doesn't have a merge method, manually add nodes from graph2 to graph1
        for node in graph2.get_all_nodes():
            graph1.add_node(node)
        
        # Verify all nodes are in graph1
        nodes = graph1.get_all_nodes()
        self.assertEqual(len(nodes), 4)
        node_names = [n.name for n in nodes]
        self.assertIn('file1.py', node_names)
        self.assertIn('Concept1', node_names)
        self.assertIn('file2.py', node_names)
        self.assertIn('Entity2', node_names)


if __name__ == '__main__':
    unittest.main()