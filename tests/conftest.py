"""
Shared pytest configuration and fixtures for Blarify tests.

This module provides common fixtures for integration testing,
particularly for GraphBuilder functionality with Neo4j containers.
"""
# pyright: reportMissingParameterType=false
# pyright: reportPrivateUsage=false

import tempfile
import uuid
from pathlib import Path
from typing import AsyncGenerator, Generator, Any, Dict

import pytest
import pytest_asyncio
from neo4j import GraphDatabase

from neo4j_container_manager.fixtures import (
    neo4j_manager,
    neo4j_query_helper,
)
from neo4j_container_manager.types import Neo4jContainerConfig, Environment, Neo4jContainerInstance
from neo4j_container_manager.container_manager import Neo4jContainerManager
from tests.utils.graph_assertions import create_graph_assertions, GraphAssertions
from tests.utils.fixtures import docker_check  # noqa: F401
from blarify.mcp_server.config import MCPServerConfig
from blarify.mcp_server.server import BlarifyMCPServer


@pytest.fixture(scope="module")
def module_neo4j_config(request: Any) -> Neo4jContainerConfig:
    """
    Create a module-scoped Neo4j configuration.

    This configuration is shared by all tests in the same module,
    reducing container creation overhead.
    """
    # Generate unique name based on module
    module_name = getattr(request.module, "__name__", "unknown")
    clean_name = module_name.replace(".", "_").replace("/", "_")

    return Neo4jContainerConfig(
        environment=Environment.TEST,
        password="test-password",
        plugins=["apoc"],
        test_id=f"module_{clean_name}",
        # Optimize for test performance
        memory="512M",
        startup_timeout=30,
        health_check_interval=1,
    )


@pytest_asyncio.fixture(scope="module")  # type: ignore[misc]
async def module_neo4j_container(
    module_neo4j_config: Neo4jContainerConfig,
    neo4j_manager: Neo4jContainerManager,
) -> AsyncGenerator[Neo4jContainerInstance, None]:
    """
    Module-scoped Neo4j container fixture (async).

    Creates one container per test module and shares it across all tests
    in that module. This significantly reduces test execution time.
    Uses pytest-asyncio for proper event loop management.
    """
    module_id = module_neo4j_config.test_id
    assert module_id is not None, "test_id should not be None"

    # Create new container for this module (don't reuse across event loops)
    instance = await neo4j_manager.start(module_neo4j_config)

    # Wait for container to be fully ready
    await neo4j_manager.wait_for_container_healthy(instance.container_id, timeout=30)

    try:
        yield instance
    finally:
        # Close any open drivers before cleanup
        if hasattr(instance, "_driver") and instance._driver:
            try:
                await instance._driver.close()
            except (RuntimeError, Exception) as e:
                # Event loop might be closed, ignore errors
                print(f"Warning: Could not close driver properly: {e}")
            instance._driver = None
        
        # Cleanup container when module completes
        try:
            # Use new event loop if current one is closed
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(neo4j_manager.stop(instance.container_id))
            else:
                await neo4j_manager.stop(instance.container_id)
        except (RuntimeError, Exception) as e:
            print(f"Warning: Could not stop container properly: {e}")


@pytest.fixture
def test_data_isolation(
    module_neo4j_container: Neo4jContainerInstance,
) -> Generator[Dict[str, Any], None, None]:
    """
    Provide isolated entity_id and repo_id for each test.

    This fixture ensures data isolation between tests while reusing
    the same Neo4j container. Cleanup is performed automatically.
    Each test gets a fresh container instance with no pre-existing driver connections.
    """
    # Generate unique IDs for this test
    test_uuid = uuid.uuid4().hex[:8]

    # Create a fresh container instance for this test to avoid event loop conflicts
    # This ensures each test gets its own Neo4j driver instance in the correct event loop
    fresh_container = Neo4jContainerInstance(
        config=module_neo4j_container.config,
        container_id=module_neo4j_container.container_id,
        ports=module_neo4j_container.ports,
        volume=module_neo4j_container.volume,
        status=module_neo4j_container.status,
        started_at=module_neo4j_container.started_at,
    )
    # Critical: Ensure no driver is pre-attached to avoid event loop conflicts
    fresh_container._driver = None

    isolation_data = {
        "entity_id": f"test_entity_{test_uuid}",
        "repo_id": f"test_repo_{test_uuid}",
        "container": fresh_container,
        "uri": fresh_container.uri,
        "password": fresh_container.config.password,
    }

    # Provide isolation data to test
    yield isolation_data

    # Cleanup test data after test completes
    _cleanup_test_data(isolation_data)

    # Close any driver that may have been created during the test
    if hasattr(fresh_container, "_driver") and fresh_container._driver:
        # Note: We can't await here since this is a sync fixture
        # The async driver cleanup will happen when the driver goes out of scope
        try:
            fresh_container._driver.close()
        except Exception:
            pass  # Best effort cleanup
        fresh_container._driver = None


