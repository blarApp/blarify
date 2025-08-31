"""
Main Blarify Tools Test Agent
Tests all available Blarify tools using LangChain
"""

import os
from typing import Any, Dict, List, Optional
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.tools import Tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.repositories.graph_db_manager.falkordb_manager import FalkorDBManager
from blarify.tools import (
    DirectoryExplorerTool,
    FindNodesByCode,
    FindNodesByNameAndType,
    FindNodesByPath,
    GetCodeByIdTool,
    GetFileContextByIdTool,
    GetRelationshipFlowchart,
)


class AgentConfig(BaseModel):
    """Configuration for the Blarify test agent"""

    repo_id: str = Field(default="test", description="Repository ID")
    entity_id: str = Field(default="test", description="Entity/Company ID")
    diff_identifier: str = Field(default="main", description="Diff identifier")
    db_type: str = Field(default="neo4j", description="Database type: neo4j or falkordb")
    neo4j_uri: Optional[str] = Field(default=None, description="Neo4j URI")
    neo4j_username: Optional[str] = Field(default=None, description="Neo4j username")
    neo4j_password: Optional[str] = Field(default=None, description="Neo4j password")
    falkordb_host: str = Field(default="localhost", description="FalkorDB host")
    falkordb_port: int = Field(default=6379, description="FalkorDB port")
    model_name: str = Field(default="gpt-4o-mini", description="LLM model name")
    temperature: float = Field(default=0.0, description="LLM temperature")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")


class BlarifyTestAgent:
    """Main agent for testing all Blarify tools"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.db_manager = self._init_db_manager()
        self.llm = self._init_llm()
        self.tools = self._init_tools()
        self.agent_executor = self._create_agent()

    def _init_db_manager(self):
        """Initialize the database manager"""
        if self.config.db_type == "neo4j":
            return Neo4jManager(
                uri=self.config.neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                user=self.config.neo4j_username or os.getenv("NEO4J_USERNAME", "neo4j"),
                password=self.config.neo4j_password or os.getenv("NEO4J_PASSWORD", "password"),
                repo_id=self.config.repo_id,
                entity_id=self.config.entity_id,
            )
        elif self.config.db_type == "falkordb":
            return FalkorDBManager(
                host=self.config.falkordb_host,
                port=self.config.falkordb_port,
                repo_id=self.config.repo_id,
                entity_id=self.config.entity_id,
            )
        else:
            raise ValueError(f"Unsupported database type: {self.config.db_type}")

    def _init_llm(self):
        """Initialize the LLM using ChatOpenAI directly"""
        api_key = self.config.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key not provided. Set OPENAI_API_KEY environment variable or pass it in config."
            )

        return ChatOpenAI(
            model=self.config.model_name,
            temperature=self.config.temperature,
            api_key=api_key,
            timeout=60,
            max_retries=2,
        )

    def _init_tools(self) -> List[Tool]:
        """Initialize all Blarify tools"""
        tools = []

        # Directory Explorer Tools
        try:
            tools.append(
                DirectoryExplorerTool(
                    company_graph_manager=self.db_manager,
                )
            )
        except Exception as e:
            print(f"Failed to initialize DirectoryExplorerTool: {e}")

        # Find Nodes by Code
        try:
            tools.append(FindNodesByCode(db_manager=self.db_manager))
        except Exception as e:
            print(f"Failed to initialize FindNodesByCode: {e}")

        # Find Nodes by Name and Type
        try:
            tools.append(FindNodesByNameAndType(db_manager=self.db_manager))
        except Exception as e:
            print(f"Failed to initialize FindNodesByNameAndType: {e}")

        # Find Nodes by Path
        try:
            tools.append(FindNodesByPath(db_manager=self.db_manager))
        except Exception as e:
            print(f"Failed to initialize FindNodesByPath: {e}")

        # Get Code by ID
        try:
            tools.append(GetCodeByIdTool(db_manager=self.db_manager, auto_generate_documentation=False))
        except Exception as e:
            print(f"Failed to initialize GetCodeByIdTool: {e}")

        # Get File Context by ID
        try:
            tools.append(GetFileContextByIdTool(db_manager=self.db_manager))
        except Exception as e:
            print(f"Failed to initialize GetFileContextByIdTool: {e}")

        # Get Relationship Flowchart
        try:
            tools.append(
                GetRelationshipFlowchart(db_manager=self.db_manager, diff_identifier=self.config.diff_identifier)
            )
        except Exception as e:
            print(f"Failed to initialize GetRelationshipFlowchart: {e}")

        return tools

    def _create_agent(self) -> AgentExecutor:
        """Create the ReAct agent"""
        prompt = PromptTemplate.from_template("""
You are a code analysis agent using Blarify tools to explore and analyze codebases.
You have access to tools that can navigate the repository structure, search for code,
and analyze relationships between different parts of the codebase.

Available tools:
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

Question: {input}
{agent_scratchpad}
""")

        agent = create_react_agent(llm=self.llm, tools=self.tools, prompt=prompt)

        return AgentExecutor(agent=agent, tools=self.tools, verbose=True, max_iterations=10, handle_parsing_errors=True)

    def run(self, query: str) -> str:
        """Run the agent with a query"""
        try:
            result = self.agent_executor.invoke({"input": query})
            return result.get("output", "No output generated")
        except Exception as e:
            return f"Error running agent: {str(e)}"

    def test_all_tools(self) -> Dict[str, Any]:
        """Test all available tools and return results"""
        results = {}

        test_queries = [
            "Find the repository root and list its contents",
            "Find all Python files that contain the word 'FallbackDefinitions'",
            # "Find functions named 'main' or '__init__'",
            # "Show me the structure of the main.py file if it exists",
            # "Generate a flowchart for any major function you can find",
        ]

        for query in test_queries:
            print(f"\n{'=' * 60}")
            print(f"Testing: {query}")
            print("=" * 60)
            results[query] = self.run(query)

        return results

    def close(self):
        """Close database connections"""
        if hasattr(self.db_manager, "close"):
            self.db_manager.close()


def main():
    """Main function to test the agent"""
    config = AgentConfig()

    print("Initializing Blarify Test Agent...")
    agent = BlarifyTestAgent(config)

    print("\nRunning comprehensive tool tests...")
    results = agent.test_all_tools()

    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)

    for query, result in results.items():
        print(f"\nQuery: {query}")
        print(f"Result: {result[:200]}..." if len(result) > 200 else f"Result: {result}")

    agent.close()
    print("\nAgent testing completed!")


if __name__ == "__main__":
    main()
