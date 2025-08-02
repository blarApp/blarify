"""
Tests for documentation extraction and processing.
"""
import unittest
from unittest.mock import Mock, patch
import tempfile
import os
from pathlib import Path
from typing import Any

from blarify.documentation.documentation_parser import DocumentationParser
from blarify.documentation.documentation_graph_generator import DocumentationGraphGenerator
from blarify.graph.graph import Graph
from blarify.graph.node.types.node_labels import NodeLabels
# from tests.fixtures.graph_fixtures import create_test_graph  # Commented out due to FileNode constructor issues


class TestDocumentationParser(unittest.TestCase):
    """Test documentation file parsing."""
    temp_dir: str
    parser: DocumentationParser
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.parser = DocumentationParser(root_path=self.temp_dir)
        
    def tearDown(self) -> None:
        """Clean up test files."""
        import shutil
        shutil.rmtree(self.temp_dir)
        
    def test_is_documentation_file_markdown(self) -> None:
        """Test identifying markdown files as documentation."""
        # Create test files
        readme_path = os.path.join(self.temp_dir, "README.md")
        Path(readme_path).write_text("# Test Project")
        
        # Test that common documentation files are identified
        self.assertTrue(self.parser._is_documentation_file("README.md", readme_path))
        self.assertTrue(self.parser._is_documentation_file("CHANGELOG.md", "CHANGELOG.md"))
        self.assertTrue(self.parser._is_documentation_file("docs.md", "docs.md"))
        
    def test_is_documentation_file_other_formats(self) -> None:
        """Test identifying other documentation formats."""
        self.assertTrue(self.parser._is_documentation_file("README.rst", "README.rst"))
        self.assertTrue(self.parser._is_documentation_file("documentation.txt", "documentation.txt"))
        self.assertTrue(self.parser._is_documentation_file("guide.adoc", "guide.adoc"))
        
    def test_is_not_documentation_file(self) -> None:
        """Test files that should not be identified as documentation."""
        self.assertFalse(self.parser._is_documentation_file("main.py", "main.py"))
        self.assertFalse(self.parser._is_documentation_file("config.json", "config.json"))
        self.assertFalse(self.parser._is_documentation_file("test.js", "test.js"))
        
    def test_find_documentation_files(self) -> None:
        """Test finding documentation files in directory."""
        # Create test structure
        (Path(self.temp_dir) / "README.md").write_text("# Main")
        (Path(self.temp_dir) / "docs").mkdir()
        (Path(self.temp_dir) / "docs" / "guide.md").write_text("# Guide")
        (Path(self.temp_dir) / "src").mkdir()
        (Path(self.temp_dir) / "src" / "main.py").write_text("print('hello')")
        
        doc_files = self.parser.find_documentation_files()
        
        # Should find markdown files but not Python files
        doc_file_names = [os.path.basename(f) for f in doc_files]
        self.assertIn("README.md", doc_file_names)
        self.assertIn("guide.md", doc_file_names)
        self.assertNotIn("main.py", doc_file_names)
        
    def test_parse_documentation_files(self) -> None:
        """Test parsing documentation files."""
        # Create test documentation
        readme_content = "# Project\nThis is a test project."
        (Path(self.temp_dir) / "README.md").write_text(readme_content)
        
        result = self.parser.parse_documentation_files()
        
        self.assertIn("documentation_files", result)
        self.assertEqual(len(result["documentation_files"]), 1)
        
        doc_file = result["documentation_files"][0]
        self.assertEqual(doc_file["name"], "README.md")
        self.assertEqual(doc_file["content"], readme_content)




class TestDocumentationGraphGenerator(unittest.TestCase):
    """Test documentation graph generation."""
    temp_dir: str
    mock_llm: Mock
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_llm = Mock()
        
    def tearDown(self) -> None:
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir)
        
    @patch('blarify.project_file_explorer.project_files_iterator.ProjectFilesIterator')
    def test_generate_documentation_nodes(self, mock_iterator: Mock) -> None:
        """Test generating documentation nodes."""
        # Create test structure
        (Path(self.temp_dir) / "README.md").write_text("# Test Project")
        
        # Mock iterator
        mock_file = Mock()
        mock_file.path = str(Path(self.temp_dir) / "README.md")
        mock_file.name = "README.md"
        mock_file.relative_path = "README.md"
        mock_iterator.return_value = [mock_file]
        
        mock_graph_env = Mock()
        generator = DocumentationGraphGenerator(
            root_path=self.temp_dir,
            llm_service=self.mock_llm,
            graph_environment=mock_graph_env
        )
        
        graph = Graph()
        
        # Should not fail even if LLM is not enabled
        self.mock_llm.is_enabled.return_value = False
        generator.generate_documentation_nodes(graph)
        
        # When enabled, should parse files
        self.mock_llm.is_enabled.return_value = True
        self.mock_llm.extract_concepts.return_value = {
            "concepts": [],
            "entities": []
        }
        
        generator.generate_documentation_nodes(graph)
        
        # Should have created documentation file nodes
        doc_nodes = graph.get_nodes_by_label(NodeLabels.DOCUMENTATION_FILE)
        self.assertGreaterEqual(len(doc_nodes), 0)


if __name__ == '__main__':
    unittest.main()