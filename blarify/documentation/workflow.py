"""
LangGraph workflow implementation for the semantic documentation layer.

This module provides the core workflow orchestration for generating semantic documentation
from graph database analysis using LangGraph and LLM providers.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Annotated
from datetime import datetime

from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

from ..agents.llm_provider import LLMProvider
from ..agents.prompt_templates import get_framework_detection_prompt, get_system_overview_prompt
from ..db_managers.db_manager import AbstractDbManager
from ..db_managers.queries import get_codebase_skeleton

logger = logging.getLogger(__name__)


class DocumentationState(TypedDict):
    """State management structure for the LangGraph documentation workflow."""
    information_nodes: List[Dict[str, Any]]                        # InformationNode objects to create
    semantic_relationships: List[Dict[str, Any]]                   # Relationships between nodes
    analyzed_nodes: List[Dict[str, Any]]                           # Analyzed code components
    repo_structure: Dict[str, Any]                                 # Repository structure info
    dependencies: Dict[str, Any]                                   # Component relationships
    root_codebase_skeleton: str                                   # AST tree structure
    detected_framework: Dict[str, Any]                             # Framework info (Django, Next.js, etc.)
    system_overview: Dict[str, Any]                                # Business context & purpose
    doc_skeleton: Dict[str, Any]                                   # Documentation template
    key_components: List[Dict[str, Any]]                           # Priority components to analyze
    
    # Workflow metadata
    entity_id: str                                                 # Database entity ID
    environment: str                                               # Database environment
    workflow_status: str                                           # Current workflow status
    error_messages: List[str]                                      # Error tracking
    processing_timestamp: str                                      # Timestamp of processing


class DocumentationWorkflow:
    """Main workflow orchestrator for semantic documentation generation."""
    
    def __init__(
        self,
        db_manager: AbstractDbManager,
        llm_provider: Optional[LLMProvider] = None
    ):
        self.db_manager = db_manager
        
        # Initialize LLM provider
        self.llm_provider = llm_provider or LLMProvider()
        
        # Initialize workflow
        self.workflow = self._create_workflow()
        
        logger.info(f"DocumentationWorkflow initialized with {llm_provider_type} provider")
    
    def _create_workflow(self) -> StateGraph:
        """Create the LangGraph workflow."""
        workflow = StateGraph(DocumentationState)
        
        # Add nodes
        workflow.add_node("load_codebase", self._load_codebase_node)
        workflow.add_node("detect_framework", self._detect_framework_node)
        workflow.add_node("generate_overview", self._generate_overview_node)
        
        # Add edges
        workflow.add_edge("load_codebase", "detect_framework")
        workflow.add_edge("detect_framework", "generate_overview")
        workflow.add_edge("generate_overview", END)
        
        # Set entry point
        workflow.set_entry_point("load_codebase")
        
        return workflow.compile()
    
    def _load_codebase_node(self, state: DocumentationState) -> Dict[str, Any]:
        """
        Load codebase skeleton from database.
        
        Args:
            state: Current workflow state
            
        Returns:
            Dictionary with state updates
        """
        try:
            logger.info(f"Loading codebase skeleton for entity_id: {state['entity_id']}")
            
            # Extract required parameters
            entity_id = state["entity_id"]
            environment = state.get("environment", "default")
            
            # Get codebase skeleton from database
            skeleton = get_codebase_skeleton(self.db_manager, entity_id, environment)
            
            logger.info(f"Successfully loaded codebase skeleton ({len(skeleton)} characters)")
            
            return {
                "root_codebase_skeleton": skeleton,
                "workflow_status": "codebase_loaded"
            }
            
        except Exception as e:
            error_msg = f"Error loading codebase: {str(e)}"
            logger.error(error_msg)
            return {
                "workflow_status": "error",
                "error_messages": [error_msg]
            }
    
    def _detect_framework_node(self, state: DocumentationState) -> Dict[str, Any]:
        """
        Detect framework and technology stack from codebase structure.
        
        Args:
            state: Current workflow state
            
        Returns:
            Dictionary with state updates
        """
        try:
            logger.info("Detecting framework and technology stack")
            
            # Get codebase skeleton
            skeleton = state.get("root_codebase_skeleton", "")
            if not skeleton:
                raise ValueError("No codebase skeleton available")
            
            # Generate framework detection prompt
            prompt = get_framework_detection_prompt(skeleton)
            
            # Get LLM response using the average agent
            response = self.llm_provider.call_average_agent(
                input_dict={"prompt": prompt},
                output_schema=None,
                system_prompt="You are a framework detection expert. Analyze the codebase structure and return a JSON response with framework information.",
                input_prompt=prompt
            )
            
            # Parse JSON response
            try:
                # Extract content from the response object
                response_content = response.content if hasattr(response, 'content') else str(response)
                framework_info = json.loads(response_content)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON response: {e}")
                # Fallback to text response
                response_content = response.content if hasattr(response, 'content') else str(response)
                framework_info = {
                    "primary_language": "unknown",
                    "framework": {"name": "unknown", "category": "unknown"},
                    "architecture_pattern": "unknown",
                    "project_type": "unknown",
                    "confidence_score": 0.0,
                    "reasoning": response_content
                }
            
            logger.info(f"Detected framework: {framework_info.get('framework', {}).get('name', 'unknown')}")
            
            return {
                "detected_framework": framework_info,
                "workflow_status": "framework_detected"
            }
            
        except Exception as e:
            error_msg = f"Error detecting framework: {str(e)}"
            logger.error(error_msg)
            return {
                "workflow_status": "error",
                "error_messages": [error_msg]
            }
    
    def _generate_overview_node(self, state: DocumentationState) -> Dict[str, Any]:
        """
        Generate comprehensive system overview.
        
        Args:
            state: Current workflow state
            
        Returns:
            Dictionary with state updates
        """
        try:
            logger.info("Generating system overview")
            
            # Get required inputs
            skeleton = state.get("root_codebase_skeleton", "")
            framework_info = state.get("detected_framework", {})
            
            if not skeleton:
                raise ValueError("No codebase skeleton available")
            
            # Convert framework info to string for prompt
            framework_str = json.dumps(framework_info, indent=2)
            
            # Generate system overview prompt
            prompt = get_system_overview_prompt(skeleton, framework_str)
            
            # Get LLM response using the reasoning agent
            response = self.llm_provider.call_agent_with_reasoning(
                input_dict={"prompt": prompt},
                output_schema=None,
                system_prompt="You are a system architecture expert. Analyze the codebase and framework information to generate a comprehensive system overview.",
                input_prompt=prompt
            )
            
            # Parse JSON response
            try:
                # Extract content from the response object
                response_content = response.content if hasattr(response, 'content') else str(response)
                system_overview = json.loads(response_content)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON response: {e}")
                # Fallback to text response
                response_content = response.content if hasattr(response, 'content') else str(response)
                system_overview = {
                    "executive_summary": "Failed to parse structured response",
                    "business_domain": "unknown",
                    "primary_purpose": "unknown",
                    "raw_response": response_content
                }
            
            logger.info("Successfully generated system overview")
            
            return {
                "system_overview": system_overview,
                "workflow_status": "overview_generated"
            }
            
        except Exception as e:
            error_msg = f"Error generating overview: {str(e)}"
            logger.error(error_msg)
            return {
                "workflow_status": "error",
                "error_messages": [error_msg]
            }
    
    def run(self, entity_id: str, environment: str = "default") -> DocumentationState:
        """
        Execute the complete documentation workflow.
        
        Args:
            entity_id: Database entity ID
            environment: Database environment
            
        Returns:
            Final workflow state
        """
        try:
            logger.info(f"Starting documentation workflow for entity_id: {entity_id}")
            
            # Initialize state
            initial_state = DocumentationState(
                information_nodes=[],
                semantic_relationships=[],
                analyzed_nodes=[],
                repo_structure={},
                dependencies={},
                root_codebase_skeleton="",
                detected_framework={},
                system_overview={},
                doc_skeleton={},
                key_components=[],
                entity_id=entity_id,
                environment=environment,
                workflow_status="started",
                error_messages=[],
                processing_timestamp=datetime.now().isoformat()
            )
            
            # Execute workflow
            final_state = self.workflow.invoke(initial_state)
            
            logger.info(f"Documentation workflow completed with status: {final_state['workflow_status']}")
            
            return final_state
            
        except Exception as e:
            error_msg = f"Workflow execution failed: {str(e)}"
            logger.error(error_msg)
            
            # Return error state
            return DocumentationState(
                information_nodes=[],
                semantic_relationships=[],
                analyzed_nodes=[],
                repo_structure={},
                dependencies={},
                root_codebase_skeleton="",
                detected_framework={},
                system_overview={},
                doc_skeleton={},
                key_components=[],
                entity_id=entity_id,
                environment=environment,
                workflow_status="failed",
                error_messages=[error_msg],
                processing_timestamp=datetime.now().isoformat()
            )
    
    def get_workflow_status(self, state: DocumentationState) -> str:
        """Get current workflow status."""
        return state.get("workflow_status", "unknown")
    
    def has_errors(self, state: DocumentationState) -> bool:
        """Check if workflow has encountered errors."""
        return len(state.get("error_messages", [])) > 0
    
    def get_errors(self, state: DocumentationState) -> List[str]:
        """Get list of workflow errors."""
        return state.get("error_messages", [])


class DocumentationWorkflowFactory:
    """Factory for creating documentation workflows."""
    
    @staticmethod
    def create_workflow(
        db_manager: AbstractDbManager,
        llm_provider: Optional[LLMProvider] = None
    ) -> DocumentationWorkflow:
        """Create a documentation workflow with specified configuration."""
        
        return DocumentationWorkflow(
            db_manager=db_manager,
            llm_provider=llm_provider
        )
    
    @staticmethod
    def create_openai_workflow(
        db_manager: AbstractDbManager,
        reasoning_agent: str = "gpt-4"
    ) -> DocumentationWorkflow:
        """Create workflow with OpenAI provider."""
        llm_provider = LLMProvider(reasoning_agent=reasoning_agent)
        return DocumentationWorkflowFactory.create_workflow(
            db_manager=db_manager,
            llm_provider=llm_provider
        )
    
    @staticmethod
    def create_anthropic_workflow(
        db_manager: AbstractDbManager,
        reasoning_agent: str = "claude-sonnet-4-20250514"
    ) -> DocumentationWorkflow:
        """Create workflow with Anthropic provider."""
        llm_provider = LLMProvider(reasoning_agent=reasoning_agent)
        return DocumentationWorkflowFactory.create_workflow(
            db_manager=db_manager,
            llm_provider=llm_provider
        )


# Convenience functions for common use cases
def run_documentation_workflow(
    db_manager: AbstractDbManager,
    entity_id: str,
    environment: str = "default",
    llm_provider: Optional[LLMProvider] = None
) -> DocumentationState:
    """
    Run documentation workflow with default configuration.
    
    Args:
        db_manager: Database manager instance
        entity_id: Database entity ID
        environment: Database environment
        llm_provider: LLM provider instance (optional)
        
    Returns:
        Final workflow state
    """
    workflow = DocumentationWorkflowFactory.create_workflow(
        db_manager=db_manager,
        llm_provider=llm_provider
    )
    
    return workflow.run(entity_id, environment)


def get_codebase_analysis(
    db_manager: AbstractDbManager,
    entity_id: str,
    environment: str = "default"
) -> Dict[str, Any]:
    """
    Get comprehensive codebase analysis.
    
    Args:
        db_manager: Database manager instance
        entity_id: Database entity ID
        environment: Database environment
        
    Returns:
        Analysis results including framework and overview
    """
    state = run_documentation_workflow(db_manager, entity_id, environment)
    
    return {
        "framework": state.get("detected_framework", {}),
        "overview": state.get("system_overview", {}),
        "status": state.get("workflow_status", "unknown"),
        "errors": state.get("error_messages", []),
        "timestamp": state.get("processing_timestamp", "")
    }