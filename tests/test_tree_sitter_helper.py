import unittest
from unittest.mock import MagicMock, patch, mock_open
from typing import Any
from blarify.code_hierarchy.tree_sitter_helper import TreeSitterHelper
from blarify.code_hierarchy.languages import (
    LanguageDefinitions,
    PythonDefinitions,
    FallbackDefinitions,
    BodyNodeNotFound
)
from blarify.code_hierarchy.languages.FoundRelationshipScope import FoundRelationshipScope
from blarify.graph.node import NodeLabels
from blarify.graph.relationship import RelationshipType
from blarify.code_references.types import Reference
from blarify.project_file_explorer import File


class TestTreeSitterHelper(unittest.TestCase):
    """Test cases for TreeSitterHelper class."""
    
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.mock_lang_def: MagicMock
        self.mock_parser: MagicMock
        self.helper: TreeSitterHelper
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_lang_def = MagicMock(spec=LanguageDefinitions)
        self.mock_parser = MagicMock()
        self.mock_lang_def.get_parsers_for_extensions.return_value = {".py": self.mock_parser}
        self.helper = TreeSitterHelper(self.mock_lang_def)
        
    def test_init(self) -> None:
        """Test TreeSitterHelper initialization."""
        mock_graph_env = MagicMock()
        helper = TreeSitterHelper(self.mock_lang_def, mock_graph_env)
        
        self.assertEqual(helper.language_definitions, self.mock_lang_def)
        self.assertEqual(helper.parsers, {".py": self.mock_parser})
        self.assertEqual(helper.graph_environment, mock_graph_env)
        
    def test_get_all_identifiers(self) -> None:
        """Test getting all identifiers from a file node."""
        mock_file_node = MagicMock()
        mock_file_node.path = "file:///test/file.py"
        mock_tree_sitter_node = MagicMock()
        mock_file_node._tree_sitter_node = mock_tree_sitter_node
        
        with patch.object(self.helper, '_traverse_and_find_identifiers') as mock_traverse:
            mock_traverse.return_value = [MagicMock(), MagicMock()]
            
            result = self.helper.get_all_identifiers(mock_file_node)
            
        self.assertEqual(self.helper.current_path, "file:///test/file.py")
        mock_traverse.assert_called_once_with(mock_tree_sitter_node)
        self.assertEqual(len(result), 2)
        
    def test_traverse_and_find_identifiers_with_identifier(self) -> None:
        """Test traversing and finding identifier nodes."""
        mock_node = MagicMock()
        mock_node.type = "identifier"
        mock_node.children = []
        
        mock_reference = MagicMock()
        
        with patch.object(self.helper, '_get_reference_from_node') as mock_get_ref:
            mock_get_ref.return_value = mock_reference
            
            result = self.helper._traverse_and_find_identifiers(mock_node)
            
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], mock_reference)
        
    def test_traverse_and_find_identifiers_with_children(self) -> None:
        """Test traversing nodes with children."""
        mock_child1 = MagicMock()
        mock_child1.type = "identifier"
        mock_child1.children = []
        
        mock_child2 = MagicMock()
        mock_child2.type = "other"
        mock_child2.children = []
        
        mock_parent = MagicMock()
        mock_parent.type = "parent"
        mock_parent.children = [mock_child1, mock_child2]
        
        with patch.object(self.helper, '_get_reference_from_node') as mock_get_ref:
            mock_get_ref.return_value = MagicMock()
            
            result = self.helper._traverse_and_find_identifiers(mock_parent)
            
        self.assertEqual(len(result), 1)  # Only one identifier node
        
    def test_get_reference_type_with_found_scope(self) -> None:
        """Test getting reference type when scope is found."""
        mock_original_node = MagicMock()
        mock_reference = MagicMock()
        mock_node_referenced = MagicMock()
        mock_ts_node = MagicMock()
        
        mock_scope = FoundRelationshipScope(
            node_in_scope=MagicMock(),
            relationship_type=RelationshipType.INSTANTIATES
        )
        
        with patch.object(self.helper, '_get_node_in_point_reference') as mock_get_node:
            mock_get_node.return_value = mock_ts_node
            self.mock_lang_def.get_relationship_type.return_value = mock_scope
            
            result = self.helper.get_reference_type(mock_original_node, mock_reference, mock_node_referenced)
            
        self.assertEqual(result, mock_scope)
        
    def test_get_reference_type_with_no_scope(self) -> None:
        """Test getting reference type when no scope is found."""
        mock_original_node = MagicMock()
        mock_reference = MagicMock()
        mock_node_referenced = MagicMock()
        
        with patch.object(self.helper, '_get_node_in_point_reference'):
            self.mock_lang_def.get_relationship_type.return_value = None
            
            result = self.helper.get_reference_type(mock_original_node, mock_reference, mock_node_referenced)
            
        self.assertIsNone(result.node_in_scope)
        self.assertEqual(result.relationship_type, RelationshipType.USES)
        
    def test_get_node_in_point_reference(self) -> None:
        """Test getting tree-sitter node for a reference point."""
        mock_node = MagicMock()
        mock_ts_node = MagicMock()
        mock_descendant = MagicMock()
        mock_ts_node.descendant_for_point_range.return_value = mock_descendant
        mock_node._tree_sitter_node = mock_ts_node
        
        mock_reference = MagicMock()
        mock_reference.range.start.line = 10
        mock_reference.range.start.character = 5
        mock_reference.range.end.line = 10
        mock_reference.range.end.character = 15
        
        result = self.helper._get_node_in_point_reference(mock_node, mock_reference)
        
        mock_ts_node.descendant_for_point_range.assert_called_once_with((10, 5), (10, 15))
        self.assertEqual(result, mock_descendant)
        
    def test_create_nodes_and_relationships_in_file_valid_extension(self) -> None:
        """Test creating nodes for file with valid extension."""
        mock_file = MagicMock(spec=File)
        mock_file.uri_path = "file:///test/file.py"
        mock_file.extension = ".py"
        
        mock_file_node = MagicMock()
        
        with patch.object(self.helper, '_get_content_from_file') as mock_get_content:
            with patch.object(self.helper, '_does_path_have_valid_extension') as mock_valid:
                with patch.object(self.helper, '_handle_paths_with_valid_extension') as mock_handle:
                    mock_get_content.return_value = "test content"
                    mock_valid.return_value = True
                    
                    # Mock the side effect of _handle_paths_with_valid_extension to populate created_nodes
                    def handle_side_effect(file, parent_folder=None):
                        self.helper.created_nodes.append(mock_file_node)
                    
                    mock_handle.side_effect = handle_side_effect
                    
                    result = self.helper.create_nodes_and_relationships_in_file(mock_file)
                    
        self.assertEqual(result, [mock_file_node])
        
    def test_create_nodes_and_relationships_in_file_invalid_extension(self) -> None:
        """Test creating nodes for file with invalid extension."""
        mock_file = MagicMock(spec=File)
        mock_file.uri_path = "file:///test/file.txt"
        
        mock_raw_node = MagicMock()
        
        with patch.object(self.helper, '_get_content_from_file') as mock_get_content:
            with patch.object(self.helper, '_does_path_have_valid_extension') as mock_valid:
                with patch.object(self.helper, '_create_file_node_from_raw_file') as mock_create:
                    mock_get_content.return_value = "test content"
                    mock_valid.return_value = False
                    mock_create.return_value = mock_raw_node
                    
                    result = self.helper.create_nodes_and_relationships_in_file(mock_file)
                    
        mock_raw_node.add_extra_label.assert_called_once_with("RAW")
        self.assertEqual(result, [mock_raw_node])
        
    def test_does_path_have_valid_extension_fallback(self) -> None:
        """Test path validation with fallback definitions."""
        self.helper.language_definitions = FallbackDefinitions
        result = self.helper._does_path_have_valid_extension("file.py")
        self.assertFalse(result)
        
    def test_does_path_have_valid_extension_valid(self) -> None:
        """Test path validation with valid extension."""
        self.mock_lang_def.get_language_file_extensions.return_value = [".py", ".pyi"]
        result = self.helper._does_path_have_valid_extension("file.py")
        self.assertTrue(result)
        
    def test_does_path_have_valid_extension_invalid(self) -> None:
        """Test path validation with invalid extension."""
        self.mock_lang_def.get_language_file_extensions.return_value = [".py", ".pyi"]
        result = self.helper._does_path_have_valid_extension("file.txt")
        self.assertFalse(result)
        
    def test_handle_paths_with_valid_extension(self) -> None:
        """Test handling files with valid extensions."""
        mock_file = MagicMock()
        mock_file.extension = ".py"
        mock_tree = MagicMock()
        mock_tree.root_node = MagicMock()
        mock_file_node = MagicMock()
        
        self.helper.base_node_source_code = "test code"
        self.helper.created_nodes = []
        
        with patch.object(self.helper, '_parse') as mock_parse:
            with patch.object(self.helper, '_create_file_node_from_module_node') as mock_create:
                with patch.object(self.helper, '_traverse') as mock_traverse:
                    mock_parse.return_value = mock_tree
                    mock_create.return_value = mock_file_node
                    
                    self.helper._handle_paths_with_valid_extension(mock_file)
                    
        mock_parse.assert_called_once_with("test code", ".py")
        mock_create.assert_called_once()
        mock_traverse.assert_called_once_with(mock_tree.root_node, context_stack=[mock_file_node])
        self.assertEqual(self.helper.created_nodes, [mock_file_node])
        
    def test_parse(self) -> None:
        """Test parsing code with tree-sitter."""
        mock_tree = MagicMock()
        self.mock_parser.parse.return_value = mock_tree
        
        result = self.helper._parse("test code", ".py")
        
        self.mock_parser.parse.assert_called_once_with(b"test code")
        self.assertEqual(result, mock_tree)
        
    @patch('blarify.code_hierarchy.tree_sitter_helper.NodeFactory')
    def test_create_file_node_from_module_node(self, mock_factory):
        """Test creating file node from module node."""
        mock_module_node = MagicMock()
        mock_file = MagicMock()
        mock_file.uri_path = "file:///test/file.py"
        mock_file.name = "file.py"
        mock_file.level = 0
        mock_parent = MagicMock()
        mock_reference = MagicMock()
        
        self.helper.base_node_source_code = "test code"
        self.helper.graph_environment = MagicMock()
        
        with patch.object(self.helper, '_get_reference_from_node') as mock_get_ref:
            mock_get_ref.return_value = mock_reference
            mock_node = MagicMock()
            mock_factory.create_file_node.return_value = mock_node
            
            result = self.helper._create_file_node_from_module_node(
                mock_module_node, mock_file, mock_parent
            )
            
        mock_factory.create_file_node.assert_called_once()
        self.assertEqual(result, mock_node)
        
    def test_get_content_from_file_success(self) -> None:
        """Test successfully reading file content."""
        mock_file = MagicMock()
        mock_file.path = "/test/file.py"
        
        with patch("builtins.open", mock_open(read_data="test content")):
            result = self.helper._get_content_from_file(mock_file)
            
        self.assertEqual(result, "test content")
        
    def test_get_content_from_file_unicode_error(self) -> None:
        """Test handling Unicode decode error."""
        mock_file = MagicMock()
        mock_file.path = "/test/file.py"
        
        with patch("builtins.open", mock_open()) as mock_file_open:
            mock_file_open.return_value.read.side_effect = UnicodeDecodeError(
                'utf-8', b'', 0, 1, 'invalid'
            )
            result = self.helper._get_content_from_file(mock_file)
            
        self.assertEqual(result, "")
        
    def test_traverse_create_node(self) -> None:
        """Test traversing and creating nodes."""
        mock_ts_node = MagicMock()
        mock_ts_node.named_children = []
        mock_node = MagicMock()
        
        self.helper.created_nodes = []
        self.mock_lang_def.should_create_node.return_value = True
        
        with patch.object(self.helper, '_handle_definition_node') as mock_handle:
            mock_handle.return_value = mock_node
            
            context_stack = [MagicMock()]
            self.helper._traverse(mock_ts_node, context_stack)
            
        mock_handle.assert_called_once()
        self.assertEqual(self.helper.created_nodes, [mock_node])
        
    def test_traverse_skip_node(self) -> None:
        """Test traversing without creating node."""
        mock_ts_node = MagicMock()
        mock_ts_node.named_children = []
        
        self.helper.created_nodes = []
        self.mock_lang_def.should_create_node.return_value = False
        
        context_stack = [MagicMock()]
        initial_len = len(context_stack)
        
        self.helper._traverse(mock_ts_node, context_stack)
        
        self.assertEqual(self.helper.created_nodes, [])
        self.assertEqual(len(context_stack), initial_len)
        
    @patch('blarify.code_hierarchy.tree_sitter_helper.NodeFactory')
    def test_handle_definition_node(self, mock_factory):
        """Test handling definition nodes."""
        mock_ts_node = MagicMock()
        mock_ts_node.text = b"class TestClass"
        
        mock_parent = MagicMock()
        mock_parent.level = 0
        context_stack = [mock_parent]
        
        mock_node = MagicMock()
        mock_factory.create_node_based_on_label.return_value = mock_node
        
        self.helper.current_path = "file:///test/file.py"
        self.helper.graph_environment = MagicMock()
        
        with patch.object(self.helper, '_process_identifier_node') as mock_process_id:
            with patch.object(self.helper, '_get_reference_from_node') as mock_get_ref:
                with patch.object(self.helper, '_try_process_body_node_snippet') as mock_body:
                    with patch.object(self.helper, 'get_parent_node') as mock_get_parent:
                        with patch.object(self.helper, '_get_label_from_node') as mock_get_label:
                            mock_process_id.return_value = ("TestClass", MagicMock())
                            mock_get_ref.return_value = MagicMock()
                            mock_body.return_value = MagicMock()
                            mock_get_parent.return_value = mock_parent
                            mock_get_label.return_value = NodeLabels.CLASS
                            
                            result = self.helper._handle_definition_node(mock_ts_node, context_stack)
                            
        mock_parent.relate_node_as_define_relationship.assert_called_once_with(mock_node)
        self.assertEqual(result, mock_node)
        
    def test_process_identifier_node(self) -> None:
        """Test processing identifier nodes."""
        mock_node = MagicMock()
        mock_identifier_node = MagicMock()
        mock_reference = MagicMock()
        
        self.mock_lang_def.get_identifier_node.return_value = mock_identifier_node
        
        with patch.object(self.helper, '_get_reference_from_node') as mock_get_ref:
            with patch.object(self.helper, '_get_identifier_name') as mock_get_name:
                mock_get_ref.return_value = mock_reference
                mock_get_name.return_value = "test_name"
                
                name, ref = self.helper._process_identifier_node(mock_node)
                
        self.assertEqual(name, "test_name")
        self.assertEqual(ref, mock_reference)
        
    def test_get_identifier_name(self) -> None:
        """Test getting identifier name from node."""
        mock_node = MagicMock()
        mock_node.text = b"test_identifier"
        
        result = self.helper._get_identifier_name(mock_node)
        
        self.assertEqual(result, "test_identifier")
        
    def test_get_code_snippet_from_base_file(self) -> None:
        """Test extracting code snippet from base file."""
        self.helper.base_node_source_code = "line1\nline2\nline3\nline4\nline5"
        
        mock_range = MagicMock()
        mock_range.start.line = 1
        mock_range.end.line = 3
        
        result = self.helper._get_code_snippet_from_base_file(mock_range)
        
        self.assertEqual(result, "line2\nline3\nline4")
        
    def test_get_reference_from_node(self) -> None:
        """Test creating reference from tree-sitter node."""
        mock_node = MagicMock()
        mock_node.start_point = (10, 5)
        mock_node.end_point = (10, 15)
        
        self.helper.current_path = "file:///test/file.py"
        
        result = self.helper._get_reference_from_node(mock_node)
        
        self.assertIsInstance(result, Reference)
        self.assertEqual(result.uri, "file:///test/file.py")
        self.assertEqual(result.range.start.line, 10)
        self.assertEqual(result.range.start.character, 5)
        self.assertEqual(result.range.end.line, 10)
        self.assertEqual(result.range.end.character, 15)
        
    def test_process_node_snippet(self) -> None:
        """Test processing node snippet."""
        mock_node = MagicMock()
        mock_reference = MagicMock()
        
        with patch.object(self.helper, '_get_reference_from_node') as mock_get_ref:
            with patch.object(self.helper, '_get_code_snippet_from_base_file') as mock_get_snippet:
                mock_get_ref.return_value = mock_reference
                mock_get_snippet.return_value = "test snippet"
                
                snippet, ref = self.helper._process_node_snippet(mock_node)
                
        self.assertEqual(snippet, "test snippet")
        self.assertEqual(ref, mock_reference)
        
    def test_try_process_body_node_snippet_success(self) -> None:
        """Test trying to process body node snippet successfully."""
        mock_node = MagicMock()
        mock_body = MagicMock()
        
        with patch.object(self.helper, '_process_body_node_snippet') as mock_process:
            mock_process.return_value = mock_body
            
            result = self.helper._try_process_body_node_snippet(mock_node)
            
        self.assertEqual(result, mock_body)
        
    def test_try_process_body_node_snippet_not_found(self) -> None:
        """Test trying to process body node when not found."""
        mock_node = MagicMock()
        
        with patch.object(self.helper, '_process_body_node_snippet') as mock_process:
            mock_process.side_effect = BodyNodeNotFound()
            
            result = self.helper._try_process_body_node_snippet(mock_node)
            
        self.assertIsNone(result)
        
    def test_process_body_node_snippet(self) -> None:
        """Test processing body node snippet."""
        mock_node = MagicMock()
        mock_body = MagicMock()
        
        self.mock_lang_def.get_body_node.return_value = mock_body
        
        result = self.helper._process_body_node_snippet(mock_node)
        
        self.assertEqual(result, mock_body)
        
    def test_get_label_from_node(self) -> None:
        """Test getting label from node type."""
        mock_node = MagicMock()
        mock_node.type = "class_definition"
        
        self.mock_lang_def.get_node_label_from_type.return_value = NodeLabels.CLASS
        
        result = self.helper._get_label_from_node(mock_node)
        
        self.assertEqual(result, NodeLabels.CLASS)
        self.mock_lang_def.get_node_label_from_type.assert_called_once_with("class_definition")
        
    def test_get_parent_node(self) -> None:
        """Test getting parent node from context stack."""
        mock_parent = MagicMock()
        context_stack = [MagicMock(), MagicMock(), mock_parent]
        
        result = self.helper.get_parent_node(context_stack)
        
        self.assertEqual(result, mock_parent)
        
    @patch('blarify.code_hierarchy.tree_sitter_helper.NodeFactory')
    def test_create_file_node_from_raw_file(self, mock_factory):
        """Test creating file node from raw file."""
        mock_file = MagicMock()
        mock_file.uri_path = "file:///test/file.txt"
        mock_file.name = "file.txt"
        mock_file.level = 0
        
        mock_node = MagicMock()
        mock_factory.create_file_node.return_value = mock_node
        
        self.helper.base_node_source_code = "raw content"
        self.helper.graph_environment = MagicMock()
        self.helper.current_path = "file:///test/file.txt"
        
        with patch.object(self.helper, '_empty_reference') as mock_empty:
            mock_empty.return_value = MagicMock()
            
            result = self.helper._create_file_node_from_raw_file(mock_file)
            
        self.assertEqual(result, mock_node)
        
    def test_empty_reference(self) -> None:
        """Test creating empty reference."""
        self.helper.current_path = "file:///test/file.py"
        
        result = self.helper._empty_reference()
        
        self.assertIsInstance(result, Reference)
        self.assertEqual(result.uri, "file:///test/file.py")
        self.assertEqual(result.range.start.line, 0)
        self.assertEqual(result.range.start.character, 0)
        self.assertEqual(result.range.end.line, 0)
        self.assertEqual(result.range.end.character, 0)
    
    def test_with_python_definitions(self) -> None:
        """Test TreeSitterHelper with actual PythonDefinitions."""
        # Test with actual PythonDefinitions instance
        python_helper = TreeSitterHelper(PythonDefinitions)
        
        # Verify the parsers dictionary is properly populated
        self.assertIn(".py", python_helper.parsers)
        self.assertIsNotNone(python_helper.parsers[".py"])
        self.assertEqual(python_helper.language_definitions, PythonDefinitions)
        
        # Test that language definitions integration works
        extensions = PythonDefinitions.get_language_file_extensions()
        self.assertIn(".py", extensions)
        for ext in extensions:
            self.assertIn(ext, python_helper.parsers)
        
        # Test path validation works with actual definitions
        self.assertTrue(python_helper._does_path_have_valid_extension("test.py"))
        self.assertFalse(python_helper._does_path_have_valid_extension("test.txt"))
        
        # Test that parser integration actually functions
        # Verify the parser object has expected tree-sitter methods
        parser = python_helper.parsers[".py"]
        self.assertTrue(hasattr(parser, 'parse'))
        self.assertTrue(callable(getattr(parser, 'parse')))
        
        # Test that language definitions methods work correctly
        self.assertEqual(PythonDefinitions.get_language_name(), "python")
        
        # Verify node label mapping works
        mock_node_type = "function_definition"
        label = PythonDefinitions.get_node_label_from_type(mock_node_type)
        self.assertIsNotNone(label)
    
    def test_with_fallback_definitions(self) -> None:
        """Test TreeSitterHelper behavior with FallbackDefinitions."""
        fallback_helper = TreeSitterHelper(FallbackDefinitions)
        
        # Verify fallback behavior
        self.assertEqual(fallback_helper.language_definitions, FallbackDefinitions)
        self.assertFalse(fallback_helper._does_path_have_valid_extension("test.py"))
        self.assertFalse(fallback_helper._does_path_have_valid_extension("test.js"))
    
    def test_language_definitions_integration(self) -> None:
        """Test integration between TreeSitterHelper and language definitions."""
        with patch.object(self.helper, 'language_definitions') as mock_lang_def:
            mock_lang_def.get_language_file_extensions.return_value = [".py", ".pyi"]
            mock_lang_def.should_create_node.return_value = True
            mock_lang_def.get_node_label_from_type.return_value = NodeLabels.CLASS
            
            # Test that helper properly delegates to language definitions
            self.assertTrue(self.helper._does_path_have_valid_extension("test.py"))
            
            mock_ts_node = MagicMock()
            mock_ts_node.type = "class_definition"
            
            result = self.helper._get_label_from_node(mock_ts_node)
            self.assertEqual(result, NodeLabels.CLASS)
            mock_lang_def.get_node_label_from_type.assert_called_with("class_definition")


if __name__ == '__main__':
    unittest.main()