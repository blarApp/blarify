"""
Container Management for Neo4j.

This module provides the core container lifecycle management functionality,
handling Neo4j container creation, startup, health checks, and cleanup
using the Docker SDK directly for full control over configuration.
"""

import asyncio
import json
import uuid
from typing import Dict, List, Optional, Any

import docker
from docker.errors import APIError, NotFound
from docker.models.containers import Container

from .types import (
    Neo4jContainerConfig,
    Neo4jContainerInstance,
    ContainerStatus,
    ContainerStartupError,
    Neo4jContainerError,
    Environment,
    PortAllocation,
    VolumeInfo,
)
from .port_manager import PortManager
from .volume_manager import VolumeManager


class Neo4jContainerManager:
    """
    Manages Neo4j container lifecycle.

    Provides high-level container management with automatic port allocation,
    volume management, and health checking for development and test environments.
    """

    def __init__(self, docker_client: Optional["docker.DockerClient"] = None):
        """
        Initialize the container manager.

        Args:
            docker_client: Docker client instance (creates new if None)
        """
        # Docker is imported directly, so this check is no longer needed
        self._docker_client: "docker.DockerClient" = docker_client or docker.from_env()
        self._port_manager = PortManager()
        self._volume_manager = VolumeManager(self._docker_client)
        self._running_containers: Dict[str, Neo4jContainerInstance] = {}

    async def start(self, config: Neo4jContainerConfig) -> Neo4jContainerInstance:
        """
        Start a Neo4j container.

        Args:
            config: Container configuration

        Returns:
            Running container instance

        Raises:
            ContainerStartupError: If container fails to start
        """
        try:
            container_id = config.container_name

            # Check if container with this ID is already running
            if container_id in self._running_containers:
                existing_instance = self._running_containers[container_id]
                if await existing_instance.is_running():
                    return existing_instance
                else:
                    # Clean up stale reference
                    del self._running_containers[container_id]

            # Allocate ports
            ports = self._port_manager.allocate_ports(container_id)

            # Create volume
            volume = self._volume_manager.create_volume(
                name=config.volume_name,
                environment=config.environment,
                cleanup_on_stop=config.environment == Environment.TEST,
            )

            # Create and start the container
            instance = await self._create_and_start_container(config, ports, volume)

            # Store reference
            self._running_containers[container_id] = instance

            return instance

        except Exception as e:
            # Clean up allocated resources on failure
            try:
                self._port_manager.release_ports(config.container_name)
                if config.environment == Environment.TEST:
                    self._volume_manager.delete_volume(config.volume_name, force=True)
            except Exception:
                pass  # Best effort cleanup

            raise ContainerStartupError(f"Failed to start container: {e}")

    async def _create_and_start_container(
        self, config: Neo4jContainerConfig, ports: PortAllocation, volume: VolumeInfo
    ) -> Neo4jContainerInstance:
        """Create and start the actual container."""

        # Create container instance object first
        instance = Neo4jContainerInstance(
            config=config,
            container_id=config.container_name,
            ports=ports,
            volume=volume,
            status=ContainerStatus.STARTING,
        )

        try:
            # Check if container with this name already exists and remove it
            try:
                existing_container = self._docker_client.containers.get(config.container_name)
                existing_container.stop()
                existing_container.remove(force=True)
            except NotFound:
                pass  # No existing container, that's fine
            except Exception:
                pass  # Best effort cleanup

            # Prepare environment variables for Neo4j 5.x
            environment = {
                "NEO4J_AUTH": f"{config.username}/{config.password}" if config.enable_auth else "none",
                "NEO4J_server_memory_heap_initial__size": config.memory or "512M",
                "NEO4J_server_memory_heap_max__size": config.memory or "1G",
                "NEO4J_ACCEPT_LICENSE_AGREEMENT": "yes",
            }

            # Add custom configuration
            for key, value in config.custom_config.items():
                environment[f"NEO4J_{key}"] = value

            # Add plugins if specified
            if config.plugins:
                environment["NEO4J_PLUGINS"] = json.dumps(config.plugins)  # e.g. ["apoc","graph-data-science"]

                # Build allowlists for APOC/GDS safely
                allow = []
                unrestrict = []
                if "apoc" in config.plugins:
                    allow.append("apoc.*")
                    unrestrict.append("apoc.*")
                if "graph-data-science" in config.plugins:
                    allow.append("gds.*")
                    unrestrict.append("gds.*")

                if allow:
                    environment["NEO4J_dbms_security_procedures_allowlist"] = ",".join(allow)
                if unrestrict:
                    environment["NEO4J_dbms_security_procedures_unrestricted"] = ",".join(unrestrict)

            # Prepare port bindings
            ports_config = {
                "7687/tcp": ports.bolt_port,  # Bolt protocol
                "7474/tcp": ports.http_port,  # HTTP interface
            }

            # Prepare volume mounts
            volumes_config = {}
            if volume:
                volumes_config[volume.name] = {"bind": "/data", "mode": "rw"}

            # Prepare Docker run kwargs
            labels = {
                "blarify.component": "neo4j-container-manager",
                "blarify.environment": config.environment.value,
                "blarify.test_id": config.test_id or "",
            }

            # Add specific label for containers created by pytest tests
            if config.test_id and (config.test_id.startswith("test_") or config.test_id.startswith("module_")):
                labels["blarify.pytest_test"] = "true"

            docker_run_kwargs = {
                "image": f"neo4j:{config.neo4j_version}",
                "name": config.container_name,
                "environment": environment,
                "ports": ports_config,
                "volumes": volumes_config,
                "detach": True,
                "remove": False,
                "labels": labels,
            }

            # Add Docker resource constraints if specified
            if config.docker_resources:
                docker_run_kwargs.update(config.docker_resources.to_docker_kwargs())

            # Create and start the container using Docker API directly
            container: Container = self._docker_client.containers.run(**docker_run_kwargs)

            # Update instance with actual container reference
            instance.container_ref = container
            instance.status = ContainerStatus.RUNNING

            # Wait for Neo4j to be ready
            await self._wait_for_neo4j_ready(instance, config.startup_timeout)

            return instance

        except Exception as e:
            instance.status = ContainerStatus.ERROR
            raise ContainerStartupError(f"Failed to create/start container: {e}")

    async def _wait_for_neo4j_ready(self, instance: Neo4jContainerInstance, timeout: int) -> None:
        """Wait for Neo4j to be ready to accept connections."""
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                health_result = await instance.health_check()
                if health_result["status"] == "healthy":
                    return

            except Exception:
                pass  # Continue waiting

            await asyncio.sleep(instance.config.health_check_interval)

        raise ContainerStartupError(f"Neo4j container did not become ready within {timeout} seconds")

    async def start_for_test(self, config: Neo4jContainerConfig) -> Neo4jContainerInstance:
        """
        Start a Neo4j container for testing.

        This is a convenience method for test scenarios that ensures
        the environment is set to TEST and generates a test_id if not provided.

        Args:
            config: Container configuration

        Returns:
            Running container instance

        Raises:
            ContainerStartupError: If container fails to start
        """
        # Ensure environment is set to TEST
        config.environment = Environment.TEST

        # Generate unique test ID if not provided
        if not config.test_id:
            config.test_id = f"test-{uuid.uuid4().hex[:8]}"

        return await self.start(config)

    async def stop(self, container_id: str) -> None:
        """
        Stop a specific container.

        Args:
            container_id: Container ID to stop
        """
        try:
            # Remove from running containers tracking
            instance = self._running_containers.pop(container_id, None)

            if instance and instance.container_ref:
                try:
                    instance.container_ref.stop()
                    instance.status = ContainerStatus.STOPPED
                except Exception:
                    pass  # Best effort

            # Try to stop via Docker API as well
            try:
                container = self._docker_client.containers.get(container_id)
                container.stop()
                container.remove(force=True)
            except NotFound:
                pass  # Already gone
            except APIError:
                pass  # Best effort

            # Release ports
            self._port_manager.release_ports(container_id)

            # Clean up volume if it's a test environment
            if instance and instance.config.environment == Environment.TEST:
                self._volume_manager.delete_volume(instance.volume.name, force=True)

        except Exception as e:
            raise Neo4jContainerError(f"Failed to stop container {container_id}: {e}")

    async def stop_test(self, container_id: str) -> None:
        """
        Stop a specific test container.

        This is a convenience method that calls the general stop method.

        Args:
            container_id: Container ID to stop
        """
        await self.stop(container_id)

    async def cleanup_all_tests(self) -> Dict[str, bool]:
        """
        Clean up all test containers.

        Returns:
            Dictionary mapping container IDs to cleanup success status
        """
        results = {}

        # Stop all tracked containers
        for container_id in list(self._running_containers.keys()):
            try:
                await self.stop_test(container_id)
                results[container_id] = True
            except Exception:
                results[container_id] = False

        # Find and clean up any orphaned test containers
        try:
            # Only get containers that are specifically marked as pytest test containers
            containers = self._docker_client.containers.list(
                filters={
                    "label": [
                        "blarify.component=neo4j-container-manager",
                        "blarify.pytest_test=true"
                    ]
                }
            )

            for container in containers:
                container_name = container.name
                if container_name not in results:
                    try:
                        container.stop()
                        container.remove(force=True)
                        results[container_name] = True
                    except Exception:
                        results[container_name] = False

        except APIError:
            pass  # Best effort

        # Clean up orphaned volumes
        self._volume_manager.cleanup_test_volumes(force=True)

        # Clean up orphaned port allocations
        self._port_manager.cleanup_stale_allocations()

        return results

    async def list_test_containers(self) -> List[Neo4jContainerInstance]:
        """
        List all active test containers.

        Returns:
            List of active container instances
        """
        active_instances = []

        for instance in list(self._running_containers.values()):
            if await instance.is_running():
                active_instances.append(instance)
            else:
                # Remove stale reference
                if instance.container_id in self._running_containers:
                    del self._running_containers[instance.container_id]

        return active_instances

    async def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        """
        Get logs from a specific container.

        Args:
            container_id: Container ID
            tail: Number of recent log lines to retrieve

        Returns:
            Container logs as string
        """
        try:
            container = self._docker_client.containers.get(container_id)
            logs = container.logs(tail=tail, timestamps=True)
            return logs.decode("utf-8")
        except NotFound:
            return f"Container {container_id} not found"
        except APIError as e:
            return f"Error retrieving logs: {e}"

    async def restart_container(self, container_id: str) -> Neo4jContainerInstance:
        """
        Restart a specific container.

        Args:
            container_id: Container ID to restart

        Returns:
            Restarted container instance
        """
        # Get the current instance
        instance = self._running_containers.get(container_id)
        if not instance:
            raise Neo4jContainerError(f"Container {container_id} not found in managed containers")

        # Stop the container
        await self.stop_test(container_id)

        # Start it again with the same configuration
        return await self.start_for_test(instance.config)

    async def execute_in_container(self, container_id: str, command: str) -> str:
        """
        Execute a command inside a container.

        Args:
            container_id: Container ID
            command: Command to execute

        Returns:
            Command output
        """
        try:
            container = self._docker_client.containers.get(container_id)
            result = container.exec_run(command)
            return result.output.decode("utf-8")
        except NotFound:
            raise Neo4jContainerError(f"Container {container_id} not found")
        except APIError as e:
            raise Neo4jContainerError(f"Failed to execute command: {e}")

    def get_container_stats(self, container_id: str) -> Dict[str, Any]:
        """
        Get resource usage statistics for a container.

        Args:
            container_id: Container ID

        Returns:
            Dictionary with resource usage statistics
        """
        try:
            container = self._docker_client.containers.get(container_id)
            stats = container.stats(stream=False)

            # Extract useful metrics
            cpu_stats = stats.get("cpu_stats", {})
            memory_stats = stats.get("memory_stats", {})

            return {
                "container_id": container_id,
                "status": container.status,
                "cpu_usage": cpu_stats.get("cpu_usage", {}),
                "memory_usage": memory_stats.get("usage", 0),
                "memory_limit": memory_stats.get("limit", 0),
                "network_io": stats.get("networks", {}),
                "block_io": stats.get("blkio_stats", {}),
            }

        except NotFound:
            return {"error": f"Container {container_id} not found"}
        except APIError as e:
            return {"error": f"Failed to get stats: {e}"}

    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Perform health checks on all managed containers.

        Returns:
            Dictionary mapping container IDs to health check results
        """
        results = {}

        for container_id, instance in self._running_containers.items():
            try:
                health_result = await instance.health_check()
                results[container_id] = health_result
            except Exception as e:
                results[container_id] = {
                    "status": "error",
                    "error": str(e),
                    "container_id": container_id,
                }

        return results

    def get_manager_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the container manager itself.

        Returns:
            Manager statistics
        """
        return {
            "running_containers": len(self._running_containers),
            "port_allocations": len(self._port_manager.list_all_allocations()),
            "volume_count": len(self._volume_manager.list_volumes()),
            "port_usage_stats": self._port_manager.get_port_usage_stats(),
        }

    async def wait_for_container_healthy(self, container_id: str, timeout: float = 60.0) -> bool:
        """
        Wait for a container to become healthy.

        Args:
            container_id: Container ID
            timeout: Maximum time to wait

        Returns:
            True if container becomes healthy, False if timeout
        """
        instance = self._running_containers.get(container_id)
        if not instance:
            return False

        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                health_result = await instance.health_check()
                if health_result["status"] == "healthy":
                    return True
            except Exception:
                pass

            await asyncio.sleep(1.0)

        return False

    def __enter__(self) -> "Neo4jContainerManager":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit with cleanup."""
        # Run cleanup in a new event loop if needed
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.cleanup_all_tests())
        except RuntimeError:
            # No event loop running, create one
            asyncio.run(self.cleanup_all_tests())

    async def __aenter__(self) -> "Neo4jContainerManager":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit with cleanup."""
        await self.cleanup_all_tests()
