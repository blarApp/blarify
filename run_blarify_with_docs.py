#!/usr/bin/env python3
"""
Script to run Blarify with enhanced documentation generation.

This script demonstrates how to use the main_with_documentation function 
to build a code graph and generate comprehensive documentation using the 
enhanced framework detection with CodeExplorer.
"""

import os
import sys
import logging
from pathlib import Path

# Add the blarify module to the path
sys.path.insert(0, str(Path(__file__).parent))

from blarify.main import main_with_documentation
import dotenv

def setup_logging():
    """Configure logging for the script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('blarify_docs.log')
        ]
    )

def validate_environment():
    """Validate that required environment variables are set."""
    required_vars = ['NEO4J_URI', 'NEO4J_USERNAME', 'NEO4J_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {missing_vars}")
        print("Please set these in your .env file or environment:")
        print("  NEO4J_URI=bolt://localhost:7687")
        print("  NEO4J_USERNAME=neo4j")
        print("  NEO4J_PASSWORD=your_password")
        return False
    
    return True

def main():
    """Main function to run Blarify with documentation generation."""
    print("🚀 Starting Blarify with Enhanced Documentation Generation")
    print("=" * 60)
    
    # Setup logging
    setup_logging()
    
    # Load environment variables
    dotenv.load_dotenv()
    
    # Validate environment
    if not validate_environment():
        sys.exit(1)
    
    # Configuration
    root_path = os.getenv("ROOT_PATH", "/Users/pepemanu/Desktop/Trabajo/Blar/Dev/blarify")
    blarignore_path = os.getenv("BLARIGNORE_PATH")
    
    print(f"📁 Root path: {root_path}")
    print(f"🚫 Blarignore path: {blarignore_path or 'Not specified'}")
    print(f"🗄️  Neo4j URI: {os.getenv('NEO4J_URI')}")
    print()
    
    # Verify root path exists
    if not os.path.exists(root_path):
        print(f"❌ Root path does not exist: {root_path}")
        sys.exit(1)
    
    try:
        # Run the integrated workflow
        print("🔄 Running integrated graph building and documentation generation...")
        result = main_with_documentation(
            root_path=root_path,
            blarignore_path=blarignore_path
        )
        
        if result:
            print("\n✅ Documentation generation completed successfully!")
            print("=" * 60)
            
            # Display summary
            generated_docs = result.get("generated_docs", [])
            detected_framework = result.get("detected_framework", {})
            key_components = result.get("key_components", [])
            analyzed_nodes = result.get("analyzed_nodes", [])
            
            print(f"📊 Results Summary:")
            print(f"   • Generated documents: {len(generated_docs)}")
            print(f"   • Framework: {detected_framework.get('framework', {}).get('name', 'unknown')}")
            print(f"   • Confidence: {detected_framework.get('confidence_score', 0.0):.2f}")
            print(f"   • Key components: {len(key_components)}")
            print(f"   • Analyzed nodes: {len(analyzed_nodes)}")
            
            # Show exploration metadata if available
            exploration_meta = detected_framework.get("exploration_metadata", {})
            if exploration_meta:
                print(f"   • Exploration goals: {exploration_meta.get('goals_explored', 0)}")
                print(f"   • Successful explorations: {exploration_meta.get('successful_explorations', 0)}")
                print(f"   • Analysis method: {exploration_meta.get('analysis_method', 'standard')}")
            
            print("\n📄 Sample Documentation:")
            for i, doc in enumerate(generated_docs[:2]):  # Show first 2 docs
                doc_type = doc.get("type", "unknown")
                title = doc.get("title", "Untitled")
                content = doc.get("content", doc.get("documentation", ""))
                preview = content[:150] + "..." if len(content) > 150 else content
                print(f"   {i+1}. [{doc_type}] {title}")
                print(f"      {preview}")
                print()
            
            return True
            
        else:
            print("❌ Documentation generation failed!")
            return False
            
    except KeyboardInterrupt:
        print("\n⚠️  Process interrupted by user")
        return False
    except Exception as e:
        print(f"❌ Error during execution: {e}")
        logging.exception("Detailed error information:")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)