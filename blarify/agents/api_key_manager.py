"""API Key Manager for handling multiple API keys with rotation support."""

from enum import Enum


class KeyStatus(Enum):
    """Status enum for API key states."""
    
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    INVALID = "invalid"