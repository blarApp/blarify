"""
Code Explorer Agent
An agent specialized in navigating and exploring codebases using Blarify tools
"""

import os
from typing import Any, Dict, List, Optional, Tuple
from langchain.agents import AgentExecutor, create_structured_chat_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain.tools import Tool, StructuredTool
from langchain.memory import ConversationBufferMemory
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
)


class ExplorationTask(BaseModel):
    """Task for code exploration"""
    
    task_type: str = Field(description="Type of exploration: structure, search, analyze")
    target: str = Field(description="Target to explore (path, function name, pattern)")
    depth: int = Field(default=2, description="Depth of exploration")
    include_relationships: bool = Field(default=True, description="Include relationship analysis")


class CodeExplorerAgent:
    """Agent specialized in code exploration and navigation"""
    
    def __init__(
        self,
        repo_id: str = "test",
        entity_id: str = "test",
        db_type: str = "neo4j",
        model_name: str = "gpt-4",
        verbose: bool = True
    ):
        self.repo_id = repo_id
        self.entity_id = entity_id
        self.db_type = db_type
        self.verbose = verbose
        
        self.db_manager = self._init_db_manager()
        self.llm = ChatOpenAI(
            model_name=model_name,
            temperature=0.0,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        self.tools = self._init_exploration_tools()
        self.agent_executor = self._create_agent()
        
        # Track exploration state
        self.exploration_history: List[Dict[str, Any]] = []
        self.current_location: Optional[str] = None
        self.discovered_nodes: Dict[str, Any] = {}
    
    def _init_db_manager(self):
        """Initialize database manager"""
        if self.db_type == "neo4j":
            return Neo4jManager(
                uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                user=os.getenv("NEO4J_USERNAME", "neo4j"),
                password=os.getenv("NEO4J_PASSWORD", "password"),
                repo_id=self.repo_id,
                entity_id=self.entity_id
            )
        else:
            return FalkorDBManager(
                host="localhost",
                port=6379,
                repo_id=self.repo_id,
                entity_id=self.entity_id
            )
    
    def _init_exploration_tools(self) -> List[Tool]:
        """Initialize specialized exploration tools"""
        tools = []
        
        # Directory exploration
        directory_explorer = DirectoryExplorerTool(
            company_graph_manager=self.db_manager,
            company_id=self.entity_id,
            repo_id=self.repo_id
        )
        
        tools.extend([
            directory_explorer.get_tool(),
            directory_explorer.get_find_repo_root_tool()
        ])
        
        # Code search tools
        find_by_code = FindNodesByCode(
            db_manager=self.db_manager,
            company_id=self.entity_id,
            repo_id=self.repo_id,
            diff_identifier="main"
        )
        
        find_by_name = FindNodesByNameAndType(
            db_manager=self.db_manager,
            company_id=self.entity_id,
            repo_id=self.repo_id,
            diff_identifier="main"
        )
        
        find_by_path = FindNodesByPath(
            db_manager=self.db_manager,
            company_id=self.entity_id,
            repo_id=self.repo_id,
            diff_identifier="main"
        )
        
        # Code retrieval tools
        get_code = GetCodeByIdTool(
            db_manager=self.db_manager,
            company_id=self.entity_id,
            auto_generate_documentation=True
        )
        
        get_context = GetFileContextByIdTool(
            db_manager=self.db_manager,
            company_id=self.entity_id
        )
        
        # Custom exploration tools
        tools.extend([
            StructuredTool.from_function(
                func=self._explore_directory_structure,
                name="explore_directory_structure",
                description="Recursively explore directory structure starting from a node"
            ),
            StructuredTool.from_function(
                func=self._find_entry_points,
                name="find_entry_points",
                description="Find main entry points in the codebase"
            ),
            StructuredTool.from_function(
                func=self._trace_function_calls,
                name="trace_function_calls",
                description="Trace function call chains from a starting point"
            ),
            StructuredTool.from_function(
                func=self._analyze_file_structure,
                name="analyze_file_structure",
                description="Analyze the structure of a specific file"
            ),
            Tool(
                name="find_by_code",
                func=lambda code: find_by_code._run(code=code),
                description="Find nodes containing specific code"
            ),
            Tool(
                name="find_by_name",
                func=lambda name: find_by_name._run(name=name, node_type=""),
                description="Find nodes by name"
            ),
            Tool(
                name="find_by_path",
                func=lambda path: find_by_path._run(file_path=path),
                description="Find nodes at a specific path"
            ),
            Tool(
                name="get_code",
                func=lambda node_id: get_code._run(node_id=node_id),
                description="Get code details for a node"
            ),
            Tool(
                name="get_context",
                func=lambda node_id: get_context._run(node_id=node_id),
                description="Get expanded file context"
            )
        ])
        
        return tools
    
    def _explore_directory_structure(
        self,
        starting_node_id: Optional[str] = None,
        max_depth: int = 3
    ) -> str:
        """Recursively explore directory structure"""
        explorer = DirectoryExplorerTool(
            company_graph_manager=self.db_manager,
            company_id=self.entity_id,
            repo_id=self.repo_id
        )
        
        def explore_recursive(node_id: Optional[str], depth: int, indent: str = "") -> str:
            if depth > max_depth:
                return f"{indent}... (max depth reached)\n"
            
            try:
                if node_id is None:
                    # Get repository root
                    root_info = explorer._find_repo_root()
                    if not root_info:
                        return "Could not find repository root\n"
                    node_id = root_info.get("node_id")
                
                # Get directory contents
                contents = explorer._list_directory_children(node_id)
                if not contents:
                    return f"{indent}(empty)\n"
                
                result = ""
                for item in contents:
                    item_type = "📁" if item.get("type") == "directory" else "📄"
                    result += f"{indent}{item_type} {item.get('name', 'Unknown')} (ID: {item.get('node_id', 'N/A')[:8]}...)\n"
                    
                    # Recursively explore subdirectories
                    if item.get("type") == "directory" and depth < max_depth:
                        result += explore_recursive(item.get("node_id"), depth + 1, indent + "  ")
                
                return result
            except Exception as e:
                return f"{indent}Error exploring: {str(e)}\n"
        
        result = "Repository Structure:\n" + "="*50 + "\n"
        result += explore_recursive(starting_node_id, 0)
        
        # Update current location
        self.current_location = starting_node_id
        
        return result
    
    def _find_entry_points(self) -> str:
        """Find main entry points in the codebase"""
        find_by_name = FindNodesByNameAndType(
            db_manager=self.db_manager,
            company_id=self.entity_id,
            repo_id=self.repo_id,
            diff_identifier="main"
        )
        
        entry_points = []
        
        # Common entry point patterns
        patterns = [
            ("main", "Function"),
            ("__main__", ""),
            ("app", ""),
            ("index", ""),
            ("server", ""),
            ("cli", ""),
            ("run", "Function"),
            ("start", "Function"),
            ("execute", "Function")
        ]
        
        for name, node_type in patterns:
            try:
                result = find_by_name._run(name=name, node_type=node_type)
                if result.get("nodes"):
                    for node in result["nodes"]:
                        entry_points.append({
                            "name": node.get("name"),
                            "type": node.get("type"),
                            "path": node.get("file_path"),
                            "node_id": node.get("node_id")
                        })
                        # Store in discovered nodes
                        self.discovered_nodes[node["node_id"]] = node
            except:
                continue
        
        if not entry_points:
            return "No standard entry points found in the codebase."
        
        result = "Found Entry Points:\n" + "="*50 + "\n"
        for ep in entry_points:
            result += f"• {ep['name']} ({ep['type']})\n"
            result += f"  Path: {ep['path']}\n"
            result += f"  Node ID: {ep['node_id'][:16]}...\n\n"
        
        return result
    
    def _trace_function_calls(
        self,
        function_node_id: str,
        max_depth: int = 3
    ) -> str:
        """Trace function call chains"""
        get_code = GetCodeByIdTool(
            db_manager=self.db_manager,
            company_id=self.entity_id
        )
        
        visited = set()
        
        def trace_recursive(node_id: str, depth: int, indent: str = "") -> str:
            if depth > max_depth or node_id in visited:
                return ""
            
            visited.add(node_id)
            
            try:
                node_info = get_code._run(node_id=node_id)
                if not node_info:
                    return f"{indent}(Node not found)\n"
                
                # Parse the response to extract relationships
                lines = node_info.split("\n")
                result = f"{indent}→ {lines[0] if lines else 'Unknown'}\n"
                
                # Look for outbound relationships
                in_outbound = False
                for line in lines:
                    if "Outbound Relations:" in line:
                        in_outbound = True
                    elif in_outbound and "→" in line:
                        # Extract called function info
                        parts = line.split("ID:")
                        if len(parts) > 1:
                            called_id = parts[1].strip().split()[0]
                            if called_id and depth < max_depth:
                                result += trace_recursive(called_id, depth + 1, indent + "  ")
                    elif in_outbound and line.strip() == "":
                        in_outbound = False
                
                return result
            except Exception as e:
                return f"{indent}(Error: {str(e)})\n"
        
        result = "Function Call Trace:\n" + "="*50 + "\n"
        result += trace_recursive(function_node_id, 0)
        
        return result
    
    def _analyze_file_structure(self, file_path: str) -> str:
        """Analyze the structure of a specific file"""
        find_by_path = FindNodesByPath(
            db_manager=self.db_manager,
            company_id=self.entity_id,
            repo_id=self.repo_id,
            diff_identifier="main"
        )
        
        get_context = GetFileContextByIdTool(
            db_manager=self.db_manager,
            company_id=self.entity_id
        )
        
        try:
            # Find the file node
            path_result = find_by_path._run(file_path=file_path)
            if not path_result or not path_result.get("nodes"):
                return f"File not found: {file_path}"
            
            file_node = path_result["nodes"][0]
            node_id = file_node.get("node_id")
            
            # Get expanded context
            context = get_context._run(node_id=node_id)
            
            # Analyze structure
            lines = context.split("\n")
            structure = {
                "imports": [],
                "classes": [],
                "functions": [],
                "variables": [],
                "total_lines": len(lines)
            }
            
            for line in lines:
                line_stripped = line.strip()
                if line_stripped.startswith("import ") or line_stripped.startswith("from "):
                    structure["imports"].append(line_stripped)
                elif line_stripped.startswith("class "):
                    class_name = line_stripped.split("(")[0].replace("class ", "").strip(":")
                    structure["classes"].append(class_name)
                elif line_stripped.startswith("def "):
                    func_name = line_stripped.split("(")[0].replace("def ", "")
                    structure["functions"].append(func_name)
                elif "=" in line_stripped and not line_stripped.startswith("#"):
                    var_name = line_stripped.split("=")[0].strip()
                    if var_name and var_name.isupper():
                        structure["variables"].append(var_name)
            
            # Format result
            result = f"File Structure Analysis: {file_path}\n" + "="*50 + "\n"
            result += f"Total Lines: {structure['total_lines']}\n\n"
            
            if structure["imports"]:
                result += f"Imports ({len(structure['imports'])}):\n"
                for imp in structure["imports"][:10]:
                    result += f"  • {imp}\n"
                if len(structure["imports"]) > 10:
                    result += f"  ... and {len(structure['imports']) - 10} more\n"
                result += "\n"
            
            if structure["classes"]:
                result += f"Classes ({len(structure['classes'])}):\n"
                for cls in structure["classes"]:
                    result += f"  • {cls}\n"
                result += "\n"
            
            if structure["functions"]:
                result += f"Functions ({len(structure['functions'])}):\n"
                for func in structure["functions"]:
                    result += f"  • {func}\n"
                result += "\n"
            
            if structure["variables"]:
                result += f"Constants ({len(structure['variables'])}):\n"
                for var in structure["variables"][:5]:
                    result += f"  • {var}\n"
                if len(structure["variables"]) > 5:
                    result += f"  ... and {len(structure['variables']) - 5} more\n"
            
            return result
            
        except Exception as e:
            return f"Error analyzing file: {str(e)}"
    
    def _create_agent(self) -> AgentExecutor:
        """Create the exploration agent"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a code exploration specialist using Blarify tools.
Your goal is to help users navigate and understand codebases effectively.

You can:
- Explore directory structures recursively
- Find entry points and main functions
- Trace function call chains
- Analyze file structures
- Search for specific code patterns
- Navigate using paths, names, or content

Available tools:
{tools}

When exploring, be systematic:
1. Start with understanding the overall structure
2. Identify key entry points
3. Follow relationships to understand flow
4. Provide clear, structured summaries

Tool usage format:
{format_instructions}"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        agent = create_structured_chat_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=self.verbose,
            max_iterations=10,
            handle_parsing_errors=True
        )
    
    def explore(self, query: str) -> str:
        """Run exploration based on query"""
        try:
            result = self.agent_executor.invoke({"input": query})
            
            # Track exploration
            self.exploration_history.append({
                "query": query,
                "result": result.get("output"),
                "location": self.current_location
            })
            
            return result.get("output", "No result")
        except Exception as e:
            return f"Exploration error: {str(e)}"
    
    def get_exploration_summary(self) -> str:
        """Get summary of exploration session"""
        summary = "Exploration Session Summary\n" + "="*50 + "\n"
        summary += f"Total Queries: {len(self.exploration_history)}\n"
        summary += f"Discovered Nodes: {len(self.discovered_nodes)}\n"
        summary += f"Current Location: {self.current_location or 'Repository Root'}\n\n"
        
        if self.exploration_history:
            summary += "Recent Explorations:\n"
            for hist in self.exploration_history[-5:]:
                summary += f"• {hist['query'][:50]}...\n"
        
        return summary
    
    def close(self):
        """Clean up resources"""
        if hasattr(self.db_manager, 'close'):
            self.db_manager.close()


def main():
    """Demo the code explorer agent"""
    print("Initializing Code Explorer Agent...")
    explorer = CodeExplorerAgent(verbose=True)
    
    # Example exploration tasks
    tasks = [
        "Show me the overall structure of this repository",
        "Find the main entry points in this codebase",
        "Search for any configuration or setup files",
        "Find and analyze the main.py file if it exists",
        "Look for any test files and show their structure"
    ]
    
    for task in tasks:
        print(f"\n{'='*60}")
        print(f"Task: {task}")
        print('='*60)
        result = explorer.explore(task)
        print(result)
    
    print("\n" + "="*60)
    print(explorer.get_exploration_summary())
    
    explorer.close()


if __name__ == "__main__":
    main()