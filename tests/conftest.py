"""
Shared pytest configuration and fixtures for Blarify tests.

This module provides common fixtures for integration testing,
particularly for GraphBuilder functionality with Neo4j containers.
"""
# pyright: reportMissingParameterType=false

import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator, Any

import pytest
import pytest_asyncio

from neo4j_container_manager.fixtures import (
    neo4j_manager,
    neo4j_instance,
    neo4j_query_helper,
)
from neo4j_container_manager.types import Neo4jContainerConfig, Environment, Neo4jContainerInstance
from tests.utils.graph_assertions import create_graph_assertions, GraphAssertions
from tests.utils.fixtures import docker_check  # noqa: F401
from blarify.mcp_server.config import MCPServerConfig
from blarify.mcp_server.server import BlarifyMCPServer


@pytest.fixture
def neo4j_config(request: Any) -> Neo4jContainerConfig:
    """
    Override the default neo4j_config fixture to include APOC plugin.

    Generates a unique test_id for each test instance to prevent container
    name conflicts when running tests in parallel.
    """
    import uuid

    # Get base test name
    base_name = getattr(getattr(request, "node", request), "name", request.__class__.__name__)
    # Clean up special characters
    clean_name = base_name.replace("[", "-").replace("]", "").replace(" ", "-")
    # Add a unique suffix to ensure no conflicts in parallel execution
    unique_suffix = uuid.uuid4().hex[:8]
    test_id = f"{clean_name}-{unique_suffix}"

    return Neo4jContainerConfig(
        environment=Environment.TEST,
        password="test-password",
        plugins=["apoc"],
        test_id=test_id,
    )


@pytest.fixture(scope="session")
def test_code_examples_path() -> Path:
    """
    Fixture that provides the path to test code examples directory.

    Returns:
        Path to the tests/code_examples directory
    """
    return Path(__file__).parent / "code_examples"


@pytest.fixture
def temp_project_dir() -> Generator[Path, None, None]:
    """
    Fixture that creates a temporary directory for test projects.

    This can be used when tests need to create temporary project structures
    without using the pre-existing code examples.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest_asyncio.fixture  # type: ignore[misc]
async def graph_assertions(neo4j_instance: Any) -> GraphAssertions:
    """
    Fixture that provides GraphAssertions helper for test validation.

    Args:
        neo4j_instance: Neo4j container instance from fixtures

    Returns:
        GraphAssertions instance configured for the test database
    """
    return create_graph_assertions(neo4j_instance)


@pytest_asyncio.fixture  # type: ignore[misc]
async def mcp_server_with_neo4j(neo4j_instance: Neo4jContainerInstance) -> AsyncGenerator[BlarifyMCPServer, None]:
    """
    Fixture that provides a BlarifyMCPServer configured with a Neo4j container.

    Args:
        neo4j_instance: Neo4j container instance from fixtures

    Yields:
        BlarifyMCPServer instance configured for the test database
    """
    # Create MCP server configuration from Neo4j instance
    config = MCPServerConfig(
        neo4j_uri=neo4j_instance.uri,
        neo4j_username="neo4j",
        neo4j_password="test-password",
        repository_id="test_repo",
        entity_id="test_entity",
        db_type="neo4j",
    )

    # Create and initialize the server
    server = BlarifyMCPServer(config)
    server._initialize_tools()

    yield server

    # Cleanup
    if server.db_manager:
        server.db_manager.close()


@pytest.fixture
async def cleanup_blarify_neo4j():
    """
    Fixture to clean up Blarify's auto-spawned Neo4j container and credentials.

    This is used for integration tests that test the auto-spawn functionality.
    It ensures a clean state before and after each test.
    """
    # Clean before test
    try:
        import docker
        from docker import errors

        client = docker.from_env()
        try:
            container = client.containers.get("blarify-neo4j-dev")
            container.stop()
            container.remove()
        except errors.NotFound:
            pass

        # Also remove the volume to ensure clean state
        try:
            volume = client.volumes.get("blarify-neo4j-dev-data")
            volume.remove()
        except errors.NotFound:
            pass
    except Exception:
        pass

    # Clean credentials before test
    creds_file = Path.home() / ".blarify" / "neo4j_credentials.json"
    if creds_file.exists():
        creds_file.unlink()

    yield

    # Clean after test
    try:
        import docker

        client = docker.from_env()
        try:
            container = client.containers.get("blarify-neo4j-dev")
            container.stop()
            container.remove()
        except docker.errors.NotFound:
            pass

        # Also remove the volume to ensure clean state
        try:
            volume = client.volumes.get("blarify-neo4j-dev-data")
            volume.remove()
        except docker.errors.NotFound:
            pass
    except Exception:
        pass

    # Clean credentials after test
    if creds_file.exists():
        creds_file.unlink()


@pytest.fixture
def mcp_server_config() -> MCPServerConfig:
    """
    Fixture that provides a default MCP server configuration for testing.

    Returns:
        MCPServerConfig instance with test defaults
    """
    return MCPServerConfig(
        neo4j_uri="bolt://localhost:7687",
        neo4j_username="test_user",
        neo4j_password="test_password",
        repository_id="test_repo",
        entity_id="test_entity",
        db_type="neo4j",
    )


# Re-export commonly used fixtures from neo4j_container_manager
# This makes them available to tests without explicit imports
__all__ = [
    "neo4j_manager",
    "neo4j_config",
    "neo4j_instance",
    "neo4j_query_helper",
    "test_code_examples_path",
    "temp_project_dir",
    "graph_assertions",
    "docker_check",
    "mcp_server_with_neo4j",
    "mcp_server_config",
]
