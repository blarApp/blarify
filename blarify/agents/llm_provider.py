import json
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

import json_repair
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool
from pydantic import BaseModel
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate

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
        tools: Optional[List[BaseTool]] = None,
    ) -> Any:
        if not fallback_list:
            fallback_list = self.reasoning_agent_order

        model = ChatFallback(
            model=ai_model, fallback_list=fallback_list, output_schema=output_schema
        ).get_fallback_chat_model()

        # Bind tools to model if provided
        if tools:
            model = model.bind_tools(tools)

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
        tools: Optional[List[BaseTool]] = None,
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
            )
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
        tools: Optional[List[BaseTool]] = None,
    ) -> Any:
        model = ai_model if ai_model else self.reasoning_agent

        # Use _invoke_agent with tools instead of call_react_agent
        response = self._invoke_agent(
            input_prompt=input_prompt,
            input_dict=input_dict,
            ai_model=model,
            output_schema=None,
            system_prompt=system_prompt,
            messages=messages,
            fallback_list=self.reasoning_agent_order,
            tools=tools,  # Pass tools to _invoke_agent
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
        main_model: Optional[str] = "gpt-4.1",
        tool_model: Optional[str] = "gpt-4.1-nano",
        config: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
    ) -> Any:
        # Get the model with fallback
        model = ChatFallback(
            model=main_model or self.reasoning_agent, fallback_list=self.reasoning_agent_order
        ).get_fallback_chat_model()

        # Create React agent prompt template
        # Use PromptTemplate since ChatPromptTemplate has issues with agent_scratchpad
        react_prompt = PromptTemplate(
            template="""You are an assistant that can use tools to accomplish tasks.

{system_prompt}

You have access to the following tools:
{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
{agent_scratchpad}""",
            input_variables=["input", "agent_scratchpad", "system_prompt", "tools", "tool_names"],
        )

        # Create LangChain React agent
        react_agent = create_react_agent(model, tools, react_prompt)

        # Create agent executor
        agent_executor = AgentExecutor(
            agent=react_agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=10,
        )

        # Format the input from messages using ChatPromptTemplate for proper separation
        if messages:
            # Extract the human message content
            human_message = messages[-1] if messages else None
            if human_message and hasattr(human_message, "content"):
                input_text = human_message.content
            else:
                input_text = str(human_message)
        else:
            input_text = "Complete the analysis using the available tools."

        # Format the input text with input_dict
        formatted_input = input_text.format(**input_dict) if input_dict else input_text

        logger.info("Invoking LangChain React agent with separated system and human messages")
        response = agent_executor.invoke({"input": formatted_input, "system_prompt": system_prompt})

        # Extract final response
        if response and "output" in response:
            output_content = response["output"]
            if output_schema:
                return self.parse_structured_output(output_content, output_schema)
            # Return in the expected format
            return {"messages": [type("Message", (), {"content": output_content})()]}

        return {"messages": []}

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
