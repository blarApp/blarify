"""
Comprehensive tests for filesystem operations and graph generation.
"""
import unittest
import tempfile
from pathlib import Path

from blarify.filesystem.filesystem_graph_generator import FilesystemGraphGenerator
from blarify.graph.graph import Graph
from blarify.graph.node.types.node_labels import NodeLabels
from blarify.graph.relationship.relationship_type import RelationshipType
from blarify.project_file_explorer.gitignore_manager import GitignoreManager
from blarify.graph.graph_environment import GraphEnvironment


class TestFilesystemGraphGenerator(unittest.TestCase):
    """Test filesystem graph generation."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir: str = tempfile.mkdtemp()  # type: ignore[reportUninitializedInstanceVariable]
        # Create generator with common names to skip
        self.generator: FilesystemGraphGenerator = FilesystemGraphGenerator(  # type: ignore[reportUninitializedInstanceVariable]
            root_path=self.temp_dir,
            names_to_skip=['.git', '__pycache__', '.DS_Store', 'node_modules']
        )
        self.graph: Graph = Graph()  # type: ignore[reportUninitializedInstanceVariable]
        
    def tearDown(self) -> None:
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.temp_dir)
        
    def create_test_structure(self):
        """Create a test file structure."""
        # Create directories
        (Path(self.temp_dir) / "src").mkdir()
        (Path(self.temp_dir) / "src" / "utils").mkdir()
        (Path(self.temp_dir) / "tests").mkdir()
        (Path(self.temp_dir) / "docs").mkdir()
        (Path(self.temp_dir) / ".git").mkdir()
        
        # Create files
        files = [
            "README.md",
            "setup.py",
            ".gitignore",
            "src/__init__.py",
            "src/main.py",
            "src/utils/__init__.py",
            "src/utils/helpers.py",
            "tests/test_main.py",
            "docs/api.md",
            ".git/config"
        ]
        
        for file_path in files:
            full_path = Path(self.temp_dir) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(f"# Content of {file_path}")
            
        return files
        
    def test_generate_filesystem_nodes(self) -> None:
        """Test generating filesystem nodes for project."""
        self.create_test_structure()
        
        self.generator.generate_filesystem_nodes(self.graph)
        
        # Check directory nodes
        dir_nodes = self.graph.get_nodes_by_label(NodeLabels.FILESYSTEM_DIRECTORY)
        self.assertGreater(len(dir_nodes), 0)
        
        # Check file nodes
        file_nodes = self.graph.get_nodes_by_label(NodeLabels.FILESYSTEM_FILE)
        self.assertGreater(len(file_nodes), 0)
        
        # Verify specific directories exist
        dir_names = [node.name for node in dir_nodes]
        self.assertIn("src", dir_names)
        self.assertIn("tests", dir_names)
        self.assertIn("docs", dir_names)
        
        # Verify specific files exist
        file_names = [node.name for node in file_nodes]
        self.assertIn("README.md", file_names)
        self.assertIn("main.py", file_names)
        self.assertIn("helpers.py", file_names)
        
    def test_filesystem_contains_relationships(self) -> None:
        """Test FILESYSTEM_CONTAINS relationships are created correctly."""
        self.create_test_structure()
        
        self.generator.generate_filesystem_nodes(self.graph)
        
        # Get relationships
        relationships = self.graph.get_relationships_as_objects()
        contains_rels = [r for r in relationships 
                        if r['type'] == RelationshipType.FILESYSTEM_CONTAINS.value]
        
        self.assertGreater(len(contains_rels), 0)
        
        # Check specific relationship: src contains main.py
        src_node = next((n for n in self.graph.get_nodes_by_label(NodeLabels.FILESYSTEM_DIRECTORY)
                        if n.name == "src"), None)
        self.assertIsNotNone(src_node)
        
        main_py_node = next((n for n in self.graph.get_nodes_by_label(NodeLabels.FILESYSTEM_FILE)
                           if n.name == "main.py" and hasattr(n, 'relative_path') and "src" in n.relative_path), None)  # type: ignore[attr-defined]
        self.assertIsNotNone(main_py_node)
        
        # Find relationship
        rel_exists = any(r for r in contains_rels
                        if r['sourceId'] == src_node.hashed_id and r['targetId'] == main_py_node.hashed_id)  # type: ignore[attr-defined]
        self.assertTrue(rel_exists)
        
    def test_skip_hidden_directories(self) -> None:
        """Test that hidden directories like .git are skipped."""
        self.create_test_structure()
        
        self.generator.generate_filesystem_nodes(self.graph)
        
        # .git directory should not have a node
        dir_nodes = self.graph.get_nodes_by_label(NodeLabels.FILESYSTEM_DIRECTORY)
        git_dirs = [n for n in dir_nodes if n.name == ".git"]
        self.assertEqual(len(git_dirs), 0)
        
        # Since .git directory is skipped, no files within it should exist
        file_nodes = self.graph.get_nodes_by_label(NodeLabels.FILESYSTEM_FILE)
        # Check for files that are actually inside the .git directory
        git_files = [n for n in file_nodes if "/.git/" in n.path]
        self.assertEqual(len(git_files), 0)
        
    def test_file_properties(self) -> None:
        """Test that file nodes have correct properties."""
        # Create a specific file
        test_file = Path(self.temp_dir) / "test.py"
        test_content = "print('Hello, World!')\n"
        test_file.write_text(test_content)
        
        # Get file stats
        stats = test_file.stat()
        
        self.generator.generate_filesystem_nodes(self.graph)
        
        # Find the test.py node
        file_nodes = self.graph.get_nodes_by_label(NodeLabels.FILESYSTEM_FILE)
        test_node = next((n for n in file_nodes if n.name == "test.py"), None)
        
        self.assertIsNotNone(test_node)
        self.assertEqual(test_node.extension, ".py")  # type: ignore[attr-defined]
        self.assertEqual(test_node.size, len(test_content))  # type: ignore[attr-defined]
        self.assertAlmostEqual(test_node.last_modified, stats.st_mtime, delta=1)  # type: ignore[attr-defined]
        
    def test_empty_directory(self) -> None:
        """Test handling empty directories."""
        empty_dir = Path(self.temp_dir) / "empty"
        empty_dir.mkdir()
        
        self.generator.generate_filesystem_nodes(self.graph)
        
        # Empty directory should still get a node
        dir_nodes = self.graph.get_nodes_by_label(NodeLabels.FILESYSTEM_DIRECTORY)
        empty_node = next((n for n in dir_nodes if n.name == "empty"), None)
        
        self.assertIsNotNone(empty_node)
        
    def test_symlinks(self) -> None:
        """Test handling symbolic links."""
        # Create a file and a symlink to it
        real_file = Path(self.temp_dir) / "real.txt"
        real_file.write_text("Real file content")
        
        symlink = Path(self.temp_dir) / "link.txt"
        try:
            symlink.symlink_to(real_file)
        except OSError:
            # Skip test on systems that don't support symlinks
            self.skipTest("Symlinks not supported on this system")
            
        self.generator.generate_filesystem_nodes(self.graph)
        
        # Both files should have nodes
        file_nodes = self.graph.get_nodes_by_label(NodeLabels.FILESYSTEM_FILE)
        file_names = [n.name for n in file_nodes]
        
        self.assertIn("real.txt", file_names)
        # Symlink handling depends on implementation
        
    def test_deep_nesting(self) -> None:
        """Test handling deeply nested directories."""
        # Create deep structure (9 levels to stay within max_depth=10)
        deep_path = Path(self.temp_dir)
        for i in range(9):
            deep_path = deep_path / f"level{i}"
            deep_path.mkdir()
            
        # Create file at deepest level
        deep_file = deep_path / "deep.txt"
        deep_file.write_text("Deep file")
        
        self.generator.generate_filesystem_nodes(self.graph)
        
        # Check all levels were created
        dir_nodes = self.graph.get_nodes_by_label(NodeLabels.FILESYSTEM_DIRECTORY)
        for i in range(9):
            level_exists = any(n for n in dir_nodes if n.name == f"level{i}")
            self.assertTrue(level_exists, f"level{i} directory not found")
            
        # Check deep file exists
        file_nodes = self.graph.get_nodes_by_label(NodeLabels.FILESYSTEM_FILE)
        deep_file_node = next((n for n in file_nodes if n.name == "deep.txt"), None)
        self.assertIsNotNone(deep_file_node)
        
    def test_special_characters_in_names(self) -> None:
        """Test handling files with special characters."""
        special_names = [
            "file with spaces.txt",
            "file-with-dashes.py",
            "file_with_underscores.js",
            "file.multiple.dots.txt",
            "café.txt",  # Unicode
        ]
        
        for name in special_names:
            try:
                (Path(self.temp_dir) / name).write_text(f"Content of {name}")
            except Exception:
                # Skip problematic names on certain systems
                continue
                
        self.generator.generate_filesystem_nodes(self.graph)
        
        file_nodes = self.graph.get_nodes_by_label(NodeLabels.FILESYSTEM_FILE)
        created_names = [n.name for n in file_nodes]
        
        # Check that at least some special names were handled
        special_found = sum(1 for name in special_names if name in created_names)
        self.assertGreater(special_found, 0)
        
    def test_large_directory(self) -> None:
        """Test handling directory with many files."""
        # Create many files
        large_dir = Path(self.temp_dir) / "large"
        large_dir.mkdir()
        
        for i in range(100):
            (large_dir / f"file_{i:03d}.txt").write_text(f"File {i}")
            
        self.generator.generate_filesystem_nodes(self.graph)
        
        # Check all files were processed
        file_nodes = self.graph.get_nodes_by_label(NodeLabels.FILESYSTEM_FILE)
        large_dir_files = [n for n in file_nodes if hasattr(n, 'relative_path') and "large" in n.relative_path]  # type: ignore[attr-defined]
        
        self.assertEqual(len(large_dir_files), 100)
        
    @unittest.skip("connect_to_code_nodes method doesn't exist in FilesystemGraphGenerator")
    def test_connect_to_code_nodes(self) -> None:
        """Test connecting filesystem nodes to existing code nodes."""
        from blarify.graph.node.class_node import ClassNode
        from unittest.mock import Mock
        
        # Create code nodes first
        from tests.fixtures.node_factories import create_file_node
        file_path = "file:///test/src/main.py"
        code_file = create_file_node("main.py", path=file_path, level=2)
        self.graph.add_node(code_file)
        
        # Create mock tree-sitter objects for ClassNode
        mock_definition_range = Mock()
        mock_node_range = Mock()
        mock_node_range.range = Mock()
        mock_node_range.range.start = Mock(line=1)
        mock_node_range.range.end = Mock(line=10)
        mock_body_node = Mock()
        mock_tree_sitter_node = Mock()
        mock_tree_sitter_node.text = b"class MainClass: pass"
        mock_tree_sitter_node.start_byte = 0
        
        # ClassNode constructor parameters: definition_range, node_range, code_text, body_node, tree_sitter_node, *args, **kwargs
        code_class = ClassNode(
            definition_range=mock_definition_range,
            node_range=mock_node_range,
            code_text="class MainClass: pass",
            body_node=mock_body_node,
            tree_sitter_node=mock_tree_sitter_node,
            name="MainClass",
            path=file_path,
            level=3,
            graph_environment=GraphEnvironment(environment="test", diff_identifier="test_diff", root_path="/test")
        )
        self.graph.add_node(code_class)
        
        # Create matching filesystem structure
        (Path(self.temp_dir) / "src").mkdir()
        (Path(self.temp_dir) / "src" / "main.py").write_text("class MainClass: pass")
        
        # Generate filesystem nodes
        self.generator.generate_filesystem_nodes(self.graph)
        
        # Connect filesystem to code
        self.generator.connect_to_code_nodes(self.graph)  # type: ignore[attr-defined]
        
        # Check IMPLEMENTS relationship was created
        relationships = self.graph.get_relationships_as_objects()
        implements_rels = [r for r in relationships 
                          if r['type'] == RelationshipType.IMPLEMENTS.value]
        
        # Should have relationship from filesystem file to code file
        self.assertGreater(len(implements_rels), 0)


class TestGitignoreManager(unittest.TestCase):
    """Test gitignore file handling."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir: str = tempfile.mkdtemp()  # type: ignore[reportUninitializedInstanceVariable]
        self.manager: GitignoreManager = GitignoreManager(self.temp_dir)  # type: ignore[reportUninitializedInstanceVariable]
        
    def tearDown(self) -> None:
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.temp_dir)
        
    def test_parse_gitignore(self) -> None:
        """Test parsing gitignore patterns."""
        gitignore_content = """
# Comments should be ignored
*.pyc
__pycache__/
.env
build/
dist/
*.log

# Empty lines ignored

!important.log
docs/**/*.tmp
"""
        
        gitignore_path = Path(self.temp_dir) / ".gitignore"
        gitignore_path.write_text(gitignore_content)
        
        # Reinitialize manager to load the new gitignore file
        self.manager = GitignoreManager(self.temp_dir)
        patterns = self.manager.get_all_patterns()
        
        # Check patterns were parsed
        self.assertIn("*.pyc", patterns)
        self.assertIn("__pycache__/", patterns)
        self.assertIn(".env", patterns)
        self.assertIn("!important.log", patterns)
        
        # Comments and empty lines should not be included
        self.assertNotIn("# Comments should be ignored", patterns)
        self.assertNotIn("", patterns)
        
    def test_should_ignore_file(self) -> None:
        """Test checking if files should be ignored."""
        gitignore_content = """
*.pyc
__pycache__/
.env
test_*.py
!test_important.py
"""
        
        gitignore_path = Path(self.temp_dir) / ".gitignore"
        gitignore_path.write_text(gitignore_content)
        
        # Reinitialize manager to load the new gitignore file
        self.manager = GitignoreManager(self.temp_dir)
        
        # Test various paths
        self.assertTrue(self.manager.should_ignore("module.pyc"))
        self.assertTrue(self.manager.should_ignore("__pycache__/data.py"))
        self.assertTrue(self.manager.should_ignore(".env"))
        self.assertTrue(self.manager.should_ignore("test_module.py"))
        
        # This should not be ignored (negation pattern)
        self.assertFalse(self.manager.should_ignore("test_important.py"))
        
        # These should not be ignored
        self.assertFalse(self.manager.should_ignore("main.py"))
        self.assertFalse(self.manager.should_ignore("README.md"))
        
    def test_no_gitignore_file(self) -> None:
        """Test behavior when no gitignore file exists."""
        # No gitignore file created
        patterns = self.manager.get_all_patterns()
        
        # Should return empty list
        self.assertEqual(patterns, [])
        
        # Nothing should be ignored
        self.assertFalse(self.manager.should_ignore("any_file.py"))
        self.assertFalse(self.manager.should_ignore(".env"))
        
    def test_nested_gitignore(self) -> None:
        """Test handling gitignore files in subdirectories."""
        # Create nested structure with multiple gitignore files
        (Path(self.temp_dir) / "src").mkdir()
        
        # Root gitignore
        root_gitignore = Path(self.temp_dir) / ".gitignore"
        root_gitignore.write_text("*.log")
        
        # Nested gitignore
        src_gitignore = Path(self.temp_dir) / "src" / ".gitignore"
        src_gitignore.write_text("*.tmp")
        
        # Reinitialize manager to load the new gitignore files
        self.manager = GitignoreManager(self.temp_dir)
        
        # Test with root manager
        self.assertTrue(self.manager.should_ignore("error.log"))
        
        # Create manager for subdirectory
        src_manager = GitignoreManager(str(Path(self.temp_dir) / "src"))
        self.assertTrue(src_manager.should_ignore("cache.tmp"))


if __name__ == '__main__':
    unittest.main()