#!/usr/bin/env python3
"""
Interactive terminal agent for querying the Blarify code graph using LangGraph.

This agent provides a command-line interface to interact with the code graph
using all available Blarify tools with LangGraph's prebuilt ReAct agent.
"""

import os
import sys
from typing import List, Dict, Any
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.markdown import Markdown

# Add blarify to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_openai import ChatOpenAI
from langchain_core.tools import BaseTool
from langchain_core.messages import BaseMessage
from langgraph.prebuilt import create_react_agent

from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.tools import (
    FindSymbols,
    VectorSearch,
    GetCodeAnalysis,
    GetExpandedContext,
    GetBlameInfo,
    GetDependencyGraph,
    GetFileContextByIdTool,
    GetNodeWorkflowsTool,
)

console = Console()


class InteractiveCodeAgent:
    """Interactive agent for querying code graph using LangGraph and ChatOpenAI."""

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
            VectorSearch(db_manager=self.db_manager),
            GetCodeAnalysis(db_manager=self.db_manager),
            GetExpandedContext(db_manager=self.db_manager),
            GetBlameInfo(db_manager=self.db_manager, repo_owner="blarApp", repo_name="blar-nextjs-front"),
            GetDependencyGraph(db_manager=self.db_manager),
            GetFileContextByIdTool(db_manager=self.db_manager),
            GetNodeWorkflowsTool(db_manager=self.db_manager),
        ]

        # Initialize ChatOpenAI
        self.llm = ChatOpenAI(model="gpt-5", streaming=False)

        # Create system prompt for the agent
        system_prompt = """You are a helpful code analysis assistant that helps users explore and understand a codebase.
You have access to tools that can search for code symbols, analyze code, explore dependencies, and retrieve git history information.

CRITICAL STOPPING RULE:
- Once you have gathered sufficient information to answer the user's question, STOP calling tools and provide your answer
- Do not call additional tools just to "explore more" - only call tools when needed to answer the specific question
- Be efficient: use the minimum number of tool calls necessary
- After each tool call, evaluate: "Do I now have enough information to answer?" If yes, STOP and answer

SEARCH WORKFLOW - CRITICAL:
- For exploratory questions where you don't know exact symbol names (e.g., "find the code that handles authentication", "where is database connection logic"), use vector_search with relevant keywords
- For precise lookups when you already know the exact name (e.g., "find the process_batch function"), use find_symbols directly
- STOP after you get the information needed - don't keep calling tools unnecessarily

AVAILABLE TOOLS:
1. vector_search: Semantic search over AI-generated descriptions of code scopes. Use for exploratory questions when you don't know exact symbol names.
2. find_symbols: Search for specific symbols by EXACT name match. Use when you know the exact name.
3. get_code_analysis: Get complete code implementation with relationships and dependencies
4. get_expanded_context: Get the full context around a code symbol including all nested references
5. get_dependency_graph: Visualize dependencies with Mermaid diagrams
6. get_blame_info: See GitHub-style blame information showing who last modified each line
7. get_file_context_by_id: See the file context around a specific node
8. get_node_workflows: Understand which workflows a node participates in and its execution context

EXAMPLE WORKFLOWS:

User: "Find the code that processes batch operations"
Correct approach:
1. vector_search(query="batch processing operations")
2. [Results show: BottomUpBatchProcessor class, process_batch function]
3. find_symbols(name="BottomUpBatchProcessor", type="CLASS") -> Gets the reference_id and location
4. STOP and provide answer with the location and reference_id
[Only call get_code_analysis if user explicitly asks to see the implementation]

User: "Show me the GraphBuilder class"
Correct approach:
1. find_symbols(name="GraphBuilder", type="CLASS") -> Gets the reference_id and location
2. STOP and provide answer with the location and reference_id
[User already knows exact name, skip vector_search. Only get implementation if explicitly requested]

User: "Show me the implementation of GraphBuilder"
Correct approach:
1. find_symbols(name="GraphBuilder", type="CLASS") -> Gets the reference_id
2. get_code_analysis(reference_id=...) -> Gets the implementation
3. STOP and provide the implementation

Reference IDs (handles) are 32-character hexadecimal strings that uniquely identify code symbols.
You can provide either a reference_id OR (file_path AND symbol_name) to most tools.

Always provide clear, concise answers with relevant code examples when appropriate.
"""

        # Create LangGraph ReAct agent
        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_prompt,
        )

        # Initialize chat history
        self.chat_history: List[BaseMessage] = []

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
- **vector_search**: Semantic search over AI-generated descriptions of code scopes using vector similarity
- **get_code_analysis**: Get complete code implementation with relationships and dependencies
- **get_expanded_context**: Get full context around a symbol including all nested references
- **get_dependency_graph**: Generate Mermaid diagrams showing dependencies and relationships
- **get_blame_info**: Show GitHub-style blame information for code (who modified each line)
- **get_file_context_by_id**: Show the file context around a specific node
- **get_node_workflows**: Discover which workflows a code node participates in

