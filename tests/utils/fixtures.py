"""
Test fixtures for integration tests.

This module provides reusable fixtures for testing, including
Docker availability checks and other common test utilities.
"""

import pytest
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import docker

try:
    import docker

    docker_available = True
except ImportError:
    docker_available = False


@pytest.fixture(scope="session")
def docker_check() -> "docker.DockerClient":
    """Check if Docker is available and running."""
    if not docker_available:
        pytest.skip("Docker not available")

    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception as e:
        pytest.skip(f"Docker not accessible: {e}")
