"""
Shared pytest configuration and fixtures for Blarify tests.

This module provides common fixtures for integration testing,
particularly for GraphBuilder functionality with Neo4j containers.
"""

import tempfile
from pathlib import Path
from typing import Generator, Any

import pytest
import pytest_asyncio

from neo4j_container_manager.fixtures import (
    event_loop,
    neo4j_manager,
    neo4j_instance,
    neo4j_query_helper,
)
from neo4j_container_manager.types import Neo4jContainerConfig, Environment, Neo4jContainerInstance
from tests.utils.graph_assertions import create_graph_assertions, GraphAssertions
from tests.utils.fixtures import docker_check  # noqa: F401
from neo4j_container_manager.manager import Neo4jContainerManager
from typing import AsyncGenerator


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
    clean_name = base_name.replace('[', '-').replace(']', '').replace(' ', '-')
    # Add a unique suffix to ensure no conflicts in parallel execution
    unique_suffix = uuid.uuid4().hex[:8]
    test_id = f"{clean_name}-{unique_suffix}"
    
    return Neo4jContainerConfig(
        environment=Environment.TEST,
        password="test-password",
        plugins=["apoc"],
        test_id=test_id,
    )


@pytest_asyncio.fixture(scope="module")
async def neo4j_suite_instance(
    neo4j_manager: Neo4jContainerManager,
    request: Any
) -> AsyncGenerator[Neo4jContainerInstance, None]:
    """
    Module-scoped fixture for Neo4j container - one per test file.
    
    Uses module name as base for container identification and provides
    isolated database instance for all tests in the module.
    """
    import uuid
    from pathlib import Path
    
    # Get test module name for container ID
    module_path = Path(request.fspath)
    module_name = module_path.stem  # e.g., "test_graphbuilder_basic"
    
    # Create unique container ID for this test suite
    suite_id = f"{module_name}-{uuid.uuid4().hex[:8]}"
    
    config = Neo4jContainerConfig(
        environment=Environment.TEST,
        password="test-password",
        plugins=["apoc"],
        memory="1G",  # Increased for longer-running container
        test_id=suite_id,
        startup_timeout=90,  # Allow more time for APOC plugin
    )
    
    instance = await neo4j_manager.start_for_test(config)
    try:
        yield instance
    finally:
        await instance.stop()


@pytest_asyncio.fixture
async def neo4j_test_instance(
    neo4j_suite_instance: Neo4jContainerInstance,
    request: Any
) -> AsyncGenerator[Neo4jContainerInstance, None]:
    """
    Function-scoped fixture that provides isolated data space within shared container.
    
    Creates unique repo_id and entity_id for each test function and cleans up
    test-specific data after test completion.
    """
    import uuid
    
    # Generate unique identifiers for this specific test
    test_name = request.node.name
    test_uuid = uuid.uuid4().hex[:8]
    
    # Use test suite name as entity_id and test name as repo_id
    # This creates predictable but unique isolation
    entity_id = request.node.module.__name__.split('.')[-1]  # e.g., "test_graphbuilder_basic"
    repo_id = f"{test_name}-{test_uuid}"
    
    # Store isolation IDs on the instance for use by GraphAssertions
    neo4j_suite_instance.test_entity_id = entity_id
    neo4j_suite_instance.test_repo_id = repo_id
    
    try:
        yield neo4j_suite_instance
    finally:
        # Clean up test-specific data
        await cleanup_test_data(neo4j_suite_instance, entity_id, repo_id)


async def cleanup_test_data(
    instance: Neo4jContainerInstance, 
    entity_id: str, 
    repo_id: str
) -> None:
    """Clean up all nodes and relationships for specific entity_id/repo_id."""
    cleanup_query = """
    MATCH (n {entityId: $entity_id, repoId: $repo_id})
    DETACH DELETE n
    """
    try:
        async with instance.get_driver() as driver:
            async with driver.session() as session:
                await session.run(cleanup_query, entity_id=entity_id, repo_id=repo_id)
    except Exception as e:
        # Log but don't fail - cleanup is best effort
        print(f"Cleanup warning for {entity_id}/{repo_id}: {e}")


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


@pytest.fixture
def neo4j_db_manager(neo4j_test_instance: Neo4jContainerInstance) -> Any:
    """Create Neo4jManager configured with test isolation IDs."""
    from blarify.db_managers.neo4j_manager import Neo4jManager
    
    return Neo4jManager(
        uri=neo4j_test_instance.uri,
        user="neo4j",
        password="test-password",
        repo_id=getattr(neo4j_test_instance, 'test_repo_id', 'default_repo'),
        entity_id=getattr(neo4j_test_instance, 'test_entity_id', 'default_entity'),
    )


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


# Backward compatibility alias during migration
@pytest_asyncio.fixture
async def neo4j_instance_optimized(neo4j_test_instance: Neo4jContainerInstance) -> Neo4jContainerInstance:
    """Backward compatibility fixture - delegates to optimized implementation."""
    return neo4j_test_instance


# Re-export commonly used fixtures from neo4j_container_manager
# This makes them available to tests without explicit imports
__all__ = [
    "event_loop",
    "neo4j_manager", 
    "neo4j_config",
    "neo4j_instance",
    "neo4j_instance_optimized",
    "neo4j_suite_instance",
    "neo4j_test_instance",
    "neo4j_db_manager",
    "neo4j_query_helper",
    "test_code_examples_path",
    "temp_project_dir",
    "graph_assertions",
    "docker_check",
]