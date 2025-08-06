"""
Port Management for Neo4j Container Testing.

This module handles dynamic port allocation for Neo4j containers to avoid
conflicts between parallel test runs. It uses file-based locking to ensure
ports are not allocated to multiple containers simultaneously.
"""

import asyncio
import socket
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Optional, Set
import json

from filelock import FileLock

from .types import PortAllocation, PortAllocationError


class PortManager:
    """
    Manages dynamic port allocation for Neo4j test containers.
    
    Uses file-based locking to coordinate port allocation across multiple
    test processes and ensures no port conflicts occur.
    """
    
    # Default Neo4j ports
    DEFAULT_BOLT_PORT = 7687
    DEFAULT_HTTP_PORT = 7474
    DEFAULT_HTTPS_PORT = 7473
    DEFAULT_BACKUP_PORT = 6362
    
    # Port allocation settings
    PORT_RANGE_SIZE = 1000  # How many ports to check for availability
    PORT_INCREMENT = 10     # Port increment for each test instance
    LOCK_TIMEOUT = 30       # Seconds to wait for port lock
    
    def __init__(self, base_port_bolt: int = DEFAULT_BOLT_PORT, 
                 base_port_http: int = DEFAULT_HTTP_PORT,
                 temp_dir: Optional[Path] = None):
        """
        Initialize the port manager.
        
        Args:
            base_port_bolt: Base port for bolt connections (default: 7687)
            base_port_http: Base port for HTTP connections (default: 7474)
            temp_dir: Directory for lock files (default: system temp)
        """
        self.base_port_bolt = base_port_bolt
        self.base_port_http = base_port_http
        self.temp_dir = temp_dir or Path(tempfile.gettempdir())
        
        # Ensure temp directory exists
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Port allocation tracking
        self._allocated_ports: Set[int] = set()
        self._port_lock_file = self.temp_dir / "blarify_neo4j_ports.lock"
        self._port_registry_file = self.temp_dir / "blarify_neo4j_port_registry.json"
    
    @contextmanager
    def _port_lock(self):
        """Context manager for port allocation locking."""
        lock = FileLock(str(self._port_lock_file), timeout=self.LOCK_TIMEOUT)
        try:
            with lock:
                yield
        except Exception as e:
            raise PortAllocationError(f"Failed to acquire port lock: {e}")
    
    def _is_port_available(self, port: int) -> bool:
        """
        Check if a specific port is available for binding.
        
        Args:
            port: Port number to check
            
        Returns:
            True if port is available, False otherwise
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('localhost', port))
                return True
        except (OSError, socket.error):
            return False
    
    def _find_available_port_range(self, start_port: int, num_ports: int = 4) -> Optional[int]:
        """
        Find a range of consecutive available ports starting from start_port.
        
        Args:
            start_port: Starting port to check from
            num_ports: Number of consecutive ports needed
            
        Returns:
            Starting port of available range, or None if not found
        """
        for base_port in range(start_port, start_port + self.PORT_RANGE_SIZE, self.PORT_INCREMENT):
            ports_to_check = [base_port + i for i in range(num_ports)]
            
            # Check if all ports in range are available
            if all(self._is_port_available(port) for port in ports_to_check):
                # Double-check that we can actually bind to these ports
                sockets = []
                try:
                    for port in ports_to_check:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        s.bind(('localhost', port))
                        sockets.append(s)
                    
                    # If we got here, all ports are bindable
                    return base_port
                except (OSError, socket.error):
                    # One of the ports failed, continue searching
                    continue
                finally:
                    # Close all test sockets
                    for s in sockets:
                        try:
                            s.close()
                        except Exception:
                            pass
        
        return None
    
    def _load_port_registry(self) -> Dict[str, Dict[str, int]]:
        """Load the current port registry from file."""
        try:
            if self._port_registry_file.exists():
                with open(self._port_registry_file, 'r') as f:
                    data = json.load(f)
                    
                    # Clean up stale entries (older than 1 hour)
                    current_time = time.time()
                    cleaned_data = {}
                    
                    for container_id, info in data.items():
                        if current_time - info.get('allocated_at', 0) < 3600:  # 1 hour
                            cleaned_data[container_id] = info
                    
                    if len(cleaned_data) != len(data):
                        self._save_port_registry(cleaned_data)
                    
                    return cleaned_data
        except (json.JSONDecodeError, OSError):
            pass
        
        return {}
    
    def _save_port_registry(self, registry: Dict[str, Dict[str, int]]) -> None:
        """Save the port registry to file."""
        try:
            with open(self._port_registry_file, 'w') as f:
                json.dump(registry, f, indent=2)
        except OSError as e:
            raise PortAllocationError(f"Failed to save port registry: {e}")
    
    def allocate_ports(self, container_id: str, include_backup: bool = False) -> PortAllocation:
        """
        Allocate a set of ports for a Neo4j container.
        
        Args:
            container_id: Unique identifier for the container
            include_backup: Whether to allocate a backup port
            
        Returns:
            PortAllocation with allocated ports
            
        Raises:
            PortAllocationError: If port allocation fails
        """
        with self._port_lock():
            registry = self._load_port_registry()
            
            # Check if this container already has ports allocated
            if container_id in registry:
                info = registry[container_id]
                allocation = PortAllocation(
                    bolt_port=info['bolt_port'],
                    http_port=info['http_port'],
                    https_port=info['https_port'],
                    backup_port=info.get('backup_port')
                )
                
                # Verify ports are still available (in case of stale registry)
                if self._verify_port_allocation(allocation):
                    return allocation
                else:
                    # Ports are no longer available, remove from registry
                    del registry[container_id]
                    self._save_port_registry(registry)
            
            # Find currently allocated ports
            allocated_ports = set()
            for info in registry.values():
                allocated_ports.add(info['bolt_port'])
                allocated_ports.add(info['http_port'])
                allocated_ports.add(info['https_port'])
                if info.get('backup_port'):
                    allocated_ports.add(info['backup_port'])
            
            # Find an available port range
            num_ports_needed = 4 if include_backup else 3
            
            # Start searching from base ports, avoiding already allocated ports
            search_start = max(self.base_port_bolt, self.base_port_http)
            
            for attempt in range(100):  # Try up to 100 different starting points
                base_port = search_start + (attempt * self.PORT_INCREMENT)
                
                if self._find_available_port_range(base_port, num_ports_needed):
                    # Calculate actual ports
                    bolt_port = base_port
                    http_port = base_port + 1
                    https_port = base_port + 2
                    backup_port = base_port + 3 if include_backup else None
                    
                    # Make sure these specific ports work for Neo4j
                    proposed_ports = [bolt_port, http_port, https_port]
                    if backup_port:
                        proposed_ports.append(backup_port)
                    
                    # Check against already allocated ports
                    if any(port in allocated_ports for port in proposed_ports):
                        continue
                    
                    # Double-check availability
                    if all(self._is_port_available(port) for port in proposed_ports):
                        allocation = PortAllocation(
                            bolt_port=bolt_port,
                            http_port=http_port,
                            https_port=https_port,
                            backup_port=backup_port
                        )
                        
                        # Register the allocation
                        port_data: Dict[str, int] = {
                            'bolt_port': bolt_port,
                            'http_port': http_port,
                            'https_port': https_port,
                            'allocated_at': int(time.time()),
                        }
                        if backup_port is not None:
                            port_data['backup_port'] = backup_port
                        port_data['container_id_hash'] = hash(container_id)  # Store hash instead
                        registry[container_id] = port_data
                        
                        self._save_port_registry(registry)
                        
                        return allocation
            
            raise PortAllocationError(
                f"Failed to allocate {num_ports_needed} consecutive ports for container {container_id}. "
                f"Tried {100} different port ranges starting from {search_start}."
            )
    
    def _verify_port_allocation(self, allocation: PortAllocation) -> bool:
        """Verify that all ports in an allocation are still available."""
        ports_to_check = [allocation.bolt_port, allocation.http_port, allocation.https_port]
        if allocation.backup_port:
            ports_to_check.append(allocation.backup_port)
        
        return all(self._is_port_available(port) for port in ports_to_check)
    
    def release_ports(self, container_id: str) -> None:
        """
        Release ports allocated to a specific container.
        
        Args:
            container_id: Container ID to release ports for
        """
        with self._port_lock():
            registry = self._load_port_registry()
            
            if container_id in registry:
                del registry[container_id]
                self._save_port_registry(registry)
    
    def get_allocated_ports(self, container_id: str) -> Optional[PortAllocation]:
        """
        Get the ports allocated to a specific container.
        
        Args:
            container_id: Container ID to look up
            
        Returns:
            PortAllocation if found, None otherwise
        """
        registry = self._load_port_registry()
        
        if container_id in registry:
            info = registry[container_id]
            return PortAllocation(
                bolt_port=info['bolt_port'],
                http_port=info['http_port'],
                https_port=info['https_port'],
                backup_port=info.get('backup_port')
            )
        
        return None
    
    def list_all_allocations(self) -> Dict[str, PortAllocation]:
        """
        List all current port allocations.
        
        Returns:
            Dictionary mapping container IDs to their port allocations
        """
        registry = self._load_port_registry()
        result = {}
        
        for container_id, info in registry.items():
            result[container_id] = PortAllocation(
                bolt_port=info['bolt_port'],
                http_port=info['http_port'],
                https_port=info['https_port'],
                backup_port=info.get('backup_port')
            )
        
        return result
    
    def cleanup_stale_allocations(self, max_age_hours: float = 1.0) -> int:
        """
        Clean up stale port allocations older than max_age_hours.
        
        Args:
            max_age_hours: Maximum age of allocations to keep
            
        Returns:
            Number of allocations cleaned up
        """
        with self._port_lock():
            registry = self._load_port_registry()
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            stale_containers = [
                container_id for container_id, info in registry.items()
                if current_time - info.get('allocated_at', 0) > max_age_seconds
            ]
            
            for container_id in stale_containers:
                del registry[container_id]
            
            if stale_containers:
                self._save_port_registry(registry)
            
            return len(stale_containers)
    
    def wait_for_port_available(self, port: int, timeout: float = 30.0, 
                               check_interval: float = 0.5) -> bool:
        """
        Wait for a specific port to become available.
        
        Args:
            port: Port number to wait for
            timeout: Maximum time to wait in seconds
            check_interval: How often to check port availability
            
        Returns:
            True if port becomes available, False if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self._is_port_available(port):
                return True
            time.sleep(check_interval)
        
        return False
    
    async def wait_for_port_available_async(self, port: int, timeout: float = 30.0,
                                          check_interval: float = 0.5) -> bool:
        """
        Async version of wait_for_port_available.
        
        Args:
            port: Port number to wait for
            timeout: Maximum time to wait in seconds
            check_interval: How often to check port availability
            
        Returns:
            True if port becomes available, False if timeout
        """
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            if self._is_port_available(port):
                return True
            await asyncio.sleep(check_interval)
        
        return False
    
    def get_port_usage_stats(self) -> Dict[str, int]:
        """
        Get statistics about current port usage.
        
        Returns:
            Dictionary with usage statistics
        """
        registry = self._load_port_registry()
        
        bolt_ports = []
        http_ports = []
        https_ports = []
        backup_ports = []
        
        for info in registry.values():
            bolt_ports.append(info['bolt_port'])
            http_ports.append(info['http_port'])
            https_ports.append(info['https_port'])
            if info.get('backup_port'):
                backup_ports.append(info['backup_port'])
        
        return {
            'total_allocations': len(registry),
            'bolt_port_min': min(bolt_ports) if bolt_ports else 0,
            'bolt_port_max': max(bolt_ports) if bolt_ports else 0,
            'http_port_min': min(http_ports) if http_ports else 0,
            'http_port_max': max(http_ports) if http_ports else 0,
            'backup_allocations': len(backup_ports),
        }