"""
Pytest fixtures for Neo4j container testing.

This module provides ready-to-use pytest fixtures for easy integration
with the Neo4j container management system. Fixtures handle automatic
container lifecycle management and cleanup.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable, Dict, Generator, List, Optional, TypeVar, Union

if TYPE_CHECKING:
    try:
        import pytest
    except ImportError:
        # Provide minimal pytest typing for type checkers
        class _pytest:
            @staticmethod
            def fixture(
                scope: Optional[str] = None,
                params: Optional[List[Any]] = None,
                autouse: bool = False,
                ids: Optional[Union[List[str], Callable[[Any], str]]] = None,
                name: Optional[str] = None,
            ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
                def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                    return func

                return decorator

            class mark:
                @staticmethod
                def neo4j_unit(func: Callable[..., Any]) -> Callable[..., Any]:
                    return func

                @staticmethod
                def neo4j_integration(func: Callable[..., Any]) -> Callable[..., Any]:
                    return func

                @staticmethod
                def neo4j_performance(func: Callable[..., Any]) -> Callable[..., Any]:
                    return func

                @staticmethod
                def slow(func: Callable[..., Any]) -> Callable[..., Any]:
                    return func

        pytest = _pytest()

    from .container_manager import Neo4jContainerManager
    from .types import Neo4jContainerConfig, Neo4jContainerInstance, Environment
else:
    # Runtime imports with fallback
    try:
        import pytest
    except ImportError:
        # Mock pytest for runtime when not available
        class _MockPytest:
            @staticmethod
            def fixture(*args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
                def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                    return func

                return decorator

            class mark:
                @staticmethod
                def neo4j_unit(func: Callable[..., Any]) -> Callable[..., Any]:
                    return func

                @staticmethod
                def neo4j_integration(func: Callable[..., Any]) -> Callable[..., Any]:
                    return func

                @staticmethod
                def neo4j_performance(func: Callable[..., Any]) -> Callable[..., Any]:
                    return func

                @staticmethod
                def slow(func: Callable[..., Any]) -> Callable[..., Any]:
                    return func

        pytest = _MockPytest()  # type: ignore[assignment]

    from .container_manager import Neo4jContainerManager
    from .types import Neo4jContainerConfig, Neo4jContainerInstance, Environment

# Type variables for better type hints
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])

# Type aliases for fixture functions
EventLoopFixture = Callable[[], Generator[asyncio.AbstractEventLoop, None, None]]
Neo4jManagerFixture = Callable[[], AsyncGenerator[Neo4jContainerManager, None]]
Neo4jConfigFixture = Callable[[Any], Neo4jContainerConfig]
Neo4jInstanceFixture = Callable[
    [Neo4jContainerManager, Neo4jContainerConfig], AsyncGenerator[Neo4jContainerInstance, None]
]


# Note: Removed event_loop fixture to avoid conflicts with pytest-asyncio
# pytest-asyncio will automatically provide event loops for async tests


@pytest.fixture(scope="session")
async def neo4j_manager() -> AsyncGenerator[Neo4jContainerManager, None]:
    """
    Session-scoped fixture for the Neo4j container manager.

    This fixture provides a single container manager instance for the entire
    test session and ensures cleanup of all containers at the end.
    """
    manager = Neo4jContainerManager()
    try:
        yield manager
    finally:
        # Cleanup all test containers at the end of the session
        await manager.cleanup_all_tests()


@pytest.fixture  # type: ignore[misc]
async def neo4j_config(request: Any) -> Neo4jContainerConfig:
    """
    Fixture that provides a basic Neo4j container configuration.

    Can be customized by setting attributes on the test request:
    - request.neo4j_password: Custom password (default: 'test-password')
    - request.neo4j_memory: Memory limit (default: '512M')
    - request.neo4j_plugins: List of plugins to install
    - request.neo4j_custom_config: Custom configuration dictionary

    Usage:
        @pytest.mark.parametrize("neo4j_password", ["custom-password"], indirect=True)
        async def test_with_custom_password(neo4j_instance):
            # Test uses custom password
            pass
    """
    # Get test-specific configuration from request
    password = getattr(request, "neo4j_password", "test-password")
    memory = getattr(request, "neo4j_memory", "512M")
    plugins = getattr(request, "neo4j_plugins", [])
    custom_config = getattr(request, "neo4j_custom_config", {})

    return Neo4jContainerConfig(
        environment=Environment.TEST,
        password=password,
        memory=memory,
        plugins=plugins,
        custom_config=custom_config,
        test_id=f"pytest-{request.node.name.replace('[', '-').replace(']', '')}",
        startup_timeout=60,
    )


@pytest.fixture  # type: ignore[misc]
async def neo4j_instance(
    neo4j_manager: Neo4jContainerManager, neo4j_config: Neo4jContainerConfig
) -> AsyncGenerator[Neo4jContainerInstance, None]:
    """
    Function-scoped fixture for a Neo4j container instance.

    This fixture provides a fresh Neo4j container for each test function
    and automatically cleans it up after the test completes.

    Usage:
        async def test_something(neo4j_instance):
            # Use neo4j_instance.uri to connect
            # Use neo4j_instance.execute_cypher() to run queries
            result = await neo4j_instance.execute_cypher("RETURN 1 as test")
            assert result[0]['test'] == 1
    """
    instance = await neo4j_manager.start_for_test(neo4j_config)
    try:
        yield instance
    finally:
        await instance.stop()


@pytest.fixture  # type: ignore[misc]
async def neo4j_instance_with_sample_data(
    neo4j_instance: Neo4jContainerInstance,
) -> AsyncGenerator[Neo4jContainerInstance, None]:
    """
    Fixture that provides a Neo4j instance pre-loaded with sample data.

    This fixture extends neo4j_instance by loading basic sample data
    useful for testing graph queries and relationships.

    Sample data includes:
    - Person nodes (Alice, Bob, Charlie)
    - Company node (TechCorp)
    - Project nodes (Web Platform, Mobile App)
    - WORKS_FOR, KNOWS, and ASSIGNED_TO relationships
    """
    from .data_manager import DataManager

    data_manager = DataManager(neo4j_instance)
    await data_manager.create_sample_data("graph")

    yield neo4j_instance
    # Cleanup is handled by the neo4j_instance fixture


@pytest.fixture  # type: ignore[misc]
async def neo4j_instance_empty(
    neo4j_manager: Neo4jContainerManager, neo4j_config: Neo4jContainerConfig
) -> AsyncGenerator[Neo4jContainerInstance, None]:
    """
    Fixture that provides an empty Neo4j instance without any data.

    Similar to neo4j_instance but guarantees the database is completely empty.
    Useful for tests that need to verify exact data counts or clean state.
    """
    instance = await neo4j_manager.start_for_test(neo4j_config)

    # Ensure database is completely empty
    await instance.clear_data()

    try:
        yield instance
    finally:
        await instance.stop()


@pytest.fixture  # type: ignore[misc]
def neo4j_test_data_path(tmp_path: Path) -> Path:
    """
    Fixture that provides a temporary directory for test data files.

    Returns:
        Path to a temporary directory that can be used for test data files
    """
    test_data_dir = tmp_path / "neo4j_test_data"
    test_data_dir.mkdir()
    return test_data_dir


@pytest.fixture  # type: ignore[misc]
def sample_cypher_file(neo4j_test_data_path: Path) -> Path:
    """
    Fixture that creates a sample Cypher file for data loading tests.

    Returns:
        Path to a .cypher file with sample data
    """
    cypher_file = neo4j_test_data_path / "sample_data.cypher"
    cypher_content = """
    // Create sample nodes
    CREATE (p1:Person {name: 'Alice', age: 30});
    CREATE (p2:Person {name: 'Bob', age: 25});
    CREATE (c1:Company {name: 'TestCorp'});
    
    // Create relationships
    MATCH (p1:Person {name: 'Alice'}), (c1:Company {name: 'TestCorp'})
    CREATE (p1)-[:WORKS_FOR]->(c1);
    
    MATCH (p1:Person {name: 'Alice'}), (p2:Person {name: 'Bob'})
    CREATE (p1)-[:KNOWS]->(p2);
    """
    cypher_file.write_text(cypher_content.strip())
    return cypher_file


@pytest.fixture  # type: ignore[misc]
def sample_json_file(neo4j_test_data_path: Path) -> Path:
    """
    Fixture that creates a sample JSON file for data loading tests.

    Returns:
        Path to a .json file with sample data
    """
    json_file = neo4j_test_data_path / "sample_data.json"
    json_content = {
        "nodes": [
            {"labels": ["Person"], "name": "Alice", "age": 30},
            {"labels": ["Person"], "name": "Bob", "age": 25},
            {"labels": ["Company"], "name": "TestCorp"},
        ],
        "relationships": [
            {
                "start_node": {"labels": ["Person"], "name": "Alice"},
                "end_node": {"labels": ["Company"], "name": "TestCorp"},
                "type": "WORKS_FOR",
            }
        ],
    }

    import json

    with open(json_file, "w") as f:
        json.dump(json_content, f, indent=2)

    return json_file


@pytest.fixture  # type: ignore[misc]
def sample_csv_file(neo4j_test_data_path: Path) -> Path:
    """
    Fixture that creates a sample CSV file for data loading tests.

    Returns:
        Path to a .csv file with sample data
    """
    csv_file = neo4j_test_data_path / "sample_data.csv"
    csv_content = """name,age,labels,department
