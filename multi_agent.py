#!/usr/bin/env python3
"""
Multi-agent system for querying across frontend and backend codebases.

This system coordinates multiple specialized agents that can communicate with
each other to answer questions spanning different codebases.
"""

import os
import sys
from typing import List, Dict, Any
from enum import Enum
import operator
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.markdown import Markdown

# Add blarify to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_openai import ChatOpenAI
from langchain_core.tools import BaseTool
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from typing_extensions import TypedDict, Annotated

from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.tools import (
    FindSymbols,
    VectorSearch,
    GrepCode,
    GetCodeAnalysis,
    GetExpandedContext,
    GetBlameInfo,
    GetDependencyGraph,
    GetFileContextByIdTool,
    GetNodeWorkflowsTool,
)

console = Console()


class AgentType(str, Enum):
    """Types of specialized agents."""

    FRONTEND = "frontend"
    BACKEND = "backend"


class MultiAgentState(TypedDict):
    """Shared state across all agents."""

    messages: Annotated[List[BaseMessage], operator.add]
    next_agent: str
    frontend_findings: List[str]
    backend_findings: List[str]
    user_query: str
    iteration_count: int


class PartialMultiAgentState(TypedDict, total=False):
    """Partial state updates - all fields optional."""

    messages: Annotated[List[BaseMessage], operator.add]
    next_agent: str
    frontend_findings: List[str]
    backend_findings: List[str]
    user_query: str
    iteration_count: int


class SpecializedCodeAgent:
    """A specialized agent for a specific codebase (frontend or backend)."""

    def __init__(
        self,
        agent_type: AgentType,
        entity_id: str,
        repo_id: str,
    ):
        """Initialize the specialized agent."""
        self.agent_type = agent_type
        self.entity_id = entity_id
        self.repo_id = repo_id

        # Initialize database manager
        self.db_manager = Neo4jManager(
            entity_id=entity_id,
            repo_id=repo_id,
        )

        # Initialize tools
        self.tools: List[BaseTool] = [
            FindSymbols(db_manager=self.db_manager),
            VectorSearch(db_manager=self.db_manager),
            GrepCode(db_manager=self.db_manager),
            GetCodeAnalysis(db_manager=self.db_manager),
            GetExpandedContext(db_manager=self.db_manager),
            GetBlameInfo(
                db_manager=self.db_manager,
                repo_owner="blarApp",
                repo_name="blar-nextjs-front" if agent_type == AgentType.FRONTEND else "blar-django-server",
            ),
            GetDependencyGraph(db_manager=self.db_manager),
            GetFileContextByIdTool(db_manager=self.db_manager),
            GetNodeWorkflowsTool(db_manager=self.db_manager),
        ]

        # Initialize LLM
        self.llm = ChatOpenAI(
            model="gpt-5",
            reasoning={
                "effort": "medium",
                "summary": "auto",
            },
            use_responses_api=True,
            stream_usage=True,
        )

        # Create agent-specific system prompt
        other_codebase = "backend" if agent_type == AgentType.FRONTEND else "frontend"
        system_prompt = f"""You are a specialized {agent_type.value} code analysis agent.

Your expertise: Analyzing the {agent_type.value} codebase

CRITICAL STOPPING RULE:
- Once you have gathered sufficient information to answer your assigned question, STOP calling tools
- Be efficient: use minimum tool calls necessary
- After each tool call, evaluate: "Do I have enough to answer?" If yes, STOP

ERROR HANDLING & PERSISTENCE:
- If vector_search returns no results, try alternative keywords or broader search terms
- If find_symbols returns nothing, try variations of the name or search for related symbols
- Don't give up after one failed search - try at least 2-3 different approaches
- If you truly can't find information, explain what you tried and what was missing
- Example: "I searched for 'email verification' and 'resend email' but found no matching symbols. This may be handled in the {other_codebase}."

COLLABORATION PROTOCOL:
- You are part of a multi-agent system with a {other_codebase} agent
- A supervisor coordinates your work and reads your messages
- Your detailed findings are saved separately for final synthesis
- Keep your messages concise and focused on coordination:
  * Ask questions when you need information from the {other_codebase}
  * Answer questions from the other agent
  * Summarize when you have complete information
- Focus on YOUR codebase ({agent_type.value})

INTER-AGENT COMMUNICATION:
When responding, consider what the supervisor and other agent need to know:

IF you found complete information:
- Provide a concise summary (1-2 sentences)
- Include the most critical detail (file path, function name, or key finding)
- Example: "I found the resend button at verify-email/page.tsx:53 calls the API without auth token."

IF you need information from the {other_codebase}:
- Ask a specific, actionable question
- Example: "Does /api/resend-verification-email require authentication? If so, what error is returned?"

IF you found nothing relevant:
- State clearly what you searched for
- Example: "I searched for 'resend' and 'verification email' but found no matches. This functionality may be in the {other_codebase}."

Keep your message concise - the detailed findings are saved separately for final synthesis.

AVAILABLE TOOLS:
1. vector_search: Semantic search over code scope descriptions (use for exploration)
2. find_symbols: Search for specific symbols by EXACT name
3. grep_code: Pattern-based search in code content (find function calls, imports, code patterns)
4. get_code_analysis: Get implementation with relationships and dependencies
5. get_expanded_context: Get full context around a symbol
6. get_dependency_graph: Visualize dependencies with Mermaid diagrams
7. get_blame_info: See who last modified each line
8. get_file_context_by_id: See file context around a node
9. get_node_workflows: Understand which workflows a node participates in

SEARCH WORKFLOW:
1. For exploration: vector_search with keywords
2. If no results, try alternative keywords
3. For exact lookups: find_symbols with exact name
4. Only get detailed analysis if explicitly needed

Always provide clear, concise answers focused on the {agent_type.value} codebase.
When you mention code locations, include file paths and line numbers.
If you can't find something after trying multiple approaches, say so clearly.
"""

        # Create ReAct agent
        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_prompt,
        )

    def invoke(self, messages: List[BaseMessage]) -> Dict[str, Any]:
        """Invoke the agent with messages."""
        result = self.agent.invoke({"messages": messages}, config={"recursion_limit": 50})
        return result

    def stream(self, messages: List[BaseMessage]) -> Any:
        """Stream the agent's execution."""
        return self.agent.stream({"messages": messages}, config={"recursion_limit": 50})


