"""
Tests for filesystem node functionality.
"""
import unittest
from unittest.mock import Mock
import tempfile
import time
from pathlib import Path

from blarify.graph.node.filesystem_file_node import FilesystemFileNode
from blarify.graph.node.filesystem_directory_node import FilesystemDirectoryNode
from blarify.graph.node.types.node_labels import NodeLabels
from blarify.graph.graph import Graph
from blarify.filesystem.filesystem_graph_generator import FilesystemGraphGenerator


class TestFilesystemFileNode(unittest.TestCase):
    """Test FilesystemFileNode functionality."""
    
    def test_filesystem_file_node_creation(self) -> None:
        """Test creating a filesystem file node."""
        node = FilesystemFileNode(
            path="file:///project/src/main.py",
            name="main.py",
            level=2,
            relative_path="src/main.py",
            size=2048,
            extension=".py",
            last_modified=1234567890.0
        )
        
        self.assertEqual(node.label, NodeLabels.FILESYSTEM_FILE)
        self.assertEqual(node.name, "main.py")
        self.assertEqual(node.relative_path, "src/main.py")
        self.assertEqual(node.size, 2048)
        self.assertEqual(node.extension, ".py")
        self.assertEqual(node.last_modified, 1234567890.0)
        
        # Test node_repr_for_identifier - it includes the type and relative path
        self.assertEqual(node.node_repr_for_identifier, "/FILESYSTEM_FILE[src/main.py]")
        
    def test_filesystem_file_node_as_object(self) -> None:
        """Test serializing filesystem file node."""
        node = FilesystemFileNode(
            path="file:///project/docs/README.md",
            name="README.md",
            level=1,
            relative_path="docs/README.md",
            size=1024,
            extension=".md",
            last_modified=1234567890.0
        )
        
        # Set graph environment to avoid AttributeError
        mock_env = Mock()
        mock_env.diff_identifier = "test"
        node.graph_environment = mock_env
        
        obj = node.as_object()
        
        self.assertEqual(obj['type'], 'FILESYSTEM_FILE')
        self.assertIn('relative_path', obj['attributes'])
        self.assertEqual(obj['attributes']['relative_path'], "docs/README.md")
        self.assertEqual(obj['attributes']['size'], 1024)
        self.assertEqual(obj['attributes']['extension'], ".md")
        
    def test_filesystem_file_node_in_graph(self) -> None:
        """Test adding filesystem file nodes to graph."""
        graph = Graph()
        
        node = FilesystemFileNode(
            path="file:///project/test.js",
            name="test.js",
            level=1,
            relative_path="test.js",
            size=512,
            extension=".js",
            last_modified=time.time()
        )
        
        graph.add_node(node)
        
        # Retrieve by ID
        retrieved = graph.get_node_by_id(node.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.extension, ".js")  # type: ignore[attr-defined]
        
        # Retrieve by label
        fs_nodes = graph.get_nodes_by_label(NodeLabels.FILESYSTEM_FILE)
        self.assertEqual(len(fs_nodes), 1)
        self.assertIn(node, fs_nodes)


class TestFilesystemDirectoryNode(unittest.TestCase):
    """Test FilesystemDirectoryNode functionality."""
    
    def test_filesystem_directory_node_creation(self) -> None:
        """Test creating a filesystem directory node."""
        node = FilesystemDirectoryNode(
            path="file:///project/src",
            name="src",
            level=1,
            relative_path="src"
        )
        
        self.assertEqual(node.label, NodeLabels.FILESYSTEM_DIRECTORY)
        self.assertEqual(node.name, "src")
        self.assertEqual(node.relative_path, "src")
        self.assertEqual(node.level, 1)
        
        # Test node_repr_for_identifier - it includes the type and relative path
        self.assertEqual(node.node_repr_for_identifier, "/FILESYSTEM_DIR[src]")
        
    def test_filesystem_directory_node_as_object(self) -> None:
        """Test serializing filesystem directory node."""
        node = FilesystemDirectoryNode(
            path="file:///project/tests/unit",
            name="unit",
            level=2,
            relative_path="tests/unit"
        )
        
        # Set graph environment
        mock_env = Mock()
        mock_env.diff_identifier = "test"
        node.graph_environment = mock_env
        
        obj = node.as_object()
        
        self.assertEqual(obj['type'], 'FILESYSTEM_DIRECTORY')
        self.assertEqual(obj['attributes']['relative_path'], "tests/unit")
        
    def test_filesystem_directory_node_in_graph(self) -> None:
        """Test adding filesystem directory nodes to graph."""
        graph = Graph()
        
        src_node = FilesystemDirectoryNode(
            path="file:///project/src",
            name="src",
            level=1,
            relative_path="src"
        )
        
        tests_node = FilesystemDirectoryNode(
            path="file:///project/tests",
            name="tests",
            level=1,
            relative_path="tests"
        )
        
        graph.add_node(src_node)
        graph.add_node(tests_node)
        
        # Retrieve by label
        dir_nodes = graph.get_nodes_by_label(NodeLabels.FILESYSTEM_DIRECTORY)
        self.assertEqual(len(dir_nodes), 2)
        self.assertIn(src_node, dir_nodes)
        self.assertIn(tests_node, dir_nodes)


