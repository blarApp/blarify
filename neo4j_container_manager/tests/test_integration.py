"""
Integration tests for Neo4j container management.

These tests verify the complete system works together, including actual
Docker containers when available. Tests are designed to be skipped
gracefully if Docker is not available.
"""

import pytest
import asyncio
from typing import Dict, Any
from pathlib import Path
import docker

try:
    import docker

    # from testcontainers.core.exceptions import DockerException
    docker_available = True
except ImportError:
    docker_available = False

from neo4j_container_manager import (
    Neo4jContainerManager,
    Neo4jContainerConfig,
    Environment,
)
from neo4j_container_manager.types import DockerResourceConfig


pytestmark = pytest.mark.skipif(not docker_available, reason="Docker not available")


@pytest.fixture(scope="session")
def docker_check() -> docker.DockerClient:
    """Check if Docker is available and running."""
    if not docker_available:
        pytest.skip("Docker not available")

    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception as e:
        pytest.skip(f"Docker not accessible: {e}")


class TestNeo4jContainerIntegration:
    """Integration tests for Neo4j container management."""

    @pytest.mark.asyncio
    async def test_container_lifecycle(self, docker_check: docker.DockerClient):
        """Test complete container lifecycle."""
        manager = Neo4jContainerManager()
        config = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="integration-test-password",
            test_id="lifecycle-test",
            startup_timeout=60,
        )

        try:
            # Start container
            instance = await manager.start_for_test(config)

            # Verify container is running
            assert await instance.is_running()
            assert instance.status.value in ["starting", "running"]

            # Test health check
            health = await instance.health_check()
            assert "status" in health

            # Test basic connectivity
            result = await instance.execute_cypher("RETURN 1 as test")
            assert result[0]["test"] == 1

            # Stop container
            await instance.stop()

            # Verify container is stopped
            # Note: There might be a brief delay
            await asyncio.sleep(2)

        except Exception as e:
            # Cleanup on failure
            try:
                await manager.cleanup_all_tests()
            except Exception:
                pass
            raise e
        finally:
            # Final cleanup
            await manager.cleanup_all_tests()
    
    @pytest.mark.asyncio
    async def test_container_with_docker_resources(self, docker_check: docker.DockerClient):
        """Test container creation with Docker resource constraints."""
        manager = Neo4jContainerManager()
        
        # Create configuration with resource constraints
        docker_resources = DockerResourceConfig(
            cpu_count=2,
            cpu_shares=2048,
            mem_limit="2g",
            shm_size="256m",
            ulimits=[
                {"Name": "nofile", "Soft": 32768, "Hard": 32768},
                {"Name": "nproc", "Soft": 4096, "Hard": 4096},
            ]
        )
        
        config = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="resource-test-password",
            test_id="resource-constraints-test",
            docker_resources=docker_resources,
            startup_timeout=90,
        )
        
        try:
            # Start container with resource constraints
            instance = await manager.start_for_test(config)
            
            # Verify container is running
            assert await instance.is_running()
            
            # Get container stats to verify resources were applied
            stats = manager.get_container_stats(instance.container_id)
            
            # Verify container is operational
            assert "status" in stats
            assert stats.get("status") == "running"
            
            # Test that Neo4j works with the resource constraints
            result = await instance.execute_cypher("RETURN 'Resource test' as message")
            assert result[0]["message"] == "Resource test"
            
            # Create some nodes to test memory limits
            for i in range(10):
                await instance.execute_cypher(
                    "CREATE (n:TestNode {id: $id, data: $data})",
                    {"id": i, "data": f"Test data for node {i}"}
                )
            
            # Query the nodes
            count_result = await instance.execute_cypher("MATCH (n:TestNode) RETURN count(n) as count")
            assert count_result[0]["count"] == 10
            
            # Health check should still work with constraints
            health = await instance.health_check()
            assert health["status"] == "healthy"
            
        finally:
            # Cleanup
            await manager.cleanup_all_tests()

    @pytest.mark.asyncio
    async def test_multiple_containers_parallel(self, docker_check: docker.DockerClient):
        """Test running multiple containers in parallel."""
        manager = Neo4jContainerManager()

        configs = [
            Neo4jContainerConfig(
                environment=Environment.TEST,
                password=f"test-password-{i}",  # At least 8 characters
                test_id=f"parallel-test-{i}",
                startup_timeout=60,
            )
            for i in range(2)  # Start with 2 to avoid resource issues
        ]

        instances = []

        try:
            # Start all containers
            for config in configs:
                instance = await manager.start_for_test(config)
                instances.append(instance)

            # Verify all are running with different ports
            ports_used = set()
            for instance in instances:
                assert await instance.is_running()

                # Ensure ports are unique
                port_key = (instance.ports.bolt_port, instance.ports.http_port)
                assert port_key not in ports_used
                ports_used.add(port_key)

                # Test basic query
                result = await instance.execute_cypher("RETURN 'test' as value")
                assert result[0]["value"] == "test"

        finally:
            # Cleanup all containers
            await manager.cleanup_all_tests()

    @pytest.mark.asyncio
    async def test_data_loading_and_queries(self, docker_check: docker.DockerClient, tmp_path: Path):
        """Test data loading and complex queries."""
        manager = Neo4jContainerManager()
        config = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="data-test-password",
            test_id="data-loading-test",
            startup_timeout=60,
        )

        # Create test data file
        cypher_file = tmp_path / "test_data.cypher"
        cypher_content = """
        CREATE (alice:Person {name: 'Alice', age: 30, department: 'Engineering'});
        CREATE (bob:Person {name: 'Bob', age: 25, department: 'Marketing'});
        CREATE (company:Company {name: 'TechCorp', industry: 'Technology'});
        CREATE (project:Project {name: 'WebApp', status: 'active'});
        
        MATCH (alice:Person {name: 'Alice'}), (company:Company {name: 'TechCorp'})
        CREATE (alice)-[:WORKS_FOR {since: '2020-01-01'}]->(company);
        
        MATCH (bob:Person {name: 'Bob'}), (company:Company {name: 'TechCorp'})
        CREATE (bob)-[:WORKS_FOR {since: '2021-01-01'}]->(company);
        
        MATCH (alice:Person {name: 'Alice'}), (project:Project {name: 'WebApp'})
        CREATE (alice)-[:ASSIGNED_TO {role: 'lead'}]->(project);
        """
        cypher_file.write_text(cypher_content.strip())

        try:
            instance = await manager.start_for_test(config)

            # Load test data
            await instance.load_test_data(cypher_file)

            # Test queries
            # Count nodes
            result = await instance.execute_cypher("MATCH (n) RETURN count(n) as total")
            assert result[0]["total"] == 4

            # Count relationships
            result = await instance.execute_cypher("MATCH ()-[r]->() RETURN count(r) as total")
            assert result[0]["total"] == 3

            # Test complex query
            result = await instance.execute_cypher("""
                MATCH (p:Person)-[:WORKS_FOR]->(c:Company)
                RETURN p.name as person, c.name as company, p.department as dept
                ORDER BY p.name
            """)

            assert len(result) == 2
            assert result[0]["person"] == "Alice"
            assert result[1]["person"] == "Bob"
            assert all(r["company"] == "TechCorp" for r in result)

            # Test data clearing
            await instance.clear_data()

            result = await instance.execute_cypher("MATCH (n) RETURN count(n) as total")
            assert result[0]["total"] == 0

        finally:
            await manager.cleanup_all_tests()

    @pytest.mark.asyncio
    async def test_container_recovery_after_failure(self, docker_check: docker.DockerClient):
        """Test container recovery scenarios."""
        manager = Neo4jContainerManager()
        config = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="recovery-test",
            test_id="recovery-test",
            startup_timeout=60,
        )

        try:
            # Start container
            instance1 = await manager.start_for_test(config)

            # Verify it's working
            result = await instance1.execute_cypher("RETURN 1 as test")
            assert result[0]["test"] == 1

            # Simulate container stopping (without cleanup)
            if hasattr(instance1, "container_ref") and instance1.container_ref:
                instance1.container_ref.stop()

            # Try to start another container with same config
            # This should handle the cleanup and start fresh
            instance2 = await manager.start_for_test(config)

            # Should be able to query the new instance
            result = await instance2.execute_cypher("RETURN 2 as test")
            assert result[0]["test"] == 2

        finally:
            await manager.cleanup_all_tests()

    @pytest.mark.asyncio
    async def test_memory_configuration(self, docker_check: docker.DockerClient):
        """Test different memory configurations."""
        manager = Neo4jContainerManager()

        memory_configs = ["512M", "1G"]

        for memory in memory_configs:
            config = Neo4jContainerConfig(
                environment=Environment.TEST,
                password="memory-test",
                memory=memory,
                test_id=f"memory-test-{memory.lower()}",
                startup_timeout=90,  # More time for larger memory configs
            )

            try:
                instance = await manager.start_for_test(config)

                # Test basic functionality
                result = await instance.execute_cypher("RETURN 1 as test")
                assert result[0]["test"] == 1

                # Verify configuration was applied
                assert instance.config.memory == memory

                await instance.stop()

            except Exception as e:
                await manager.cleanup_all_tests()
                raise e

    @pytest.mark.asyncio
    async def test_health_check_and_monitoring(self, docker_check: docker.DockerClient):
        """Test health checking and monitoring features."""
        manager = Neo4jContainerManager()
        config = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="health-test",
            test_id="health-monitoring-test",
            startup_timeout=60,
        )

        try:
            instance = await manager.start_for_test(config)

            # Test health check
            health = await instance.health_check()
            assert health["status"] in ["healthy", "starting"]
            assert "response_time_ms" in health or "error" in health
            assert "uptime_seconds" in health

            # Test manager health check for all containers
            all_health = await manager.health_check_all()
            assert instance.container_id in all_health

            # Test container stats (might not work in all environments)
            stats = manager.get_container_stats(instance.container_id)
            assert isinstance(stats, dict)
            assert "container_id" in stats

            # Test manager stats
            manager_stats = manager.get_manager_stats()
            assert manager_stats["running_containers"] >= 1
            assert isinstance(manager_stats["port_allocations"], int)

        finally:
            await manager.cleanup_all_tests()

    @pytest.mark.asyncio
    async def test_fixture_integration(self, docker_check: docker.DockerClient):
        """Test that our fixtures work correctly."""
        # This test simulates how the fixtures would be used
        from neo4j_container_manager.fixtures import Neo4jContainerManager as FixtureManager

        # This is similar to what the neo4j_instance fixture does
        manager = FixtureManager()
        config = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="fixture-test",
            test_id="fixture-integration-test",
            startup_timeout=60,
        )

        try:
            instance = await manager.start_for_test(config)

            # Load sample data (like neo4j_instance_with_sample_data)
            from neo4j_container_manager.data_manager import DataManager

            data_manager = DataManager(instance)

            stats = await data_manager.create_sample_data("basic")
            assert stats["nodes_created"] > 0
            assert stats["relationships_created"] > 0

            # Test query helper functionality
            result = await instance.execute_cypher("MATCH (n) RETURN count(n) as count")
            assert result[0]["count"] == stats["nodes_created"]

        finally:
            await manager.cleanup_all_tests()


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_invalid_configuration(self, docker_check: docker.DockerClient):
        """Test handling of invalid configurations."""

        # Test password too short
        with pytest.raises(ValueError, match="Password must be at least 8 characters"):
            Neo4jContainerConfig(environment=Environment.TEST, password="short")

        # Test invalid memory format
        with pytest.raises(ValueError, match="Invalid memory format"):
            Neo4jContainerConfig(environment=Environment.TEST, password="valid-password-123", memory="invalid-memory")

        # Test invalid memory value
        with pytest.raises(ValueError, match="Invalid memory value"):
            Neo4jContainerConfig(environment=Environment.TEST, password="valid-password-123", memory="0M")

        # Test invalid startup timeout (too low)
        with pytest.raises(ValueError, match="Startup timeout must be at least 30 seconds"):
            Neo4jContainerConfig(
                environment=Environment.TEST,
                password="valid-password-123",
                startup_timeout=10,  # Too low
            )

        # Test invalid startup timeout (too high)
        with pytest.raises(ValueError, match="Startup timeout cannot exceed 600 seconds"):
            Neo4jContainerConfig(
                environment=Environment.TEST,
                password="valid-password-123",
                startup_timeout=700,  # Too high
            )

        # Test invalid Neo4j version format
        with pytest.raises(ValueError, match="Invalid Neo4j version format"):
            Neo4jContainerConfig(
                environment=Environment.TEST,
                password="valid-password-123",
                neo4j_version="invalid.version",
            )

        # Test invalid plugin name
        with pytest.raises(ValueError, match="Invalid plugin"):
            Neo4jContainerConfig(
                environment=Environment.TEST,
                password="valid-password-123",
                plugins=["invalid-plugin"],
            )

    @pytest.mark.asyncio
    async def test_port_conflict_resolution(self, docker_check: docker.DockerClient):
        """Test port conflict resolution."""
        manager = Neo4jContainerManager()

        # Start first container
        config1 = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="test-password-1",  # At least 8 characters
            test_id="port-test-1",
            startup_timeout=60,
        )

        config2 = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="test-password-2",  # At least 8 characters
            test_id="port-test-2",
            startup_timeout=60,
        )

        try:
            instance1 = await manager.start_for_test(config1)
            instance2 = await manager.start_for_test(config2)

            # Containers should have different ports
            assert instance1.ports.bolt_port != instance2.ports.bolt_port
            assert instance1.ports.http_port != instance2.ports.http_port

            # Both should be functional
            result1 = await instance1.execute_cypher("RETURN 1 as test")
            result2 = await instance2.execute_cypher("RETURN 2 as test")

            assert result1[0]["test"] == 1
            assert result2[0]["test"] == 2

        finally:
            await manager.cleanup_all_tests()

    @pytest.mark.asyncio
    async def test_cleanup_robustness(self, docker_check: docker.DockerClient):
        """Test that cleanup works even with partial failures."""
        manager = Neo4jContainerManager()

        configs = [
            Neo4jContainerConfig(
                environment=Environment.TEST,
                password=f"cleanup-test-{i}",
                test_id=f"cleanup-test-{i}",
                startup_timeout=60,
            )
            for i in range(3)
        ]

        instances = []

        try:
            # Start multiple containers
            for config in configs:
                instance = await manager.start_for_test(config)
                instances.append(instance)

            # Verify all are running
            for instance in instances:
                assert await instance.is_running()

        finally:
            # Test cleanup - should work even if some containers are in weird states
            cleanup_results = await manager.cleanup_all_tests()

            # Should return results for cleanup attempts
            assert isinstance(cleanup_results, dict)

            # Wait a bit and verify containers are gone
            await asyncio.sleep(2)

            # Check Docker directly to ensure cleanup
            client = docker.from_env()
            containers = client.containers.list(all=True)

            # Should not find our test containers
            our_containers = [
                c for c in containers if any(test_id in c.name for test_id in [f"cleanup-test-{i}" for i in range(3)])
            ]

            # If containers still exist, they should be stopped
            for container in our_containers:
                assert container.status in ["exited", "removing", "dead"]


