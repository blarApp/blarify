"""API providers with rotating API key support."""

import logging
import threading
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

from blarify.agents.api_key_manager import APIKeyManager

logger = logging.getLogger(__name__)

T = TypeVar('T')


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
    
    def execute_with_rotation(self, func: Callable[[], T], max_retries: int = 3) -> T:
        """Execute function with automatic key rotation on errors.
        
        Thread-safe execution with key rotation support.
        
        Args:
            func: The function to execute
            max_retries: Maximum number of retry attempts
            
        Returns:
            The result from func
            
        Raises:
            The last error if all retries fail
        """
        last_error: Optional[Exception] = None
        keys_tried: set[str] = set()
        
        for attempt in range(max_retries):
            # Thread-safe key selection
            with self._lock:
                key = self.key_manager.get_next_available_key()
                
                if not key:
                    logger.error(f"No available keys for {self.get_provider_name()}")
                    if last_error:
                        raise last_error
                    raise RuntimeError(f"No available API keys for {self.get_provider_name()}")
                
                if key in keys_tried and len(keys_tried) == self.key_manager.get_available_count():
                    # We've tried all available keys
                    if last_error:
                        raise last_error
                    raise RuntimeError(f"All available keys exhausted for {self.get_provider_name()}")
                
                keys_tried.add(key)
                self._current_key = key
            
            try:
                # Create client with current key and execute
                result = func()
                
                # Success - update metadata
                self._record_success(key)
                return result
                
            except Exception as e:
                last_error = e
                error_type, retry_after = self.analyze_error(e)
                
                if error_type == ErrorType.RATE_LIMIT:
                    self.key_manager.mark_rate_limited(key, retry_after)
                    logger.warning(f"Rate limit hit for {self.get_provider_name()} key {key[:10]}...")
                    
                elif error_type == ErrorType.AUTH_ERROR:
                    self.key_manager.mark_invalid(key)
                    logger.error(f"Auth failed for {self.get_provider_name()} key {key[:10]}...")
                    
                elif error_type == ErrorType.QUOTA_EXCEEDED:
                    self.key_manager.mark_quota_exceeded(key)
                    logger.error(f"Quota exceeded for {self.get_provider_name()} key {key[:10]}...")
                    
                elif error_type == ErrorType.NON_RETRYABLE:
                    # Don't retry non-retryable errors
                    raise
                
                # Continue to next iteration for retryable errors
        
        # All retries exhausted
        raise last_error or RuntimeError(f"Max retries exceeded for {self.get_provider_name()}")
    
    def _record_success(self, key: str) -> None:
        """Record successful request for a key.
        
        Args:
            key: The API key that was successful
        """
        # Will be implemented in next step
        pass