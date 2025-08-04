import logging
from typing import List, Optional, TypedDict

from langchain.tools import tool
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from blarify.agents.react_agent import ReactAgent
from blarify.agents.tools.get_code_by_id_tool import GetCodeByIdTool
from blarify.agents.tools.get_file_context_tool import GetFileContextByIdTool
from blarify.agents.tools.find_nodes_by_code import FindNodesByCode
from blarify.agents.tools.find_nodes_by_name_and_type import FindNodesByNameAndType
from blarify.agents.tools.get_relationship_flowchart import GetRelationshipFlowchart
from blarify.agents.tools.directory_explorer_tool import DirectoryExplorerTool

from .prompts import (
    code_explorer_reasoner_system_prompt,
    code_explorer_tool_caller_system_prompt,
)

logger = logging.getLogger(__name__)


class CodeExplorationState(TypedDict):
    # node_info: Optional[NodeInfo]  # Removed undefined NodeInfo
    exploration_goal: str
    relevant_nodes: List[str]
    messages: Optional[List[AnyMessage]]
    iteration_count: int


class RelevantCodeSnippet:
    """Data class for relevant code snippets found during exploration."""

    def __init__(self, node_id: str, file_path: str, code_snippet: str, relevance_reason: str):
        self.node_id = node_id
        self.file_path = file_path
        self.code_snippet = code_snippet
        self.relevance_reason = relevance_reason


