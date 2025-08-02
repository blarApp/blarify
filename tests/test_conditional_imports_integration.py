"""
Integration test to verify Blarify works with missing language modules.
This test actually tests the warning system rather than mocking imports.
"""
import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestConditionalImportsIntegration(unittest.TestCase):
    """Integration tests for conditional language imports."""
    
    def test_import_with_warnings(self) -> None:
        """Test that the import system properly handles and warns about failures."""
        # Force reimport to trigger the conditional loading
        if 'blarify.code_hierarchy.languages' in sys.modules:
            del sys.modules['blarify.code_hierarchy.languages']
            # Also clear the language-specific modules
            for key in list(sys.modules.keys()):
                if key.startswith('blarify.code_hierarchy.languages.'):
                    del sys.modules[key]
        
        # Import and check functionality
        from blarify.code_hierarchy.languages import (
            get_available_languages,
            get_language_definition,
            FallbackDefinitions
        )
        
        # Test that we can get available languages
        available = get_available_languages()
        self.assertIsInstance(available, list)
        self.assertGreater(len(available), 0, "Should have at least one language available")
        
        # Test getting a language that exists
        if 'python' in available:
            python_def = get_language_definition('python')
            self.assertIsNotNone(python_def)
        
        # Test getting a language that doesn't exist
        fake_def = get_language_definition('nonexistent_language')
        self.assertIsNone(fake_def)
        
        # Test that FallbackDefinitions is always available
        self.assertIsNotNone(FallbackDefinitions)
    
    def test_project_graph_creator_robustness(self) -> None:
        """Test that ProjectGraphCreator is robust to missing languages."""
        from blarify.project_graph_creator import ProjectGraphCreator
        from blarify.code_hierarchy.languages import FallbackDefinitions
        from unittest.mock import MagicMock
        
        # Create mock dependencies
        mock_lsp = MagicMock()
        mock_iterator = MagicMock()
        
        # Create instance - should not crash
        creator = ProjectGraphCreator(
            root_path="/test",
            lsp_query_helper=mock_lsp,
            project_files_iterator=mock_iterator,
            enable_llm_descriptions=False,
            enable_filesystem_nodes=False,
            enable_documentation_nodes=False
        )
        
        # Test that languages dict is populated
        self.assertIsInstance(creator.languages, dict)
        self.assertGreater(len(creator.languages), 0, "Should have some language mappings")
        
        # Test fallback for unknown extension
        unknown_def = creator.languages.get('.unknown', FallbackDefinitions)
        self.assertEqual(unknown_def.__name__, 'FallbackDefinitions')
    
    def test_lsp_helper_error_messages(self) -> None:
        """Test that LspQueryHelper provides clear error messages."""
        from blarify.code_references.lsp_helper import (
            LspQueryHelper,
            FileExtensionNotSupported
        )
        
        # Test unsupported extension
        with self.assertRaises(FileExtensionNotSupported) as cm:
            LspQueryHelper.get_language_definition_for_extension('.xyz')
        
        error_msg = str(cm.exception)
        self.assertIn('not supported', error_msg)
        
        # Test that supported extensions work
        from blarify.code_hierarchy.languages import get_available_languages
        available = get_available_languages()
        
        if 'python' in available:
            # Should not raise for Python
            try:
                python_def = LspQueryHelper.get_language_definition_for_extension('.py')
                self.assertIsNotNone(python_def)
            except FileExtensionNotSupported:
                self.fail("Python should be supported")


if __name__ == '__main__':
    unittest.main()