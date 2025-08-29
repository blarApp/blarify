import json
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import json_repair
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from .api_key_manager import APIKeyManager
from .rotating_provider import (
    RotatingKeyChatAnthropic,
    RotatingKeyChatGoogle,
    RotatingKeyChatOpenAI,
)
from .utils import discover_keys_for_provider

logger = logging.getLogger(__name__)


STRUCTURED_PROMPT = """
Parse content to a structured output using the provided schema. If no clear information is provided, return the structure with empty values.

{content}
"""


class ReasoningEffort(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


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


class LLMProvider:
    dumb_agent_order = ["gpt-4.1-nano", "claude-3-5-haiku-latest", "gemini-2.5-flash-preview-05-20"]
    average_agent_order = ["gpt-4.1-nano", "claude-3-5-haiku-latest", "gemini-2.5-flash-preview-05-20"]
    reasoning_agent_order = ["o4-mini", "claude-sonnet-4-20250514", "gemini-2.5-pro-preview-06-05"]
    TIMEOUT = 80
    MAX_RETRIES = 3

    # Mapping of providers to their rotating classes
    ROTATING_PROVIDER_MAP: Dict[str, Type[Any]] = {
        "openai": RotatingKeyChatOpenAI,
        "anthropic": RotatingKeyChatAnthropic,
        "google": RotatingKeyChatGoogle,
    }

    def __init__(self, reasoning_agent_order: Optional[List[str]] = None, reasoning_agent: Optional[str] = None):
        if reasoning_agent_order:
            self.reasoning_agent_order = reasoning_agent_order
        if reasoning_agent:
            self.reasoning_agent = reasoning_agent
        else:
            self.reasoning_agent = "o4-mini"
        self.dumb_agent = "gpt-4.1-nano"
        self.average_agent = "gpt-4.1-nano"
        # Cache for model instances to maintain metrics
        self._model_cache: Dict[Tuple[str, Optional[int], Optional[Type[BaseModel]]], Runnable[Any, Any]] = {}
        # Cache for API key managers
        self._api_key_managers: Dict[str, APIKeyManager] = {}

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

    def _get_or_create_api_key_manager(self, provider: str) -> APIKeyManager:
        """Get or create an APIKeyManager for the provider."""
        if provider not in self._api_key_managers:
            self._api_key_managers[provider] = APIKeyManager(provider, auto_discover=True)
        return self._api_key_managers[provider]

    def _create_rotating_model(
        self, model: str, provider: str, timeout: Optional[int] = None, output_schema: Optional[Type[BaseModel]] = None
    ) -> Runnable[Any, Any]:
        """Create a rotating model instance."""
        rotating_class = self.ROTATING_PROVIDER_MAP.get(provider)
        if not rotating_class:
            raise ValueError(f"No rotating provider available for {provider}")

        # Get or create APIKeyManager
        key_manager = self._get_or_create_api_key_manager(provider)

        # Get model kwargs based on provider
        model_kwargs: Dict[str, Any] = {
            "timeout": timeout or self.TIMEOUT,
        }

        # Different providers use different parameter names
        if provider == "anthropic":
            model_kwargs["model_name"] = model
        else:  # OpenAI and Google use 'model'
            model_kwargs["model"] = model

        # Create rotating provider instance
        chat_model = rotating_class(key_manager, **model_kwargs)

        if output_schema:
            chat_model = chat_model.with_structured_output(output_schema)

        return chat_model

    def _create_standard_model(
        self, model: str, timeout: Optional[int] = None, output_schema: Optional[Type[BaseModel]] = None
    ) -> Runnable[Any, Any]:
        """Create a standard (non-rotating) model instance."""
        if model not in MODEL_PROVIDER_DICT:
            raise ValueError(f"Model {model} not found in MODEL_PROVIDER_DICT")

        chat_model_class: Type[Union[ChatGoogleGenerativeAI, ChatAnthropic, ChatOpenAI]] = MODEL_PROVIDER_DICT[model]

        # Use provided timeout or instance timeout
        model_timeout = timeout or self.TIMEOUT

        chat_model: Any  # Will be one of the chat model types
        if issubclass(chat_model_class, ChatGoogleGenerativeAI):
            chat_model = (
                ChatGoogleGenerativeAI(model=model, timeout=model_timeout)
                if model_timeout
                else ChatGoogleGenerativeAI(model=model)
            )
        elif issubclass(chat_model_class, ChatAnthropic):
            if model_timeout:
                chat_model = ChatAnthropic(model_name=model, timeout=model_timeout, stop=None)
            else:
                chat_model = ChatAnthropic(model_name=model, timeout=None, stop=None)
        elif issubclass(chat_model_class, ChatOpenAI):
            chat_model = ChatOpenAI(model=model, timeout=model_timeout) if model_timeout else ChatOpenAI(model=model)
        else:
            raise ValueError(f"Unsupported chat model class for model {model}")

        if output_schema:
            chat_model = chat_model.with_structured_output(output_schema)

        return chat_model

    def _get_or_create_model(
        self, model: str, timeout: Optional[int] = None, output_schema: Optional[Type[BaseModel]] = None
    ) -> Runnable[Any, Any]:
        """Get cached model or create new one with rotation if multiple keys exist."""
        # Create cache key
        cache_key = (model, timeout, output_schema)

        # Return cached model if available
        if cache_key in self._model_cache:
            return self._model_cache[cache_key]

        # Check if model exists
        if model not in MODEL_PROVIDER_DICT:
            raise ValueError(f"Model {model} not found in MODEL_PROVIDER_DICT")

        # Determine provider and check for multiple keys
        provider = self._get_provider_from_model(model)
        if provider:
            keys = discover_keys_for_provider(provider)
            if len(keys) > 1:
                logger.info(f"Found {len(keys)} keys for {provider}, using rotation for {model}")
                model_instance = self._create_rotating_model(model, provider, timeout, output_schema)
            else:
                model_instance = self._create_standard_model(model, timeout, output_schema)
        else:
            model_instance = self._create_standard_model(model, timeout, output_schema)

        # Cache the model instance
        self._model_cache[cache_key] = model_instance
        return model_instance

    def _invoke_agent(
        self,
        system_prompt: str,
        input_prompt: str,
        input_dict: Dict[str, Any],
        ai_model: str,
        output_schema: Optional[Type[BaseModel]] = None,
        messages: Optional[List[BaseMessage]] = None,
        tools: Optional[List[BaseTool]] = None,
        config: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        # Get or create the model with rotation support if multiple keys exist
        model = self._get_or_create_model(ai_model, timeout, output_schema)

        # Bind tools to model if provided
        if tools:
            model = model.bind_tools(tools)  # type: ignore

        prompt_list: List[Tuple[str, str]] = [("system", system_prompt)]
        if messages:
            # Convert BaseMessage objects to tuples
            for msg in messages:
                # Use type to determine role
                if hasattr(msg, "__class__"):
                    role = msg.__class__.__name__.lower().replace("message", "")
                    if role == "human":
                        prompt_list.append(("human", str(msg.content)))
                    elif role == "ai" or role == "assistant":
                        prompt_list.append(("assistant", str(msg.content)))
                    elif role == "system":
                        prompt_list.append(("system", str(msg.content)))
                    else:
                        prompt_list.append(("human", str(msg.content)))
                elif hasattr(msg, "content"):
                    # Default to 'human' role if not specified
                    prompt_list.append(("human", str(msg.content)))
        else:
            prompt_list.append(("human", input_prompt))

        chat_prompt = ChatPromptTemplate.from_messages(prompt_list)
        chain = chat_prompt | model
        response = chain.invoke(input_dict, config=config)  # type: ignore

        return response

    def call_dumb_agent(
        self,
        system_prompt: str,
        input_dict: Dict[str, Any],
        output_schema: Optional[Type[BaseModel]] = None,
        ai_model: Optional[str] = None,
        input_prompt: str = "Start",
        config: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        model_to_use = ai_model if ai_model else self.dumb_agent
        response = self._invoke_agent(
            input_prompt=input_prompt,
            input_dict=input_dict,
            ai_model=model_to_use,
            output_schema=output_schema,
            system_prompt=system_prompt,
            config=config,
            timeout=timeout,
        )

        if hasattr(response, "content"):
            return response.content
        return response

    def call_average_agent(
        self,
        input_dict: Dict[str, Any],
        output_schema: Optional[Type[BaseModel]],
        system_prompt: str,
        input_prompt: str = "Start",
        tools: Optional[List[BaseTool]] = None,
        config: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        if tools:
            # Use reasoning agent when tools are provided
            return self.call_agent_with_reasoning(
                system_prompt=system_prompt,
                input_dict=input_dict,
                output_schema=output_schema,
                input_prompt=input_prompt,
                ai_model=self.average_agent,
                tools=tools,
                config=config,
                timeout=timeout,
            )
        return self._invoke_agent(
            input_prompt=input_prompt,
            input_dict=input_dict,
            ai_model=self.average_agent,
            output_schema=output_schema,
            system_prompt=system_prompt,
            messages=None,
            config=config,
            timeout=timeout,
        )

    def call_agent_with_reasoning(
        self,
        system_prompt: str,
        input_dict: Dict[str, Any],
        output_schema: Optional[Type[BaseModel]] = None,
        input_prompt: str = "Start",
        ai_model: Optional[str] = None,
        messages: Optional[List[BaseMessage]] = None,
        tools: Optional[List[BaseTool]] = None,
        config: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        model = ai_model if ai_model else self.reasoning_agent

        response = self._invoke_agent(
            input_prompt=input_prompt,
            input_dict=input_dict,
            ai_model=model,
            output_schema=None,  # Handle structured output separately
            system_prompt=system_prompt,
            messages=messages,
            tools=tools,
            config=config,
            timeout=timeout,
        )

        if output_schema:
            return self.parse_structured_output(response.content, output_schema)
        return response

    def _parse_structured_output(self, content: str, output_schema: Type[BaseModel]) -> Any:
        try:
            # Try to handle content that might contain markdown code blocks with JSON
            if content.startswith("```json"):
                # Extract JSON between ```json and ``` markers
                json_content = content.split("```json")[1].split("```")[0].strip()
                parsed_content = json_repair.loads(json_content)
            elif content.startswith("```"):
                # Extract content from any code block
                json_content = content.split("```")[1].split("```")[0].strip()
                parsed_content = json_repair.loads(json_content)
            else:
                # Try parsing the content directly
                parsed_content = json_repair.loads(content)

            if isinstance(parsed_content, dict):
                return output_schema.model_validate(parsed_content)
            else:
                logger.warning(f"Parsed content is not a dictionary: {type(parsed_content)}")
                logger.warning(f"Expected output schema: {output_schema}")
                raise ValueError("Parsed content is not in the expected format")
        except (json.JSONDecodeError, IndexError) as e:
            logger.warning(f"Failed to parse JSON from content: {e}")
            raise
        except Exception as e:
            logger.warning(f"Error creating output schema from parsed content: {e}")
            raise

    def parse_structured_output(self, content: str, output_schema: Type[BaseModel]) -> Any:
        """First try to parse the content using the output schema. If it fails use the dumb agent to parse it."""
        try:
            return self._parse_structured_output(content=content, output_schema=output_schema)
        except Exception as e:
            logger.info(f"Failed to directly parse structured output: {e}. Using dumb agent as fallback.")
            return self.call_dumb_agent(
                system_prompt=STRUCTURED_PROMPT,
                input_dict={"content": content},
                output_schema=output_schema,
                ai_model="gpt-4.1-nano",
            )
