#!/usr/bin/env python3
"""
Test the framework detection workflow step by step.
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

def test_framework_detection_step():
    """Test just the framework detection step."""
    print("🔍 Testing framework detection step...")
    
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
        
        # Test just the framework detection step
        print("🔄 Testing framework detection...")
        
        # Create a minimal state for testing
        state = {
            "root_codebase_skeleton": "test_skeleton"
        }
        
        # Call the framework detection method directly
        result = documentation_workflow._DocumentationWorkflow__detect_framework(state)
        
        if result:
            print("✅ Framework detection completed!")
            
            # Display results
            detected_framework = result.get("detected_framework", {})
            print(f"🔍 Framework: {detected_framework.get('framework', {}).get('name', 'unknown')}")
            print(f"📊 Confidence: {detected_framework.get('confidence_score', 0.0)}")
            print(f"🔧 Method: {detected_framework.get('exploration_metadata', {}).get('analysis_method', 'unknown')}")
            
            # Show reasoning (first 200 chars)
            reasoning = detected_framework.get('reasoning', '')
            print(f"💭 Reasoning: {reasoning[:200]}...")
            
            return True
        else:
            print("❌ Framework detection failed!")
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        graph_manager.close()

if __name__ == "__main__":
    success = test_framework_detection_step()
    sys.exit(0 if success else 1)