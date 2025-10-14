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
    FindSymbols,
    SearchDocumentation,
    GetCodeAnalysis,
    GetExpandedContext,
    GetBlameInfo,
    GetDependencyGraph,
    GetFileContextByIdTool,
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
        self.db_manager = Neo4jManager(
            entity_id=entity_id,
            repo_id=repo_id,
        )

        # Test connection before proceeding
        self._test_connection()

        # Initialize Blarify tools (they already inherit from BaseTool)
        self.tools: List[BaseTool] = [
            FindSymbols(db_manager=self.db_manager),
            SearchDocumentation(db_manager=self.db_manager),
            GetCodeAnalysis(db_manager=self.db_manager),
            GetExpandedContext(db_manager=self.db_manager),
            GetBlameInfo(db_manager=self.db_manager, repo_owner="blarApp", repo_name="blar-nextjs-front"),
            GetDependencyGraph(db_manager=self.db_manager),
            GetFileContextByIdTool(db_manager=self.db_manager),
            GetNodeWorkflowsTool(db_manager=self.db_manager),
        ]

        # Initialize ChatOpenAI
        self.llm = ChatOpenAI(model="gpt-5", streaming=False)

        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a helpful code analysis assistant that helps users explore and understand a codebase.
            You have access to tools that can search for code symbols, analyze code, explore dependencies, and retrieve git history information.
            
            When answering questions:
            1. Use find_symbols to search for specific functions, classes, files, or folders by exact name
            2. Use search_documentation to semantically search through AI-generated documentation for symbols
            3. Use get_code_analysis to get complete code implementation with relationships and dependencies
            4. Use get_expanded_context to get the full context around a code symbol including all nested references
            5. Use get_dependency_graph to visualize dependencies with Mermaid diagrams
            6. Use get_blame_info to see GitHub-style blame information showing who last modified each line
            7. Use get_file_context_by_id to see the file context around a specific node
            8. Use get_node_workflows to understand which workflows a node participates in and its execution context
            
            Reference IDs (handles) are 32-character hexadecimal strings that uniquely identify code symbols.
            You can provide either a reference_id OR (file_path AND symbol_name) to most tools.
            
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

    def _test_connection(self):
        """Test the Neo4j database connection and print credentials."""
        console.print("\n[yellow]Testing database connection...[/yellow]")

        # Print connection credentials
        uri = os.environ.get("NEO4J_URI", "Not set")
        username = os.environ.get("NEO4J_USERNAME", "Not set")
        password = os.environ.get("NEO4J_PASSWORD", "Not set")

        console.print(
            Panel(
                f"""[bold]Neo4j Connection Credentials:[/bold]
            
URI: {uri}
Username: {username}
Password: {password}
Entity ID: {self.entity_id}
Repo ID: {self.repo_id}""",
                title="Connection Info",
                border_style="cyan",
            )
        )

        try:
            # Test the connection by running a simple query
            with self.db_manager.driver.session() as session:
                result = session.run("RETURN 1 as test")
                result.single()

            console.print("[green]✓ Database connection successful![/green]\n")
        except Exception as e:
            console.print(f"[red]✗ Database connection failed: {str(e)}[/red]\n")
            raise RuntimeError(f"Failed to connect to Neo4j database: {str(e)}")

    def display_welcome(self):
        """Display welcome message."""
        welcome_text = f"""
# Blarify Code Graph AI Agent

Welcome! I'm an AI assistant that can help you explore and understand the codebase.

**Connected to:**
- Entity ID: {self.entity_id}
- Repo ID: {self.repo_id}

## Available Tools:

- **find_symbols**: Search for code symbols (functions, classes, files, or folders) by exact name
- **search_documentation**: Semantic search through AI-generated documentation using vector similarity
- **get_code_analysis**: Get complete code implementation with relationships and dependencies
- **get_expanded_context**: Get full context around a symbol including all nested references
- **get_dependency_graph**: Generate Mermaid diagrams showing dependencies and relationships
- **get_blame_info**: Show GitHub-style blame information for code (who modified each line)
- **get_file_context_by_id**: Show the file context around a specific node
- **get_node_workflows**: Discover which workflows a code node participates in

## Example questions:

- "Find the BottomUpBatchProcessor class"
- "Search documentation for batch processing"
- "Show me the code analysis for the process_node function in file path blarify/tools/process.py"
- "Get expanded context for reference ID abc123..."
- "Show me a dependency graph for the GraphBuilder class"
- "Who last modified the create_graph function?"
- "What workflows does the process_node function participate in?"

## How to specify code elements:

Most tools accept either:
- **reference_id**: A 32-character hexadecimal identifier (tool handle)
- **file_path + symbol_name**: The file path and symbol name together

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
