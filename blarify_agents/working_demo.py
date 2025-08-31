"""
Working Demo - Direct Testing of Blarify Tools
This demonstrates the tools that are currently working
"""

import os
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.tools import (
    DirectoryExplorerTool,
    FindNodesByNameAndType,
    GetFileContextByIdTool,
    GetRelationshipFlowchart,
)


def demo_working_tools():
    """Demo the tools that are currently working"""
    
    print("="*60)
    print("BLARIFY TOOLS DEMO")
    print("Testing with repository: test/test")
    print("="*60)
    
    # Initialize database manager
    print("\n1. Initializing Neo4j connection...")
    try:
        db_manager = Neo4jManager(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
            repo_id="test",
            entity_id="test"
        )
        print("   ✓ Connected to Neo4j")
    except Exception as e:
        print(f"   ✗ Failed to connect: {e}")
        return
    
    # Demo 1: Directory Explorer
    print("\n2. Testing Directory Explorer Tool")
    print("-"*40)
    try:
        explorer = DirectoryExplorerTool(
            company_graph_manager=db_manager,
            company_id="test",
            repo_id="test"
        )
        
        # Find repository root
        root_node_id = explorer._find_repo_root()
        if root_node_id:
            print(f"   ✓ Found repository root: {root_node_id}")
            
            # List root contents
            print("\n   Repository structure:")
            tool = explorer.get_tool()
            contents = tool.invoke({"node_id": None})
            if contents:
                # Print first 20 lines of the directory listing
                lines = contents.split('\n')[:20]
                for line in lines:
                    print(f"     {line}")
                if len(contents.split('\n')) > 20:
                    print("     ...")
        else:
            print("   ✗ Could not find repository root")
            
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Demo 2: Find Nodes by Name and Type
    print("\n3. Testing Find Nodes by Name and Type")
    print("-"*40)
    try:
        find_tool = FindNodesByNameAndType(
            db_manager=db_manager,
            company_id="test",
            repo_id="test",
            diff_identifier="main"
        )
        
        # Search for main functions
        print("   Searching for 'main' functions...")
        result = find_tool._run(name="main", type="Function")
        if result and result.get("nodes"):
            print(f"   ✓ Found {len(result['nodes'])} main functions:")
            for node in result["nodes"][:5]:
                print(f"     - {node.get('name')} in {node.get('file_path')}")
        else:
            print("   → No 'main' functions found")
        
        # Search for __init__ methods
        print("\n   Searching for '__init__' methods...")
        result = find_tool._run(name="__init__", type="Function")
        if result and result.get("nodes"):
            print(f"   ✓ Found {len(result['nodes'])} __init__ methods:")
            for node in result["nodes"][:5]:
                print(f"     - {node.get('name')} in {node.get('file_path')}")
                if len(result["nodes"]) > 5:
                    print(f"     ... and {len(result['nodes']) - 5} more")
        else:
            print("   → No '__init__' methods found")
            
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Demo 3: Get File Context
    print("\n4. Testing Get File Context Tool")
    print("-"*40)
    try:
        context_tool = GetFileContextByIdTool(
            db_manager=db_manager,
            company_id="test"
        )
        
        # First find a file to get context for
        find_tool = FindNodesByNameAndType(
            db_manager=db_manager,
            company_id="test",
            repo_id="test",
            diff_identifier="main"
        )
        
        # Look for main.py or any Python file
        result = find_tool._run(name="main", type="File")
        if result and result.get("nodes"):
            node = result["nodes"][0]
            node_id = node.get("node_id")
            file_path = node.get("file_path")
            
            print(f"   Getting context for: {file_path}")
            print(f"   Node ID: {node_id[:16]}...")
            
            context = context_tool._run(node_id=node_id)
            if context:
                lines = context.split('\n')[:20]
                print("\n   File content (first 20 lines):")
                for line in lines:
                    print(f"     {line}")
                if len(context.split('\n')) > 20:
                    print("     ...")
            else:
                print("   ✗ Could not get file context")
        else:
            print("   → No suitable files found for context demo")
            
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Demo 4: Relationship Flowchart
    print("\n5. Testing Relationship Flowchart Tool")
    print("-"*40)
    try:
        flowchart_tool = GetRelationshipFlowchart(
            company_id="test",
            db_manager=db_manager,
            diff_identifier="main"
        )
        
        # Find a function to generate flowchart for
        find_tool = FindNodesByNameAndType(
            db_manager=db_manager,
            company_id="test",
            repo_id="test",
            diff_identifier="main"
        )
        
        result = find_tool._run(name="__init__", type="Function")
        if result and result.get("nodes"):
            node = result["nodes"][0]
            node_id = node.get("node_id")
            func_name = node.get("name")
            file_path = node.get("file_path")
            
            print(f"   Generating flowchart for: {func_name} in {file_path}")
            print(f"   Node ID: {node_id[:16]}...")
            
            flowchart = flowchart_tool._run(node_id=node_id)
            if flowchart:
                print("\n   Mermaid Flowchart:")
                lines = flowchart.split('\n')[:15]
                for line in lines:
                    print(f"     {line}")
                if len(flowchart.split('\n')) > 15:
                    print("     ...")
            else:
                print("   → No relationships found for flowchart")
        else:
            print("   → No suitable functions found for flowchart demo")
            
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Close connection
    if hasattr(db_manager, 'close'):
        db_manager.close()
    
    print("\n" + "="*60)
    print("Demo completed!")
    print("\nNote: Some tools require fixes to work properly:")
    print("- FindNodesByCode: Needs 'get_nodes_by_text' method in Neo4jManager")
    print("- FindNodesByPath: Needs 'get_nodes_by_path' method in Neo4jManager")
    print("- GetCodeByIdTool: Parameter mismatch issues")
    print("="*60)


if __name__ == "__main__":
    demo_working_tools()