class CodeExplorer:
    """
    LangGraph workflow for exploring codebase to find relevant code snippets/files for a general exploration goal.
    This is a generalized version that can be used for various code exploration objectives beyond just task-based exploration.
    """

    def __init__(
        self,
        exploration_goal: str,
        company_id: str,
        company_graph_manager,
        initial_node_info = None,  # Remove NodeInfo type hint
        messages: Optional[List[AnyMessage]] = None,
    ):
        self.__exploration_goal = exploration_goal
        self.__company_id = company_id
        self.__company_graph_manager = company_graph_manager
        self.__diff_identifier = "0"
        self.__initial_node_info = initial_node_info
        self.__found_snippets = []
        self.__flagged_nodes = []
        self.__messages = messages
        # ReactAgent will be initialized when needed
        self.__react_agent = None

    def _initialize_react_agent(self):
        """Initialize the ReactAgent with the fixed tools."""
        self.__react_agent = ReactAgent(
            reasoner_prompt=code_explorer_reasoner_system_prompt,
            tool_caller_prompt=code_explorer_tool_caller_system_prompt,
            tools=self.__get_tools(),
            stop_tools=[
                self.__flag_relevant_nodes_tool(),
                self.__complete_exploration_tool(),
            ],
            caller_specific_task=self.__get_caller_specific_task(),
        )

    def __get_caller_specific_task(self) -> str:
        return """
Following the `### Reasoning` next action make one of the following:
  - Use the exploration tools to find relevant code snippets and files for the given exploration goal.
  - Search for patterns, configurations, and implementations that address the exploration objective.
  - Complete the exploration with a comprehensive summary of findings and insights.

Focus on generating a rich summary rather than just flagging individual nodes. The summary should provide clear answers to the exploration goal.
"""


    def __flag_relevant_nodes_tool(self) -> BaseTool:
        @tool
        def flag_relevant_nodes(nodes: List[dict]) -> str:
            """
            Flag nodes that are relevant for the exploration goal.

            Args:
                nodes: List of dicts with keys: node_id, file_path, relevance_reason, code_snippet_summary

            Each node should contain:
            - node_id: The unique identifier of the code node
            - file_path: Path to the file containing the code
            - relevance_reason: Why this code is relevant to the exploration goal
            - code_snippet_summary: Brief summary of what the code does
            """
            for node_data in nodes:
                snippet = RelevantCodeSnippet(
                    node_id=node_data["node_id"],
                    file_path=node_data["file_path"],
                    code_snippet=node_data.get("code_snippet_summary", ""),
                    relevance_reason=node_data["relevance_reason"],
                )
                self.__found_snippets.append(snippet)
                self.__flagged_nodes.append(node_data["node_id"])

            return f"Flagged {len(nodes)} relevant nodes for the exploration goal."

        return flag_relevant_nodes

    def __complete_exploration_tool(self) -> BaseTool:
        @tool
        def complete_exploration() -> str:
            """
            Complete the exploration and return the last reasoner message.
            """
            # Get the last message from the reasoner
            if self.__react_agent and self.__react_agent.last_reasoner_message:
                return self.__react_agent.last_reasoner_message
            return "No reasoner message available."

        return complete_exploration

    def __get_tools(self) -> List[BaseTool]:
        # Use selected repo ID (either provided or selected during repo selection)
        # current_repo_id = self.__selected_repo_id or self.__repo_id # Removed repository selection logic

        # Initialize directory explorer tool
        directory_explorer = DirectoryExplorerTool(
            company_graph_manager=self.__company_graph_manager,
            company_id=self.__company_id,
            repo_id="test",  # Use test repo_id to match main workflow
        )

        tools = [
            GetRelationshipFlowchart(
                company_id=self.__company_id,
                db_manager=self.__company_graph_manager,
                diff_identifier=self.__diff_identifier,
                handle_validation_error=True,
            ),
            GetCodeByIdTool(
                company_id=self.__company_id,
                db_manager=self.__company_graph_manager,
                diff_identifier=self.__diff_identifier,
                handle_validation_error=True,
            ),
            GetFileContextByIdTool(
                company_id=self.__company_id,
                db_manager=self.__company_graph_manager,
                handle_validation_error=True,
            ),
            FindNodesByCode(
                company_id=self.__company_id,
                db_manager=self.__company_graph_manager,
                diff_identifier=self.__diff_identifier,
                repo_id="test",  # Use test repo_id to match main workflow
                handle_validation_error=True,
            ),
            FindNodesByNameAndType(
                company_id=self.__company_id,
                db_manager=self.__company_graph_manager,
                diff_identifier=self.__diff_identifier,
                repo_id="test",  # Use test repo_id to match main workflow
                handle_validation_error=True,
            ),
            # Directory exploration tools
            directory_explorer.get_tool(),
            directory_explorer.get_find_repo_root_tool(),
            # Workflow control tools
            self.__flag_relevant_nodes_tool(),
            self.__complete_exploration_tool(),
        ]

        return tools

    def __get_node_info_str(self) -> str:
        if self.__initial_node_info:
            return self.__initial_node_info.as_str(include_diff_text=True)
        return "No initial node information provided."

    def __get_messages_list(self) -> List[AnyMessage]:
        """Get the conversation history as messages for the ReactAgent."""
        messages = [
            SystemMessage(content=code_explorer_reasoner_system_prompt),
            HumanMessage(
                content=f"""
Exploration Goal: {self.__exploration_goal}

Initial Context:
{self.__get_node_info_str()}

Please explore the codebase to find relevant code snippets and files that relate to this exploration goal.
Focus on:
1. Code patterns, architectures, and implementations relevant to the goal
2. Key files, functions, classes, and modules that provide insights
3. Related functionality that helps understand the codebase structure
4. Examples and best practices demonstrated in the code

Start by understanding the project structure and then systematically explore relevant areas based on the exploration objective.
"""
            ),
        ]

        # Add any additional messages if provided
        if self.__messages:
            messages.extend(self.__messages)

        return messages

    def run(self) -> tuple[List[RelevantCodeSnippet], List[AnyMessage], dict]:
        """
        Run the code exploration workflow.

        Returns:
            tuple: (relevant_snippets, messages, exploration_summary)
        """
        # Initialize ReactAgent
        self._initialize_react_agent()

        # Run the exploration
        messages = self.__react_agent.run(messages=self.__get_messages_list())

        exploration_summary = getattr(
            self,
            "_CodeExplorer__exploration_summary",
            {
                "summary": "Exploration completed",
                "insights": "No specific insights found",
                "flagged_nodes_count": len(self.__flagged_nodes),
                "relevant_snippets_count": len(self.__found_snippets),
            },
        )

        return self.__found_snippets, messages, exploration_summary

    def get_flagged_node_ids(self) -> List[str]:
        """Get the list of flagged node IDs."""
        return self.__flagged_nodes

    def get_relevant_snippets(self) -> List[RelevantCodeSnippet]:
        """Get the list of relevant code snippets."""
        return self.__found_snippets

    def get_selected_repo_id(self) -> Optional[str]:
        """Get the selected repository ID."""
        return None # Removed repository selection logic
