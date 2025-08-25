"""API Key Manager for handling multiple API keys with rotation support."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


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