class SupervisorAgent:
    """Supervisor agent that coordinates between frontend and backend agents."""

    def __init__(self) -> None:
        """Initialize the supervisor."""
        self.llm = ChatOpenAI(
            model="gpt-5",
            streaming=False,
            reasoning={
                "effort": "medium",
                "summary": "auto",
            },
            use_responses_api=True,
            stream_usage=True,
        )

    def route_query(self, state: MultiAgentState) -> str:
        """Decide which agent should handle the query next."""
        user_query = state["user_query"]
        conversation_messages = state.get("messages", [])
        iteration_count = state.get("iteration_count", 0)

        # Safety check: max iterations
        if iteration_count >= 10:
            console.print("[red]⚠ Max iterations (10) reached, finishing...[/red]")
            return "finish"

        system_message = """You are a supervisor coordinating code analysis across frontend (Next.js/React) and backend (Django) codebases.

Your job: Analyze the conversation history and decide which agent should investigate next.

AGENT CAPABILITIES:
- frontend: Analyzes Next.js/React frontend code (blar-nextjs-front repo)
- backend: Analyzes Python/Django backend code (blar-django-server repo)

ROUTING RULES:
1. Customer success context: prefer "frontend" as starting point (iteration 1)
2. If query mentions "UI", "component", "page", "button", "form", "React", "Next.js" → route to "frontend"
3. If query mentions "API", "database", "Django", "model", "view", "server", "backend" → route to "backend"
4. Look at the conversation history to see what each agent found
5. If one agent found something that needs follow-up in the other codebase → route to that other agent
6. If both agents have provided sufficient information → route to "finish"
7. If unclear, default to "frontend" (customer success priority)

COLLABORATION EXAMPLES:
- Frontend finds "calls /api/users" → route to backend to find that endpoint
- Backend finds "UserSerializer used by frontend" → route to frontend to see usage
- Both found their parts → finish and synthesize

You MUST respond with ONLY one word: "frontend", "backend", or "finish"
"""

        # Build messages: system + conversation history + routing prompt
        messages: List[BaseMessage] = [SystemMessage(content=system_message)]

        # Add conversation history (all agent findings in order)
        messages.extend(conversation_messages)

        # Add routing prompt
        messages.append(
            HumanMessage(
                content=f"""Iteration: {iteration_count + 1}/10

Based on the conversation above for the user query: "{user_query}"

Where should we route next? Respond with ONLY one word: frontend, backend, or finish"""
            )
        )

        response = self.llm.invoke(messages)

        # Display reasoning if available
        if hasattr(response, "additional_kwargs") and response.additional_kwargs:
            reasoning = response.additional_kwargs.get("reasoning", None)
            if reasoning:
                summary = reasoning.get("summary", [])
                for line in summary:
                    console.print(f"[dim][SUPERVISOR REASONING] {line['text']}[/dim]")

        # Handle content which can be str or list
        content = response.content
        if isinstance(content, str):
            decision = content.strip().lower()
        else:
            decision = str(content).strip().lower()

        # Validate decision
        if decision not in ["frontend", "backend", "finish"]:
            console.print(f"[red]Invalid decision '{decision}', defaulting to 'frontend'[/red]")
            decision = "frontend"

        console.print(f"[yellow]📋 Supervisor decision: {decision}[/yellow]")
        return decision

    def synthesize_response(self, state: MultiAgentState) -> str:
        """Synthesize final response from all agent findings."""
        user_query = state["user_query"]
        frontend_findings = state.get("frontend_findings", [])
        backend_findings = state.get("backend_findings", [])

        system_message = """You are a supervisor synthesizing findings from code analysis agents.

Your job: Create a clear, comprehensive answer combining insights from frontend and backend agents.

SYNTHESIS RULES:
1. Combine findings into a coherent narrative
2. Show the data flow or connection between frontend and backend if both contributed
3. Include specific file paths and line numbers when available
4. Use markdown formatting for clarity (headings, lists, code blocks)
5. If only one agent contributed, acknowledge that and provide their findings clearly
6. If neither agent found anything useful, state that clearly

Provide a well-structured, helpful response."""

        frontend_text = (
            "\n".join(f"- {f}" for f in frontend_findings) if frontend_findings else "No frontend analysis performed"
        )
        backend_text = (
            "\n".join(f"- {f}" for f in backend_findings) if backend_findings else "No backend analysis performed"
        )

        synthesis_messages = [
            SystemMessage(content=system_message),
            HumanMessage(
                content=f"""User query: {user_query}

Frontend findings:
{frontend_text}

Backend findings:
{backend_text}

Synthesize a comprehensive response:"""
            ),
        ]

        response = self.llm.invoke(synthesis_messages)

        # Handle content which can be str or list
        content = response.content
        if isinstance(content, str):
            return content
        else:
            return str(content)


