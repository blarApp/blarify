"""
Main Documentation Workflow for generating comprehensive documentation files.

This module provides a dedicated LangGraph workflow for the final steps of documentation
generation: grouping related knowledge, creating markdown sections, and consolidating
final documentation files.
"""

from operator import add
from typing import Annotated, TypedDict, Dict, Any, Optional, List
import logging

from langgraph.graph import START, StateGraph

from ..agents.llm_provider import LLMProvider
from ..db_managers.db_manager import AbstractDbManager
from ..graph.graph_environment import GraphEnvironment

logger = logging.getLogger(__name__)


class MainDocumentationState(TypedDict):
    """State management for main documentation workflow."""
    
    # Input data
    main_folders: List[str]
    detected_framework: Dict[str, Any]
    discovered_workflows: List[Dict[str, Any]]
    workflow_analysis_results: Annotated[list, add]
    workflow_relationships: Annotated[list, add]
    
    # Output data  
    markdown_sections: Annotated[list, add]  # Narrative markdown content
    markdown_groupings: Dict[str, Any]  # Logical groupings for .md files
    markdown_files: Dict[str, Any]  # Final .md file contents
    generated_docs: List[Dict[str, Any]]  # Final documentation output
    error: Optional[str]


class MainDocumentationWorkflow:
    """
    Dedicated workflow for the final documentation generation steps.
    
    This workflow takes processed information nodes and workflows to generate
    the final markdown documentation files with proper grouping and consolidation.
    """
    
    def __init__(
        self,
        company_id: str,
        company_graph_manager: AbstractDbManager,
        repo_id: str,
        graph_environment: GraphEnvironment,
        agent_caller: Optional[LLMProvider] = None,
    ) -> None:
        self.company_id = company_id
        self.company_graph_manager = company_graph_manager
        self.repo_id = repo_id
        self.graph_environment = graph_environment
        self.agent_caller = agent_caller if agent_caller else LLMProvider()
        self._compiled_graph = None
    
    def compile_graph(self):
        """Compile the main documentation workflow graph."""
        workflow = StateGraph(MainDocumentationState)
        
        # Add documentation generation nodes
        workflow.add_node("group_related_knowledge", self._group_related_knowledge)
        workflow.add_node("compact_to_markdown_per_folder", self._compact_to_markdown_per_folder)
        workflow.add_node("consolidate_final_markdown", self._consolidate_final_markdown)
        
        # Linear flow for documentation generation
        workflow.add_edge(START, "group_related_knowledge")
        workflow.add_edge("group_related_knowledge", "compact_to_markdown_per_folder")
        workflow.add_edge("compact_to_markdown_per_folder", "consolidate_final_markdown")
        
        self._compiled_graph = workflow.compile()
    
    def _group_related_knowledge(self, state: MainDocumentationState) -> Dict[str, Any]:
        """Group related InformationNodes within each folder hierarchy."""
        logger.info("Grouping related knowledge node called - raising NotImplementedError as planned")
        raise NotImplementedError("group_related_knowledge node needs to be implemented")
    
    def _compact_to_markdown_per_folder(self, state: MainDocumentationState) -> Dict[str, Any]:
        """Generate markdown sections for each main folder."""
        logger.info("Compact to markdown per folder node called - raising NotImplementedError as planned")
        raise NotImplementedError("compact_to_markdown_per_folder node needs to be implemented")
    
    def _consolidate_final_markdown(self, state: MainDocumentationState) -> Dict[str, Any]:
        """Combine all folder-based markdown into comprehensive documentation."""
        logger.info("Consolidate final markdown node called - raising NotImplementedError as planned")
        raise NotImplementedError("consolidate_final_markdown node needs to be implemented")
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run main documentation workflow independently.
        
        Args:
            input_data: Dictionary containing information_nodes, main_folders, detected_framework,
                       discovered_workflows, workflow_analysis_results, and workflow_relationships
                       
        Returns:
            Dictionary with final documentation results
        """
        try:
            logger.info("Starting main documentation workflow")
            
            # Ensure graph is compiled
            if not self._compiled_graph:
                self.compile_graph()
            
            # Initialize state
            initial_state = MainDocumentationState(
                main_folders=input_data.get("main_folders", []),
                detected_framework=input_data.get("detected_framework", {}),
                discovered_workflows=input_data.get("discovered_workflows", []),
                workflow_analysis_results=input_data.get("workflow_analysis_results", []),
                workflow_relationships=input_data.get("workflow_relationships", []),
                markdown_sections=[],
                markdown_groupings={},
                markdown_files={},
                generated_docs=[],
                error=None
            )
            
            # Execute workflow
            runnable_config = {"run_name": "main_documentation"}
            response = self._compiled_graph.invoke(input=initial_state, config=runnable_config)
            
            logger.info("Main documentation workflow completed successfully")
            return response
            
        except Exception as e:
            logger.exception(f"Error running main documentation workflow: {e}")
            return {
                "markdown_sections": [],
                "markdown_groupings": {},
                "markdown_files": {"error": f"Workflow execution failed: {str(e)}"},
                "generated_docs": [],
                "error": str(e)
            }