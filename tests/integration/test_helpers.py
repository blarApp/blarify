"""Helper functions for integration tests."""

from typing import List, Dict, Any, Optional
from blarify.graph.node import FileNode, ClassNode, FunctionNode
from blarify.graph.graph_environment import GraphEnvironment
from blarify.code_references.types import Reference, Range, Point
from blarify.db_managers.db_manager import AbstractDbManager


class MockTreeSitterNode:
    """Mock TreeSitter node for testing purposes."""

    def __init__(self, start_byte: int = 0, end_byte: int = 100, text: bytes = b"mock content"):
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.text = text
        self.named_children = []  # Required for stats calculation
        self.type = "mock_node"

    def child_by_field_name(self, name: str):
        """Mock implementation of child_by_field_name."""
        return None


def create_test_reference(start_line: int = 0, end_line: int = 10, path: str = "/test.py") -> Reference:
    """Create a test Reference object."""
    return Reference(
        range=Range(start=Point(line=start_line, character=0), end=Point(line=end_line, character=0)),
        uri=f"file://{path}",
    )


def create_test_file_node(
    path: str,
    name: str,
    content: str = "test content",
    entity_id: str = "test-entity",
    repo_id: str = "test-repo",
    graph_environment: Optional[GraphEnvironment] = None,
) -> FileNode:
    """Create a test FileNode with minimal required fields."""
    if graph_environment is None:
        graph_environment = GraphEnvironment(environment="test", diff_identifier="test-diff", root_path="/")

    mock_tree_sitter_node = MockTreeSitterNode(text=content.encode())
    reference = create_test_reference(path=path)

    node = FileNode(
        path=f"file://{path}",
        name=name,
        level=0,
        node_range=reference,
        definition_range=reference,
        code_text=content,
        parent=None,
        body_node=mock_tree_sitter_node,
        tree_sitter_node=mock_tree_sitter_node,
        graph_environment=graph_environment,
    )

    # Add the entity_id and repo_id as extra attributes
    node.add_extra_attribute("entityId", entity_id)
    node.add_extra_attribute("repoId", repo_id)

    return node


def create_test_class_node(
    path: str,
    name: str,
    content: str = "class content",
    parent: Optional[FileNode] = None,
    entity_id: str = "test-entity",
    repo_id: str = "test-repo",
    graph_environment: Optional[GraphEnvironment] = None,
) -> ClassNode:
    """Create a test ClassNode with minimal required fields."""
    if graph_environment is None:
        graph_environment = GraphEnvironment(environment="test", diff_identifier="test-diff", root_path="/")

    mock_tree_sitter_node = MockTreeSitterNode(text=content.encode())
    # Extract the file path from path like "/file.py:ClassA" -> "/file.py"
    file_path = path.split(":")[0] if ":" in path else path
    reference = create_test_reference(path=file_path)

    node = ClassNode(
        path=f"file://{path}",
        name=name,
        level=1,
        node_range=reference,
        definition_range=reference,
        code_text=content,
        parent=parent,
        body_node=mock_tree_sitter_node,
        tree_sitter_node=mock_tree_sitter_node,
        graph_environment=graph_environment,
    )

    # Add the entity_id and repo_id as extra attributes
    node.add_extra_attribute("entityId", entity_id)
    node.add_extra_attribute("repoId", repo_id)

    return node


def create_test_function_node(
    path: str,
    name: str,
    content: str = "function content",
    parent: Optional[FileNode] = None,
    entity_id: str = "test-entity",
    repo_id: str = "test-repo",
    graph_environment: Optional[GraphEnvironment] = None,
) -> FunctionNode:
    """Create a test FunctionNode with minimal required fields."""
    if graph_environment is None:
        graph_environment = GraphEnvironment(environment="test", diff_identifier="test-diff", root_path="/")

    mock_tree_sitter_node = MockTreeSitterNode(text=content.encode())
    # Extract the file path from path like "/file.py:func1" -> "/file.py"
    file_path = path.split(":")[0] if ":" in path else path
    reference = create_test_reference(path=file_path)

    node = FunctionNode(
        path=f"file://{path}",
        name=name,
        level=1 if parent else 0,
        node_range=reference,
        definition_range=reference,
        code_text=content,
        parent=parent,
        body_node=mock_tree_sitter_node,
        tree_sitter_node=mock_tree_sitter_node,
        graph_environment=graph_environment,
    )

    # Add the entity_id and repo_id as extra attributes
    node.add_extra_attribute("entityId", entity_id)
    node.add_extra_attribute("repoId", repo_id)

    return node


def insert_nodes_and_edges(db_manager: AbstractDbManager, nodes: List[Any], edges: List[Dict[str, Any]] = None) -> None:
    """Insert nodes and optionally edges into the database using the proper methods."""
    # Convert nodes to their object representation
    node_objects = [node.as_object() for node in nodes]

    # Use the database manager's create_nodes method
    db_manager.create_nodes(node_objects)

    # If edges are provided, create them
    if edges:
        db_manager.create_edges(edges)


def create_contains_edge(parent_node_id: str, child_node_id: str) -> Dict[str, Any]:
    """Create a CONTAINS relationship between two nodes."""
    return {"type": "CONTAINS", "sourceId": parent_node_id, "targetId": child_node_id}


def create_calls_edge(caller_node_id: str, callee_node_id: str) -> Dict[str, Any]:
    """Create a CALLS relationship between two function nodes."""
    return {"type": "CALLS", "sourceId": caller_node_id, "targetId": callee_node_id}
