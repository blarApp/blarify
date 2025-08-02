import unittest
from blarify.graph.node.types.node_labels import NodeLabels
from blarify.graph.relationship.relationship_type import RelationshipType


class TestFilesystemNodeTypes(unittest.TestCase):
    """Test that filesystem node and relationship types exist."""
    
    def test_filesystem_node_types_exist(self) -> None:
        """Test that FILESYSTEM node types exist in NodeLabels."""
        # These types should exist
        self.assertEqual(NodeLabels.FILESYSTEM.value, "FILESYSTEM")
        self.assertEqual(NodeLabels.FILESYSTEM_FILE.value, "FILESYSTEM_FILE")
        self.assertEqual(NodeLabels.FILESYSTEM_DIRECTORY.value, "FILESYSTEM_DIRECTORY")
    
    def test_filesystem_relationship_types_exist(self) -> None:
        """Test that filesystem relationship types exist."""
        # These types should exist
        self.assertEqual(RelationshipType.IMPLEMENTS.value, "IMPLEMENTS")
        self.assertEqual(RelationshipType.DEPENDS_ON.value, "DEPENDS_ON")
        self.assertEqual(RelationshipType.FILESYSTEM_CONTAINS.value, "FILESYSTEM_CONTAINS")
        self.assertEqual(RelationshipType.REFERENCED_BY_DESCRIPTION.value, "REFERENCED_BY_DESCRIPTION")


if __name__ == '__main__':
    unittest.main()