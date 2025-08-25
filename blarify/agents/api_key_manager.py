"""API Key Manager for handling multiple API keys with rotation support."""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from blarify.agents.utils import discover_keys_for_provider, validate_key

logger = logging.getLogger(__name__)


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
    
    def __init__(self, provider: str, auto_discover: bool = True) -> None:
        """Initialize API Key Manager.
        
        Args:
            provider: Name of the provider (e.g., 'openai', 'anthropic', 'google')
            auto_discover: Whether to automatically discover keys from environment
        """
        self.provider = provider
        self.keys: Dict[str, KeyState] = {}
        self._lock = threading.RLock()
        self._key_order: List[str] = []
        self._current_index = 0
        
        if auto_discover:
            self._auto_discover_keys()
        
        logger.debug(f"Initialized APIKeyManager for {provider}")
    
    def _auto_discover_keys(self) -> None:
        """Automatically discover and add keys from environment."""
        discovered_keys = discover_keys_for_provider(self.provider)
        for key in discovered_keys:
            self.add_key(key)
        
        if discovered_keys:
            logger.info(f"Discovered {len(discovered_keys)} keys for {self.provider}")
    
    def add_key(self, key: str, validate: bool = True) -> bool:
        """Add a new API key to the manager with validation.
        
        Args:
            key: The API key to add
            validate: Whether to validate the key format
            
        Returns:
            True if key was added, False otherwise
        """
        if validate and not validate_key(key, self.provider):
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
        
        Returns:
            The next available API key, or None if no keys are available
        """
        with self._lock:
            self.reset_expired_cooldowns()
            
            if not self._key_order:
                return None
            
            # Try each key once
            for _ in range(len(self._key_order)):
                key = self._key_order[self._current_index]
                self._current_index = (self._current_index + 1) % len(self._key_order)
                
                key_state = self.keys[key]
                if key_state.is_available():
                    key_state.last_used = datetime.now()
                    logger.debug(f"Selected key {key[:8]}... for {self.provider}")
                    return key
            
            logger.warning(f"No available API keys for {self.provider}")
            return None  # No available keys
    
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