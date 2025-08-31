"""
Interactive Blarify Agent - Explore and analyze codebases with natural language
"""

import os
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from blarify.db_managers.neo4j_manager import Neo4jManager
from blarify.tools import (
    DirectoryExplorerTool,
    FindNodesByCode,
    FindNodesByNameAndType,
    FindNodesByPath,
    GetCodeByIdTool,
    GetFileContextByIdTool,
    GetRelationshipFlowchart,
)


class InteractiveBlarifyAgent:
    """Interactive agent for exploring code with Blarify tools"""
    
    def __init__(
        self,
        repo_id: str = "test",
        entity_id: str = "test",
        model_name: str = "gpt-4",
        temperature: float = 0.0
    ):
        # Initialize database manager
        self.db_manager = Neo4jManager(
            repo_id=repo_id,
            entity_id=entity_id,
        )
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Initialize Blarify tools - they're already LangChain compatible!
        self.tools = [
            DirectoryExplorerTool(db_manager=self.db_manager),
            FindNodesByCode(db_manager=self.db_manager),
            FindNodesByNameAndType(db_manager=self.db_manager),
            FindNodesByPath(db_manager=self.db_manager),
            GetCodeByIdTool(db_manager=self.db_manager),
            GetFileContextByIdTool(db_manager=self.db_manager),
            GetRelationshipFlowchart(db_manager=self.db_manager),
        ]
        
        # Create agent
        self.agent_executor = self._create_agent()
    
    def _create_agent(self) -> AgentExecutor:
        """Create the agent with tool calling capabilities"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful code analysis assistant using Blarify tools.
            
Available tools:
- DirectoryExplorerTool: Explore directory structure of the repository
- FindNodesByCode: Search for code containing specific text
- FindNodesByNameAndType: Find nodes by name and type (Function, Class, etc.)
- FindNodesByPath: Find nodes at specific file paths
- GetCodeByIdTool: Get detailed code and relationships for a node ID
- GetFileContextByIdTool: Get expanded file context with all code
- GetRelationshipFlowchart: Generate Mermaid diagrams of relationships

Be helpful and thorough in your analysis. When users ask questions, use the appropriate tools to find the answer."""),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_tool_calling_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            max_iterations=10,
            handle_parsing_errors=True
        )
    
    def run(self):
        """Run the interactive agent"""
        print("\n" + "="*60)
        print("🔍 BLARIFY INTERACTIVE CODE EXPLORER")
        print("="*60)
        print("\nI can help you explore and analyze your codebase!")
        print("\nExample queries:")
        print("  • Show me the repository structure")
        print("  • Find all test files")
        print("  • Search for TODO comments")
        print("  • Find the main entry point")
        print("  • Show me all classes in the project")
        print("  • Find functions that call 'process_data'")
        print("  • Analyze the authentication module")
        print("\nType 'exit' to quit, 'help' for more examples")
        print("-"*60)
        
        while True:
            try:
                query = input("\n💬 You: ").strip()
                
                if query.lower() == 'exit':
                    print("\n👋 Goodbye!")
                    break
                
                elif query.lower() == 'help':
                    self._show_help()
                
                elif query:
                    print("\n🤖 Agent: Analyzing...\n")
                    result = self.agent_executor.invoke({"input": query})
                    print("\n📊 Result:")
                    print(result.get("output", "No output generated"))
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {str(e)}")
                print("Please try a different query or type 'help' for examples.")
    
    def _show_help(self):
        """Show help information"""
        print("\n" + "="*60)
        print("HELP - Example Queries")
        print("="*60)
        print("""
EXPLORATION:
  • "Show me the directory structure"
  • "List all Python files"
  • "Find the main entry point of the application"
  
SEARCH:
  • "Find all functions that start with 'test_'"
  • "Search for TODO or FIXME comments"
  • "Find all class definitions"
  • "Look for configuration files"
  
ANALYSIS:
  • "Analyze the main.py file"
  • "Show me what functions the 'process' function calls"
  • "Generate a flowchart for the authentication module"
  • "Find all imports in the project"
  
SPECIFIC PATTERNS:
  • "Find error handling patterns"
  • "Look for database queries"
  • "Find all API endpoints"
  • "Search for security-related code"
        """)
    
    def close(self):
        """Close database connections"""
        if hasattr(self.db_manager, 'close'):
            self.db_manager.close()


def main():
    """Main entry point"""
    print("🚀 Starting Blarify Interactive Agent...")
    print("\nMake sure you have:")
    print("  ✓ Neo4j running with a graph loaded")
    print("  ✓ OPENAI_API_KEY environment variable set")
    print("  ✓ Graph data with repo_id='test' and entity_id='test'")
    
    agent = InteractiveBlarifyAgent()
    
    try:
        agent.run()
    finally:
        agent.close()
        print("\n✅ Session completed successfully!")


if __name__ == "__main__":
    main()