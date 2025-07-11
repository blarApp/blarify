import json
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

import json_repair
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from .chat_fallback import ChatFallback

logger = logging.getLogger(__name__)


STRUCTURED_PROMPT = """
Parse content to a structured output using the provided schema. If no clear information is provided, return the structure with empty values.

{content}
"""


class ReasoningEffort(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LLMProvider:
    dumb_agent_order = ["gpt-4.1-nano", "claude-3-5-haiku-latest", "gemini-2.5-flash-preview-05-20"]
    average_agent_order = ["gpt-4.1-nano", "claude-3-5-haiku-latest", "gemini-2.5-flash-preview-05-20"]
    reasoning_agent_order = ["o4-mini", "claude-sonnet-4-20250514", "gemini-2.5-pro-preview-06-05"]
    TIMEOUT = 80
    MAX_RETRIES = 3

    def __init__(self, reasoning_agent_order: Optional[List[str]] = None, reasoning_agent: Optional[str] = None):
        if reasoning_agent_order:
            self.reasoning_agent_order = reasoning_agent_order
        if reasoning_agent:
            self.reasoning_agent = reasoning_agent
        else:
            self.reasoning_agent = "o4-mini"
        self.dumb_agent = "gpt-4.1-nano"
        self.average_agent = "gpt-4.1-nano"

    def _invoke_agent(
        self,
        system_prompt: str,
        input_prompt: str,
        input_dict: Dict[str, Any],
        ai_model: str,
        fallback_list: Optional[List[str]] = None,
        output_schema: Optional[BaseModel] = None,
        messages: Optional[List[BaseMessage]] = None,
    ) -> Any:
        if not fallback_list:
            fallback_list = self.reasoning_agent_order

        model = ChatFallback(
            model=ai_model, fallback_list=fallback_list, output_schema=output_schema
        ).get_fallback_chat_model()

        prompt_list = [("system", system_prompt)]
        if messages:
            prompt_list.extend(messages)
        else:
            prompt_list.append(("human", input_prompt))

        chat_prompt = ChatPromptTemplate.from_messages(prompt_list)
        chain = chat_prompt | model
        response = chain.invoke(input_dict)

        return response

    def call_dumb_agent(
        self,
        system_prompt: str,
        input_dict: Dict[str, Any],
        output_schema: Optional[BaseModel] = None,
        ai_model: Optional[str] = None,
        input_prompt: Optional[str] = "Start",
    ) -> Any:
        if ai_model:
            return self._invoke_agent(
                input_prompt=input_prompt,
                input_dict=input_dict,
                ai_model=ai_model,
                output_schema=output_schema,
                system_prompt=system_prompt,
                fallback_list=self.dumb_agent_order,
            )
        return self._invoke_agent(
            input_prompt=input_prompt,
            input_dict=input_dict,
            ai_model=self.dumb_agent,
            output_schema=output_schema,
            system_prompt=system_prompt,
            fallback_list=self.dumb_agent_order,
        )

    def call_average_agent(
        self,
        input_dict: Dict[str, Any],
        output_schema: BaseModel,
        system_prompt: str,
        input_prompt: Optional[str] = "Start",
    ) -> Any:
        return self._invoke_agent(
            input_prompt=input_prompt,
            input_dict=input_dict,
            ai_model=self.average_agent,
            output_schema=output_schema,
            system_prompt=system_prompt,
            fallback_list=self.average_agent_order,
            messages=None,  # Explicitly pass None or rely on default
        )

    def call_agent_with_reasoning(
        self,
        system_prompt: str,
        input_dict: Dict[str, Any],
        output_schema: Optional[BaseModel] = None,
        input_prompt: Optional[str] = "Start",
        ai_model: Optional[str] = None,
        messages: Optional[List[BaseMessage]] = None,
    ) -> Any:
        model = ai_model if ai_model else self.reasoning_agent
        response = self._invoke_agent(
            input_prompt=input_prompt,
            input_dict=input_dict,
            ai_model=model,
            output_schema=None,
            system_prompt=system_prompt,
            messages=messages,
            fallback_list=self.reasoning_agent_order,
        )

        if output_schema:
            return self.parse_structured_output(response.content, output_schema)
        return response

    def call_react_agent(
        self,
        system_prompt: str,
        tools: List[BaseTool],
        input_dict: Dict[str, Any],
        messages: Optional[List[BaseMessage]],
        output_schema: Optional[BaseModel] = None,
        ai_model: Optional[str] = "gpt-4.1",
        checkpointer: Optional[PostgresSaver] = None,
        config: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
    ) -> Any:
        # Always use ChatPromptTemplate with system and human messages
        chat_prompt_messages = ChatPromptTemplate.from_messages(
            messages=[
                ("system", system_prompt),
            ]
            + messages
        )
        chat_prompt_messages_formated = chat_prompt_messages.format_messages(**input_dict)

        model = ChatFallback(
            model=ai_model, fallback_list=self.average_agent_order, output_schema=None
        ).get_fallback_chat_model()

        if name:
            react_agent = create_react_agent(model=model, tools=tools, checkpointer=checkpointer, name=name)
        else:
            react_agent = create_react_agent(
                model=model,
                tools=tools,
                checkpointer=checkpointer,
            )

        if not messages:
            messages = [("human", "Start")]

        default_config = {"recursion_limit": 50}
        if config is not None:
            default_config.update(config)

        logger.info("Invoking react agent with config")
        response = react_agent.invoke({"messages": chat_prompt_messages_formated}, default_config)

        if output_schema:
            return self.parse_structured_output(response["messages"][-1].content, output_schema)
        return response

    def _parse_structured_output(self, content: str, output_schema: BaseModel) -> Any:
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
                return output_schema(**parsed_content)
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

    def parse_structured_output(self, content: str, output_schema: BaseModel) -> Any:
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
