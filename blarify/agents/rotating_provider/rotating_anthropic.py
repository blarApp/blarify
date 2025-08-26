"""Anthropic provider with rotating API key support."""

import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from langchain_anthropic import ChatAnthropic
from pydantic import SecretStr

from blarify.agents.api_key_manager import APIKeyManager
from .rotating_providers import ErrorType, RotatingProviderBase

logger = logging.getLogger(__name__)


class RotatingKeyChatAnthropic(RotatingProviderBase):
    """Anthropic chat model with automatic key rotation."""

    def __init__(self, key_manager: APIKeyManager, **kwargs: Any) -> None:
        """Initialize the rotating Anthropic provider.

        Args:
            key_manager: The API key manager instance
            **kwargs: Additional ChatAnthropic arguments
        """
        super().__init__(key_manager, **kwargs)
        self.model_kwargs = {k: v for k, v in kwargs.items() if k != "api_key"}

    def _create_client(self, api_key: str) -> ChatAnthropic:
        """Create ChatAnthropic instance with specific API key.

        Args:
            api_key: The API key to use

        Returns:
            ChatAnthropic instance configured with the key
        """
        return ChatAnthropic(api_key=SecretStr(api_key), **self.model_kwargs)

    def get_provider_name(self) -> str:
        """Return provider name for logging.

        Returns:
            The provider name
        """
        return "anthropic"

    def analyze_error(self, error: Exception) -> Tuple[ErrorType, Optional[int]]:
        """Analyze Anthropic-specific errors.

        Anthropic errors include:
        - rate_limit_error with Retry-After header
        - authentication errors
        - Can trigger on usage spikes

        Args:
            error: The exception to analyze

        Returns:
            Tuple of (ErrorType, retry_after_seconds)
        """
        error_str = str(error).lower()

        # Check for rate limit error
        if "rate_limit_error" in error_str or "429" in error_str or "rate limit" in error_str:
            # Anthropic provides Retry-After header
            retry_after = self._extract_retry_after(error)
            return (ErrorType.RATE_LIMIT, retry_after)

        # Check for authentication errors
        elif "401" in error_str or "403" in error_str or "authentication" in error_str:
            return (ErrorType.AUTH_ERROR, None)

        # Check for quota exceeded
        elif "quota" in error_str:
            return (ErrorType.QUOTA_EXCEEDED, None)

        # Check if retryable
        elif any(term in error_str for term in ["timeout", "connection", "network"]):
            return (ErrorType.RETRYABLE, None)

        return (ErrorType.NON_RETRYABLE, None)

    def extract_headers_from_error(self, error: Exception) -> Dict[str, str]:
        """Extract rate limit headers from Anthropic errors.

        Anthropic headers:
        - retry-after
        - anthropic-ratelimit-requests-limit
        - anthropic-ratelimit-requests-remaining
        - anthropic-ratelimit-requests-reset
        - anthropic-ratelimit-input-tokens-*
        - anthropic-ratelimit-output-tokens-*

        Args:
            error: The exception that may contain headers

        Returns:
            Dictionary of headers (empty if none available)
        """
        headers: Dict[str, str] = {}

        if hasattr(error, "response") and hasattr(error.response, "headers"):  # type: ignore
            response_headers = error.response.headers  # type: ignore

            # Extract Anthropic-specific headers
            anthropic_headers = [
                "retry-after",
                "anthropic-ratelimit-requests-limit",
                "anthropic-ratelimit-requests-remaining",
                "anthropic-ratelimit-requests-reset",
                "anthropic-ratelimit-input-tokens-limit",
                "anthropic-ratelimit-input-tokens-remaining",
                "anthropic-ratelimit-input-tokens-reset",
                "anthropic-ratelimit-output-tokens-limit",
                "anthropic-ratelimit-output-tokens-remaining",
                "anthropic-ratelimit-output-tokens-reset",
            ]

            for header in anthropic_headers:
                if header in response_headers:
                    headers[header] = response_headers[header]

        return headers

    def _extract_retry_after(self, error: Exception) -> int:
        """Extract Retry-After value from error or default.

        Args:
            error: The exception that may contain retry-after info

        Returns:
            Seconds to wait before retrying
        """
        # Check for Retry-After in headers
        headers = self.extract_headers_from_error(error)
        if "retry-after" in headers:
            try:
                return int(headers["retry-after"])
            except ValueError:
                pass

        # Default for Anthropic
        return 30  # Anthropic typically has shorter cooldowns

    def _calculate_cooldown_from_headers(self, headers: Dict[str, str]) -> Optional[int]:
        """Calculate cooldown from Anthropic headers.

        Uses RFC 3339 timestamps in reset headers.

        Args:
            headers: Dictionary of HTTP headers

        Returns:
            Seconds to wait, or None if no cooldown needed
        """
        # First check Retry-After (highest priority)
        if "retry-after" in headers:
            try:
                return int(headers["retry-after"])
            except ValueError:
                pass

        # Check reset timestamps
        for reset_header in [
            "anthropic-ratelimit-requests-reset",
            "anthropic-ratelimit-input-tokens-reset",
            "anthropic-ratelimit-output-tokens-reset",
        ]:
            if reset_header in headers:
                try:
                    # Parse RFC 3339 timestamp
                    reset_time = datetime.fromisoformat(headers[reset_header].replace("Z", "+00:00"))
                    now = datetime.now(reset_time.tzinfo)
                    delta = (reset_time - now).total_seconds()
                    if delta > 0:
                        return int(delta) + 1  # Add 1 second buffer
                except (ValueError, AttributeError):
                    pass

        return None

    def _is_spike_triggered(self, headers: Dict[str, str]) -> bool:
        """Check if rate limit was triggered by usage spike.

        Anthropic can trigger 429 even with remaining quota on spikes.

        Args:
            headers: Dictionary of HTTP headers

        Returns:
            True if spike-triggered, False otherwise
        """
        # Anthropic can trigger 429 even with remaining quota on spikes
        remaining = headers.get("anthropic-ratelimit-requests-remaining", "0")
        try:
            if int(remaining) > 0:
                logger.warning(f"Anthropic: Rate limit triggered by spike (remaining: {remaining})")
                return True
        except ValueError:
            pass
        return False