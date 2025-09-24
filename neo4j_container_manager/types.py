"""
Type definitions for Neo4j Container Management.

This module defines all the data structures and types used throughout the
Neo4j container management system, including configuration objects, container
instances, and various enums for status tracking.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Protocol, Union, Any, TYPE_CHECKING
from pathlib import Path
import re

if TYPE_CHECKING:
    from types import TracebackType


@dataclass
class DockerResourceConfig:
    """Docker resource constraints configuration for containers."""
    
    cpu_count: Optional[int] = None  # Number of CPUs to allocate
    cpu_shares: Optional[int] = None  # CPU shares (relative weight)
    cpu_period: Optional[int] = None  # CPU CFS period in microseconds
    cpu_quota: Optional[int] = None  # CPU CFS quota in microseconds
    mem_limit: Optional[str] = None  # Memory limit (e.g., "20g", "512m")
    memswap_limit: Optional[str] = None  # Total memory + swap limit
    mem_reservation: Optional[str] = None  # Memory soft limit
    shm_size: Optional[str] = None  # Shared memory size (e.g., "2g")
    ulimits: Optional[List[Dict[str, Union[str, int]]]] = None  # ulimit settings
    pids_limit: Optional[int] = None  # Process ID limit
    
    def __post_init__(self) -> None:
        """Validate Docker resource configuration."""
        # Validate cpu_count
        if self.cpu_count is not None and self.cpu_count <= 0:
            raise ValueError(f"cpu_count must be positive, got {self.cpu_count}")
        
        # Validate cpu_shares
        if self.cpu_shares is not None and self.cpu_shares < 0:
            raise ValueError(f"cpu_shares must be non-negative, got {self.cpu_shares}")
        
        # Validate cpu_period and cpu_quota
        if self.cpu_period is not None and self.cpu_period <= 0:
            raise ValueError(f"cpu_period must be positive, got {self.cpu_period}")
        if self.cpu_quota is not None and self.cpu_quota <= 0:
            raise ValueError(f"cpu_quota must be positive, got {self.cpu_quota}")
        
        # Validate memory formats
        memory_fields = [
            ("mem_limit", self.mem_limit),
            ("memswap_limit", self.memswap_limit),
            ("mem_reservation", self.mem_reservation),
            ("shm_size", self.shm_size),
        ]
        
        for field_name, value in memory_fields:
            if value is not None:
                if not self._validate_memory_format(value):
                    raise ValueError(
                        f"Invalid {field_name} format: {value}. "
                        "Use formats like '512m', '1g', '2G', '1024M', etc."
                    )
        
        # Validate pids_limit
        if self.pids_limit is not None and self.pids_limit <= 0:
            raise ValueError(f"pids_limit must be positive, got {self.pids_limit}")
        
        # Validate ulimits structure
        if self.ulimits is not None:
            for ulimit in self.ulimits:
                # Check if it's actually a dict (this check is for runtime validation)
                if not hasattr(ulimit, 'get'):
                    raise ValueError(f"Each ulimit must be a dictionary, got {type(ulimit)}")
                
                if "Name" not in ulimit:
                    raise ValueError("Each ulimit must have a 'Name' field")
                
                # Validate that Soft and Hard are present and are integers
                for field in ["Soft", "Hard"]:
                    if field in ulimit:
                        value = ulimit[field]
                        if not isinstance(value, int) or value < 0:
                            raise ValueError(
                                f"ulimit {field} value must be a non-negative integer, "
                                f"got {value} for {ulimit['Name']}"
                            )
    
    def _validate_memory_format(self, memory: str) -> bool:
        """Validate Docker memory format string."""
        # Docker accepts formats like: 512m, 1g, 2G, 1024M, etc.
        # Can also accept bytes without suffix
        pattern = r'^(\d+)([bkmgBKMG])?$'
        match = re.match(pattern, memory.lower())
        
        if not match:
            return False
        
        value = int(match.group(1))
        return value > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: Dict[str, Any] = {}
        
        for field_name in [
            "cpu_count", "cpu_shares", "cpu_period", "cpu_quota",
            "mem_limit", "memswap_limit", "mem_reservation", "shm_size",
            "ulimits", "pids_limit"
        ]:
            value = getattr(self, field_name)
            if value is not None:
                result[field_name] = value
        
        return result
    
    def to_docker_kwargs(self) -> Dict[str, Any]:
        """Convert to Docker API keyword arguments."""
        kwargs: Dict[str, Any] = {}
        
        # Direct mappings
        if self.cpu_count is not None:
            kwargs["cpu_count"] = self.cpu_count
        if self.cpu_shares is not None:
            kwargs["cpu_shares"] = self.cpu_shares
        if self.cpu_period is not None:
            kwargs["cpu_period"] = self.cpu_period
        if self.cpu_quota is not None:
            kwargs["cpu_quota"] = self.cpu_quota
        if self.mem_limit is not None:
            kwargs["mem_limit"] = self.mem_limit
        if self.memswap_limit is not None:
            kwargs["memswap_limit"] = self.memswap_limit
        if self.mem_reservation is not None:
            kwargs["mem_reservation"] = self.mem_reservation
        if self.shm_size is not None:
            kwargs["shm_size"] = self.shm_size
        if self.ulimits is not None:
            kwargs["ulimits"] = self.ulimits
        if self.pids_limit is not None:
            kwargs["pids_limit"] = self.pids_limit
        
        return kwargs


class Environment(str, Enum):
    """Environment types for Neo4j container deployment."""

    TEST = "test"
    DEVELOPMENT = "development"
    MCP = "mcp"


class ContainerStatus(str, Enum):
    """Status of a Neo4j container instance."""

    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class DataFormat(str, Enum):
    """Supported data formats for test data import/export."""

    CYPHER = "cypher"
    JSON = "json"
    CSV = "csv"


@dataclass(frozen=True)
class PortAllocation:
    """Information about allocated ports for Neo4j services."""

    bolt_port: int
    http_port: int
    https_port: int
    backup_port: Optional[int] = None

    def to_dict(self) -> Dict[str, int]:
        """Convert port allocation to dictionary for easy access."""
        result = {
            "bolt": self.bolt_port,
            "http": self.http_port,
            "https": self.https_port,
        }
        if self.backup_port:
            result["backup"] = self.backup_port
        return result

    @property
    def bolt_uri(self) -> str:
        """Get the bolt URI for this port allocation."""
        return f"bolt://localhost:{self.bolt_port}"

    @property
    def http_uri(self) -> str:
        """Get the HTTP URI for this port allocation."""
        return f"http://localhost:{self.http_port}"


@dataclass(frozen=True)
class VolumeInfo:
    """Information about Docker volumes for Neo4j data persistence."""

    name: str
    mount_path: str
    size_limit: Optional[str] = None
    cleanup_on_stop: bool = True

    def to_dict(self) -> Dict[str, Union[str, bool]]:
        """Convert volume info to dictionary."""
        result = {
            "name": self.name,
            "mount_path": self.mount_path,
            "cleanup_on_stop": self.cleanup_on_stop,
        }
        if self.size_limit:
            result["size_limit"] = self.size_limit
        return result


@dataclass
class Neo4jContainerConfig:
    """Configuration for a Neo4j test container."""

    environment: Environment
    password: str
    username: str = "neo4j"
    data_path: Optional[Path] = None
    plugins: List[str] = field(default_factory=lambda: [])
    memory: Optional[str] = None
    test_id: Optional[str] = None
    neo4j_version: str = "5.25.1"
    enable_auth: bool = True
    custom_config: Dict[str, str] = field(default_factory=lambda: {})
    startup_timeout: int = 120
    health_check_interval: int = 5
    docker_resources: Optional[DockerResourceConfig] = None  # Docker resource constraints

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        
        if self.environment == Environment.TEST and not self.test_id:
            import uuid

            self.test_id = f"test-{uuid.uuid4().hex[:8]}"

        # Validate password length (Neo4j requires minimum 8 characters)
        if self.enable_auth and len(self.password) < 8:
            raise ValueError(
                f"Password must be at least 8 characters long (current: {len(self.password)} characters). "
                "Use a stronger password or disable auth with enable_auth=False"
            )

        # Validate username (Neo4j has restrictions on usernames)
        if self.enable_auth and not self.username:
            raise ValueError("Username cannot be empty when authentication is enabled")

        # Validate memory format
        if self.memory:
            if not self.memory.endswith(("M", "G", "MB", "GB")):
                raise ValueError(f"Invalid memory format: {self.memory}. Use formats like '1G', '512M', etc.")
            
            # Extract numeric part and validate it's positive
            match = re.match(r'^(\d+)(M|G|MB|GB)$', self.memory)
            if not match or int(match.group(1)) <= 0:
                raise ValueError(f"Invalid memory value: {self.memory}. Must be a positive number with M/G/MB/GB suffix")

        # Validate startup timeout
        if self.startup_timeout < 30:
            raise ValueError("Startup timeout must be at least 30 seconds")
        if self.startup_timeout > 600:
            raise ValueError("Startup timeout cannot exceed 600 seconds (10 minutes)")

        # Validate health check interval
        if self.health_check_interval < 1:
            raise ValueError("Health check interval must be at least 1 second")
        if self.health_check_interval > 60:
            raise ValueError("Health check interval cannot exceed 60 seconds")

        # Validate Neo4j version format (basic check)
        if not re.match(r'^\d+\.\d+(\.\d+)?(-.*)?$', self.neo4j_version):
            raise ValueError(
                f"Invalid Neo4j version format: {self.neo4j_version}. "
                "Expected format like '5.25.1' or '5.25.1-enterprise'"
            )

        # Validate plugins list
        valid_plugins = {"apoc", "apoc-extended", "bloom", "streams", "graph-data-science", "gds", "n10s"}
        for plugin in self.plugins:
            if plugin not in valid_plugins:
                raise ValueError(
                    f"Invalid plugin: {plugin}. Valid plugins are: {', '.join(sorted(valid_plugins))}"
                )

    @property
    def container_name(self) -> str:
        """Generate a unique container name based on configuration."""
        if self.environment == Environment.TEST:
            return f"blarify-neo4j-test-{self.test_id}"
        elif self.environment == Environment.MCP:
            return "neo4j-blarify-mcp"
        else:
            return "blarify-neo4j-dev"

    @property
    def volume_name(self) -> str:
        """Generate a unique volume name based on configuration."""
        if self.environment == Environment.TEST:
            return f"blarify-neo4j-test-{self.test_id}-data"
        elif self.environment == Environment.MCP:
            return "neo4j-blarify-mcp-data"
        else:
            return "blarify-neo4j-dev-data"

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization."""
        result = {
            "environment": self.environment.value,
            "username": self.username,
            "password": "***",  # Don't expose password in serialization
            "data_path": str(self.data_path) if self.data_path else None,
            "plugins": self.plugins,
            "memory": self.memory,
            "test_id": self.test_id,
            "neo4j_version": self.neo4j_version,
            "enable_auth": self.enable_auth,
            "custom_config": self.custom_config,
            "startup_timeout": self.startup_timeout,
            "health_check_interval": self.health_check_interval,
            "container_name": self.container_name,
            "volume_name": self.volume_name,
        }
        
        if self.docker_resources is not None:
            result["docker_resources"] = self.docker_resources.to_dict()
        
        return result


