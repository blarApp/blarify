"""API providers with rotating API key support."""

import logging
import threading
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from blarify.agents.api_key_manager import APIKeyManager

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Types of errors that can occur when calling providers."""
    
    RATE_LIMIT = "rate_limit"
    AUTH_ERROR = "auth_error"
    QUOTA_EXCEEDED = "quota_exceeded"
    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"


class RotatingProviderBase(ABC):
    """Abstract base class for providers with rotating API keys."""
    
    def __init__(self, key_manager: APIKeyManager, **kwargs: Any) -> None:
        """Initialize the rotating provider.
        
        Args:
            key_manager: The API key manager instance
            **kwargs: Additional provider-specific arguments
        """
        self.key_manager = key_manager
        self.kwargs = kwargs
        self._current_key: Optional[str] = None
        self._lock = threading.RLock()  # For thread-safe operations
    
    @abstractmethod
    def _create_client(self, api_key: str) -> Any:
        """Create the underlying provider client with the given API key.
        
        Args:
            api_key: The API key to use
            
        Returns:
            The provider-specific client instance
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the provider name for logging and identification.
        
        Returns:
            The provider name
        """
        pass
    
    @abstractmethod
    def analyze_error(self, error: Exception) -> Tuple[ErrorType, Optional[int]]:
        """Analyze an error and determine its type and retry timing.
        
        Args:
            error: The exception to analyze
            
        Returns:
            Tuple of (ErrorType, retry_after_seconds)
            retry_after_seconds is only set for RATE_LIMIT errors
        """
        pass
    
    @abstractmethod
    def extract_headers_from_error(self, error: Exception) -> Dict[str, str]:
        """Extract HTTP headers from provider-specific error if available.
        
        Args:
            error: The exception that may contain headers
            
        Returns:
            Dictionary of headers (empty if none available)
        """
        pass