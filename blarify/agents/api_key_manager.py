"""API Key Manager for handling multiple API keys with rotation support."""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


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
    
    def __init__(self, provider: str) -> None:
        """Initialize API Key Manager.
        
        Args:
            provider: Name of the provider (e.g., 'openai', 'anthropic', 'google')
        """
        self.provider = provider
        self.keys: Dict[str, KeyState] = {}
        self._lock = threading.RLock()
        self._key_order: List[str] = []
        self._current_index = 0
    
    def add_key(self, key: str) -> None:
        """Add a new API key to the manager.
        
        Args:
            key: The API key to add
        """
        with self._lock:
            if key not in self.keys:
                self.keys[key] = KeyState(key=key, state=KeyStatus.AVAILABLE)
                self._key_order.append(key)
    
    def reset_expired_cooldowns(self) -> None:
        """Reset keys whose cooldown period has expired."""
        now = datetime.now()
        with self._lock:
            for key_state in self.keys.values():
                if key_state.state == KeyStatus.RATE_LIMITED:
                    if key_state.cooldown_until and now >= key_state.cooldown_until:
                        key_state.state = KeyStatus.AVAILABLE
                        key_state.cooldown_until = None
    
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
                    return key
            
            return None  # No available keys