class Neo4jInstanceProtocol(Protocol):
    """Protocol defining the interface for Neo4j container instances."""

    async def stop(self) -> None:
        """Stop the container instance."""
        ...

    async def is_running(self) -> bool:
        """Check if the container is running."""
        ...

    async def load_test_data(self, path: Union[str, Path]) -> None:
        """Load test data from file."""
        ...

    async def clear_data(self) -> None:
        """Clear all data in the database."""
        ...

    async def execute_cypher(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results."""
        ...


@dataclass
class Neo4jContainerInstance:
    """Represents a running Neo4j container instance."""

    config: Neo4jContainerConfig
    container_id: str
    ports: PortAllocation
    volume: VolumeInfo
    status: ContainerStatus = ContainerStatus.STARTING
    started_at: Optional[float] = None
    container_ref: Optional[Any] = field(default=None, repr=False)  # Internal container reference
    _driver: Optional[Any] = field(default=None, repr=False)  # Neo4j driver instance

    def __post_init__(self) -> None:
        """Initialize the instance after creation."""
        if self.started_at is None:
            import time

            self.started_at = time.time()

    @property
    def uri(self) -> str:
        """Get the bolt URI for this instance."""
        return self.ports.bolt_uri

    @property
    def http_uri(self) -> str:
        """Get the HTTP URI for this instance."""
        return self.ports.http_uri

    @property
    def uptime_seconds(self) -> float:
        """Get the uptime of this instance in seconds."""
        if self.started_at is None:
            return 0.0
        import time

        return time.time() - self.started_at

    async def stop(self) -> None:
        """Stop the container instance."""
        from .container_manager import Neo4jContainerManager

        manager = Neo4jContainerManager()
        await manager.stop_test(self.container_id)
        self.status = ContainerStatus.STOPPED

    async def is_running(self) -> bool:
        """Check if the container is running."""
        try:
            if not self.container_ref:
                return False

            # Check container status via Docker API
            import docker
            from docker.errors import NotFound

            client = docker.from_env()
            try:
                container = client.containers.get(self.container_id)
                is_running = container.status == "running"

                if is_running and self.status != ContainerStatus.RUNNING:
                    self.status = ContainerStatus.RUNNING
                elif not is_running and self.status == ContainerStatus.RUNNING:
                    self.status = ContainerStatus.STOPPED

                return is_running
            except NotFound:
                self.status = ContainerStatus.STOPPED
                return False
        except Exception:
            return False

    async def load_test_data(self, path: Union[str, Path]) -> None:
        """Load test data from file."""
        from .data_manager import DataManager

        data_manager = DataManager(self)
        await data_manager.load_data_from_file(Path(path))

    async def clear_data(self) -> None:
        """Clear all data in the database."""
        await self.execute_cypher("MATCH (n) DETACH DELETE n")

    async def execute_cypher(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results."""
        if not self._driver:
            import neo4j

            self._driver = neo4j.AsyncGraphDatabase.driver(self.uri, auth=(self.config.username, self.config.password))

        async with self._driver.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the Neo4j instance."""
        try:
            start_time = asyncio.get_event_loop().time()

            # Simple health check query
            await self.execute_cypher("RETURN 1 as health")

            response_time = (asyncio.get_event_loop().time() - start_time) * 1000  # ms

            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "uptime_seconds": round(self.uptime_seconds, 2),
                "uri": self.uri,
                "container_status": self.status.value,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "uptime_seconds": round(self.uptime_seconds, 2),
                "uri": self.uri,
                "container_status": self.status.value,
            }

    def to_dict(self) -> Dict[str, Any]:
        """Convert instance to dictionary for serialization."""
        return {
            "config": self.config.to_dict(),
            "container_id": self.container_id,
            "ports": self.ports.to_dict(),
            "volume": self.volume.to_dict(),
            "status": self.status.value,
            "started_at": self.started_at,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "uri": self.uri,
            "http_uri": self.http_uri,
        }

    async def __aenter__(self) -> "Neo4jContainerInstance":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self, exc_type: Optional[type], exc_val: Optional[BaseException], exc_tb: Optional["TracebackType"]
    ) -> None:
        """Async context manager exit with automatic cleanup."""
        await self.stop()


@dataclass
class TestDataSpec:
    """Specification for loading test data."""

    file_path: Path
    format: DataFormat
    clear_before_load: bool = True
    parameters: Dict[str, Any] = field(default_factory=lambda: {})

    def __post_init__(self) -> None:
        """Validate the test data specification."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"Test data file not found: {self.file_path}")

        # Validate format matches file extension
        expected_extensions = {
            DataFormat.CYPHER: [".cypher", ".cql"],
            DataFormat.JSON: [".json"],
            DataFormat.CSV: [".csv"],
        }

        if self.file_path.suffix.lower() not in expected_extensions[self.format]:
            raise ValueError(
                f"File extension {self.file_path.suffix} doesn't match format {self.format.value}. "
                f"Expected: {expected_extensions[self.format]}"
            )


# Exception types for better error handling
class Neo4jContainerError(Exception):
    """Base exception for Neo4j container management errors."""

    pass


class ContainerStartupError(Neo4jContainerError):
    """Raised when container fails to start properly."""

    pass


class PortAllocationError(Neo4jContainerError):
    """Raised when port allocation fails."""

    pass


class VolumeManagementError(Neo4jContainerError):
    """Raised when volume operations fail."""

    pass


class DataLoadError(Neo4jContainerError):
    """Raised when test data loading fails."""

    pass


class HealthCheckError(Neo4jContainerError):
    """Raised when health check operations fail."""

    pass