class MultiAgentCodeAnalyzer:
    """Multi-agent system for analyzing code across frontend and backend."""

    # Hardcoded configuration
    ENTITY_ID = "blar"
    FRONTEND_REPO_ID = "/Users/berrazuriz/Desktop/Blar/repositories/blar-nextjs-front"
    BACKEND_REPO_ID = "/Users/berrazuriz/Desktop/Blar/repositories/blar-django-server"

    def __init__(self) -> None:
        """Initialize the multi-agent system."""
        console.print("[yellow]Initializing frontend agent...[/yellow]")
        self.frontend_agent = SpecializedCodeAgent(
            agent_type=AgentType.FRONTEND,
            entity_id=self.ENTITY_ID,
            repo_id=self.FRONTEND_REPO_ID,
        )

        console.print("[yellow]Initializing backend agent...[/yellow]")
        self.backend_agent = SpecializedCodeAgent(
            agent_type=AgentType.BACKEND,
            entity_id=self.ENTITY_ID,
            repo_id=self.BACKEND_REPO_ID,
        )

        console.print("[yellow]Initializing supervisor...[/yellow]")
        self.supervisor = SupervisorAgent()

        console.print("[yellow]Building agent graph...[/yellow]")
        self.graph = self._build_graph()

        console.print("[green]✓ Multi-agent system initialized![/green]\n")

    def _build_graph(self) -> CompiledStateGraph[MultiAgentState]:
        """Build the LangGraph workflow."""
        # Create state graph
        workflow: StateGraph[MultiAgentState] = StateGraph(MultiAgentState)

        # Add nodes
        workflow.add_node("supervisor", self._supervisor_node)
        workflow.add_node("frontend_agent", self._frontend_agent_node)
        workflow.add_node("backend_agent", self._backend_agent_node)
        workflow.add_node("synthesize", self._synthesize_node)

        # Set entry point
        workflow.set_entry_point("supervisor")

        # Conditional routing from supervisor
        def route_to_agent(state: MultiAgentState) -> str:
            return state["next_agent"]

        workflow.add_conditional_edges(
            "supervisor",
            route_to_agent,
            {
                "frontend": "frontend_agent",
                "backend": "backend_agent",
                "finish": "synthesize",
            },
        )

        # After agents, go back to supervisor
        workflow.add_edge("frontend_agent", "supervisor")
        workflow.add_edge("backend_agent", "supervisor")

        # After synthesis, end
        workflow.add_edge("synthesize", END)

        return workflow.compile()

    def _supervisor_node(self, state: MultiAgentState) -> PartialMultiAgentState:
        """Supervisor node: routes queries."""
        # Route query
        next_agent = self.supervisor.route_query(state)

        return {"iteration_count": state.get("iteration_count", 0) + 1, "next_agent": next_agent}

    def _frontend_agent_node(self, state: MultiAgentState) -> PartialMultiAgentState:
        """Frontend agent node."""
        console.print("\n[cyan]🎨 Frontend agent working...[/cyan]")

        messages = state["messages"]

        # Stream agent execution for visibility
        tool_call_count: int = 0
        final_messages: List[BaseMessage] = []

        for chunk in self.frontend_agent.stream(messages):
            reasoning = chunk.get("additional_kwargs", {}).get("reasoning_content", None)
            if reasoning:
                console.print(f"[dim][REASONING] {reasoning}[/dim]")
            if "agent" in chunk:
                agent_messages = chunk["agent"]["messages"]
                for msg in agent_messages:
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            tool_call_count += 1
                            tool_name = tool_call.get("name", "unknown")
                            console.print(f"[dim]  → Tool {tool_call_count}: {tool_name}[/dim]")
                    if hasattr(msg, "additional_kwargs") and msg.additional_kwargs:
                        reasoning = msg.additional_kwargs.get("reasoning", None)
                        if reasoning:
                            summary = reasoning.get("summary", [])
                            for line in summary:
                                console.print(f"[dim][REASONING] {line['text']}[/dim]")

            if "tools" in chunk:
                tool_messages = chunk["tools"]["messages"]
                for msg in tool_messages:
                    if hasattr(msg, "content"):
                        content_preview = str(msg.content)[:80]
                        console.print(f"[dim]    ← {content_preview}...[/dim]")

            # Collect all messages
            for key in chunk:
                if "messages" in chunk[key]:
                    final_messages.extend(chunk[key]["messages"])

        # Extract final AI response (last message without tool_calls)
        final_ai_response: AIMessage | None = None
        for msg in reversed(final_messages):
            if isinstance(msg, AIMessage) and not (hasattr(msg, "tool_calls") and msg.tool_calls):
                final_ai_response = msg
                break

        if final_ai_response and hasattr(final_ai_response, "content"):
            content = final_ai_response.content
            response_text: str = content if isinstance(content, str) else str(content)
        else:
            response_text = "No response from frontend agent"

        # Add to findings
        state["frontend_findings"].append(response_text)

        # Create a new message with agent name attribution
        attributed_message = AIMessage(content=response_text, name="frontend_agent") if final_ai_response else None

        console.print(f"\n[green]✓ Frontend completed with {tool_call_count} tool calls[/green]")
        console.print(f"[dim]Finding: {response_text[:150]}...[/dim]\n")

        return {
            "frontend_findings": [response_text] if response_text else [],
            "messages": [attributed_message] if attributed_message else [],
        }

    def _backend_agent_node(self, state: MultiAgentState) -> PartialMultiAgentState:
        """Backend agent node."""
        console.print("\n[cyan]⚙️  Backend agent working...[/cyan]")

        messages = state["messages"]

        # Stream agent execution for visibility
        tool_call_count: int = 0
        final_messages: List[BaseMessage] = []

        for chunk in self.backend_agent.stream(messages):
            if "agent" in chunk:
                agent_messages = chunk["agent"]["messages"]
                for msg in agent_messages:
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            tool_call_count += 1
                            tool_name = tool_call.get("name", "unknown")
                            console.print(f"[dim]  → Tool {tool_call_count}: {tool_name}[/dim]")

            if "tools" in chunk:
                tool_messages = chunk["tools"]["messages"]
                for msg in tool_messages:
                    if hasattr(msg, "content"):
                        content_preview = str(msg.content)[:80]
                        console.print(f"[dim]    ← {content_preview}...[/dim]")

            # Collect all messages
            for key in chunk:
                if "messages" in chunk[key]:
                    final_messages.extend(chunk[key]["messages"])

        # Extract final AI response (last message without tool_calls)
        final_ai_response: AIMessage | None = None
        for msg in reversed(final_messages):
            if isinstance(msg, AIMessage) and not (hasattr(msg, "tool_calls") and msg.tool_calls):
                final_ai_response = msg
                break

        if final_ai_response and hasattr(final_ai_response, "content"):
            content = final_ai_response.content
            response_text: str = content if isinstance(content, str) else str(content)
        else:
            response_text = "No response from backend agent"

        # Create a new message with agent name attribution
        attributed_message = AIMessage(content=response_text, name="backend_agent") if final_ai_response else None

        console.print(f"\n[green]✓ Backend completed with {tool_call_count} tool calls[/green]")
        console.print(f"[dim]Finding: {response_text[:150]}...[/dim]\n")

        return {
            "backend_findings": [response_text] if response_text else [],
            "messages": [attributed_message] if attributed_message else [],
        }

    def _synthesize_node(self, state: MultiAgentState) -> MultiAgentState:
        """Synthesize final response."""
        console.print("\n[magenta]🔮 Synthesizing final response...[/magenta]\n")

        final_response = self.supervisor.synthesize_response(state)
        state["messages"].append(AIMessage(content=final_response))

        return state

    def query(self, user_query: str) -> str:
        """Process a user query."""
        # Initialize state
        initial_state: MultiAgentState = {
            "messages": [HumanMessage(content=user_query)],
            "next_agent": "",
            "frontend_findings": [],
            "backend_findings": [],
            "user_query": user_query,
            "iteration_count": 0,
        }

        # Run the graph
        final_state = self.graph.invoke(initial_state)

        # Return final message
        final_messages: List[BaseMessage] = final_state["messages"]
        if final_messages:
            last_message = final_messages[-1]
            if hasattr(last_message, "content"):
                content = last_message.content
                if isinstance(content, str):
                    return content
                else:
                    return str(content)
            else:
                return str(last_message)
        return "No response generated"

    def display_welcome(self) -> None:
        """Display welcome message."""
        welcome_text = f"""
# Multi-Agent Code Analysis System

Welcome! I coordinate multiple AI agents to help you explore code across frontend and backend.

**Connected Codebases:**
- 🎨 Frontend: Next.js/React ({self.FRONTEND_REPO_ID.split("/")[-1]})
- ⚙️  Backend: Django ({self.BACKEND_REPO_ID.split("/")[-1]})
- 🏢 Entity: {self.ENTITY_ID}

## How It Works:

1. **Supervisor Agent** analyzes your query and routes to the right specialist
2. **Frontend Agent** explores React/Next.js code
3. **Backend Agent** explores Python/Django code
4. Agents **share findings** and supervisor coordinates follow-ups
5. **Final synthesis** combines all discoveries

## Example Questions (Customer Success Context):

- "How does the user dashboard load data?"
- "Find the authentication flow from login button to server"
- "Where is the payment processing handled?"
- "Show me how the search feature works"
- "How does the profile page update user information?"
- "Where are API errors displayed to users?"

## Commands:

- Type your question to start analysis
- 'quit' or 'exit' to leave
- 'clear' to clear the screen
- 'help' for this message
"""
        console.print(Panel(Markdown(welcome_text), title="Multi-Agent System", border_style="blue"))

    def run(self) -> None:
        """Run the interactive multi-agent system."""
        self.display_welcome()

        while True:
            try:
                query = Prompt.ask("\n[bold blue]Ask about the codebase>[/bold blue]")

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

                # Process query
                console.print("\n[yellow]🚀 Starting multi-agent analysis...[/yellow]\n")
                response = self.query(query)

                # Display response
                console.print(Panel(Markdown(response), title="Analysis Result", border_style="green"))

            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'quit' or 'exit' to leave[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                import traceback

                traceback.print_exc()


def main() -> None:
    """Main entry point."""
    # Check for OpenAI API key
    if not os.environ.get("OPENAI_API_KEY"):
        console.print("[red]Error: OPENAI_API_KEY environment variable not set[/red]")
        console.print("Please set your OpenAI API key: export OPENAI_API_KEY='your-key-here'")
        sys.exit(1)

    try:
        analyzer = MultiAgentCodeAnalyzer()
        analyzer.run()
    except Exception as e:
        console.print(f"[red]Failed to initialize multi-agent system: {e}[/red]")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
