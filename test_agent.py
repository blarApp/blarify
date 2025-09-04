#!/usr/bin/env python3
"""
Interactive terminal agent for querying the Blarify code graph using LangChain.

This agent provides a command-line interface to interact with the code graph
using all available Blarify tools with ChatOpenAI.
"""

import os
import sys
from typing import List
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.markdown import Markdown

# Add blarify to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import BaseTool

from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.tools import (
    GetCodeByIdTool,
    GetFileContextByIdTool,
    GetBlameByIdTool,
    DirectoryExplorerTool,
    FindNodesByCode,
    FindNodesByNameAndType,
    FindNodesByPath,
    GetRelationshipFlowchart,
    GetNodeWorkflowsTool,
)

console = Console()


class InteractiveCodeAgent:
    """Interactive agent for querying code graph using LangChain and ChatOpenAI."""

    def __init__(self, entity_id: str = "test", repo_id: str = "test"):
        """Initialize the agent with Blarify tools."""
        self.entity_id = entity_id
        self.repo_id = repo_id

        # Initialize database manager with entity_id and repo_id
        self.db_manager = Neo4jManager(entity_id=entity_id, repo_id=repo_id)

        # Initialize Blarify tools (they already inherit from BaseTool)
        self.tools: List[BaseTool] = [
            GetCodeByIdTool(db_manager=self.db_manager),
            GetFileContextByIdTool(db_manager=self.db_manager),
            GetBlameByIdTool(db_manager=self.db_manager, repo_owner="blarApp", repo_name="blarify"),
            DirectoryExplorerTool(db_manager=self.db_manager),
            FindNodesByCode(db_manager=self.db_manager),
            FindNodesByNameAndType(db_manager=self.db_manager),
            FindNodesByPath(db_manager=self.db_manager),
            GetRelationshipFlowchart(db_manager=self.db_manager),
            GetNodeWorkflowsTool(db_manager=self.db_manager),
        ]

        # Initialize ChatOpenAI
        self.llm = ChatOpenAI(model="gpt-5-mini", streaming=False)

        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a helpful code analysis assistant that helps users explore and understand a codebase.
            You have access to tools that can search for code, show file contents, explore directory structures, and analyze relationships between code components.
            
            When answering questions:
            1. Use the find_nodes_by_name_and_type, find_nodes_by_path, or find_nodes_by_code tools to search for relevant code first
            2. Use get_code_by_id to show specific implementations when you have a node_id
            3. Use directory_explorer to understand project structure
            4. Use get_relationship_flowchart to show dependencies
            5. Use get_file_context_by_id to see the context around a specific node
            6. Use get_blame_by_id to see git history information
            7. Use get_node_workflows to understand which workflows a node participates in and its execution context
            
            Node IDs are 32-character hexadecimal strings (like UUIDs).
            
            Always provide clear, concise answers with relevant code examples when appropriate.
            """,
                ),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        # Create agent
        self.agent = create_openai_tools_agent(self.llm, self.tools, self.prompt)

        # Create agent executor
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            max_iterations=5,
            handle_parsing_errors=True,
            return_intermediate_steps=True,
        )

        # Chat history
        self.chat_history = []

    def display_welcome(self):
        """Display welcome message."""
        welcome_text = f"""
# Blarify Code Graph AI Agent

Welcome! I'm an AI assistant that can help you explore and understand the codebase.

**Connected to:**
- Entity ID: {self.entity_id}
- Repo ID: {self.repo_id}

## Available Tools:

- **find_nodes_by_name_and_type**: Search for functions, classes, and files by name and type
- **find_nodes_by_path**: Find nodes by file path pattern
- **find_nodes_by_code**: Search for nodes containing specific code snippets
- **get_code_by_id**: Display the full code of a node by its ID
- **get_file_context_by_id**: Show the file context around a node
- **get_blame_by_id**: Show git blame information for a node
- **get_relationship_flowchart**: Display dependencies and relationships
- **directory_explorer**: Explore the directory structure
- **get_node_workflows**: Discover which workflows a code node participates in

## Example questions:

- "Show me all functions with 'process' in the name"
- "Find the BottomUpBatchProcessor class and show its code"
- "What files are in the documentation folder?"
- "Show me functions that call process_node"
- "Find code that contains 'def process_node'"
- "Show the directory structure of /blarify/tools"
- "What workflows does the process_node function participate in?"

Type 'quit' or 'exit' to leave, 'clear' to clear the screen, 'help' for this message.
"""
        console.print(Panel(Markdown(welcome_text), title="Welcome", border_style="blue"))

    def run_query(self, query: str) -> str:
        """Run a query through the agent."""
        try:
            result = self.agent_executor.invoke(
                {
                    "input": query,
                    "chat_history": self.chat_history,
                }
            )

            # Update chat history
            self.chat_history.append(HumanMessage(content=query))
            self.chat_history.append(AIMessage(content=result["output"]))

            # Keep chat history limited to last 10 exchanges
            if len(self.chat_history) > 20:
                self.chat_history = self.chat_history[-20:]

            return result["output"]
        except Exception as e:
            return f"Error processing query: {str(e)}"

    def run(self):
        """Run the interactive agent."""
        self.display_welcome()

        while True:
            try:
                query = Prompt.ask("\n[bold blue]Ask me about the code>[/bold blue]")

                if query.lower() in ["quit", "exit", "q"]:
                    console.print("[green]Goodbye![/green]")
                    break

                if query.lower() == "clear":
                    console.clear()
                    self.display_welcome()
                    continue

                if query.lower() == "help":
                    self.display_welcome()
                    continue

                # Process the query
                console.print("[yellow]Analyzing...[/yellow]\n")
                response = self.run_query(query)

                # Display response
                console.print(Panel(Markdown(response), title="Response", border_style="green"))

            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'quit' or 'exit' to leave[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")


def main():
    """Main entry point."""
    import argparse

    # Configure logging to show DEBUG level messages
    # logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(description="Interactive Blarify Code Graph AI Agent")
    parser.add_argument("--entity-id", default="test", help="Entity ID for the graph (default: test)")
    parser.add_argument("--repo-id", default="test", help="Repository ID for the graph (default: test)")

    args = parser.parse_args()

    # Check for OpenAI API key
    if not os.environ.get("OPENAI_API_KEY"):
        console.print("[red]Error: OPENAI_API_KEY environment variable not set[/red]")
        console.print("Please set your OpenAI API key: export OPENAI_API_KEY='your-key-here'")
        sys.exit(1)

    try:
        agent = InteractiveCodeAgent(entity_id=args.entity_id, repo_id=args.repo_id)
        agent.run()
    except Exception as e:
        console.print(f"[red]Failed to initialize agent: {e}[/red]")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