## Example questions:

- "Find the BottomUpBatchProcessor class"
- "Search for batch processing code"
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
            # Add the new user message to chat history
            new_message: tuple[str, str] = ("user", query)
            messages: List[tuple[str, str] | BaseMessage] = [*self.chat_history, new_message]

            # Track tool calls to detect loops
            tool_call_history: List[Dict[str, Any]] = []
            iteration_count: int = 0

            # Stream the agent's execution to show progress
            console.print("[dim]Agent is thinking and calling tools...[/dim]\n")

            final_messages: List[BaseMessage] = []

            for chunk in self.agent.stream(
                {"messages": messages},
                config={"recursion_limit": 50, "reasoning": {"effort": "minimal", "summary": "auto"}},
            ):
                iteration_count += 1

                # Extract agent or tool messages from chunk
                if "agent" in chunk:
                    agent_messages = chunk["agent"]["messages"]
                    for msg in agent_messages:
                        # Display reasoning/thinking tokens if present (GPT-5)
                        if hasattr(msg, "response_metadata") and "reasoning_content" in msg.response_metadata:
                            reasoning = msg.response_metadata["reasoning_content"]
                            console.print(
                                Panel(
                                    f"[yellow]{reasoning}[/yellow]", title="🧠 Chain of Thought", border_style="yellow"
                                )
                            )

                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tool_call in msg.tool_calls:
                                tool_name = tool_call.get("name", "unknown")
                                tool_args = tool_call.get("args", {})

                                # Track this tool call
                                tool_call_history.append(
                                    {"iteration": iteration_count, "tool": tool_name, "args": tool_args}
                                )

                                # Display tool call
                                console.print(f"[cyan]→ Step {iteration_count}: Calling {tool_name}[/cyan]")

                                # Check for loops (same tool called 3+ times in last 5 calls)
                                if len(tool_call_history) >= 5:
                                    recent_tools = [tc["tool"] for tc in tool_call_history[-5:]]
                                    if recent_tools.count(tool_name) >= 3:
                                        console.print(
                                            f"[yellow]⚠ Warning: {tool_name} called {recent_tools.count(tool_name)} times recently - possible loop![/yellow]"
                                        )

                if "tools" in chunk:
                    tool_messages = chunk["tools"]["messages"]
                    for msg in tool_messages:
                        # Show abbreviated tool result
                        if hasattr(msg, "content"):
                            content_preview = str(msg.content)[:100]
                            console.print(f"[dim]  ← Tool returned: {content_preview}...[/dim]")

                # Collect all messages
                for key in chunk:
                    if "messages" in chunk[key]:
                        final_messages.extend(chunk[key]["messages"])

            # Extract the final response from the messages
            final_message = final_messages[-1] if final_messages else None

            if not final_message:
                return "Error: No response from agent"

            # Handle content which can be str or list
            if hasattr(final_message, "content"):
                content = final_message.content
                response_content: str = content if isinstance(content, str) else str(content)
            else:
                response_content = str(final_message)

            # Display summary
            console.print(
                f"\n[green]✓ Completed in {iteration_count} iterations with {len(tool_call_history)} tool calls[/green]\n"
            )

            # Update chat history with all messages from this turn
            self.chat_history = final_messages

            # Keep chat history limited to last 20 messages
            if len(self.chat_history) > 20:
                self.chat_history = self.chat_history[-20:]

            return response_content
        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            return f"Error processing query: {str(e)}\n\nDetails:\n{error_details}"

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
