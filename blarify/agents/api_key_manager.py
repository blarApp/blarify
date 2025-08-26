"""API Key Manager for handling multiple API keys with rotation support."""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from blarify.agents.utils import discover_keys_for_provider, validate_key

logger = logging.getLogger(__name__)


@dataclass
class KeyManagerConfig:
    """Configuration for APIKeyManager."""

    auto_discover: bool = True
    validate_keys: bool = True
    max_error_count: int = 3
    default_cooldown_seconds: int = 60


@dataclass
class KeyStatistics:
    """Statistics for API key usage."""

    total_keys: int
    available_keys: int
    rate_limited_keys: int
    invalid_keys: int
    quota_exceeded_keys: int
    total_requests: int
    successful_requests: int
    failed_requests: int


class KeyStatus(Enum):
    """Status enum for API key states."""

    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    INVALID = "invalid"


@dataclass
class KeyState:
    """State information for an individual API key."""

    key: str
    state: KeyStatus
    cooldown_until: Optional[datetime] = None
    last_used: Optional[datetime] = None
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_available(self) -> bool:
        """Check if key is available for use."""
        if self.state != KeyStatus.AVAILABLE:
            return False
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return False
        return True


class APIKeyManager:
    """Manages multiple API keys with thread-safe operations and rotation support."""

    def __init__(
        self, provider: str, config: Optional[KeyManagerConfig] = None, auto_discover: Optional[bool] = None
    ) -> None:
        """Initialize API Key Manager.

        Args:
            provider: Name of the provider (e.g., 'openai', 'anthropic', 'google')
            config: Configuration for the key manager
            auto_discover: Override for auto_discover config (for backward compatibility)
        """
        self.provider = provider
        self.config = config or KeyManagerConfig()

        # Handle backward compatibility for auto_discover parameter
        if auto_discover is not None:
            self.config.auto_discover = auto_discover

        self.keys: Dict[str, KeyState] = {}
        self._lock = threading.RLock()
        self._key_order: List[str] = []
        self._current_index = 0

        if self.config.auto_discover:
            self._auto_discover_keys()

        logger.debug(f"Initialized APIKeyManager for {provider}")

    def _auto_discover_keys(self) -> None:
        """Automatically discover and add keys from environment."""
        discovered_keys = discover_keys_for_provider(self.provider)
        for key in discovered_keys:
            self.add_key(key)

        if discovered_keys:
            logger.info(f"Discovered {len(discovered_keys)} keys for {self.provider}")

    def add_key(self, key: str, validate: Optional[bool] = None) -> bool:
        """Add a new API key to the manager with validation.

        Args:
            key: The API key to add
            validate: Whether to validate the key format (uses config default if None)

        Returns:
            True if key was added, False otherwise
        """
        should_validate = validate if validate is not None else self.config.validate_keys
        if should_validate and not validate_key(key, self.provider):
            logger.warning(f"Invalid key format for {self.provider}: {key[:10] if len(key) > 10 else key}...")
            return False

        with self._lock:
            if key not in self.keys:
                self.keys[key] = KeyState(key=key, state=KeyStatus.AVAILABLE)
                self._key_order.append(key)
                logger.debug(f"Added API key for {self.provider}: {key[:8]}...")
                return True
        return False

    def reset_expired_cooldowns(self) -> None:
        """Reset keys whose cooldown period has expired."""
        now = datetime.now()
        with self._lock:
            for key_state in self.keys.values():
                if key_state.state == KeyStatus.RATE_LIMITED:
                    if key_state.cooldown_until and now >= key_state.cooldown_until:
                        key_state.state = KeyStatus.AVAILABLE
                        key_state.cooldown_until = None
                        logger.debug(f"Key {key_state.key[:8]}... cooldown expired, now available")

    def get_next_available_key(self) -> Optional[str]:
        """Get next available key using round-robin selection.

        If no keys are currently available, returns the key that will
        become available soonest (for rate-limited keys).

        Returns:
            The next available API key, or None if no keys exist or all are invalid/quota exceeded
        """
        with self._lock:
            self.reset_expired_cooldowns()

            if not self._key_order:
                return None

            # First, try to find an immediately available key
            for _ in range(len(self._key_order)):
                key = self._key_order[self._current_index]
                self._current_index = (self._current_index + 1) % len(self._key_order)

                key_state = self.keys[key]
                if key_state.is_available():
                    key_state.last_used = datetime.now()
                    logger.debug(f"Selected key {key[:8]}... for {self.provider}")
                    return key

            # No immediately available keys - find the one that will be available soonest
            # Only consider rate-limited keys (not invalid or quota exceeded)
            best_key = None
            earliest_available = None
            now = datetime.now()

            for key, key_state in self.keys.items():
                if key_state.state == KeyStatus.RATE_LIMITED and key_state.cooldown_until:
                    if earliest_available is None or key_state.cooldown_until < earliest_available:
                        earliest_available = key_state.cooldown_until
                        best_key = key

            if best_key and earliest_available:
                # Return the key that will be available soonest
                wait_time = (earliest_available - now).total_seconds()
                logger.warning(
                    f"All keys rate limited for {self.provider}, returning key that will be available in {wait_time:.1f}s"
                )
                return best_key

            # All keys are either invalid or quota exceeded
            logger.warning(f"No usable API keys for {self.provider} (all invalid or quota exceeded)")
            return None

    def is_key_available(self, key: str) -> bool:
        """Check if a specific key is available for use without rotating.
        
        Args:
            key: The API key to check
            
        Returns:
            True if the key is available, False otherwise
        """
        with self._lock:
            if key not in self.keys:
                return False
            
            # Reset expired cooldowns before checking
            self.reset_expired_cooldowns()
            
            # Check if the key is available
            key_state = self.keys[key]
            return key_state.is_available()

    def mark_rate_limited(self, key: str, retry_after: Optional[int] = None) -> None:
        """Mark a key as rate limited with optional cooldown.

        Args:
            key: The API key to mark as rate limited
            retry_after: Optional seconds to wait before retry
        """
        with self._lock:
            if key in self.keys:
                self.keys[key].state = KeyStatus.RATE_LIMITED
                if retry_after:
                    self.keys[key].cooldown_until = datetime.now() + timedelta(seconds=retry_after)
                    logger.debug(f"Key {key[:8]}... marked as rate limited for {retry_after}s")
                else:
                    logger.debug(f"Key {key[:8]}... marked as rate limited")

    def mark_invalid(self, key: str) -> None:
        """Mark a key as permanently invalid.

        Args:
            key: The API key to mark as invalid
        """
        with self._lock:
            if key in self.keys:
                self.keys[key].state = KeyStatus.INVALID
                self.keys[key].error_count += 1
                logger.warning(f"Key {key[:8]}... marked as invalid, error count: {self.keys[key].error_count}")

    def mark_quota_exceeded(self, key: str) -> None:
        """Mark a key as having exceeded quota.

        Args:
            key: The API key to mark as quota exceeded
        """
        with self._lock:
            if key in self.keys:
                self.keys[key].state = KeyStatus.QUOTA_EXCEEDED
                logger.warning(f"Key {key[:8]}... marked as quota exceeded")

    def get_key_states(self) -> Dict[str, KeyState]:
        """Get current state of all keys.

        Returns:
            Dictionary mapping keys to their current state
        """
        with self._lock:
            return dict(self.keys)

    def get_available_count(self) -> int:
        """Get count of currently available keys.

        Returns:
            Number of keys currently available for use
        """
        with self._lock:
            self.reset_expired_cooldowns()
            return sum(1 for state in self.keys.values() if state.is_available())

    def remove_key(self, key: str) -> bool:
        """Remove a key from management.

        Args:
            key: The API key to remove

        Returns:
            True if key was removed, False if not found
        """
        with self._lock:
            if key in self.keys:
                del self.keys[key]
                self._key_order.remove(key)
                # Adjust current index if needed
                if self._current_index >= len(self._key_order) and self._key_order:
                    self._current_index = 0
                logger.debug(f"Removed key {key[:8]}... from {self.provider}")
                return True
        return False

    def cleanup_invalid_keys(self) -> int:
        """Remove keys that have exceeded error threshold.

        Returns:
            Number of keys removed
        """
        removed = 0
        with self._lock:
            keys_to_remove = [
                key
                for key, state in self.keys.items()
                if state.state == KeyStatus.INVALID and state.error_count >= self.config.max_error_count
            ]
            for key in keys_to_remove:
                self.remove_key(key)
                removed += 1

        if removed:
            logger.info(f"Removed {removed} invalid keys for {self.provider}")
        return removed

    def get_statistics(self) -> KeyStatistics:
        """Get current statistics for all keys.

        Returns:
            Statistics object with current metrics
        """
        with self._lock:
            self.reset_expired_cooldowns()

            stats = KeyStatistics(
                total_keys=len(self.keys),
                available_keys=sum(1 for s in self.keys.values() if s.state == KeyStatus.AVAILABLE),
                rate_limited_keys=sum(1 for s in self.keys.values() if s.state == KeyStatus.RATE_LIMITED),
                invalid_keys=sum(1 for s in self.keys.values() if s.state == KeyStatus.INVALID),
                quota_exceeded_keys=sum(1 for s in self.keys.values() if s.state == KeyStatus.QUOTA_EXCEEDED),
                total_requests=sum(s.metadata.get("request_count", 0) for s in self.keys.values()),
                successful_requests=sum(s.metadata.get("success_count", 0) for s in self.keys.values()),
                failed_requests=sum(s.metadata.get("failure_count", 0) for s in self.keys.values()),
            )
            return stats

    def refresh_keys(self) -> int:
        """Re-discover keys from environment and add new ones.

        Returns:
            Number of new keys added
        """
        discovered_keys = discover_keys_for_provider(self.provider)

        new_keys = 0
        for key in discovered_keys:
            if key not in self.keys:
                if self.add_key(key):
                    new_keys += 1

        if new_keys:
            logger.info(f"Added {new_keys} new keys for {self.provider}")

        return new_keys

    def export_state(self) -> Dict[str, Any]:
        """Export current state for persistence.

        Returns:
            Dictionary containing the current state
        """
        with self._lock:
            state = {"provider": self.provider, "keys": {}}
            for key, key_state in self.keys.items():
                state["keys"][key] = {
                    "state": key_state.state.value,
                    "cooldown_until": key_state.cooldown_until.isoformat() if key_state.cooldown_until else None,
                    "error_count": key_state.error_count,
                    "metadata": key_state.metadata,
                }
            return state

    def import_state(self, state: Dict[str, Any]) -> None:
        """Import previously exported state.

        Args:
            state: State dictionary to import
        """
        with self._lock:
            for key, key_data in state.get("keys", {}).items():
                if key in self.keys:
                    self.keys[key].state = KeyStatus(key_data["state"])
                    self.keys[key].error_count = key_data.get("error_count", 0)
                    if key_data.get("cooldown_until"):
                        self.keys[key].cooldown_until = datetime.fromisoformat(key_data["cooldown_until"])
                    self.keys[key].metadata = key_data.get("metadata", {})
