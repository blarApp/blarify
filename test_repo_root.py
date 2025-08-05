#!/usr/bin/env python3
"""
Test script to verify repository root detection.
"""

import os
import sys
import logging
from pathlib import Path

# Add the blarify module to the path
sys.path.insert(0, str(Path(__file__).parent))

from blarify.agents.tools.directory_explorer_tool import DirectoryExplorerTool
from blarify.db_managers.neo4j_manager import Neo4jManager
import dotenv

def test_repo_root_detection():
    """Test if the repository root can be found."""
    print("🔍 Testing repository root detection...")
    
    # Load environment variables
    dotenv.load_dotenv()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Create a graph manager
    graph_manager = Neo4jManager("test", "test")
    
    # Create the directory explorer tool
    directory_explorer = DirectoryExplorerTool(
        company_graph_manager=graph_manager,
        company_id="test",
        repo_id="test"
    )
    
    try:
        # Test finding the repository root
        print("🔍 Looking for repository root...")
        repo_root = directory_explorer._find_repo_root()
        
        if repo_root:
            print(f"✅ Repository root found: {repo_root}")
            
            # Test listing directory contents
            print("📁 Testing directory listing...")
            contents = directory_explorer._list_directory_children(repo_root)
            print(f"✅ Found {len(contents)} items in root directory")
            
            # Show first few items
            for i, item in enumerate(contents[:5]):
                print(f"   {i+1}. {item.get('name', 'Unknown')} ({item.get('type', 'Unknown type')})")
            
            return True
        else:
            print("❌ Repository root not found!")
            
            # Try a direct query to see what nodes exist
            print("🔍 Checking what nodes exist in the database...")
            query = """
            MATCH (n:NODE {entityId: "test", repoId: "test"})
            RETURN n.environment as env, n.level as level, n.name as name, n.node_path as path, labels(n) as types
            ORDER BY n.level, n.name
            LIMIT 10
            """
            
            result = graph_manager.query(query, {})
            if result:
                print(f"Found {len(result)} nodes:")
                for node in result:
                    print(f"  - {node['name']} (level: {node['level']}, env: {node['env']}, path: {node['path']})")
            else:
                print("No nodes found in database!")
            
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        return False
    finally:
        graph_manager.close()

if __name__ == "__main__":
    success = test_repo_root_detection()
    sys.exit(0 if success else 1)