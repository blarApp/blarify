"""
Tests for KuzuManager database backend.
"""
import tempfile
import shutil
from pathlib import Path
import pytest

from cue.db_managers.kuzu_manager import KuzuManager


@pytest.fixture
def temp_kuzu_db():
    """Create a temporary Kuzu database directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def kuzu_manager(temp_kuzu_db):
    """Create a KuzuManager instance for testing."""
    manager = KuzuManager(
        repo_id="test_repo",
        entity_id="test_entity",
        db_path=temp_kuzu_db
    )
    yield manager
    manager.close()


def test_kuzu_manager_initialization(temp_kuzu_db):
    """Test that KuzuManager initializes correctly."""
    manager = KuzuManager(
        repo_id="test_repo",
        entity_id="test_entity",
        db_path=temp_kuzu_db
    )

    assert manager.repo_id == "test_repo"
    assert manager.entity_id == "test_entity"
    assert manager.db is not None
    assert manager.conn is not None

    manager.close()


def test_kuzu_manager_default_values(temp_kuzu_db):
    """Test that KuzuManager uses default values when not provided."""
    manager = KuzuManager(db_path=temp_kuzu_db)

    assert manager.repo_id == "default_repo"
    assert manager.entity_id == "default_user"

    manager.close()


def test_create_single_node(kuzu_manager):
    """Test creating a single node in Kuzu."""
    nodes = [
        {
            "type": "FILE",
            "attributes": {
                "node_id": "file_1",
                "name": "test.py",
                "path": "/test/test.py"
            }
        }
    ]

    kuzu_manager.create_nodes(nodes)

    # Query to verify node was created
    result = kuzu_manager.conn.execute(
        "MATCH (n:NODE {node_id: $node_id}) RETURN n",
        {"node_id": "file_1"}
    )

    assert result.has_next()
    row = result.get_next()
    assert row is not None


def test_create_multiple_nodes(kuzu_manager):
    """Test creating multiple nodes in Kuzu."""
    nodes = [
        {
            "type": "FILE",
            "attributes": {
                "node_id": "file_1",
                "name": "test1.py",
                "path": "/test/test1.py"
            }
        },
        {
            "type": "CLASS",
            "attributes": {
                "node_id": "class_1",
                "name": "TestClass",
                "path": "/test/test1.py"
            }
        },
        {
            "type": "FUNCTION",
            "attributes": {
                "node_id": "func_1",
                "name": "test_function",
                "path": "/test/test1.py"
            }
        }
    ]

    kuzu_manager.create_nodes(nodes)

    # Count total nodes
    result = kuzu_manager.conn.execute("MATCH (n:NODE) RETURN count(n) as count")
    row = result.get_next()
    count = row[0]

    assert count == 3


def test_create_edge(kuzu_manager):
    """Test creating an edge between two nodes."""
    # Create two nodes first
    nodes = [
        {
            "type": "FILE",
            "attributes": {
                "node_id": "file_1",
                "name": "test.py",
                "path": "/test/test.py"
            }
        },
        {
            "type": "CLASS",
            "attributes": {
                "node_id": "class_1",
                "name": "TestClass",
                "path": "/test/test.py"
            }
        }
    ]

    kuzu_manager.create_nodes(nodes)

    # Create edge
    edges = [
        {
            "sourceId": "file_1",
            "targetId": "class_1",
            "type": "CONTAINS",
            "scopeText": ""
        }
    ]

    kuzu_manager.create_edges(edges)

    # Verify edge was created
    result = kuzu_manager.conn.execute("""
        MATCH (a:NODE {node_id: $source})-[r:CONTAINS]->(b:NODE {node_id: $target})
        RETURN r
    """, {"source": "file_1", "target": "class_1"})

    assert result.has_next()


def test_create_multiple_edge_types(kuzu_manager):
    """Test creating different types of edges."""
    # Create nodes
    nodes = [
        {
            "type": "FUNCTION",
            "attributes": {
                "node_id": "func_1",
                "name": "caller",
                "path": "/test/test.py"
            }
        },
        {
            "type": "FUNCTION",
            "attributes": {
                "node_id": "func_2",
                "name": "callee",
                "path": "/test/test.py"
            }
        },
        {
            "type": "CLASS",
            "attributes": {
                "node_id": "class_1",
                "name": "TestClass",
                "path": "/test/test.py"
            }
        }
    ]

    kuzu_manager.create_nodes(nodes)

    # Create different edge types
    edges = [
        {
            "sourceId": "func_1",
            "targetId": "func_2",
            "type": "CALLS",
            "scopeText": "callee()"
        },
        {
            "sourceId": "func_1",
            "targetId": "class_1",
            "type": "REFERENCES",
            "scopeText": "TestClass"
        }
    ]

    kuzu_manager.create_edges(edges)

    # Verify CALLS edge
    result = kuzu_manager.conn.execute("""
        MATCH (a:NODE)-[r:CALLS]->(b:NODE)
        RETURN count(r) as count
    """)
    row = result.get_next()
    assert row[0] == 1

    # Verify REFERENCES edge
    result = kuzu_manager.conn.execute("""
        MATCH (a:NODE)-[r:REFERENCES]->(b:NODE)
        RETURN count(r) as count
    """)
    row = result.get_next()
    assert row[0] == 1


def test_save_graph(kuzu_manager):
    """Test the save_graph convenience method."""
    nodes = [
        {
            "type": "FILE",
            "attributes": {
                "node_id": "file_1",
                "name": "test.py",
                "path": "/test/test.py"
            }
        },
        {
            "type": "CLASS",
            "attributes": {
                "node_id": "class_1",
                "name": "TestClass",
                "path": "/test/test.py"
            }
        }
    ]

    edges = [
        {
            "sourceId": "file_1",
            "targetId": "class_1",
            "type": "CONTAINS",
            "scopeText": ""
        }
    ]

    kuzu_manager.save_graph(nodes, edges)

    # Verify nodes
    result = kuzu_manager.conn.execute("MATCH (n:NODE) RETURN count(n) as count")
    row = result.get_next()
    assert row[0] == 2

    # Verify edges
    result = kuzu_manager.conn.execute("MATCH ()-[r]->() RETURN count(r) as count")
    row = result.get_next()
    assert row[0] == 1


def test_detatch_delete_nodes_with_path(kuzu_manager):
    """Test deleting nodes by path."""
    # Create nodes with different paths
    nodes = [
        {
            "type": "FILE",
            "attributes": {
                "node_id": "file_1",
                "name": "test1.py",
                "path": "/test/test1.py"
            }
        },
        {
            "type": "FILE",
            "attributes": {
                "node_id": "file_2",
                "name": "test2.py",
                "path": "/test/test2.py"
            }
        },
        {
            "type": "CLASS",
            "attributes": {
                "node_id": "class_1",
                "name": "TestClass",
                "path": "/test/test1.py"
            }
        }
    ]

    kuzu_manager.create_nodes(nodes)

    # Create edge
    edges = [
        {
            "sourceId": "file_1",
            "targetId": "class_1",
            "type": "CONTAINS",
            "scopeText": ""
        }
    ]

    kuzu_manager.create_edges(edges)

    # Delete nodes with path /test/test1.py
    kuzu_manager.detatch_delete_nodes_with_path("/test/test1.py")

    # Verify only file_2 remains
    result = kuzu_manager.conn.execute("MATCH (n:NODE) RETURN count(n) as count")
    row = result.get_next()
    assert row[0] == 1

    # Verify it's file_2
    result = kuzu_manager.conn.execute("MATCH (n:NODE) RETURN n.node_id as id")
    row = result.get_next()
    assert row[0] == "file_2"


def test_node_merge_idempotency(kuzu_manager):
    """Test that creating the same node twice doesn't create duplicates."""
    node = {
        "type": "FILE",
        "attributes": {
            "node_id": "file_1",
            "name": "test.py",
            "path": "/test/test.py"
        }
    }

    # Create the same node twice
    kuzu_manager.create_nodes([node])
    kuzu_manager.create_nodes([node])

    # Should only have one node
    result = kuzu_manager.conn.execute("MATCH (n:NODE) RETURN count(n) as count")
    row = result.get_next()
    assert row[0] == 1


