"""
Tool for executing code exploration using the CodeExplorer workflow.
"""

import logging
from typing import List

from langchain.tools import tool
from langchain_core.tools import BaseTool

from blarify.agents.code_explorer.workflow import CodeExplorer, RelevantCodeSnippet

logger = logging.getLogger(__name__)


class CodeExplorerTool:
    """Tool for executing code exploration workflows."""

    def __init__(self, company_id: str, company_graph_manager):
        self.company_graph_manager = company_graph_manager
        self.company_id = str(company_id)

    def get_tool(self) -> BaseTool:
        """Get the code exploration tool."""

        @tool
        def explore_codebase(exploration_goal: str) -> str:
            """
            Explore the codebase to find relevant code snippets and files for a specific goal.

            This tool systematically explores the codebase to find relevant patterns, files, and components
            that address the given exploration objective.

            Args:
                exploration_goal: What you want to explore in the codebase (e.g., "Find authentication patterns",
                                "Understand database interaction layers", "Locate error handling code")

            Returns:
                A formatted summary of the exploration results including relevant code snippets and insights.
            """
            try:
                logger.info(f"Starting code exploration for goal: {exploration_goal}")

                # Initialize CodeExplorer
                explorer = CodeExplorer(
                    exploration_goal=exploration_goal,
                    company_id=self.company_id,
                    company_graph_manager=self.company_graph_manager,
                    initial_node_info=None,  # No initial node context
                    messages=None  # No prior conversation history
                )

                # Run the exploration
                snippets, messages, summary = explorer.run()

                # Format the results
                result = self._format_exploration_results(
                    exploration_goal=exploration_goal,
                    snippets=snippets,
                    summary=summary,
                )

                logger.info(
                    f"Code exploration completed. Found {len(snippets)} relevant snippets."
                )
                return result

            except Exception as e:
                error_msg = f"Error during code exploration: {str(e)}"
                logger.error(error_msg)
                return error_msg

        return explore_codebase

    def _format_exploration_results(
        self,
        exploration_goal: str,
        snippets: List[RelevantCodeSnippet],
        summary: dict,
    ) -> str:
        """Format the exploration results into a readable summary."""

        result_parts = []

        # Header
        result_parts.append("# Code Exploration Results")
        result_parts.append(f"**Goal:** {exploration_goal}")
        result_parts.append("")

        # Summary section
        if summary.get("summary"):
            result_parts.append("## Summary")
            result_parts.append(summary["summary"])
            result_parts.append("")

        # Insights section
        if summary.get("insights"):
            result_parts.append("## Key Insights")
            result_parts.append(summary["insights"])
            result_parts.append("")

        # Remove relevant code snippets section
        # Statistics
        result_parts.append("## Exploration Statistics")
        result_parts.append(f"- Flagged nodes: {summary.get('flagged_nodes_count', 0)}")
        # Remove relevant snippets count from statistics
        if summary.get("error"):
            result_parts.append(f"- Error: {summary['error']}")

        return "\n".join(result_parts)