def _cleanup_test_data(isolation_data: Dict[str, Any]) -> None:
    """
    Clean up all data for a specific entity_id and repo_id.

    This ensures complete data isolation between tests.
    """
    driver = GraphDatabase.driver(isolation_data["uri"], auth=("neo4j", isolation_data["password"]))

    try:
        with driver.session() as session:
            # Delete all nodes for this test's entity and repo
            session.run(
                """
                MATCH (n)
                WHERE (n.entityId = $entityId AND n.repoId = $repoId)
                   OR (n.entity_id = $entityId AND n.repo_id = $repoId)
                DETACH DELETE n
                RETURN count(n) as deleted_count
                """,
                entityId=isolation_data["entity_id"],
                repoId=isolation_data["repo_id"],
                entity_id=isolation_data["entity_id"],
                repo_id=isolation_data["repo_id"],
            )

            # Also clean up any orphaned relationships (defensive)
            session.run(
                """
                MATCH ()-[r]->()
                WHERE (r.entityId = $entityId AND r.repoId = $repoId)
                   OR (r.entity_id = $entityId AND r.repo_id = $repoId)
                DELETE r
                """,
                entityId=isolation_data["entity_id"],
                repoId=isolation_data["repo_id"],
                entity_id=isolation_data["entity_id"],
                repo_id=isolation_data["repo_id"],
            )
    finally:
        driver.close()


# Provide neo4j_instance fixture that uses module-scoped container
@pytest.fixture
def neo4j_instance(
    test_data_isolation: Dict[str, Any],
) -> Neo4jContainerInstance:
    """
    Provides Neo4j instance using module-scoped container with data isolation.

    All tests should use this fixture instead of creating per-test containers.
    """
    return test_data_isolation["container"]


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
async def graph_assertions(
    test_data_isolation: Dict[str, Any],
) -> GraphAssertions:
    """
    Fixture that provides GraphAssertions helper for test validation.

    Args:
        test_data_isolation: Test isolation data with container and IDs

    Returns:
        GraphAssertions instance configured for the test database
    """
    return create_graph_assertions(
        test_data_isolation["container"],
        entity_id=test_data_isolation["entity_id"],
        repo_id=test_data_isolation["repo_id"],
    )


@pytest_asyncio.fixture  # type: ignore[misc]
async def mcp_server_with_neo4j(
    test_data_isolation: Dict[str, Any],
    temp_project_dir: Path,
) -> AsyncGenerator[BlarifyMCPServer, None]:
    """
    Fixture that provides a BlarifyMCPServer configured with isolated test data.

    Args:
        test_data_isolation: Test isolation data with container and IDs
        temp_project_dir: Temporary directory for test repository

    Yields:
        BlarifyMCPServer instance configured for the test database
    """
    # Create MCP server configuration with isolated IDs
    config = MCPServerConfig(
        neo4j_uri=test_data_isolation["uri"],
        neo4j_username="neo4j",
        neo4j_password=test_data_isolation["password"],
        entity_id=test_data_isolation["entity_id"],
        root_path=str(temp_project_dir),
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
        # Only clean up development containers, not MCP containers
        try:
            container = client.containers.get("blarify-neo4j-dev")
            container.stop()
            container.remove()
        except errors.NotFound:
            pass

        # Also remove the development volume to ensure clean state
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
        from docker import errors

        client = docker.from_env()
        # Only clean up development containers, not MCP containers
        try:
            container = client.containers.get("blarify-neo4j-dev")
            container.stop()
            container.remove()
        except errors.NotFound:
            pass

        # Also remove the development volume to ensure clean state
        try:
            volume = client.volumes.get("blarify-neo4j-dev-data")
            volume.remove()
        except errors.NotFound:
            pass
    except Exception:
        pass

    # Clean credentials after test
    if creds_file.exists():
        creds_file.unlink()


@pytest.fixture
def mcp_server_config(
    test_data_isolation: Dict[str, Any],
    temp_project_dir: Path,
) -> MCPServerConfig:
    """
    Fixture that provides a default MCP server configuration for testing.

    Args:
        test_data_isolation: Test isolation data with container and IDs
        temp_project_dir: Temporary directory for test repository

    Returns:
        MCPServerConfig instance with test defaults
    """
    return MCPServerConfig(
        neo4j_uri=test_data_isolation["uri"],
        neo4j_username="neo4j",
        neo4j_password=test_data_isolation["password"],
        entity_id=test_data_isolation["entity_id"],
        root_path=str(temp_project_dir),
        db_type="neo4j",
    )


# Re-export commonly used fixtures
# All tests should use module-scoped fixtures for performance
__all__ = [
    "neo4j_manager",
    "neo4j_instance",  # Uses module-scoped container
    "neo4j_query_helper",
    "module_neo4j_config",
    "module_neo4j_container",
    "test_data_isolation",  # Primary fixture for tests
    "test_code_examples_path",
    "temp_project_dir",
    "graph_assertions",
    "docker_check",
    "mcp_server_with_neo4j",
    "mcp_server_config",
]
