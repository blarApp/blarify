#!/usr/bin/env python3
"""
Quick test script to verify the enhanced framework detection is working.
"""

import os
import sys
import logging
from pathlib import Path

# Add the blarify module to the path
sys.path.insert(0, str(Path(__file__).parent))

from blarify.agents.tools.code_explorer_tool import CodeExplorerTool
from blarify.db_managers.neo4j_manager import Neo4jManager
import dotenv

def test_code_explorer():
    """Test the CodeExplorer tool directly."""
    print("🔍 Testing CodeExplorer tool...")
    
    # Load environment variables
    dotenv.load_dotenv()
    
    # Setup simple logging
    logging.basicConfig(level=logging.INFO)
    
    # Create a simple graph manager
    graph_manager = Neo4jManager("test", "test")
    
    # Create the tool
    code_explorer = CodeExplorerTool(
        company_id="test",
        company_graph_manager=graph_manager,
    )
    
    explore_tool = code_explorer.get_tool()
    
    # Test a simple exploration
    print("📁 Testing configuration file exploration...")
    try:
        result = explore_tool.invoke({
            "exploration_goal": "Find configuration files like pyproject.toml"
        })
        print("✅ Exploration completed!")
        print(f"Result preview: {result[:200]}...")
        return True
    except Exception as e:
        print(f"❌ Exploration failed: {e}")
        return False
    finally:
        graph_manager.close()

if __name__ == "__main__":
    success = test_code_explorer()
    sys.exit(0 if success else 1)