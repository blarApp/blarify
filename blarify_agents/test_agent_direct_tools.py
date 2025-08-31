"""
Test Blarify Tools with Direct LangChain Integration
"""

import os
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.tools import (
    DirectoryExplorerTool,
    FindNodesByCode,
    FindNodesByNameAndType,
    FindNodesByPath,
    GetCodeByIdTool,
    GetFileContextByIdTool,
    GetRelationshipFlowchart,
)


class BlarifyDirectToolAgent:
    """Agent using Blarify tools directly as LangChain tools"""

    def __init__(self, model_name: str = "gpt-4", temperature: float = 0.0):
        # Initialize database manager
        self.db_manager = Neo4jManager(
            repo_id="test",
            entity_id="test",
        )

        # Initialize LLM
        self.llm = ChatOpenAI(model=model_name, temperature=temperature, api_key=os.getenv("OPENAI_API_KEY"))

        # Initialize tools directly - they're already LangChain tools!
        self.tools = [
            DirectoryExplorerTool(db_manager=self.db_manager),
            FindNodesByCode(db_manager=self.db_manager),
            FindNodesByNameAndType(db_manager=self.db_manager),
            FindNodesByPath(db_manager=self.db_manager),
            GetCodeByIdTool(db_manager=self.db_manager),
            GetFileContextByIdTool(db_manager=self.db_manager),
            GetRelationshipFlowchart(db_manager=self.db_manager),
        ]

        # Create agent with tools
        self.agent_executor = self._create_agent()

    def _create_agent(self) -> AgentExecutor:
        """Create the agent with direct tool usage"""

        # Create prompt
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a code analysis assistant using Blarify tools.
You have access to the following tools to explore and analyze codebases:

1. DirectoryExplorerTool - Explore directory structure
2. FindNodesByCode - Search for nodes containing specific code
3. FindNodesByNameAndType - Find nodes by name and type
4. FindNodesByPath - Find nodes at specific file paths
5. GetCodeByIdTool - Get detailed code and relationships for a node
6. GetFileContextByIdTool - Get expanded file context
7. GetRelationshipFlowchart - Generate relationship diagrams

Use these tools to thoroughly analyze the codebase and provide insights.""",
                ),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        # Create the agent
        agent = create_tool_calling_agent(llm=self.llm, tools=self.tools, prompt=prompt)

        # Create agent executor
        agent_executor = AgentExecutor(
            agent=agent, tools=self.tools, verbose=True, max_iterations=10, handle_parsing_errors=True
        )

        return agent_executor

    def analyze(self, query: str) -> str:
        """Analyze code using the available tools

        Args:
            query: The analysis query
        """
        try:
            result = self.agent_executor.invoke({"input": query})
            return result.get("output", "No output generated")
        except Exception as e:
            return f"Error during analysis: {str(e)}"

    def test_all_tools(self):
        """Test all available tools with various queries"""

        print("\n" + "=" * 60)
        print("TESTING ALL BLARIFY TOOLS DIRECTLY")
        print("=" * 60)

        # Test each tool individually first
        print("\n1. Testing DirectoryExplorerTool...")
        print("-" * 40)
        try:
            explorer = DirectoryExplorerTool(db_manager=self.db_manager)
            result = explorer._run(node_id=None, run_manager=None)
            print(result[:300] + "..." if len(result) > 300 else result)
        except Exception as e:
            print(f"Error: {e}")

        print("\n2. Testing FindNodesByCode...")
        print("-" * 40)
        try:
            finder = FindNodesByCode(db_manager=self.db_manager, diff_identifier="main")
            result = finder._run(code="def ")
            if result.get("too many nodes"):
                print("Found too many nodes containing 'def'")
            else:
                nodes = result.get("nodes", [])
                print(f"Found {len(nodes)} nodes containing 'def'")
                if nodes:
                    print(f"First match: {nodes[0].get('file_path', 'Unknown')}")
        except Exception as e:
            print(f"Error: {e}")

        print("\n3. Testing FindNodesByNameAndType...")
        print("-" * 40)
        try:
            finder = FindNodesByNameAndType(db_manager=self.db_manager, diff_identifier="main")
            result = finder._run(name="main", node_type="Function")
            nodes = result.get("nodes", [])
            print(f"Found {len(nodes)} functions named 'main'")
            for node in nodes[:3]:
                print(f"  - {node.get('file_path')}: {node.get('name')}")
        except Exception as e:
            print(f"Error: {e}")

        # Now test with the agent
        print("\n" + "=" * 60)
        print("TESTING AGENT WITH QUERIES")
        print("=" * 60)

        test_queries = [
            "List the contents of the repository root directory",
            "Find all Python files that contain class definitions",
            "Search for functions named 'main' or '__init__'",
            "Find any README or documentation files",
            "Look for test files and analyze their structure",
        ]

        results = {}

        for query in test_queries:
            print(f"\n{'=' * 60}")
            print(f"Query: {query}")
            print("=" * 60)

            result = self.analyze(query)
            results[query] = result
            print(result[:500] + "..." if len(result) > 500 else result)

        return results

    def interactive_exploration(self):
        """Interactive mode for exploring the codebase"""
        print("\n" + "=" * 60)
        print("INTERACTIVE CODE EXPLORATION MODE")
        print("=" * 60)
        print("Type 'exit' to quit, 'help' for available commands")
        print("-" * 60)

        while True:
            query = input("\n> ").strip()

            if query.lower() == "exit":
                break
            elif query.lower() == "help":
                print("""
Available commands:
- Ask any question about the codebase
- Examples:
  - "Show me the repository structure"
  - "Find all test files"
  - "Search for TODO comments"
  - "Find the main entry point"
  - "Show me all classes in the project"
                """)
            elif query:
                print("\nAnalyzing...")
                result = self.analyze(query)
                print(result)

    def close(self):
        """Close database connections"""
        if hasattr(self.db_manager, "close"):
            self.db_manager.close()


def main():
    """Main function to test the agent"""
    print("Initializing Blarify Direct Tool Agent...")

    agent = BlarifyDirectToolAgent()

    # Run comprehensive tests
    # results = agent.test_all_tools()

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    # success_count = 0
    # for query, result in results.items():
    #     if "Error" not in result:
    #         success_count += 1
    #         print(f"✓ {query[:50]}...")
    #     else:
    #         print(f"✗ {query[:50]}...")

    # print(f"\nSuccess rate: {success_count}/{len(results)} queries completed")

    # Optional: Enter interactive mode
    print("\nWould you like to enter interactive exploration mode? (y/n)")
    if input().lower() == "y":
        agent.interactive_exploration()

    agent.close()
    print("\nAgent testing completed!")


if __name__ == "__main__":
    main()
