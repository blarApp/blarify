"""
Neo4j Container Management

A robust Neo4j container management system focused on testing that provides:
- Automatic test container lifecycle management
- Dynamic port allocation to avoid conflicts
- Clean test isolation with separate containers/data
- Test data setup/teardown functionality
- Transparent operation - developers never need to manually manage containers

Usage:
    import pytest
    from neo4j_container_manager import Neo4jContainerManager, Neo4jContainerConfig

    @pytest.fixture
    async def neo4j_instance():
        manager = Neo4jContainerManager()
        instance = await manager.start_for_test(
            Neo4jContainerConfig(
                environment='test',
                password='test-password'
            )
        )
        yield instance
        await instance.stop()
"""

from .types import (
    Neo4jContainerConfig,
    Neo4jContainerInstance,
    Environment,
    ContainerStatus,
    PortAllocation,
    VolumeInfo,
)

from .container_manager import Neo4jContainerManager
from .port_manager import PortManager
from .volume_manager import VolumeManager
from .data_manager import DataManager
from .fixtures import neo4j_manager, neo4j_instance

__version__ = "1.0.0"

__all__ = [
    # Configuration and data types
    "Neo4jContainerConfig",
    "Neo4jContainerInstance",
    "Environment",
    "ContainerStatus",
    "PortAllocation",
    "VolumeInfo",
    # Core managers
    "Neo4jContainerManager",
    "PortManager",
    "VolumeManager",
    "DataManager",
    # Pytest fixtures
    "neo4j_manager",
    "neo4j_instance",
    # Version
    "__version__",
]
