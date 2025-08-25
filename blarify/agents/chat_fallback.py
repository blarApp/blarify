"""
This module contains the ChatFallback class, which is used to construct the runnable with fallbacks from a base model and a list of fallback models.
"""

import logging
from typing import Any, Dict, Optional, Type

from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import Runnable, RunnableWithFallbacks
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from blarify.agents.api_key_manager import APIKeyManager
from blarify.agents.rotating_anthropic import RotatingKeyChatAnthropic
from blarify.agents.rotating_google import RotatingKeyChatGoogle
from blarify.agents.rotating_openai import RotatingKeyChatOpenAI
from blarify.agents.utils import discover_keys_for_provider

logger = logging.getLogger(__name__)

MODEL_PROVIDER_DICT = {
    "gpt-4.1": ChatOpenAI,
    "gpt-4.1-nano": ChatOpenAI,
    "gpt-4.1-mini": ChatOpenAI,
    "o4-mini": ChatOpenAI,
    "o3": ChatOpenAI,
    "gemini-2.5-flash-preview-05-20": ChatGoogleGenerativeAI,
    "gemini-2.5-pro-preview-06-05": ChatGoogleGenerativeAI,
    "claude-3-5-haiku-latest": ChatAnthropic,
    "claude-sonnet-4-20250514": ChatAnthropic,
}


class ChatFallback:
    # Mapping of providers to their rotating classes
    ROTATING_PROVIDER_MAP: Dict[str, Type[Any]] = {
        "openai": RotatingKeyChatOpenAI,
        "anthropic": RotatingKeyChatAnthropic,
        "google": RotatingKeyChatGoogle,
    }

    def __init__(self, *, model: str, fallback_list: list[str], output_schema: Optional[BaseModel] = None, timeout: Optional[int] = None):
        self.model = model
        self.fallback_list = fallback_list
        self.output_schema = output_schema
        self.timeout = timeout
        self._rotation_enabled: Dict[str, bool] = {}  # Track which models use rotation

    def _get_provider_from_model(self, model: str) -> Optional[str]:
        """Get provider name from MODEL_PROVIDER_DICT."""
        provider_class = MODEL_PROVIDER_DICT.get(model)
        if not provider_class:
            return None
        
        # Extract provider from class name
        class_name = provider_class.__name__
        if "OpenAI" in class_name:
            return "openai"
        elif "Anthropic" in class_name:
            return "anthropic"
        elif "Google" in class_name or "Gemini" in class_name:
            return "google"
        
        return None

    def _should_use_rotation(self, model: str) -> bool:
        """Check if multiple keys exist for the model's provider."""
        provider = self._get_provider_from_model(model)
        if not provider:
            return False
        
        keys = discover_keys_for_provider(provider)
        has_multiple = len(keys) > 1
        
        if has_multiple:
            logger.debug(f"Found {len(keys)} keys for {provider}, enabling rotation")
        
        return has_multiple

    def _get_rotating_provider_class(self, provider: str) -> Optional[Type[Any]]:
        """Get the rotating provider class for a provider."""
        return self.ROTATING_PROVIDER_MAP.get(provider)

    def get_chat_model(self, model: str, timeout: Optional[int] = None) -> Runnable:
        """
        Get the chat model class for the given model.
        If the model is not found in the MODEL_PROVIDER_DICT, raise a ValueError.
        If the model is found, return the chat model class instance.
        """
        try:
            chat_model_class: Type[ChatGoogleGenerativeAI | ChatAnthropic | ChatOpenAI] = MODEL_PROVIDER_DICT[model]
        except KeyError:
            logger.exception(f"Model {model} not found in MODEL_PROVIDER_DICT")
            raise ValueError(f"Model {model} not found in MODEL_PROVIDER_DICT")

        # Use provided timeout or instance timeout
        model_timeout = timeout or self.timeout
        
        if issubclass(chat_model_class, ChatGoogleGenerativeAI):
            chat_model = ChatGoogleGenerativeAI(
                model=model,
                timeout=model_timeout
            ) if model_timeout else ChatGoogleGenerativeAI(model=model)
        elif issubclass(chat_model_class, ChatAnthropic):
            chat_model = ChatAnthropic(
                model=model,
                timeout=model_timeout
            ) if model_timeout else ChatAnthropic(model=model)
        elif issubclass(chat_model_class, ChatOpenAI):
            chat_model = ChatOpenAI(
                model_name=model,
                timeout=model_timeout
            ) if model_timeout else ChatOpenAI(model_name=model)

        if self.output_schema:
            chat_model = chat_model.with_structured_output(self.output_schema)
        return chat_model

    def get_fallback_chat_model(self) -> RunnableWithFallbacks:
        """
        Get the fallback chat model for the given model.
        If the model is found, return the fallback chat model.
        Return the runnable with fallbacks.
        """
        fallback_list: list[Runnable] = []
        for fallback_model in self.fallback_list:
            if fallback_model in MODEL_PROVIDER_DICT and fallback_model != self.model:
                fallback_list.append(self.get_chat_model(fallback_model, self.timeout))
        model: Runnable = self.get_chat_model(self.model, self.timeout)
        model: RunnableWithFallbacks = model.with_fallbacks(fallback_list)
        return model
