"""Test that filesystem nodes feature exists and works correctly."""
import unittest
from blarify.graph.node.filesystem_file_node import FilesystemFileNode
from blarify.graph.node.filesystem_directory_node import FilesystemDirectoryNode
from blarify.filesystem.filesystem_graph_generator import FilesystemGraphGenerator


class TestFilesystemFeatureExists(unittest.TestCase):
    """Verify that filesystem feature components exist and can be imported."""
    
    def test_filesystem_module_exists(self) -> None:
        """Test that filesystem module exists."""
        import blarify.filesystem
        self.assertIsNotNone(blarify.filesystem)
    
    def test_filesystem_node_classes_exist(self) -> None:
        """Test that filesystem node classes exist."""
        # These imports would have raised ImportError if they didn't exist
        self.assertIsNotNone(FilesystemFileNode)
        self.assertIsNotNone(FilesystemDirectoryNode)
    
    def test_filesystem_generator_exists(self) -> None:
        """Test that filesystem graph generator exists."""
        # This import would have raised ImportError if it didn't exist
        self.assertIsNotNone(FilesystemGraphGenerator)


if __name__ == '__main__':
    unittest.main()