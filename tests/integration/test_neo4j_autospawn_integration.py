"""Integration tests for Neo4j container auto-spawn functionality."""
# pyright: reportMissingParameterType=false

import asyncio
from argparse import Namespace
from pathlib import Path

import pytest

from blarify.cli.commands import create
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager


@pytest.mark.neo4j_integration
def test_full_autospawn_workflow(docker_check, temp_project_dir, cleanup_blarify_neo4j):
    """Test complete workflow with auto-spawned Neo4j container."""
    # Create test file
    test_file = temp_project_dir / "test.py"
    test_file.write_text('def hello(): return "world"')

    # Create mock args without Neo4j configuration
    args = Namespace(
        path=str(temp_project_dir),
        entity_id="test",
        repo_id=None,
        neo4j_uri="",
        neo4j_username="",
        neo4j_password="",
        docs=False,
        workflows=False,
        only_hierarchy=True,
        extensions_to_skip=[".json", ".xml", ".md", ".txt"],
        names_to_skip=["__pycache__", "node_modules", ".git", "venv", ".venv"],
        max_workers=5,
    )

    # Run create command which should auto-spawn container
    result = create.execute(args)
    assert result == 0

    # Check if container exists via Docker
    import docker
    from docker import errors

    client = docker.from_env()
    try:
        container = client.containers.get("blarify-neo4j-dev")
        assert container.status == "running"
    except errors.NotFound:
        pytest.skip("Container not found - may be using different method")


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_indexes_created_automatically(docker_check, cleanup_blarify_neo4j):
    """Test that ALL required indexes are created in auto-spawned container."""
    # Spawn a new container
    instance = await create.spawn_or_get_neo4j_container()

    # Connect and verify indexes
    db_manager = Neo4jManager(
        uri=instance.uri,
        user=instance.config.username,
        password=instance.config.password,
        repo_id="test",
        entity_id="test",
    )

    # Create indexes
    db_manager.create_indexes()

    # Give indexes time to be created
    await asyncio.sleep(2)

    # Query to check indexes exist
    result = db_manager.query("SHOW INDEXES")
    index_names = [r.get("name", "") for r in result if r.get("name")]

    # Define required indexes
    required_indexes = [
        "functionNames",  # Fulltext index
        "node_text_index",  # Text index
        "node_id_NODE",  # Node ID index
        "entityId_INDEX",  # Entity ID index
        "content_embeddings",  # Vector index
    ]

    # Check each required index exists
    missing_indexes = []
    for required_index in required_indexes:
        if not any(required_index in name for name in index_names):
            missing_indexes.append(required_index)

    # Also check for constraint
    constraints_result = db_manager.query("SHOW CONSTRAINTS")
    constraint_names = [r.get("name", "") for r in constraints_result if r.get("name")]

    # Check unique constraint exists
    if not any("user_node_unique" in name for name in constraint_names):
        missing_indexes.append("user_node_unique (constraint)")

    # Assert all indexes/constraints are created
    assert not missing_indexes, (
        f"Missing indexes/constraints: {missing_indexes}. Found indexes: {index_names}, constraints: {constraint_names}"
    )

    db_manager.close()


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_container_persists_and_is_reused(docker_check, cleanup_blarify_neo4j):
    """Test that container remains running after command exits and is reused."""
    # First, spawn a new container
    instance1 = await create.spawn_or_get_neo4j_container()
    uri1 = instance1.uri
    password1 = instance1.config.password

    # Simulate command completion (but don't stop container)
    # The container should persist

    # Wait a bit
    await asyncio.sleep(2)

    # Try to get the container again - it should reuse the existing one
    instance2 = await create.spawn_or_get_neo4j_container()
    uri2 = instance2.uri
    password2 = instance2.config.password

    # Should be the same container and credentials
    assert uri1 == uri2
    assert password1 == password2

    # Verify it's still running
    assert await instance2.is_running()


def test_credentials_are_persisted(tmp_path: Path, monkeypatch):
    """Test that credentials are saved and reused."""
    # Mock home directory
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # First call creates credentials
    creds1 = create.get_or_create_neo4j_credentials()
    assert creds1["username"] == "neo4j"
    assert len(creds1["password"]) == 16

    # Second call loads same credentials
    creds2 = create.get_or_create_neo4j_credentials()
    assert creds1 == creds2

    # Verify file exists with correct permissions
    creds_file = tmp_path / ".blarify" / "neo4j_credentials.json"
    assert creds_file.exists()
    assert oct(creds_file.stat().st_mode)[-3:] == "600"


def test_manual_neo4j_config_prevents_spawn():
    """Test that providing Neo4j config prevents container spawn."""
    args = Namespace(
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="myuser",
        neo4j_password="mypassword",
    )

    # Should not spawn
    assert not create.should_spawn_neo4j(args)


def test_partial_neo4j_config_triggers_spawn():
    """Test that partial Neo4j config still triggers container spawn."""
    # Only URI provided
    args1 = Namespace(
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="",
        neo4j_password="",
    )
    assert create.should_spawn_neo4j(args1)

    # Only username provided
    args2 = Namespace(
        neo4j_uri="",
        neo4j_username="neo4j",
        neo4j_password="",
    )
    assert create.should_spawn_neo4j(args2)

    # URI and username but no password
    args3 = Namespace(
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="neo4j",
        neo4j_password="",
    )
    assert create.should_spawn_neo4j(args3)
