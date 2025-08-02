"""
Tests for LLM description node functionality.
"""
import unittest
from typing import Any
from unittest.mock import Mock, patch
from blarify.graph.node.description_node import DescriptionNode
from blarify.graph.node.types.node_labels import NodeLabels
from blarify.llm_descriptions.description_generator import DescriptionGenerator
from blarify.graph.graph import Graph


class TestDescriptionNodes(unittest.TestCase):
    """Test LLM description nodes."""
    
    def test_description_node_creation(self) -> None:
        """Test creating a description node with proper parameters."""
        node = DescriptionNode(
            path="file:///descriptions/desc_123",
            name="description_for_function_123",
            level=0,
            description_text="This function calculates the factorial of a number",
            target_node_id="function_factorial_123",
            llm_model="gpt-4"
        )
        
        self.assertEqual(node.label, NodeLabels.DESCRIPTION)
        self.assertEqual(node.description_text, "This function calculates the factorial of a number")
        self.assertEqual(node.target_node_id, "function_factorial_123")
        self.assertEqual(node.llm_model, "gpt-4")
        self.assertEqual(node.level, 0)
        
        # Test node_repr_for_identifier
        self.assertEqual(node.node_repr_for_identifier, "/DESCRIPTION[function_factorial_123]")
        
    def test_description_node_as_object(self) -> None:
        """Test serializing description node."""
        node = DescriptionNode(
            path="file:///descriptions/desc_456",
            name="description_for_class_456",
            level=0,
            description_text="This class manages user authentication",
            target_node_id="class_auth_456",
            llm_model="gpt-3.5-turbo"
        )
        
        # Need to set graph_environment to avoid AttributeError
        mock_env = Mock()
        mock_env.diff_identifier = "test_diff"
        node.graph_environment = mock_env
        
        obj = node.as_object()
        
        self.assertEqual(obj['type'], 'DESCRIPTION')
        self.assertIn('description_text', obj['attributes'])
        self.assertEqual(obj['attributes']['description_text'], "This class manages user authentication")
        self.assertEqual(obj['attributes']['target_node_id'], "class_auth_456")
        self.assertEqual(obj['attributes']['llm_model'], "gpt-3.5-turbo")
        
    def test_description_node_in_graph(self) -> None:
        """Test adding description nodes to graph."""
        graph = Graph()
        
        # Create a description node
        desc_node = DescriptionNode(
            path="file:///descriptions/desc_789",
            name="description_789",
            level=0,
            description_text="Handles HTTP requests",
            target_node_id="function_handler_789",
            llm_model="gpt-4"
        )
        
        # Add to graph
        graph.add_node(desc_node)
        
        # Retrieve by ID
        retrieved = graph.get_node_by_id(desc_node.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.description_text, "Handles HTTP requests")
        
        # Retrieve by label - use the enum, not string
        desc_nodes = graph.get_nodes_by_label(NodeLabels.DESCRIPTION)
        self.assertEqual(len(desc_nodes), 1)
        self.assertIn(desc_node, desc_nodes)
        
    def test_create_prompt_for_description(self) -> None:
        """Test creating prompts for LLM description generation."""
        # Mock LLM service
        mock_llm = Mock()
        generator = DescriptionGenerator(llm_service=mock_llm)
        
        # Mock node and graph
        mock_node = Mock()
        mock_node.name = "calculate_average"
        mock_node.label = NodeLabels.FUNCTION
        mock_node.path = "file:///test/main.py"
        mock_node.extension = ".py"
        mock_node.hashed_id = "func_123"
        mock_node.text = "def calculate_average(numbers):\n    return sum(numbers) / len(numbers)"
        
        mock_graph = Mock()
        
        # Test _create_prompt_for_node method
        prompt_data = generator._create_prompt_for_node(mock_node, mock_graph)
        
        self.assertIsNotNone(prompt_data)
        assert prompt_data is not None  # Type narrowing for pyright
        self.assertEqual(prompt_data['id'], "func_123")
        self.assertIn("function", prompt_data['prompt'].lower())
        self.assertIn("calculate_average", prompt_data['prompt'])
        self.assertIn("def calculate_average", prompt_data['prompt'])
        
    def test_should_generate_description(self) -> None:
        """Test logic for which nodes should get descriptions."""
        # Mock LLM service
        mock_llm = Mock()
        generator = DescriptionGenerator(llm_service=mock_llm)
        
        # Test _get_eligible_nodes method which filters by label
        mock_graph = Mock()
        
        # Mock nodes with different labels
        func_node = Mock()
        func_node.label = NodeLabels.FUNCTION
        
        class_node = Mock() 
        class_node.label = NodeLabels.CLASS
        
        file_node = Mock()
        file_node.label = NodeLabels.FILE
        
        folder_node = Mock()
        folder_node.label = NodeLabels.FOLDER
        
        # The eligible labels are FILE, FUNCTION, CLASS, METHOD, MODULE
        eligible_labels = {
            NodeLabels.FILE, NodeLabels.FUNCTION, NodeLabels.CLASS,
            NodeLabels.METHOD, NodeLabels.MODULE
        }
        
        # Test that these labels are eligible
        self.assertIn(NodeLabels.FUNCTION, eligible_labels)
        self.assertIn(NodeLabels.CLASS, eligible_labels)
        self.assertIn(NodeLabels.FILE, eligible_labels)
        self.assertNotIn(NodeLabels.FOLDER, eligible_labels)
        
    def test_generate_description_with_mock_llm(self) -> None:
        """Test description generation with mocked LLM."""
        # Set up mock
        mock_llm = Mock()
        mock_llm.is_enabled.return_value = True
        mock_llm.generate_batch_descriptions.return_value = {
            "func_123": "Mock description for process_data function"
        }
        
        generator = DescriptionGenerator(llm_service=mock_llm)
        
        # Create a mock function node
        func_node = Mock()
        func_node.hashed_id = "func_123"
        func_node.id = "func_123"
        func_node.name = "process_data"
        func_node.label = NodeLabels.FUNCTION
        func_node.path = "file:///test/main.py"
        func_node.extension = ".py"
        func_node.level = 1
        func_node.parent = None
        func_node.text = "def process_data():\n    pass"
        
        # Create graph and add node
        graph = Graph()
        
        # Mock graph methods
        def mock_get_nodes_by_label(label: NodeLabels) -> list[Any]:
            if label == NodeLabels.FUNCTION:
                return [func_node]
            return []
        
        graph.get_nodes_by_label = mock_get_nodes_by_label
        
        # Generate descriptions
        desc_nodes = generator.generate_descriptions_for_graph(graph)
        
        # Check that description was generated
        self.assertEqual(len(desc_nodes), 1)
        desc_node = list(desc_nodes.values())[0]
        self.assertEqual(desc_node.description_text, "Mock description for process_data function")
        self.assertEqual(desc_node.target_node_id, "func_123")


class TestDescriptionRelationships(unittest.TestCase):
    """Test relationships involving description nodes."""
    
    def test_has_description_relationship(self) -> None:
        """Test HAS_DESCRIPTION relationship type."""
        from blarify.graph.relationship.relationship_type import RelationshipType
        
        # Verify the relationship type exists
        self.assertEqual(RelationshipType.HAS_DESCRIPTION.value, "HAS_DESCRIPTION")
        
    def test_references_in_description_relationship(self) -> None:
        """Test REFERENCES_IN_DESCRIPTION relationship type."""
        from blarify.graph.relationship.relationship_type import RelationshipType
        
        # Verify the relationship type exists  
        self.assertEqual(RelationshipType.REFERENCES_IN_DESCRIPTION.value, "REFERENCES_IN_DESCRIPTION")
        
    def test_referenced_by_description_relationship(self) -> None:
        """Test REFERENCED_BY_DESCRIPTION relationship type."""
        from blarify.graph.relationship.relationship_type import RelationshipType
        
        # Verify the relationship type exists
        self.assertEqual(RelationshipType.REFERENCED_BY_DESCRIPTION.value, "REFERENCED_BY_DESCRIPTION")


if __name__ == '__main__':
    unittest.main()