def test_repo_and_entity_namespacing(kuzu_manager):
    """Test that repo_id and entity_id are correctly set on nodes."""
    node = {
        "type": "FILE",
        "attributes": {
            "node_id": "file_1",
            "name": "test.py",
            "path": "/test/test.py"
        }
    }

    kuzu_manager.create_nodes([node])

    # Verify repo_id and entity_id
    result = kuzu_manager.conn.execute("""
        MATCH (n:NODE {node_id: $node_id})
        RETURN n.repoId as repoId, n.entityId as entityId
    """, {"node_id": "file_1"})

    row = result.get_next()
    assert row[0] == "test_repo"
    assert row[1] == "test_entity"


def test_edge_with_scope_text(kuzu_manager):
    """Test that scopeText is preserved in edges."""
    # Create nodes
    nodes = [
        {
            "type": "FUNCTION",
            "attributes": {
                "node_id": "func_1",
                "name": "caller",
                "path": "/test/test.py"
            }
        },
        {
            "type": "FUNCTION",
            "attributes": {
                "node_id": "func_2",
                "name": "callee",
                "path": "/test/test.py"
            }
        }
    ]

    kuzu_manager.create_nodes(nodes)

    # Create edge with scopeText
    edges = [
        {
            "sourceId": "func_1",
            "targetId": "func_2",
            "type": "CALLS",
            "scopeText": "callee(arg1, arg2)"
        }
    ]

    kuzu_manager.create_edges(edges)

    # Verify scopeText
    result = kuzu_manager.conn.execute("""
        MATCH (a:NODE)-[r:CALLS]->(b:NODE)
        RETURN r.scopeText as scopeText
    """)

    row = result.get_next()
    assert row[0] == "callee(arg1, arg2)"


def test_missing_node_attributes_graceful_handling(kuzu_manager):
    """Test that missing node attributes are handled gracefully."""
    # Node with minimal attributes
    node = {
        "type": "FILE",
        "attributes": {
            "node_id": "file_1"
            # Missing name and path
        }
    }

    # Should not raise exception
    kuzu_manager.create_nodes([node])

    # Verify node was created with empty strings for missing attributes
    result = kuzu_manager.conn.execute("""
        MATCH (n:NODE {node_id: $node_id})
        RETURN n.name as name, n.path as path
    """, {"node_id": "file_1"})

    row = result.get_next()
    assert row[0] == ""  # name
    assert row[1] == ""  # path
