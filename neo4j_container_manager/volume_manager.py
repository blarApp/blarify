"""
Volume Management for Neo4j Container Testing.

This module handles Docker volume creation, management, and cleanup for
Neo4j test containers. It ensures proper data persistence during tests
and automatic cleanup after completion.
"""

import asyncio
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    import docker
    from docker.errors import APIError, NotFound
else:
    import docker
    from docker.errors import APIError, NotFound

from .types import VolumeInfo, VolumeManagementError, Environment


class VolumeManager:
    """
    Manages Docker volumes for Neo4j test containers.
    
    Provides automatic volume creation, tracking, and cleanup for test isolation.
    Handles both development and test environments with appropriate cleanup policies.
    """
    
    def __init__(self, docker_client: Optional["docker.DockerClient"] = None):
        """
        Initialize the volume manager.
        
        Args:
            docker_client: Docker client instance (creates new if None)
        """
        # Docker is imported directly, so this check is no longer needed
        self._client: "docker.DockerClient" = docker_client or docker.from_env()
        self._volume_registry: Dict[str, VolumeInfo] = {}
    
    def create_volume(self, name: str, environment: Environment = Environment.TEST,
                     size_limit: Optional[str] = None, 
                     cleanup_on_stop: bool = True) -> VolumeInfo:
        """
        Create a new Docker volume for Neo4j data.
        
        Args:
            name: Volume name (should be unique)
            environment: Environment type (test volumes auto-cleanup)
            size_limit: Volume size limit (e.g., '1G', '500M')
            cleanup_on_stop: Whether to cleanup volume when container stops
            
        Returns:
            VolumeInfo with volume details
            
        Raises:
            VolumeManagementError: If volume creation fails
        """
        try:
            # Check if volume already exists
            existing_volume = self._get_existing_volume(name)
            if existing_volume:
                volume_info = VolumeInfo(
                    name=name,
                    mount_path="/data",
                    size_limit=size_limit,
                    cleanup_on_stop=cleanup_on_stop
                )
                self._volume_registry[name] = volume_info
                return volume_info
            
            # Prepare volume options
            driver_opts = {}
            
            if size_limit:
                # Note: Size limits depend on Docker storage driver
                # This is a best-effort approach
                driver_opts['size'] = size_limit
            
            # Create volume with labels for tracking
            labels = {
                'blarify.component': 'neo4j-container-manager',
                'blarify.environment': environment.value,
                'blarify.created_at': str(time.time()),
                'blarify.cleanup_on_stop': str(cleanup_on_stop).lower(),
            }
            
            if size_limit:
                labels['blarify.size_limit'] = size_limit
            
            self._client.volumes.create(
                name=name,
                driver='local',
                driver_opts=driver_opts if driver_opts else None,
                labels=labels
            )
            
            volume_info = VolumeInfo(
                name=name,
                mount_path="/data",
                size_limit=size_limit,
                cleanup_on_stop=cleanup_on_stop
            )
            
            self._volume_registry[name] = volume_info
            
            return volume_info
            
        except APIError as e:
            raise VolumeManagementError(f"Failed to create volume '{name}': {e}")
        except Exception as e:
            raise VolumeManagementError(f"Unexpected error creating volume '{name}': {e}")
    
    def _get_existing_volume(self, name: str) -> Optional[Dict[str, Any]]:
        """Check if a volume with the given name already exists."""
        try:
            volume = self._client.volumes.get(name)
            return volume.attrs
        except NotFound:
            return None
        except APIError:
            return None
    
    def get_volume_info(self, name: str) -> Optional[VolumeInfo]:
        """
        Get information about an existing volume.
        
        Args:
            name: Volume name
            
        Returns:
            VolumeInfo if volume exists, None otherwise
        """
        # Check registry first
        if name in self._volume_registry:
            return self._volume_registry[name]
        
        # Check Docker
        volume_attrs = self._get_existing_volume(name)
        if volume_attrs:
            labels = volume_attrs.get('Labels') or {}
            
            volume_info = VolumeInfo(
                name=name,
                mount_path="/data",
                size_limit=labels.get('blarify.size_limit'),
                cleanup_on_stop=labels.get('blarify.cleanup_on_stop', 'true').lower() == 'true'
            )
            
            self._volume_registry[name] = volume_info
            return volume_info
        
        return None
    
    def delete_volume(self, name: str, force: bool = False) -> bool:
        """
        Delete a Docker volume.
        
        Args:
            name: Volume name to delete
            force: Force deletion even if volume is in use
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            volume = self._client.volumes.get(name)
            volume.remove(force=force)
            
            # Remove from registry
            if name in self._volume_registry:
                del self._volume_registry[name]
            
            return True
            
        except NotFound:
            # Volume doesn't exist, consider it deleted
            if name in self._volume_registry:
                del self._volume_registry[name]
            return True
        except APIError as e:
            if not force and "volume is in use" in str(e).lower():
                # Volume is in use, retry with force after a brief wait
                time.sleep(1)
                try:
                    volume = self._client.volumes.get(name)
                    volume.remove(force=True)
                    
                    if name in self._volume_registry:
                        del self._volume_registry[name]
                    return True
                except Exception:
                    pass
            
            return False
        except Exception:
            return False
    
    def list_volumes(self, environment: Optional[Environment] = None) -> List[VolumeInfo]:
        """
        List all volumes managed by this system.
        
        Args:
            environment: Filter by environment (None for all)
            
        Returns:
            List of VolumeInfo objects
        """
        volumes = []
        
        try:
            # Get all Docker volumes with our labels
            all_volumes = self._client.volumes.list(
                filters={'label': 'blarify.component=neo4j-container-manager'}
            )
            
            for volume in all_volumes:
                labels = volume.attrs.get('Labels') or {}
                vol_env = labels.get('blarify.environment')
                
                # Filter by environment if specified
                if environment and vol_env != environment.value:
                    continue
                
                volume_info = VolumeInfo(
                    name=volume.name,
                    mount_path="/data",
                    size_limit=labels.get('blarify.size_limit'),
                    cleanup_on_stop=labels.get('blarify.cleanup_on_stop', 'true').lower() == 'true'
                )
                
                volumes.append(volume_info)
                # Update registry
                self._volume_registry[volume.name] = volume_info
        
        except APIError:
            pass
        
        return volumes
    
    def cleanup_test_volumes(self, max_age_hours: float = 1.0, 
                           force: bool = False) -> Dict[str, bool]:
        """
        Clean up old test volumes.
        
        Args:
            max_age_hours: Maximum age of volumes to keep (hours)
            force: Force cleanup even if volumes are in use
            
        Returns:
            Dictionary mapping volume names to cleanup success status
        """
        results = {}
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        try:
            test_volumes = self._client.volumes.list(
                filters={
                    'label': [
                        'blarify.component=neo4j-container-manager',
                        'blarify.environment=test'
                    ]
                }
            )
            
            for volume in test_volumes:
                labels = volume.attrs.get('Labels') or {}
                created_at = float(labels.get('blarify.created_at', 0))
                
                # Check if volume is old enough for cleanup
                if current_time - created_at > max_age_seconds:
                    # Check if cleanup is enabled
                    cleanup_enabled = labels.get('blarify.cleanup_on_stop', 'true').lower() == 'true'
                    
                    if cleanup_enabled or force:
                        success = self.delete_volume(volume.name, force=force)
                        results[volume.name] = success
                    else:
                        results[volume.name] = False  # Cleanup disabled
        
        except APIError as e:
            raise VolumeManagementError(f"Failed to list volumes for cleanup: {e}")
        
        return results
    
    def cleanup_volumes_by_pattern(self, pattern: str, 
                                  force: bool = False) -> Dict[str, bool]:
        """
        Clean up volumes matching a specific name pattern.
        
        Args:
            pattern: Pattern to match volume names (simple string contains)
            force: Force cleanup even if volumes are in use
            
        Returns:
            Dictionary mapping volume names to cleanup success status
        """
        results = {}
        
        try:
            volumes = self._client.volumes.list(
                filters={'label': 'blarify.component=neo4j-container-manager'}
            )
            
            for volume in volumes:
                if pattern in volume.name:
                    success = self.delete_volume(volume.name, force=force)
                    results[volume.name] = success
        
        except APIError as e:
            raise VolumeManagementError(f"Failed to list volumes for pattern cleanup: {e}")
        
        return results
    
    def get_volume_usage(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get usage statistics for a volume.
        
        Args:
            name: Volume name
            
        Returns:
            Dictionary with usage information, or None if volume not found
        """
        try:
            volume = self._client.volumes.get(name)
            attrs = volume.attrs
            
            # Basic volume information
            usage_info = {
                'name': name,
                'driver': attrs.get('Driver'),
                'mountpoint': attrs.get('Mountpoint'),
                'created_at': attrs.get('CreatedAt'),
                'labels': attrs.get('Labels', {}),
                'options': attrs.get('Options', {}),
            }
            
            # Try to get size information (not available on all Docker setups)
            try:
                # This is a best-effort approach
                mountpoint = Path(attrs.get('Mountpoint', ''))
                if mountpoint.exists():
                    # Get basic directory information
                    total_size = sum(f.stat().st_size for f in mountpoint.rglob('*') if f.is_file())
                    usage_info['size_bytes'] = total_size
                    usage_info['size_mb'] = round(total_size / (1024 * 1024), 2)
            except (PermissionError, OSError):
                # Can't access volume data, skip size calculation
                pass
            
            return usage_info
            
        except NotFound:
            return None
        except APIError:
            return None
    
    def create_volume_snapshot(self, source_volume: str, 
                             snapshot_name: str) -> bool:
        """
        Create a snapshot of a volume (basic copy approach).
        
        Note: This creates a new volume with copied data, not a true snapshot.
        
        Args:
            source_volume: Source volume name
            snapshot_name: Name for the new snapshot volume
            
        Returns:
            True if snapshot created successfully
        """
        try:
            # Create a temporary container to copy data
            self._client.containers.run(
                'alpine:latest',
                command='sh -c "cp -r /source/* /target/ 2>/dev/null || true"',
                volumes={
                    source_volume: {'bind': '/source', 'mode': 'ro'},
                    snapshot_name: {'bind': '/target', 'mode': 'rw'},
                },
                detach=False,
                auto_remove=True,
                remove=True
            )
            
            return True
            
        except APIError:
            return False
        except Exception:
            return False
    
    async def wait_for_volume_ready(self, name: str, timeout: float = 30.0) -> bool:
        """
        Wait for a volume to be ready for use.
        
        Args:
            name: Volume name
            timeout: Maximum time to wait
            
        Returns:
            True if volume is ready, False if timeout
        """
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            if self.get_volume_info(name):
                return True
            await asyncio.sleep(0.5)
        
        return False
    
    def get_volume_mount_config(self, volume_info: VolumeInfo) -> Dict[str, Dict[str, str]]:
        """
        Get Docker mount configuration for a volume.
        
        Args:
            volume_info: Volume information
            
        Returns:
            Dictionary suitable for Docker container volumes parameter
        """
        return {
            volume_info.name: {
                'bind': volume_info.mount_path,
                'mode': 'rw'
            }
        }
    
    def validate_volume_name(self, name: str) -> bool:
        """
        Validate that a volume name meets Docker requirements.
        
        Args:
            name: Volume name to validate
            
        Returns:
            True if name is valid
        """
        # Docker volume name requirements:
        # - Only lowercase letters, numbers, hyphens, underscores, and periods
        # - Cannot start with hyphen or period
        # - Must be 1-63 characters
        
        if not name or len(name) > 63:
            return False
        
        if name.startswith(('-', '.')):
            return False
        
        allowed_chars = set('abcdefghijklmnopqrstuvwxyz0123456789-_.')
        return all(c in allowed_chars for c in name)
    
    def __enter__(self) -> "VolumeManager":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit with cleanup."""
        # Could add automatic cleanup logic here if needed
        pass