@pytest.mark.slow
class TestPerformanceAndStress:
    """Performance and stress tests (marked as slow)."""

    @pytest.mark.asyncio
    async def test_rapid_container_cycling(self, docker_check: docker.DockerClient):
        """Test rapidly creating and destroying containers."""
        manager = Neo4jContainerManager()

        for i in range(5):  # Reduced from 10 to be gentler
            config = Neo4jContainerConfig(
                environment=Environment.TEST,
                password=f"cycle-test-{i}",
                test_id=f"rapid-cycle-{i}",
                startup_timeout=60,
            )

            try:
                instance = await manager.start_for_test(config)

                # Quick test
                result = await instance.execute_cypher("RETURN $i as test", {"i": i})
                assert result[0]["test"] == i

                await instance.stop()

                # Brief pause to let Docker clean up
                await asyncio.sleep(1)

            except Exception as e:
                await manager.cleanup_all_tests()
                raise e

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, docker_check: docker.DockerClient):
        """Test concurrent container operations."""
        manager = Neo4jContainerManager()

        async def create_and_test_container(test_id: int) -> Dict[str, Any]:
            config = Neo4jContainerConfig(
                environment=Environment.TEST,
                password=f"concurrent-test-{test_id}",
                test_id=f"concurrent-{test_id}",
                startup_timeout=90,
            )

            instance = await manager.start_for_test(config)

            # Run some operations
            await instance.execute_cypher(f"CREATE (n:Test {{id: {test_id}}})")
            result = await instance.execute_cypher("MATCH (n:Test) RETURN n.id as id")

            return {
                "test_id": test_id,
                "container_id": instance.container_id,
                "result": result[0]["id"],
                "ports": instance.ports.to_dict(),
            }

        try:
            # Run multiple containers concurrently
            tasks = [create_and_test_container(i) for i in range(3)]
            results = await asyncio.gather(*tasks)

            # Verify all completed successfully
            assert len(results) == 3

            # Verify unique ports
            all_ports = [r["ports"] for r in results]
            bolt_ports = [p["bolt"] for p in all_ports]
            assert len(set(bolt_ports)) == 3  # All unique

            # Verify correct results
            for i, result in enumerate(results):
                assert result["result"] == i

        finally:
            await manager.cleanup_all_tests()
