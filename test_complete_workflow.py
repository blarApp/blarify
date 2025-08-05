#!/usr/bin/env python3
"""
Test script to run just the documentation workflow portion.
"""

import os
import sys
import logging
from pathlib import Path

# Add the blarify module to the path
sys.path.insert(0, str(Path(__file__).parent))

from blarify.documentation.workflow import DocumentationWorkflow
from blarify.agents.llm_provider import LLMProvider
from blarify.db_managers.neo4j_manager import Neo4jManager
import dotenv

def test_documentation_workflow():
    """Test the documentation workflow with enhanced framework detection."""
    print("📚 Testing documentation workflow...")
    
    # Load environment variables
    dotenv.load_dotenv()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Create graph manager
    graph_manager = Neo4jManager("test", "test")
    
    try:
        # Initialize the documentation workflow
        llm_provider = LLMProvider()
        documentation_workflow = DocumentationWorkflow(
            company_id="test",
            company_graph_manager=graph_manager,
            environment="default",
            agent_caller=llm_provider
        )
        
        print("🔄 Running documentation workflow...")
        
        # Run only the first few steps to test framework detection
        result = documentation_workflow.run()
        
        if result:
            print("✅ Documentation workflow completed!")
            
            # Display results
            detected_framework = result.get("detected_framework", {})
            print(f"🔍 Framework detected: {detected_framework.get('framework', {}).get('name', 'unknown')}")
            print(f"📊 Confidence: {detected_framework.get('confidence_score', 0.0)}")
            
            # Show exploration metadata
            exploration_meta = detected_framework.get("exploration_metadata", {})
            if exploration_meta:
                print(f"🎯 Exploration goals: {exploration_meta.get('goals_explored', 0)}")
                print(f"✅ Successful explorations: {exploration_meta.get('successful_explorations', 0)}")
            
            return True
        else:
            print("❌ Documentation workflow failed!")
            return False
            
    except Exception as e:
        print(f"❌ Error during workflow: {e}")
        return False
    finally:
        graph_manager.close()

if __name__ == "__main__":
    success = test_documentation_workflow()
    sys.exit(0 if success else 1)