Alice,30,Person,Engineering
Bob,25,Person,Marketing
Charlie,35,Person,Engineering"""

    csv_file.write_text(csv_content)
    return csv_file


# Parameterized fixtures for different Neo4j configurations


@pytest.fixture(params=["5.23.0", "5.24.0", "5.25.1"])
async def neo4j_instance_multi_version(
    neo4j_manager: Neo4jContainerManager, request: Any
) -> AsyncGenerator[Neo4jContainerInstance, None]:
    """
    Parametrized fixture that tests against multiple Neo4j versions.

    This fixture will run tests against different Neo4j versions to ensure
    compatibility across versions.
    """
    config = Neo4jContainerConfig(
        environment=Environment.TEST,
        password="test-password",
        neo4j_version=request.param,
        test_id=f"version-test-{request.param.replace('.', '-')}",
    )

    instance = await neo4j_manager.start_for_test(config)
    try:
        yield instance
    finally:
        await instance.stop()


@pytest.fixture(params=[None, ["apoc"]])
async def neo4j_instance_with_plugins(
    neo4j_manager: Neo4jContainerManager, request: Any
) -> AsyncGenerator[Neo4jContainerInstance, None]:
    """
    Parametrized fixture that tests with and without plugins.

    Tests will run once without plugins and once with APOC plugin enabled.
    """
    plugins = request.param or []

    config = Neo4jContainerConfig(
        environment=Environment.TEST,
        password="test-password",
        plugins=plugins,
        test_id=f"plugins-test-{'-'.join(plugins) if plugins else 'none'}",
    )

    instance = await neo4j_manager.start_for_test(config)
    try:
        yield instance
    finally:
        await instance.stop()


@pytest.fixture(params=["512M", "1G"])
async def neo4j_instance_memory_sizes(
    neo4j_manager: Neo4jContainerManager, request: Any
) -> AsyncGenerator[Neo4jContainerInstance, None]:
    """
    Parametrized fixture that tests different memory configurations.
    """
    memory = request.param

    config = Neo4jContainerConfig(
        environment=Environment.TEST,
        password="test-password",
        memory=memory,
        test_id=f"memory-test-{memory.lower()}",
    )

    instance = await neo4j_manager.start_for_test(config)
    try:
        yield instance
    finally:
        await instance.stop()


# Utility fixtures for test helpers


@pytest.fixture  # type: ignore[misc]
def neo4j_query_helper() -> Any:
    """
    Fixture that provides utility functions for common Neo4j queries.

    Returns a helper object with methods for common operations.
    """

    class Neo4jQueryHelper:
        @staticmethod
        async def count_nodes(instance: Neo4jContainerInstance, label: Optional[str] = None) -> int:
            """Count nodes, optionally filtered by label."""
            if label:
                query = f"MATCH (n:{label}) RETURN count(n) as count"
            else:
                query = "MATCH (n) RETURN count(n) as count"

            result = await instance.execute_cypher(query)
            return result[0]["count"]

        @staticmethod
        async def count_relationships(instance: Neo4jContainerInstance, rel_type: Optional[str] = None) -> int:
            """Count relationships, optionally filtered by type."""
            if rel_type:
                query = f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count"
            else:
                query = "MATCH ()-[r]->() RETURN count(r) as count"

            result = await instance.execute_cypher(query)
            return result[0]["count"]

        @staticmethod
        async def get_node_properties(instance: Neo4jContainerInstance, label: str, property_name: str) -> List[Any]:
            """Get all values of a property from nodes with a specific label."""
            query = f"MATCH (n:{label}) RETURN n.{property_name} as prop"
            result = await instance.execute_cypher(query)
            return [record["prop"] for record in result]

        @staticmethod
        async def create_test_graph(instance: Neo4jContainerInstance) -> Dict[str, int]:
            """Create a standard test graph and return creation counts."""
            queries = [
                "CREATE (a:TestNode {name: 'A', value: 1})",
                "CREATE (b:TestNode {name: 'B', value: 2})",
                "CREATE (c:TestNode {name: 'C', value: 3})",
                "MATCH (a:TestNode {name: 'A'}), (b:TestNode {name: 'B'}) CREATE (a)-[:TEST_REL]->(b)",
                "MATCH (b:TestNode {name: 'B'}), (c:TestNode {name: 'C'}) CREATE (b)-[:TEST_REL]->(c)",
            ]

            for query in queries:
                await instance.execute_cypher(query)

            return {
                "nodes_created": 3,
                "relationships_created": 2,
            }

    return Neo4jQueryHelper()


@pytest.fixture  # type: ignore[misc]
async def neo4j_performance_monitor() -> Any:
    """
    Fixture that provides performance monitoring utilities.

    Returns a helper for measuring query performance and container resource usage.
    """
    import time
    from typing import Tuple

    class PerformanceMonitor:
        def __init__(self):
            self.query_times: List[Tuple[str, float]] = []

        async def time_query(
            self, instance: Neo4jContainerInstance, query: str, parameters: Optional[Dict[str, Any]] = None
        ) -> Tuple[List[Dict[str, Any]], float]:
            """Execute a query and measure its execution time."""
            start_time = time.time()
            result = await instance.execute_cypher(query, parameters)
            execution_time = time.time() - start_time

            self.query_times.append((query[:50] + "..." if len(query) > 50 else query, execution_time))
            return result, execution_time

        def get_query_stats(self) -> Dict[str, Any]:
            """Get statistics about executed queries."""
            if not self.query_times:
                return {"total_queries": 0}

            times = [t for _, t in self.query_times]
            return {
                "total_queries": len(self.query_times),
                "total_time": sum(times),
                "average_time": sum(times) / len(times),
                "min_time": min(times),
                "max_time": max(times),
                "queries": self.query_times,
            }

        def reset_stats(self):
            """Reset performance statistics."""
            self.query_times.clear()

    return PerformanceMonitor()


# Marks for test categorization

# Define custom marks for test categorization
neo4j_unit = pytest.mark.neo4j_unit
neo4j_integration = pytest.mark.neo4j_integration
neo4j_performance = pytest.mark.neo4j_performance
neo4j_slow = pytest.mark.slow  # For tests that take longer
