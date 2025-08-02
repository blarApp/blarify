import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from typing import Any

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blarify.llm_descriptions.description_generator import DescriptionGenerator
from blarify.llm_descriptions.llm_service import LLMService
from blarify.graph.graph import Graph
from blarify.graph.node.types.node_labels import NodeLabels
from blarify.graph.graph_environment import GraphEnvironment


class TestDescriptionGenerator(unittest.TestCase):
    mock_llm_service: MagicMock
    graph_env: GraphEnvironment
    generator: DescriptionGenerator
    graph: Graph
    
    def setUp(self) -> None:
        self.mock_llm_service = MagicMock(spec=LLMService)
        self.mock_llm_service.is_enabled.return_value = True
        self.mock_llm_service.deployment_name = "test-deployment"
        
        self.graph_env = GraphEnvironment("test", "repo", "/test/path")
        self.generator = DescriptionGenerator(self.mock_llm_service, self.graph_env)
        self.graph = Graph()
    
    def test_detect_language(self) -> None:
        test_cases = [
            (".py", "Python"),
            (".js", "JavaScript"),
            (".ts", "TypeScript"),
            (".rb", "Ruby"),
            (".cs", "C#"),
            (".go", "Go"),
            (".php", "PHP"),
            (".java", "Java"),
            (".unknown", "Unknown")
        ]
        
        for extension, expected_language in test_cases:
            with self.subTest(extension=extension):
                language = self.generator._detect_language(extension)
                self.assertEqual(language, expected_language)
    
    def test_get_eligible_nodes(self) -> None:
        # Create test nodes
        file_node = MagicMock()
        file_node.label = NodeLabels.FILE
        
        function_node = MagicMock()
        function_node.label = NodeLabels.FUNCTION
        
        class_node = MagicMock()
        class_node.label = NodeLabels.CLASS
        
        # Add nodes to graph
        self.graph.add_node(file_node)
        self.graph.add_node(function_node)
        self.graph.add_node(class_node)
        
        eligible_nodes = self.generator._get_eligible_nodes(self.graph)
        
        self.assertEqual(len(eligible_nodes), 3)
        self.assertIn(file_node, eligible_nodes)
        self.assertIn(function_node, eligible_nodes)
        self.assertIn(class_node, eligible_nodes)
    
    def test_create_prompt_for_file_node(self) -> None:
        file_node = MagicMock()
        file_node.label = NodeLabels.FILE
        file_node.path = "file:///test/project/main.py"
        file_node.name = "main.py"
        file_node.extension = ".py"
        file_node.hashed_id = "test-hash-1"
        
        prompt_data = self.generator._create_prompt_for_node(file_node, self.graph)
        
        self.assertIsNotNone(prompt_data)
        assert prompt_data is not None  # Type narrowing for pyright
        self.assertEqual(prompt_data["id"], "test-hash-1")
        self.assertIn("main.py", prompt_data["prompt"])
        self.assertIn("Python", prompt_data["prompt"])
    
    def test_create_prompt_for_function_node(self) -> None:
        function_node = MagicMock()
        function_node.label = NodeLabels.FUNCTION
        function_node.path = "file:///test/project/utils.py"
        function_node.name = "calculate_total"
        function_node.extension = ".py"
        function_node.hashed_id = "test-hash-2"
        function_node.text = "def calculate_total(items):\n    return sum(item.price for item in items)"
        
        prompt_data = self.generator._create_prompt_for_node(function_node, self.graph)
        
        self.assertIsNotNone(prompt_data)
        assert prompt_data is not None  # Type narrowing for pyright
        self.assertEqual(prompt_data["id"], "test-hash-2")
        self.assertIn("calculate_total", prompt_data["prompt"])
        self.assertIn("def calculate_total", prompt_data["prompt"])
    
    def test_generate_descriptions_for_graph_disabled(self) -> None:
        self.mock_llm_service.is_enabled.return_value = False
        
        result = self.generator.generate_descriptions_for_graph(self.graph)
        
        self.assertEqual(result, {})
        self.mock_llm_service.generate_batch_descriptions.assert_not_called()
    
    @patch('blarify.llm_descriptions.description_generator.logger')
    def test_generate_descriptions_for_graph(self, mock_logger: MagicMock) -> None:
        # Create test nodes
        file_node = MagicMock()
        file_node.label = NodeLabels.FILE
        file_node.path = "file:///test/project/main.py"
        file_node.name = "main.py"
        file_node.extension = ".py"
        file_node.hashed_id = "file-hash"
        file_node.level = 1
        file_node.parent = None
        
        self.graph.add_node(file_node)
        
        # Mock LLM response
        self.mock_llm_service.generate_batch_descriptions.return_value = {
            "file-hash": "This is the main entry point of the application."
        }
        
        # Generate descriptions
        result = self.generator.generate_descriptions_for_graph(self.graph)
        
        # Verify results
        self.assertEqual(len(result), 1)
        self.mock_llm_service.generate_batch_descriptions.assert_called_once()
        
        # Check that description node was created
        description_nodes = list(result.values())
        self.assertEqual(len(description_nodes), 1)
        
        desc_node = description_nodes[0]
        self.assertEqual(desc_node.description_text, "This is the main entry point of the application.")
        self.assertEqual(desc_node.target_node_id, "file-hash")
    
    def test_extract_referenced_nodes(self) -> None:
        # Create test nodes in graph
        func_node = MagicMock()
        func_node.label = NodeLabels.FUNCTION
        func_node.name = "process_data"
        
        class_node = MagicMock()
        class_node.label = NodeLabels.CLASS
        class_node.name = "DataProcessor"
        
        self.graph.add_node(func_node)
        self.graph.add_node(class_node)
        
        # Test description with references
        description = "This function calls `process_data` and instantiates the 'DataProcessor' class."
        
        referenced_nodes = self.generator._extract_referenced_nodes(description, self.graph)
        
        self.assertEqual(len(referenced_nodes), 2)
        self.assertIn(func_node, referenced_nodes)
        self.assertIn(class_node, referenced_nodes)
    
    def test_create_description_node_and_relationship(self) -> None:
        # Create target node
        target_node = MagicMock()
        target_node.path = "file:///test/project/utils.py"
        target_node.name = "calculate_total"
        target_node.level = 2
        target_node.hashed_id = "target-hash"
        target_node.parent = None
        
        description_text = "This function calculates the total price of items."
        
        desc_node, relationship = self.generator._create_description_node_and_relationship(
            target_node, description_text, self.graph
        )
        
        self.assertIsNotNone(desc_node)
        self.assertIsNotNone(relationship)
        
        self.assertEqual(desc_node.description_text, description_text)
        self.assertEqual(desc_node.target_node_id, "target-hash")
        self.assertEqual(desc_node.name, "Description of calculate_total")
        
        self.assertEqual(relationship.start_node, target_node)
        self.assertEqual(relationship.end_node, desc_node)


if __name__ == '__main__':
    unittest.main()