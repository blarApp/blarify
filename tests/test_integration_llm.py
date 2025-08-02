import unittest
import tempfile
import shutil
import os
from typing import Any
from unittest.mock import patch, MagicMock
from blarify.prebuilt.graph_builder import GraphBuilder


class TestLLMIntegration(unittest.TestCase):
    
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.test_dir: str
    
    def setUp(self) -> None:
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        
        # Create test Python files
        self.create_test_file("main.py", """
def main():
    '''Main entry point of the application'''
    calculator = Calculator()
    result = calculator.add(5, 3)
    print(f"Result: {result}")

class Calculator:
    '''A simple calculator class'''
    def add(self, a, b):
        '''Add two numbers together'''
        return a + b
    
    def subtract(self, a, b):
        '''Subtract b from a'''
        return a - b

if __name__ == "__main__":
    main()
""")
        
        self.create_test_file("utils.py", """
def format_number(num):
    '''Format a number with thousands separators'''
    return f"{num:,}"

def validate_input(value):
    '''Validate that input is a positive number'''
    try:
        num = float(value)
        return num > 0
    except ValueError:
        return False
""")
    
    def tearDown(self) -> None:
        # Clean up temporary directory
        shutil.rmtree(self.test_dir)
    
    def create_test_file(self, filename: str, content: str) -> None:
        filepath = os.path.join(self.test_dir, filename)
        with open(filepath, 'w') as f:
            f.write(content)
    
    @patch.dict(os.environ, {
        'AZURE_OPENAI_API_KEY': 'test-key',
        'AZURE_OPENAI_ENDPOINT': 'https://test.openai.azure.com/',
        'AZURE_OPENAI_DEPLOYMENT_NAME': 'test-deployment',
        'ENABLE_LLM_DESCRIPTIONS': 'true'
    })
    @patch('blarify.llm_descriptions.llm_service.AzureOpenAI')
    def test_graph_with_llm_descriptions(self, mock_azure_openai: MagicMock) -> None:
        # Mock the OpenAI client
        mock_client = MagicMock()
        mock_azure_openai.return_value = mock_client
        
        # Mock responses for different node types
        response_counter = 0
        descriptions = [
            "This is the main entry point file containing the Calculator class and main function.",
            "The main function that initializes a Calculator and demonstrates addition.",
            "A simple calculator class providing basic arithmetic operations.",
            "Adds two numbers and returns their sum.",
            "Subtracts the second number from the first and returns the result.",
            "Utility file containing helper functions for number formatting and validation.",
            "Formats a number with thousands separators for better readability.",
            "Validates that the input is a positive number, returning True if valid."
        ]
        
        def mock_create(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal response_counter
            mock_response = MagicMock()
            mock_response.choices[0].message.content = descriptions[response_counter % len(descriptions)]
            response_counter += 1
            return mock_response
        
        mock_client.chat.completions.create.side_effect = mock_create
        
        # Build graph with LLM descriptions enabled
        builder = GraphBuilder(
            root_path=self.test_dir,
            extensions_to_skip=[".pyc"],
            names_to_skip=["__pycache__"],
            enable_llm_descriptions=True
        )
        
        graph = builder.build()
        
        # Verify nodes were created
        all_nodes = graph.get_nodes_as_objects()
        self.assertGreater(len(all_nodes), 0)
        
        # Check for description nodes
        description_nodes = [n for n in all_nodes if n['type'] == 'DESCRIPTION']
        self.assertGreater(len(description_nodes), 0)
        
        # Verify relationships
        relationships = graph.get_relationships_as_objects()
        has_description_rels = [r for r in relationships if r['type'] == 'HAS_DESCRIPTION']
        self.assertGreater(len(has_description_rels), 0)
        
        # Verify LLM was called
        self.assertGreater(mock_client.chat.completions.create.call_count, 0)
    
    @patch.dict(os.environ, {
        'ENABLE_LLM_DESCRIPTIONS': 'false'
    })
    def test_graph_without_llm_descriptions(self) -> None:
        # Build graph with LLM descriptions disabled
        builder = GraphBuilder(
            root_path=self.test_dir,
            extensions_to_skip=[".pyc"],
            names_to_skip=["__pycache__"],
            enable_llm_descriptions=False
        )
        
        graph = builder.build()
        
        # Verify nodes were created
        all_nodes = graph.get_nodes_as_objects()
        self.assertGreater(len(all_nodes), 0)
        
        # Check that no description nodes were created
        description_nodes = [n for n in all_nodes if n['type'] == 'DESCRIPTION']
        self.assertEqual(len(description_nodes), 0)
        
        # Verify no HAS_DESCRIPTION relationships
        relationships = graph.get_relationships_as_objects()
        has_description_rels = [r for r in relationships if r['type'] == 'HAS_DESCRIPTION']
        self.assertEqual(len(has_description_rels), 0)


if __name__ == '__main__':
    unittest.main()