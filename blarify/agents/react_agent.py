import copy
import logging
from typing import List

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

logger = logging.getLogger(__name__)


class ReactMessagesState(MessagesState):
    current_reasoning: str


class ReactAgent:
    """
    ReAct architecture agent based on the paper:
    https://arxiv.org/abs/2210.03629

    This is a simple implementation of the ReAct architecture based on the LangGraph tutorial:
    https://langchain-ai.github.io/langgraph/how-tos/react-agent-from-scratch/?h=react#use-react-agent

    The modifications center in the uncapacity of OpenAI's models to handle the reasoning and tool calling in the same message. So, the agent is split into two parts:
    - The reasoner, which is the one that will handle the reasoning.
    - The tool caller, which is the one that will handle the tool calling.

    In this way the reasoning is always in the messages thread and the tool caller can focus on the tool calling.
    """

    def __init__(
        self,
        reasoner_prompt: str,
        tool_caller_prompt: str,
        stop_tools,
        tools,
        caller_specific_task: str,
    ):
        self.reasoner_prompt = reasoner_prompt
        self.tool_caller_prompt = tool_caller_prompt
        self.stop_tools_names: list[str] = [tool.name for tool in stop_tools]
        self.tools = tools
        self.caller_specific_task = caller_specific_task
        self.tools_by_name = {tool.name: tool for tool in tools}

        self.llm_caller = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-preview-05-20",
        ).with_fallbacks(
            [
                ChatOpenAI(
                    model_name="gpt-4.1-mini",
                )
            ]
        )

    def __should_continue(self, state: ReactMessagesState):
        messages = state["messages"]
        last_message = messages[-1]
        if last_message.tool_calls:
            if self.__should_stop(last_message.tool_calls):
                return "finish"
            return "tools"
        return END

    def __should_stop(self, tool_calls) -> bool:
        for tool_call in tool_calls:
            if tool_call["name"] in self.stop_tools_names:
                return True
        return False

    def __finish_tool_call(self, tool_calls) -> list[ToolMessage]:
        tool_messages = []
        for tool_call in tool_calls:
            tool = self.tools_by_name.get(tool_call["name"])
            if not tool:
                # In a real-world scenario, you might want to handle this case more gracefully.
                # For example, by returning an error message to the user.
                continue
            try:
                observation = tool.invoke(tool_call["args"])
                tool_messages.append(
                    ToolMessage(
                        content=str(observation),
                        tool_call_id=tool_call["id"],
                        name=tool_call["name"],
                    )
                )
            except Exception as e:
                tool_messages.append(
                    ToolMessage(
                        content=f"Error running tool {tool_call['name']}: {e}",
                        tool_call_id=tool_call["id"],
                        name=tool_call["name"],
                    )
                )
        return tool_messages

    def __call_finish(self, state: ReactMessagesState):
        messages = state["messages"]
        last_message = messages[-1]
        tool_messages = self.__finish_tool_call(last_message.tool_calls)
        return {"messages": tool_messages}

    def __call_reasoner(self, state: ReactMessagesState):
        messages = state["messages"]
        copy_messages = copy.deepcopy(messages)
        llm_reasoning = ChatOpenAI(
            model_name="gpt-4.1",
        )
        copy_messages[0].content = self.reasoner_prompt
        reasoning_response = llm_reasoning.invoke(copy_messages)

        return {"current_reasoning": reasoning_response.content}

    def __call_tool_caller(self, state: ReactMessagesState):
        messages = state["messages"]
        reasoning = state["current_reasoning"]
        copy_messages = copy.deepcopy(messages)

        copy_messages.append(AIMessage(content=f"### Reasoning\n\n{reasoning}"))
        copy_messages.append(HumanMessage(content=self.caller_specific_task))

        llm_caller_w_tools = self.llm_caller.bind_tools(self.tools)

        copy_messages[0].content = self.tool_caller_prompt
        tool_call_response = llm_caller_w_tools.invoke(copy_messages)

        if tool_call_response.content == "" and not tool_call_response.tool_calls:
            tool_call_response = self.__call_backup_tool_caller(copy_messages=copy_messages)

        if tool_call_response.tool_calls:
            tool_call_response.content = reasoning

        return {"messages": [tool_call_response]}

    def __call_backup_tool_caller(self, copy_messages: List[AnyMessage]) -> AIMessage:
        """
        Gemini 2.5 flash and pro sometimes return empty message
        https://discuss.ai.google.dev/t/gemini-2-5-pro-with-empty-response-text/81175/43
        """
        logger.info("Gemini returned an empty message in tool caller, switching to gpt")
        copy_messages.append(
            HumanMessage(content="Please provide an answer to the given question, by using the corresponding tool")
        )
        llm_reasoning = ChatOpenAI(
            model_name="gpt-4.1",
        )
        llm_caller_w_tools = llm_reasoning.bind_tools(self.tools)
        tool_call_response = llm_caller_w_tools.invoke(copy_messages)
        return tool_call_response

    def run(self, messages: list[AnyMessage]) -> list[AnyMessage]:
        workflow = StateGraph(ReactMessagesState)

        workflow.add_node("reasoner", self.__call_reasoner)
        workflow.add_node("tool_caller", self.__call_tool_caller)
        workflow.add_node("tools", ToolNode(tools=self.tools))
        workflow.add_node("finish", self.__call_finish)

        workflow.add_edge(START, "reasoner")
        workflow.add_edge("reasoner", "tool_caller")
        workflow.add_conditional_edges("tool_caller", self.__should_continue, ["tools", "finish", END])
        workflow.add_edge("tools", "reasoner")
        workflow.add_edge("finish", END)

        app = workflow.compile()

        config_dict = {"recursion_limit": 100}

        result = app.invoke(
            {
                "messages": messages,
            },
            config_dict,
        )
        return result.get("messages")
