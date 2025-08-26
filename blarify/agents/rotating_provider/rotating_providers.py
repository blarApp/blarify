"""API providers with rotating API key support."""

import copy
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

from langchain_core.runnables import Runnable

from blarify.agents.api_key_manager import APIKeyManager

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorType(Enum):
    """Types of errors that can occur when calling providers."""

    RATE_LIMIT = "rate_limit"
    AUTH_ERROR = "auth_error"
    QUOTA_EXCEEDED = "quota_exceeded"
    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"


@dataclass
class ProviderMetrics:
    """Metrics for provider usage."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limit_hits: int = 0
    auth_failures: int = 0
    quota_exceeded_count: int = 0
    key_rotations: int = 0
    last_rotation: Optional[datetime] = None
    error_breakdown: Dict[str, int] = field(default_factory=dict)


class RotatingProviderBase(Runnable[Any, Any], ABC):
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
        self.metrics = ProviderMetrics()

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
        Only rotates keys when errors occur, not on every call.

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

        for _ in range(max_retries):
            # Thread-safe key selection
            with self._lock:
                # Decision logic for key selection:
                # 1. If no current key -> get a new one
                # 2. If current key is not available -> get a new one  
                # 3. Otherwise -> reuse the current key
                
                need_new_key = (
                    not self._current_key or 
                    not self.key_manager.is_key_available(self._current_key)
                )
                
                if need_new_key:
                    # Get a new key
                    key = self.key_manager.get_next_available_key()
                    
                    if not key:
                        logger.error(f"No available keys for {self.get_provider_name()}")
                        if last_error:
                            raise last_error
                        raise RuntimeError(f"No available API keys for {self.get_provider_name()}")
                    
                    # Track key rotation if key actually changed
                    if self._current_key and self._current_key != key:
                        # This is an actual rotation
                        self.metrics.key_rotations += 1
                        self.metrics.last_rotation = datetime.now()
                        logger.debug(f"Rotated from key {self._current_key[:10]}... to {key[:10]}...")
                    
                    self._current_key = key
                else:
                    # Reuse existing key
                    key = self._current_key
                    if key:
                        logger.debug(f"Reusing existing key {key[:10]}... for {self.get_provider_name()}")
                
                # Check if we've exhausted all available keys
                if key and key in keys_tried and len(keys_tried) >= self.key_manager.get_available_count():
                    # We've tried all available keys
                    logger.error(f"All available keys exhausted for {self.get_provider_name()}")
                    if last_error:
                        raise last_error
                    raise RuntimeError(f"All available keys exhausted for {self.get_provider_name()}")
                
                if key:
                    keys_tried.add(key)

            try:
                # Create client with current key and execute
                result = func()

                # Success - update metadata and metrics
                if key:
                    self._record_success(key)
                    logger.debug(f"Request successful with key {key[:10]}... for {self.get_provider_name()}")
                self._update_metrics()
                return result

            except Exception as e:
                last_error = e
                error_type, retry_after = self.analyze_error(e)

                # Record the failure and update metrics
                if key:
                    self._record_failure(key, error_type)
                self._update_metrics(error_type)

                # Handle different error types
                if error_type == ErrorType.RATE_LIMIT:
                    if key:
                        self.key_manager.mark_rate_limited(key, retry_after)
                        logger.warning(f"Rate limit hit for {self.get_provider_name()} key {key[:10]}...")
                    # Clear current key to force rotation on next attempt
                    with self._lock:
                        self._current_key = None

                elif error_type == ErrorType.AUTH_ERROR:
                    if key:
                        self.key_manager.mark_invalid(key)
                        logger.error(f"Auth failed for {self.get_provider_name()} key {key[:10]}...")
                    # Clear current key to force rotation on next attempt
                    with self._lock:
                        self._current_key = None

                elif error_type == ErrorType.QUOTA_EXCEEDED:
                    if key:
                        self.key_manager.mark_quota_exceeded(key)
                        logger.error(f"Quota exceeded for {self.get_provider_name()} key {key[:10]}...")
                    # Clear current key to force rotation on next attempt
                    with self._lock:
                        self._current_key = None

                elif error_type == ErrorType.NON_RETRYABLE:
                    # Don't retry non-retryable errors
                    logger.error(f"Non-retryable error for {self.get_provider_name()}: {str(e)}")
                    raise
                
                # For RETRYABLE errors, continue to next iteration without clearing current key
                # This allows retrying with the same key for transient errors

        # All retries exhausted
        logger.error(f"Max retries ({max_retries}) exceeded for {self.get_provider_name()}")
        raise last_error or RuntimeError(f"Max retries exceeded for {self.get_provider_name()}")

    def _record_success(self, key: str) -> None:
        """Record successful request for a key (thread-safe).

        Args:
            key: The API key that was successful
        """
        with self._lock:
            if key in self.key_manager.keys:
                metadata = self.key_manager.keys[key].metadata
                metadata["request_count"] = metadata.get("request_count", 0) + 1
                metadata["success_count"] = metadata.get("success_count", 0) + 1
                metadata["last_success"] = datetime.now().isoformat()

    def _record_failure(self, key: str, error_type: ErrorType) -> None:
        """Record failed request for a key (thread-safe).

        Args:
            key: The API key that failed
            error_type: The type of error that occurred
        """
        with self._lock:
            if key in self.key_manager.keys:
                metadata = self.key_manager.keys[key].metadata
                metadata["request_count"] = metadata.get("request_count", 0) + 1
                metadata["failure_count"] = metadata.get("failure_count", 0) + 1
                metadata[f"{error_type.value}_count"] = metadata.get(f"{error_type.value}_count", 0) + 1
                metadata["last_failure"] = datetime.now().isoformat()

    def _update_metrics(self, error_type: Optional[ErrorType] = None) -> None:
        """Update provider metrics (thread-safe).

        Args:
            error_type: The type of error if this was a failure
        """
        with self._lock:
            self.metrics.total_requests += 1

            if error_type:
                self.metrics.failed_requests += 1
                self.metrics.error_breakdown[error_type.value] = (
                    self.metrics.error_breakdown.get(error_type.value, 0) + 1
                )

                if error_type == ErrorType.RATE_LIMIT:
                    self.metrics.rate_limit_hits += 1
                elif error_type == ErrorType.AUTH_ERROR:
                    self.metrics.auth_failures += 1
                elif error_type == ErrorType.QUOTA_EXCEEDED:
                    self.metrics.quota_exceeded_count += 1
            else:
                self.metrics.successful_requests += 1

    def get_success_rate(self) -> float:
        """Get success rate as percentage (thread-safe).

        Returns:
            Success rate as a percentage (0-100)
        """
        with self._lock:
            if self.metrics.total_requests == 0:
                return 0.0
            return (self.metrics.successful_requests / self.metrics.total_requests) * 100

    def get_metrics_snapshot(self) -> ProviderMetrics:
        """Get a snapshot of current metrics (thread-safe).

        Returns:
            A deep copy of the current metrics
        """
        with self._lock:
            return copy.deepcopy(self.metrics)

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        """Override invoke to use rotation logic.

        Args:
            *args: Positional arguments to pass to the underlying client
            **kwargs: Keyword arguments to pass to the underlying client

        Returns:
            The result from the underlying client's invoke method
        """

        def _invoke() -> Any:
            if not self._current_key:
                raise RuntimeError("No current key available")
            client = self._create_client(self._current_key)
            return client.invoke(*args, **kwargs)

        return self.execute_with_rotation(_invoke)

    def stream(self, *args: Any, **kwargs: Any) -> Any:
        """Override stream to use rotation logic.

        Args:
            *args: Positional arguments to pass to the underlying client
            **kwargs: Keyword arguments to pass to the underlying client

        Returns:
            The result from the underlying client's stream method
        """

        def _stream() -> Any:
            if not self._current_key:
                raise RuntimeError("No current key available")
            client = self._create_client(self._current_key)
            return client.stream(*args, **kwargs)

        return self.execute_with_rotation(_stream)

    def batch(self, *args: Any, **kwargs: Any) -> Any:
        """Override batch to use rotation logic.

        Args:
            *args: Positional arguments to pass to the underlying client
            **kwargs: Keyword arguments to pass to the underlying client

        Returns:
            The result from the underlying client's batch method
        """

        def _batch() -> Any:
            if not self._current_key:
                raise RuntimeError("No current key available")
            client = self._create_client(self._current_key)
            return client.batch(*args, **kwargs)

        return self.execute_with_rotation(_batch)
