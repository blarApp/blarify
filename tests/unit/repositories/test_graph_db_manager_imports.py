"""Test backward compatibility and new imports for graph_db_manager reorganization."""


def test_abstract_db_manager_import_from_new_location():
    """Test AbstractDbManager imports from new location."""
    from blarify.repositories.graph_db_manager import AbstractDbManager

    assert AbstractDbManager is not None


def test_neo4j_manager_import_from_new_location():
    """Test Neo4jManager imports from new location."""
    from blarify.repositories.graph_db_manager import Neo4jManager

    assert Neo4jManager is not None


def test_falkordb_manager_import_from_new_location():
    """Test FalkorDBManager imports from new location."""
    from blarify.repositories.graph_db_manager import FalkorDBManager

    assert FalkorDBManager is not None


def test_backward_compatibility_abstract_db_manager():
    """Test old imports still work for AbstractDbManager."""
    from blarify.repositories.graph_db_manager import AbstractDbManager
    from blarify.repositories.graph_db_manager import AbstractDbManager as NewAbstractDbManager

    # Should be the same class
    assert AbstractDbManager is NewAbstractDbManager


def test_backward_compatibility_neo4j_manager():
    """Test old imports still work for Neo4jManager."""
    from blarify.repositories.graph_db_manager import Neo4jManager
    from blarify.repositories.graph_db_manager import Neo4jManager as NewNeo4jManager

    # Should be the same class
    assert Neo4jManager is NewNeo4jManager


def test_backward_compatibility_falkordb_manager():
    """Test old imports still work for FalkorDBManager."""
    from blarify.repositories.graph_db_manager import FalkorDBManager
    from blarify.repositories.graph_db_manager import FalkorDBManager as NewFalkorDBManager

    # Should be the same class
    assert FalkorDBManager is NewFalkorDBManager


def test_db_manager_module_exports():
    """Test that the new module exports the expected classes."""
    from blarify.repositories import graph_db_manager

    assert hasattr(graph_db_manager, "AbstractDbManager")
    assert hasattr(graph_db_manager, "Neo4jManager")
    assert hasattr(graph_db_manager, "FalkorDBManager")
