#!/usr/bin/env python3
"""
Simple test to understand the framework detection requirements.
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

def test_simple_framework_detection():
    """Test a simple framework detection approach."""
    print("🔍 Testing simple framework detection...")
    
    # Load environment variables
    dotenv.load_dotenv()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Create graph manager
    graph_manager = Neo4jManager("test", "test")
    
    # Create the tool
    code_explorer = CodeExplorerTool(
        company_id="test",
        company_graph_manager=graph_manager,
    )
    
    explore_tool = code_explorer.get_tool()
    
    # Test framework detection goal
    print("📁 Testing framework detection...")
    try:
        result = explore_tool.invoke({
            "exploration_goal": "Detect the primary framework and technology stack of this codebase"
        })
        print("✅ Framework detection completed!")
        print(f"Result: {result}")
        return True
    except Exception as e:
        print(f"❌ Framework detection failed: {e}")
        return False
    finally:
        graph_manager.close()

if __name__ == "__main__":
    success = test_simple_framework_detection()
    sys.exit(0 if success else 1)