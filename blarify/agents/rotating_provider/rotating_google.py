"""Google (Gemini/Vertex AI) provider wrapper with automatic key rotation support."""

import logging
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

from langchain_google_genai import ChatGoogleGenerativeAI

from blarify.agents.api_key_manager import APIKeyManager
from .rotating_providers import ErrorType, RotatingProviderBase

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RotatingKeyChatGoogle(RotatingProviderBase):
    """Google chat model with automatic key rotation."""

    def __init__(self, key_manager: APIKeyManager, **kwargs: Any):
        """Initialize RotatingKeyChatGoogle.

        Args:
            key_manager: The API key manager instance
            **kwargs: Additional arguments for ChatGoogleGenerativeAI
        """
        super().__init__(key_manager, **kwargs)
        self.model_kwargs = {k: v for k, v in kwargs.items() if k != "google_api_key"}
        # Track exponential backoff per key
        self._backoff_multipliers: Dict[str, int] = {}

    def _create_client(self, api_key: str) -> ChatGoogleGenerativeAI:
        """Create ChatGoogleGenerativeAI instance with specific API key.

        Args:
            api_key: The Google API key to use

        Returns:
            ChatGoogleGenerativeAI instance
        """
        return ChatGoogleGenerativeAI(google_api_key=api_key, **self.model_kwargs)

    def get_provider_name(self) -> str:
        """Return provider name for logging.

        Returns:
            The provider name
        """
        return "google"

    def analyze_error(self, error: Exception) -> Tuple[ErrorType, Optional[int]]:
        """Analyze Google-specific errors.

        Google errors include:
        - 429 / RESOURCE_EXHAUSTED for rate limits
        - No headers available, must use exponential backoff

        Args:
            error: The exception to analyze

        Returns:
            Tuple of (ErrorType, retry_after_seconds)
        """
        error_str = str(error).lower()

        # Check for rate limit error (429 or RESOURCE_EXHAUSTED)
        if "429" in error_str or "resource_exhausted" in error_str or "quota exceeded" in error_str:
            # Google doesn't provide retry-after, use exponential backoff
            retry_after = self._calculate_backoff()
            return (ErrorType.RATE_LIMIT, retry_after)

        # Check for authentication errors
        elif "401" in error_str or "403" in error_str or "unauthenticated" in error_str:
            return (ErrorType.AUTH_ERROR, None)

        # Check for quota exceeded (different from rate limit)
        elif "quota" in error_str and "increase" in error_str:
            return (ErrorType.QUOTA_EXCEEDED, None)

        # Check if retryable
        elif any(term in error_str for term in ["timeout", "connection", "network", "unavailable"]):
            return (ErrorType.RETRYABLE, None)

        return (ErrorType.NON_RETRYABLE, None)

    def _calculate_backoff(self) -> int:
        """Calculate exponential backoff for current key.

        Returns:
            Backoff time in seconds
        """
        if not self._current_key:
            return 60

        # Get current backoff multiplier for this key
        multiplier = self._backoff_multipliers.get(self._current_key, 0)

        # Calculate backoff: 2^multiplier seconds, max 300 seconds
        backoff = min(2**multiplier, 300)

        # Increment multiplier for next time
        self._backoff_multipliers[self._current_key] = multiplier + 1

        logger.info(f"Google: Using exponential backoff of {backoff}s for key {self._current_key[:10]}...")
        return backoff

    def _reset_backoff(self, key: str) -> None:
        """Reset backoff multiplier after successful request.

        Args:
            key: The API key to reset backoff for
        """
        if key in self._backoff_multipliers:
            del self._backoff_multipliers[key]

    def extract_headers_from_error(self, error: Exception) -> Dict[str, str]:
        """Extract headers from Google errors.

        Google doesn't provide rate limit headers, but we extract
        any available headers for debugging.

        Args:
            error: The exception that may contain headers

        Returns:
            Dictionary of headers (empty if none available)
        """
        headers = {}

        if hasattr(error, "response"):
            response = getattr(error, "response")
            if hasattr(response, "headers"):
                # Get any headers that might be useful for debugging
                response_headers = response.headers

                # Google might have some standard headers
                standard_headers = ["date", "content-type", "server"]

                for header in standard_headers:
                    if header in response_headers:
                        headers[header] = response_headers[header]

        return headers

    def execute_with_rotation(self, func: Callable[[], T], max_retries: int = 3) -> T:
        """Override to add backoff reset on success.

        Args:
            func: The function to execute
            max_retries: Maximum number of retry attempts

        Returns:
            The result from func

        Raises:
            The last error if all retries fail
        """
        try:
            result = super().execute_with_rotation(func, max_retries)
            # Reset backoff on success
            if self._current_key:
                self._reset_backoff(self._current_key)
            return result
        except Exception:
            # Re-raise the exception
            raise