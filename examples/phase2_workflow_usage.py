#!/usr/bin/env python3
"""
Example usage of the Phase 2 semantic documentation workflow.

This example demonstrates how to use the LangGraph workflow to analyze
a codebase and generate semantic documentation.
"""

import os
from blarify.documentation.workflow import (
    DocumentationWorkflow,
    DocumentationWorkflowFactory,
    run_documentation_workflow,
    get_codebase_analysis
)
from blarify.db_managers.falkordb_manager import FalkorDBManager
from blarify.agents.llm_provider import LLMProvider


def example_basic_usage():
    """Example of basic workflow usage."""
    print("=== Basic Workflow Usage ===")
    
    # Initialize database manager
    db_manager = FalkorDBManager(
        repo_id="my-repo",
        entity_id="my-entity",
        host="localhost",
        port=6379
    )
    
    try:
        # Run the workflow with default settings
        llm_provider = LLMProvider(reasoning_agent="claude-sonnet-4-20250514")
        result = run_documentation_workflow(
            db_manager=db_manager,
            entity_id="my-entity",
            environment="production",
            llm_provider=llm_provider
        )
        
        # Display results
        print(f"Workflow Status: {result['workflow_status']}")
        print(f"Detected Framework: {result['detected_framework'].get('framework', {}).get('name', 'Unknown')}")
        print(f"Project Type: {result['detected_framework'].get('project_type', 'Unknown')}")
        
        if result['system_overview']:
            print(f"Executive Summary: {result['system_overview'].get('executive_summary', 'N/A')}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        db_manager.close()


def example_custom_configuration():
    """Example of workflow with custom configuration."""
    print("\n=== Custom Configuration Usage ===")
    
    # Initialize database manager
    db_manager = FalkorDBManager(
        repo_id="my-repo",
        entity_id="my-entity",
        host="localhost",
        port=6379
    )
    
    try:
        # Create workflow with custom configuration
        workflow = DocumentationWorkflowFactory.create_anthropic_workflow(
            db_manager=db_manager,
            reasoning_agent="claude-sonnet-4-20250514"
        )
        
        # Run the workflow
        result = workflow.run(
            entity_id="my-entity",
            environment="development"
        )
        
        # Check for errors
        if workflow.has_errors(result):
            print("Workflow encountered errors:")
            for error in workflow.get_errors(result):
                print(f"  - {error}")
        else:
            print("Workflow completed successfully!")
            
            # Access detailed results
            framework = result.get('detected_framework', {})
            overview = result.get('system_overview', {})
            
            print(f"\nFramework Analysis:")
            print(f"  Primary Language: {framework.get('primary_language', 'Unknown')}")
            print(f"  Architecture: {framework.get('architecture_pattern', 'Unknown')}")
            print(f"  Confidence: {framework.get('confidence_score', 0.0):.2f}")
            
            print(f"\nSystem Overview:")
            print(f"  Business Domain: {overview.get('business_domain', 'Unknown')}")
            print(f"  Primary Purpose: {overview.get('primary_purpose', 'Unknown')}")
    
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        db_manager.close()


def example_analysis_only():
    """Example of getting just the analysis results."""
    print("\n=== Analysis Only Usage ===")
    
    # Initialize database manager
    db_manager = FalkorDBManager(
        repo_id="my-repo",
        entity_id="my-entity",
        host="localhost",
        port=6379
    )
    
    try:
        # Get comprehensive analysis
        analysis = get_codebase_analysis(
            db_manager=db_manager,
            entity_id="my-entity",
            environment="production"
        )
        
        print("Analysis Results:")
        print(f"  Status: {analysis['status']}")
        print(f"  Timestamp: {analysis['timestamp']}")
        
        if analysis['framework']:
            framework = analysis['framework']
            print(f"  Framework: {framework.get('framework', {}).get('name', 'Unknown')}")
            print(f"  Technology Stack: {framework.get('technology_stack', {})}")
        
        if analysis['overview']:
            overview = analysis['overview']
            print(f"  Executive Summary: {overview.get('executive_summary', 'N/A')[:100]}...")
        
        if analysis['errors']:
            print(f"  Errors: {analysis['errors']}")
    
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        db_manager.close()


def example_openai_usage():
    """Example of using OpenAI provider."""
    print("\n=== OpenAI Provider Usage ===")
    
    # Check if OpenAI API key is available
    if not os.getenv("OPENAI_API_KEY"):
        print("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
        return
    
    # Initialize database manager
    db_manager = FalkorDBManager(
        repo_id="my-repo",
        entity_id="my-entity",
        host="localhost",
        port=6379
    )
    
    try:
        # Create OpenAI workflow
        workflow = DocumentationWorkflowFactory.create_openai_workflow(
            db_manager=db_manager,
            model="gpt-4",
            temperature=0.1
        )
        
        # Run the workflow
        result = workflow.run(
            entity_id="my-entity",
            environment="production"
        )
        
        print(f"OpenAI Workflow Status: {result['workflow_status']}")
        
        if result.get('detected_framework'):
            framework = result['detected_framework']
            print(f"Detected Framework: {framework.get('framework', {}).get('name', 'Unknown')}")
            print(f"Reasoning: {framework.get('reasoning', 'N/A')[:100]}...")
    
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        db_manager.close()


def main():
    """Run all examples."""
    print("🚀 Phase 2 Workflow Usage Examples\n")
    
    # Check environment variables
    print("Environment Check:")
    print(f"  ANTHROPIC_API_KEY: {'✓' if os.getenv('ANTHROPIC_API_KEY') else '✗'}")
    print(f"  OPENAI_API_KEY: {'✓' if os.getenv('OPENAI_API_KEY') else '✗'}")
    print()
    
    # Note: These examples require actual database and API keys
    print("Note: These examples require:")
    print("  1. Running FalkorDB instance (docker run -d -p 6379:6379 falkordb/falkordb:latest)")
    print("  2. Valid LLM API keys (ANTHROPIC_API_KEY or OPENAI_API_KEY)")
    print("  3. Populated graph database with your codebase")
    print()
    
    # Uncomment to run examples (requires proper setup)
    # example_basic_usage()
    # example_custom_configuration()
    # example_analysis_only()
    # example_openai_usage()
    
    print("Examples are ready to run when you have the proper setup!")


if __name__ == "__main__":
    main()