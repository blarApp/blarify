"""
Integration tests for processing status management in Neo4j.

These tests verify that the database infrastructure correctly manages
node processing status for bottom-up processing order.
"""

import pytest
from pathlib import Path
from typing import Any

from blarify.repositories.graph_db_manager import Neo4jManager
from blarify.repositories.graph_db_manager.queries import (
    cleanup_processing_query,
    get_processable_nodes_query,
    initialize_processing_query,
    mark_processing_status_query,
)
from blarify.prebuilt.graph_builder import GraphBuilder
from neo4j_container_manager.types import Neo4jContainerInstance


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_initialize_processing_marks_all_nodes_pending(
    docker_check: Any,
    neo4j_instance: Neo4jContainerInstance,
    test_code_examples_path: Path,
) -> None:
    """Test that initializing marks all nodes as pending."""
    # Setup: Create graph with nodes
    builder = GraphBuilder(root_path=str(test_code_examples_path))
    graph = builder.build()

    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password",
        entity_id="test-entity",
        repo_id="test-repo",
    )
    db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

    # Execute: Initialize processing
    query_str = initialize_processing_query()
    db_manager.query(
        query_str,
        {
            "entity_id": "test-entity",
            "repo_id": "test-repo",
        },
    )

    # Verify: All nodes have pending status
    check_query = """
    MATCH (n:NODE {entityId: $entity_id, repoId: $repo_id})
    WHERE n.processing_status IS NOT NULL
    RETURN count(n) as total, 
           count(CASE WHEN n.processing_status = 'pending' THEN 1 END) as pending
    """
    check_result = db_manager.query(
        check_query,
        {
            "entity_id": "test-entity",
            "repo_id": "test-repo",
        },
    )

    assert check_result[0]["total"] > 0
    assert check_result[0]["total"] == check_result[0]["pending"]

    # Cleanup
    db_manager.close()


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_mark_node_processing_status_updates_correctly(
    docker_check: Any,
    neo4j_instance: Neo4jContainerInstance,
    test_code_examples_path: Path,
) -> None:
    """Test that marking node status updates the database correctly."""
    # Setup
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password",
        entity_id="test-entity",
        repo_id="test-repo",
    )

    # Create a test node
    create_query = """
    CREATE (n:FILE:NODE {path: $path, entityId: $entity_id, repoId: $repo_id})
    RETURN n
    """
    node_path = "/test/file.py"
    db_manager.query(
        create_query,
        {
            "path": node_path,
            "entity_id": "test-entity",
            "repo_id": "test-repo",
        },
    )

    # Initialize processing
    init_query = initialize_processing_query()
    db_manager.query(
        init_query,
        {
            "entity_id": "test-entity",
            "repo_id": "test-repo",
        },
    )

    # Execute: Mark as in_progress
    mark_query = mark_processing_status_query()
    db_manager.query(
        mark_query,
        {
            "node_path": node_path,
            "status": "in_progress",
            "entity_id": "test-entity",
            "repo_id": "test-repo",
        },
    )

    # Verify: Status changed
    verify_query = """
    MATCH (n:FILE {path: $path, entityId: $entity_id, repoId: $repo_id})
    RETURN n.processing_status as status
    """
    result = db_manager.query(
        verify_query,
        {
            "path": node_path,
            "entity_id": "test-entity",
            "repo_id": "test-repo",
        },
    )
    assert result[0]["status"] == "in_progress"

    # Execute: Mark as completed
    db_manager.query(
        mark_query,
        {
            "node_path": node_path,
            "status": "completed",
            "entity_id": "test-entity",
            "repo_id": "test-repo",
        },
    )

    # Verify: Status changed to completed
    result = db_manager.query(
        verify_query,
        {
            "path": node_path,
            "entity_id": "test-entity",
            "repo_id": "test-repo",
        },
    )
    assert result[0]["status"] == "completed"

    db_manager.close()


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_get_processable_nodes_returns_leaves_first(
    docker_check: Any, neo4j_instance: Neo4jContainerInstance
) -> None:
    """Test that processable nodes query returns leaf nodes first (bottom-up)."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password",
        entity_id="test-entity",
        repo_id="test-repo",
    )

    # Setup: Create hierarchy
    # parent -> child1 -> grandchild1
    #        -> child2
    setup_query = """
    CREATE (parent:FILE:NODE {path: '/parent.py', entityId: $entity_id, repoId: $repo_id})
    CREATE (child1:FILE:NODE {path: '/child1.py', entityId: $entity_id, repoId: $repo_id})
    CREATE (child2:FILE:NODE {path: '/child2.py', entityId: $entity_id, repoId: $repo_id})
    CREATE (grandchild:FILE:NODE {path: '/grandchild.py', entityId: $entity_id, repoId: $repo_id})
    CREATE (parent)-[:CONTAINS]->(child1)
    CREATE (parent)-[:CONTAINS]->(child2)
    CREATE (child1)-[:CONTAINS]->(grandchild)
    """
    db_manager.query(
        setup_query,
        {"entity_id": "test-entity", "repo_id": "test-repo"},
    )

    # Initialize processing
    init_query = initialize_processing_query()
    db_manager.query(
        init_query,
        {
            "entity_id": "test-entity",
            "repo_id": "test-repo",
        },
    )

    # Execute: Get first batch of processable nodes
    get_query = get_processable_nodes_query()
    batch1 = db_manager.query(
        get_query,
        {
            "batch_size": 10,
            "entity_id": "test-entity",
            "repo_id": "test-repo",
        },
    )

    # Verify: Should get leaf nodes (grandchild and child2)
    paths = [node["path"] for node in batch1]
    assert "/grandchild.py" in paths
    assert "/child2.py" in paths
    assert "/parent.py" not in paths  # Has unprocessed children
    assert "/child1.py" not in paths  # Has unprocessed children

    # Mark leaves as completed
    mark_query = mark_processing_status_query()
    for path in ["/grandchild.py", "/child2.py"]:
        db_manager.query(
            mark_query,
            {
                "node_path": path,
                "status": "completed",
                "entity_id": "test-entity",
                "repo_id": "test-repo",
            },
        )

    # Execute: Get next batch
    batch2 = db_manager.query(
        get_query,
        {
            "batch_size": 10,
            "entity_id": "test-entity",
            "repo_id": "test-repo",
        },
    )

    # Verify: Now child1 is processable
    paths = [node["path"] for node in batch2]
    assert "/child1.py" in paths
    assert "/parent.py" not in paths  # child1 not complete yet

    db_manager.close()


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_cleanup_removes_all_processing_data(docker_check: Any, neo4j_instance: Neo4jContainerInstance) -> None:
    """Test that cleanup removes all processing data."""
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password",
        entity_id="test-entity",
        repo_id="test-repo",
    )

    # Setup: Create nodes and initialize processing
    create_query = """
    CREATE (n1:FILE:NODE {path: '/file1.py', entityId: $entity_id, repoId: $repo_id})
    CREATE (n2:FILE:NODE {path: '/file2.py', entityId: $entity_id, repoId: $repo_id})
    """
    db_manager.query(
        create_query,
        {"entity_id": "test-entity", "repo_id": "test-repo"},
    )

    # Initialize and mark some nodes
    init_query = initialize_processing_query()
    db_manager.query(
        init_query,
        {
            "entity_id": "test-entity",
            "repo_id": "test-repo",
        },
    )

    mark_query = mark_processing_status_query()
    db_manager.query(
        mark_query,
        {
            "node_path": "/file1.py",
            "status": "completed",
            "entity_id": "test-entity",
            "repo_id": "test-repo",
        },
    )

    # Verify processing data exists
    check_query = """
    MATCH (n:NODE {entityId: $entity_id, repoId: $repo_id})
    WHERE n.processing_status IS NOT NULL
    RETURN count(n) as count
    """
    result = db_manager.query(
        check_query,
        {"entity_id": "test-entity", "repo_id": "test-repo"},
    )
    assert result[0]["count"] > 0

    # Execute: Cleanup processing
    cleanup_query = cleanup_processing_query()
    db_manager.query(
        cleanup_query,
        {
            "entity_id": "test-entity",
            "repo_id": "test-repo",
        },
    )

    # Verify: Processing data removed
    result = db_manager.query(
        check_query,
        {"entity_id": "test-entity", "repo_id": "test-repo"},
    )
    assert result[0]["count"] == 0

    # Verify: Nodes still exist
    node_check = """
    MATCH (n:FILE {entityId: $entity_id, repoId: $repo_id})
    RETURN count(n) as count
    """
    result = db_manager.query(
        node_check,
        {"entity_id": "test-entity", "repo_id": "test-repo"},
    )
    assert result[0]["count"] == 2

    db_manager.close()
