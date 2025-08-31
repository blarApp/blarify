"""
Direct test of Blarify tools without LangChain
This script tests each tool directly to understand their actual interfaces
"""

import os
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


def test_tools():
    """Test each tool directly"""
    
    # Initialize database manager
    print("Initializing Neo4j Manager...")
    try:
        db_manager = Neo4jManager(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
            repo_id="test",
            entity_id="test"
        )
        print("✓ Neo4j Manager initialized")
    except Exception as e:
        print(f"✗ Failed to initialize Neo4j Manager: {e}")
        return
    
    # Test DirectoryExplorerTool
    print("\n" + "="*60)
    print("Testing DirectoryExplorerTool")
    print("="*60)
    try:
        explorer = DirectoryExplorerTool(
            company_graph_manager=db_manager,
            company_id="test",
            repo_id="test"
        )
        print("✓ DirectoryExplorerTool initialized")
        
        # Try to find repo root
        try:
            root_info = explorer._find_repo_root()
            print(f"✓ Found repo root: {root_info}")
        except Exception as e:
            print(f"✗ Failed to find repo root: {e}")
            
    except Exception as e:
        print(f"✗ Failed to initialize DirectoryExplorerTool: {e}")
    
    # Test FindNodesByCode
    print("\n" + "="*60)
    print("Testing FindNodesByCode")
    print("="*60)
    try:
        find_by_code = FindNodesByCode(
            db_manager=db_manager,
            company_id="test",
            repo_id="test",
            diff_identifier="main"
        )
        print("✓ FindNodesByCode initialized")
        
        # Test searching for 'def'
        try:
            result = find_by_code._run(code="def")
            print(f"✓ Search for 'def' returned: {len(result.get('nodes', [])) if result else 0} nodes")
        except Exception as e:
            print(f"✗ Failed to search for 'def': {e}")
            
    except Exception as e:
        print(f"✗ Failed to initialize FindNodesByCode: {e}")
    
    # Test FindNodesByNameAndType
    print("\n" + "="*60)
    print("Testing FindNodesByNameAndType")
    print("="*60)
    try:
        find_by_name = FindNodesByNameAndType(
            db_manager=db_manager,
            company_id="test",
            repo_id="test",
            diff_identifier="main"
        )
        print("✓ FindNodesByNameAndType initialized")
        
        # Test searching for 'main' function
        try:
            # Check what parameters it actually expects
            import inspect
            sig = inspect.signature(find_by_name._run)
            print(f"  _run method signature: {sig}")
            
            result = find_by_name._run(name="main", type="Function")
            print(f"✓ Search for 'main' function returned: {result}")
        except Exception as e:
            print(f"✗ Failed to search for 'main': {e}")
            
    except Exception as e:
        print(f"✗ Failed to initialize FindNodesByNameAndType: {e}")
    
    # Test FindNodesByPath
    print("\n" + "="*60)
    print("Testing FindNodesByPath")
    print("="*60)
    try:
        find_by_path = FindNodesByPath(
            db_manager=db_manager,
            company_id="test",
            repo_id="test",
            diff_identifier="main"
        )
        print("✓ FindNodesByPath initialized")
        
        # Test searching for main.py
        try:
            # Check what parameters it actually expects
            import inspect
            sig = inspect.signature(find_by_path._run)
            print(f"  _run method signature: {sig}")
            
            result = find_by_path._run(path="main.py")
            print(f"✓ Search for 'main.py' returned: {result}")
        except Exception as e:
            print(f"✗ Failed to search for 'main.py': {e}")
            
    except Exception as e:
        print(f"✗ Failed to initialize FindNodesByPath: {e}")
    
    # Test GetCodeByIdTool
    print("\n" + "="*60)
    print("Testing GetCodeByIdTool")
    print("="*60)
    try:
        # Check the actual constructor
        import inspect
        sig = inspect.signature(GetCodeByIdTool.__init__)
        print(f"  GetCodeByIdTool.__init__ signature: {sig}")
        
        get_code = GetCodeByIdTool(
            db_manager=db_manager,
            auto_generate_documentation=False
        )
        print("✓ GetCodeByIdTool initialized")
        
    except Exception as e:
        print(f"✗ Failed to initialize GetCodeByIdTool: {e}")
    
    # Test GetFileContextByIdTool
    print("\n" + "="*60)
    print("Testing GetFileContextByIdTool")
    print("="*60)
    try:
        get_context = GetFileContextByIdTool(
            db_manager=db_manager,
            company_id="test"
        )
        print("✓ GetFileContextByIdTool initialized")
        
    except Exception as e:
        print(f"✗ Failed to initialize GetFileContextByIdTool: {e}")
    
    # Test GetRelationshipFlowchart
    print("\n" + "="*60)
    print("Testing GetRelationshipFlowchart")
    print("="*60)
    try:
        get_flowchart = GetRelationshipFlowchart(
            company_id="test",
            db_manager=db_manager,
            diff_identifier="main"
        )
        print("✓ GetRelationshipFlowchart initialized")
        
    except Exception as e:
        print(f"✗ Failed to initialize GetRelationshipFlowchart: {e}")
    
    # Close database connection
    if hasattr(db_manager, 'close'):
        db_manager.close()
    
    print("\n" + "="*60)
    print("Testing complete!")


if __name__ == "__main__":
    test_tools()