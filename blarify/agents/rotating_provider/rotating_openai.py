"""OpenAI provider with automatic API key rotation support."""

from typing import Any, Dict, Optional, Tuple
import re
from datetime import datetime
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from blarify.agents.rotating_provider.rotating_providers import RotatingProviderBase, ErrorType
from blarify.agents.api_key_manager import APIKeyManager

import logging

logger = logging.getLogger(__name__)


@dataclass
class OpenAIRotationConfig:
    """Configuration specific to OpenAI rotation."""

    proactive_rotation_threshold_requests: int = 1
    proactive_rotation_threshold_tokens: int = 100
    default_cooldown_seconds: int = 60
    respect_retry_after: bool = True


class RotatingKeyChatOpenAI(RotatingProviderBase):
    """OpenAI chat model with automatic key rotation."""

    def __init__(
        self, key_manager: APIKeyManager, rotation_config: Optional[OpenAIRotationConfig] = None, **kwargs: Any
    ) -> None:
        """Initialize OpenAI wrapper with rotation support.

        Args:
            key_manager: Manager for API keys
            rotation_config: OpenAI-specific rotation configuration
            **kwargs: Additional arguments for ChatOpenAI
        """
        super().__init__(key_manager, **kwargs)
        self.rotation_config = rotation_config or OpenAIRotationConfig()
        # Remove api_key from kwargs if present (we'll set it per request)
        self.model_kwargs = {k: v for k, v in kwargs.items() if k != "api_key"}

    def _create_client(self, api_key: str) -> ChatOpenAI:
        """Create ChatOpenAI instance with specific API key.

        Args:
            api_key: The API key to use

        Returns:
            ChatOpenAI instance configured with the API key
        """
        return ChatOpenAI(api_key=SecretStr(api_key), **self.model_kwargs)

    def get_provider_name(self) -> str:
        """Return provider name for logging.

        Returns:
            Provider name string
        """
        return "openai"

    def analyze_error(self, error: Exception) -> Tuple[ErrorType, Optional[int]]:
        """Analyze OpenAI-specific errors.

        OpenAI errors include:
        - Rate limit errors (429) with retry timing
        - Authentication errors (401/403)
        - Quota exceeded errors

        Args:
            error: The exception to analyze

        Returns:
            Tuple of (error type, optional retry seconds)
        """
        error_str = str(error).lower()
        error_type_name = type(error).__name__.lower()

        # Check for rate limit error (429)
        if "429" in error_str or "rate_limit" in error_type_name or "rate limit" in error_str:
            # Extract wait time from error message
            retry_after = self._extract_retry_seconds(error_str)
            return (ErrorType.RATE_LIMIT, retry_after)

        # Check for authentication errors
        elif "401" in error_str or "403" in error_str or "unauthorized" in error_str or "invalid api key" in error_str:
            return (ErrorType.AUTH_ERROR, None)

        # Check for quota exceeded
        elif "quota" in error_str and "exceeded" in error_str:
            return (ErrorType.QUOTA_EXCEEDED, None)

        # Check if retryable (connection errors, timeouts)
        elif any(term in error_str for term in ["timeout", "connection", "network"]):
            return (ErrorType.RETRYABLE, None)

        # Default to non-retryable
        return (ErrorType.NON_RETRYABLE, None)

    def _extract_retry_seconds(self, error_str: str) -> int:
        """Extract retry seconds from OpenAI error message.

        Args:
            error_str: The error message string

        Returns:
            Number of seconds to wait before retry
        """
        # Pattern: "try again in 20s" or "retry after 60 seconds"
        patterns = [
            r"try again in (\d+)s",
            r"try again in (\d+) second",
            r"retry after (\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, error_str, re.IGNORECASE)
            if match:
                return int(match.group(1))

        # Default to configured cooldown if not found
        return self.rotation_config.default_cooldown_seconds

    def extract_headers_from_error(self, error: Exception) -> Dict[str, str]:
        """Extract rate limit headers from OpenAI errors.

        OpenAI includes headers in some error responses:
        - X-RateLimit-Limit-Requests
        - X-RateLimit-Remaining-Requests
        - X-RateLimit-Reset-Requests
        - X-RateLimit-Limit-Tokens
        - X-RateLimit-Remaining-Tokens
        - X-RateLimit-Reset-Tokens

        Args:
            error: The exception potentially containing headers

        Returns:
            Dictionary of extracted headers
        """
        headers: Dict[str, str] = {}

        # Check if error has response attribute (common in HTTP errors)
        if hasattr(error, "response"):
            response = getattr(error, "response")
            if hasattr(response, "headers"):
                response_headers = response.headers

                # Extract OpenAI-specific headers
                openai_headers = [
                    "x-ratelimit-limit-requests",
                    "x-ratelimit-remaining-requests",
                    "x-ratelimit-reset-requests",
                    "x-ratelimit-limit-tokens",
                    "x-ratelimit-remaining-tokens",
                    "x-ratelimit-reset-tokens",
                ]

                for header in openai_headers:
                    if header in response_headers:
                        headers[header] = response_headers[header]

        return headers

    def _should_preemptively_rotate(self, headers: Dict[str, str]) -> bool:
        """Check if we should rotate keys proactively based on headers.

        Args:
            headers: Response headers from OpenAI

        Returns:
            True if proactive rotation is recommended
        """
        if not headers:
            return False

        # Check remaining requests
        remaining_requests = headers.get("x-ratelimit-remaining-requests")
        if remaining_requests:
            try:
                if int(remaining_requests) <= self.rotation_config.proactive_rotation_threshold_requests:
                    logger.info(f"OpenAI: Proactively rotating due to low remaining requests ({remaining_requests})")
                    return True
            except ValueError:
                pass

        # Check remaining tokens
        remaining_tokens = headers.get("x-ratelimit-remaining-tokens")
        if remaining_tokens:
            try:
                if int(remaining_tokens) <= self.rotation_config.proactive_rotation_threshold_tokens:
                    logger.info(f"OpenAI: Proactively rotating due to low remaining tokens ({remaining_tokens})")
                    return True
            except ValueError:
                pass

        return False

    def _calculate_cooldown_from_headers(self, headers: Dict[str, str]) -> Optional[int]:
        """Calculate cooldown period from reset headers.

        Args:
            headers: Response headers containing reset times

        Returns:
            Number of seconds until rate limit resets, or None
        """
        # Try to get reset time for requests
        reset_requests = headers.get("x-ratelimit-reset-requests")
        reset_tokens = headers.get("x-ratelimit-reset-tokens")

        reset_time = reset_requests or reset_tokens
        if reset_time:
            try:
                # Parse timestamp and calculate seconds until reset
                reset_dt = datetime.fromisoformat(reset_time.replace("Z", "+00:00"))
                now = datetime.now(reset_dt.tzinfo)
                delta = (reset_dt - now).total_seconds()
                return max(1, int(delta))  # At least 1 second
            except (ValueError, AttributeError):
                logger.warning(f"Failed to parse reset time: {reset_time}")

        return None