class TestFilesystemGraphGenerator(unittest.TestCase):
    """Test filesystem graph generation."""
    
    def setUp(self) -> None:
        """Set up test directory."""
        self.test_dir: str = tempfile.mkdtemp()  # type: ignore[reportUninitializedInstanceVariable]
        
    def tearDown(self) -> None:
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.test_dir)
        
    def create_test_structure(self):
        """Create a test file structure."""
        # Create directories
        (Path(self.test_dir) / "src").mkdir()
        (Path(self.test_dir) / "tests").mkdir()
        
        # Create files
        (Path(self.test_dir) / "README.md").write_text("# Test Project")
        (Path(self.test_dir) / "src" / "main.py").write_text("def main(): pass")
        (Path(self.test_dir) / "src" / "utils.py").write_text("def helper(): pass")
        (Path(self.test_dir) / "tests" / "test_main.py").write_text("def test(): pass")
        
    def test_filesystem_graph_generation(self) -> None:
        """Test generating filesystem nodes."""
        self.create_test_structure()
        
        graph = Graph()
        generator = FilesystemGraphGenerator(root_path=self.test_dir)
        
        # Generate filesystem nodes
        generator.generate_filesystem_nodes(graph)
        
        # Check that nodes were created
        file_nodes = graph.get_nodes_by_label(NodeLabels.FILESYSTEM_FILE)
        dir_nodes = graph.get_nodes_by_label(NodeLabels.FILESYSTEM_DIRECTORY)
        
        self.assertGreater(len(file_nodes), 0)
        self.assertGreater(len(dir_nodes), 0)
        
        # Check for specific files
        file_names = [node.name for node in file_nodes]
        self.assertIn("README.md", file_names)
        self.assertIn("main.py", file_names)
        self.assertIn("utils.py", file_names)
        
        # Check for specific directories
        dir_names = [node.name for node in dir_nodes]
        self.assertIn("src", dir_names)
        self.assertIn("tests", dir_names)
        
    def test_file_properties(self) -> None:
        """Test that filesystem nodes have correct properties."""
        # Create a single file
        test_file = Path(self.test_dir) / "test.txt"
        test_content = "Hello, World!"
        test_file.write_text(test_content)
        
        # Get file stats
        stats = test_file.stat()
        
        # Generate graph
        graph = Graph()
        generator = FilesystemGraphGenerator(root_path=self.test_dir)
        generator.generate_filesystem_nodes(graph)
        
        # Find the test file node
        file_nodes = graph.get_nodes_by_label(NodeLabels.FILESYSTEM_FILE)
        test_node = next((n for n in file_nodes if n.name == "test.txt"), None)
        
        self.assertIsNotNone(test_node)
        self.assertEqual(test_node.extension, ".txt")  # type: ignore[attr-defined]
        self.assertEqual(test_node.size, len(test_content))  # type: ignore[attr-defined]
        # Allow some delta for timing
        self.assertAlmostEqual(test_node.last_modified, stats.st_mtime, delta=1)  # type: ignore[attr-defined,arg-type]


class TestFilesystemRelationships(unittest.TestCase):
    """Test filesystem relationships."""
    
    def test_filesystem_relationship_types(self) -> None:
        """Test that filesystem relationship types exist."""
        from blarify.graph.relationship.relationship_type import RelationshipType
        
        # Verify filesystem relationship types
        self.assertEqual(RelationshipType.FILESYSTEM_CONTAINS.value, "FILESYSTEM_CONTAINS")
        self.assertEqual(RelationshipType.IMPLEMENTS.value, "IMPLEMENTS")
        self.assertEqual(RelationshipType.DEPENDS_ON.value, "DEPENDS_ON")
        
    def test_implements_relationship(self) -> None:
        """Test IMPLEMENTS relationship between filesystem and code nodes."""
        # This tests that the relationship type exists and has correct value
        from blarify.graph.relationship.relationship_type import RelationshipType
        
        impl_rel = RelationshipType.IMPLEMENTS
        self.assertEqual(impl_rel.value, "IMPLEMENTS")
        
        # In a real scenario, IMPLEMENTS would connect:
        # FilesystemFileNode -> FileNode (code file)
        # to show that the filesystem file implements the code


if __name__ == '__main__':
    unittest.main()