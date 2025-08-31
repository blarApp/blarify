#!/usr/bin/env python3
"""Test script to verify workflow auto-generation in GetCodeByIdTool."""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.tools.get_code_by_id_tool import GetCodeByIdTool


def test_get_code_with_workflows():
    """Test the GetCodeByIdTool with workflow generation."""
    # Initialize Neo4j manager
    db_manager = Neo4jManager()
    
    # Create the tool with auto-generation enabled
    tool = GetCodeByIdTool(
        db_manager=db_manager,
        auto_generate_documentation=False,  # Disable doc generation for faster testing
        auto_generate_workflows=False,  # Start with no auto-generation to see existing data
    )
    
    # Test with a sample node ID (you'll need to replace this with an actual node ID from your database)
    # You can get a node ID by running a query to find a function node
    test_node_id = "YOUR_NODE_ID_HERE"  # Replace with an actual node ID
    
    print("Testing GetCodeByIdTool with workflows...")
    print("=" * 80)
    
    try:
        # First, let's find a valid node to test with
        query = """
        MATCH (n:NODE:FUNCTION {entityId: $entity_id, repoId: $repo_id})
        RETURN n.node_id as node_id, n.name as name
        LIMIT 5
        """
        params = {
            "entity_id": os.getenv("ENTITY_ID", "test_entity"),
            "repo_id": os.getenv("REPO_ID", "test_repo")
        }
        
        results = db_manager.query(query, params)
        
        if results:
            print("Found test nodes:")
            for result in results:
                print(f"  - {result['name']}: {result['node_id']}")
            
            # Use the first node for testing
            test_node_id = results[0]['node_id']
            print(f"\nUsing node: {test_node_id}")
            print("-" * 80)
            
            # Run the tool
            output = tool._run(node_id=test_node_id)
            print(output)
            
            # Now test with auto-generation enabled
            print("\n" + "=" * 80)
            print("Testing with workflow auto-generation enabled...")
            print("=" * 80)
            
            tool_with_auto = GetCodeByIdTool(
                db_manager=db_manager,
                auto_generate_documentation=False,
                auto_generate_workflows=True,
            )
            
            output_with_auto = tool_with_auto._run(node_id=test_node_id)
            print(output_with_auto)
            
        else:
            print("No function nodes found in the database.")
            print("Please ensure the database is populated with a parsed codebase.")
            
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_get_code_with_workflows()