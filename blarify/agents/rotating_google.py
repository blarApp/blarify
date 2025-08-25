"""Google (Gemini/Vertex AI) provider wrapper with automatic key rotation support."""

import logging
from typing import Any, Dict, Optional, Tuple

from langchain_google_genai import ChatGoogleGenerativeAI

from blarify.agents.api_key_manager import APIKeyManager
from blarify.agents.rotating_providers import ErrorType, RotatingProviderBase

logger = logging.getLogger(__name__)


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