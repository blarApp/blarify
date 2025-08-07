"""
Shared pytest configuration and fixtures for Blarify tests.

This module provides common fixtures for integration testing,
particularly for GraphBuilder functionality with Neo4j containers.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest

from neo4j_container_manager.fixtures import (
    event_loop,
    neo4j_manager,
    neo4j_config,
    neo4j_instance,
    neo4j_query_helper,
)
from tests.utils.graph_assertions import create_graph_assertions, GraphAssertions


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
async def graph_assertions(neo4j_instance) -> GraphAssertions:
    """
    Fixture that provides GraphAssertions helper for test validation.
    
    Args:
        neo4j_instance: Neo4j container instance from fixtures
        
    Returns:
        GraphAssertions instance configured for the test database
    """
    return create_graph_assertions(neo4j_instance)


# Re-export commonly used fixtures from neo4j_container_manager
# This makes them available to tests without explicit imports
__all__ = [
    "event_loop",
    "neo4j_manager", 
    "neo4j_config",
    "neo4j_instance",
    "neo4j_query_helper",
    "test_code_examples_path",
    "temp_project_dir",
    "graph_assertions",
]