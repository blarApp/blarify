"""
Documentation Generator Workflow for creating comprehensive documentation.

This module provides a LangGraph workflow that generates comprehensive documentation
for LLM agents by analyzing codebase structure and creating structured documentation content.
"""

from operator import add
from typing import Annotated, TypedDict, Dict, Any, Optional, List
import logging
from pathlib import Path

from langgraph.graph import START, StateGraph

from ..agents.llm_provider import LLMProvider
from ..agents.prompt_templates import FRAMEWORK_DETECTION_TEMPLATE
from ..db_managers.db_manager import AbstractDbManager
from ..db_managers.queries import get_codebase_skeleton, get_root_folders_and_files
from ..graph.graph_environment import GraphEnvironment
from .root_file_folder_processing_workflow import RooFileFolderProcessingWorkflow
from .workflow_analysis_workflow import WorkflowAnalysisWorkflow
from .main_documentation_workflow import MainDocumentationWorkflow

logger = logging.getLogger(__name__)


class DocumentationState(TypedDict):
    """State management for the documentation generation workflow."""

    # Fine-grained InformationNode data (stored in graph database)
    semantic_relationships: Annotated[list, add]  # Relationships between nodes
    code_references: Annotated[list, add]  # Precise code location mappings

    # Comprehensive markdown data (for file system)
    markdown_sections: Annotated[list, add]  # Narrative markdown content
    markdown_groupings: dict  # Logical groupings for .md files
    markdown_files: dict  # Final .md file contents

    # Shared analysis data
    analyzed_nodes: Annotated[list, add]  # Analyzed code components
    repo_structure: dict  # Repository structure info
    dependencies: dict  # Component relationships
    root_codebase_skeleton: str  # AST tree structure
    detected_framework: dict  # Framework info (Django, Next.js, etc.)
    system_overview: dict  # Business context & purpose
    doc_skeleton: dict  # Documentation template
    key_components: list  # Priority components to analyze

    # New fields for bottoms-up approach
    leaf_node_descriptions: Annotated[list, add]  # Initial descriptions of all leaf nodes

    # Workflow analysis fields
    discovered_workflows: List[Dict[str, Any]]  # From discover_workflows node
    workflow_analysis_results: Annotated[list, add]  # From process_workflows node
    workflow_relationships: Annotated[list, add]  # Workflow-specific relationships


class DocumentationWorkflow:
    """
    Agentic workflow for generating comprehensive documentation for LLM agents.
    Analyzes a particular branch using the AST code graph to understand codebase structure.
    """

    __company_id: str
    __company_graph_manager: AbstractDbManager
    __repo_id: str
    __agent_caller: LLMProvider
    __agent_type: str
    __compiled_graph: Optional[Any]

    def __init__(
        self,
        company_id: str,
        company_graph_manager: AbstractDbManager,
        repo_id: str,
        graph_environment: GraphEnvironment,
        agent_caller: Optional[LLMProvider] = None,
    ) -> None:
        self.__company_id = company_id
        self.__company_graph_manager = company_graph_manager
        self.__repo_id = repo_id
        self.__graph_environment = graph_environment
        self.__agent_caller = agent_caller if agent_caller else LLMProvider()
        self.__agent_type = "documentation_generator"
        self.__compiled_graph = None

    def compile_graph(self):
        """Compile the LangGraph workflow with normalized node names and orchestration approach."""
        workflow = StateGraph(DocumentationState)

        # Add workflow nodes with normalized names
        workflow.add_node("load_codebase", self.__load_codebase)
        workflow.add_node("detect_framework", self.__detect_framework)
        workflow.add_node("create_descriptions", self.__create_descriptions)
        workflow.add_node("get_workflows", self.__get_workflows)
        workflow.add_node("construct_general_documentation", self.__construct_general_documentation)

        # Sequential execution workflow with normalized names
        workflow.add_edge(START, "load_codebase")
        workflow.add_edge("load_codebase", "detect_framework")
        workflow.add_edge("detect_framework", "create_descriptions")
        workflow.add_edge("create_descriptions", "get_workflows")
        workflow.add_edge("get_workflows", "construct_general_documentation")

        self.__compiled_graph = workflow.compile()

    def __load_codebase(self, state: DocumentationState) -> Dict[str, Any]:
        """Load the root codebase skeleton from the AST code graph."""
        try:
            logger.info(f"Loading codebase skeleton for company_id: {self.__company_id}")

            root_skeleton = get_codebase_skeleton(
                db_manager=self.__company_graph_manager, entity_id=self.__company_id, repo_id=self.__repo_id
            )

            logger.info(f"Successfully loaded codebase skeleton ({len(root_skeleton)} characters)")
            return {"root_codebase_skeleton": root_skeleton}

        except Exception as e:
            logger.exception(f"Error loading codebase: {e}")
            return {"root_codebase_skeleton": f"Error loading codebase: {str(e)}"}

    def __detect_framework(self, state: DocumentationState) -> Dict[str, Any]:
        """Detect the primary framework, technology stack, and identify main architectural folders using structured output."""
        try:
            logger.info("Detecting framework and main folders with structured output")

            # Get the codebase structure from the state (loaded in previous node)
            codebase_structure = state.get("root_codebase_skeleton", "")

            if not codebase_structure:
                logger.exception("No codebase structure available - stopping workflow")
                raise ValueError("No codebase structure available")

            # Use the updated prompt template for combined framework detection and main folder identification
            system_prompt, input_prompt = FRAMEWORK_DETECTION_TEMPLATE.get_prompts()

            # Initialize only GetCodeByIdTool for config file reading
            tools = None
            try:
                from ..agents.tools import GetCodeByIdTool

                # Create code reader tool instance
                code_reader = GetCodeByIdTool(self.__company_graph_manager, self.__company_id)

                # Only provide the code reader tool
                tools = [code_reader]

                logger.info("GetCodeByIdTool initialized for config file reading")
            except Exception as e:
                logger.warning(f"Could not initialize GetCodeByIdTool: {e}. Running without tools.")
                tools = None

            # Use ReactAgent for framework detection with raw response
            response = self.__agent_caller.call_react_agent(
                system_prompt=system_prompt,
                tools=tools,
                input_dict={"codebase_structure": codebase_structure},
                input_prompt=input_prompt,
            )

            # Extract raw response content
            framework_analysis = response.content if hasattr(response, "content") else str(response)

            logger.info("Framework detection completed")

            # Return only framework analysis
            return {"detected_framework": framework_analysis}

        except Exception as e:
            logger.exception(f"Error detecting framework: {e}")
            raise  # Re-raise exception to stop workflow

    def __create_descriptions(self, state: DocumentationState) -> Dict[str, Any]:
        """Process all root-level folders and files using parallel RecursiveDFSProcessor nodes for better LangSmith tracking."""
        try:
            # Get all root folders and files from database
            root_paths = get_root_folders_and_files(
                db_manager=self.__company_graph_manager,
                entity_id=self.__company_id,
                repo_id=self.__repo_id,
            )

            if not root_paths:
                logger.warning("No root folders and files found - skipping analysis")
                return {"information_nodes": []}

            logger.info(f"Starting parallel root processing workflow for {len(root_paths)} root items: {root_paths}")

            # Create single workflow instance that will handle all root items in parallel
            parallel_workflow = RooFileFolderProcessingWorkflow(
                db_manager=self.__company_graph_manager,
                agent_caller=self.__agent_caller,
                company_id=self.__company_id,
                repo_id=self.__repo_id,
                root_paths=root_paths,  # Pass all root paths for parallel processing
                graph_environment=self.__graph_environment,
            )

            # Run the parallel workflow (creates individual nodes for each root path)
            workflow_result = parallel_workflow.run()

            if workflow_result.error:
                logger.exception(f"Error in parallel root processing workflow: {workflow_result.error}")
                return {"information_nodes": [], "error": workflow_result.error}

            # Get all information nodes from parallel processing
            all_information_nodes = workflow_result.information_nodes or []

            logger.info(
                f"Completed parallel root processing workflow: {len(all_information_nodes)} total information nodes from {len(root_paths)} root paths"
            )

            return {"information_nodes": all_information_nodes}

        except Exception as e:
            logger.exception(f"Error in parallel root processing workflow: {e}")
            return {"information_nodes": [], "error": str(e)}

    def __get_workflows(self, state: DocumentationState) -> Dict[str, Any]:
        """Orchestrate workflow analysis using WorkflowAnalysisWorkflow."""
        try:
            logger.info("Starting workflow analysis orchestration")

            # Get required data from state
            information_nodes = state.get("information_nodes", [])
            detected_framework = state.get("detected_framework", {})

            if not information_nodes:
                logger.warning("No information nodes available for workflow analysis")
                return {"discovered_workflows": [], "workflow_analysis_results": [], "workflow_relationships": []}

            # Create WorkflowAnalysisWorkflow instance
            workflow_analysis = WorkflowAnalysisWorkflow(
                company_id=self.__company_id,
                company_graph_manager=self.__company_graph_manager,
                repo_id=self.__repo_id,
                graph_environment=self.__graph_environment,
                agent_caller=self.__agent_caller,
            )

            # Prepare input data for the workflow analysis
            workflow_input = {
                "information_nodes": information_nodes,
                "detected_framework": detected_framework,
            }

            # Run the workflow analysis workflow
            workflow_result = workflow_analysis.run(workflow_input)

            logger.info("Workflow analysis orchestration completed")
            return {
                "discovered_workflows": workflow_result.get("discovered_workflows", []),
                "workflow_analysis_results": workflow_result.get("workflow_analysis_results", []),
                "workflow_relationships": workflow_result.get("workflow_relationships", []),
            }

        except Exception as e:
            logger.exception(f"Error in workflow analysis orchestration: {e}")
            return {
                "discovered_workflows": [],
                "workflow_analysis_results": [],
                "workflow_relationships": [],
                "error": str(e),
            }

    def __construct_general_documentation(self, state: DocumentationState) -> Dict[str, Any]:
        """Orchestrate final documentation generation using MainDocumentationWorkflow."""
        try:
            logger.info("Starting general documentation construction orchestration")

            # Get required data from state
            information_nodes = state.get("information_nodes", [])
            detected_framework = state.get("detected_framework", {})
            discovered_workflows = state.get("discovered_workflows", [])
            workflow_analysis_results = state.get("workflow_analysis_results", [])
            workflow_relationships = state.get("workflow_relationships", [])

            # Create MainDocumentationWorkflow instance
            main_documentation = MainDocumentationWorkflow(
                company_id=self.__company_id,
                company_graph_manager=self.__company_graph_manager,
                repo_id=self.__repo_id,
                graph_environment=self.__graph_environment,
                agent_caller=self.__agent_caller,
            )

            # Prepare input data for the main documentation workflow
            documentation_input = {
                "information_nodes": information_nodes,
                "detected_framework": detected_framework,
                "discovered_workflows": discovered_workflows,
                "workflow_analysis_results": workflow_analysis_results,
                "workflow_relationships": workflow_relationships,
            }

            # Run the main documentation workflow
            documentation_result = main_documentation.run(documentation_input)

            logger.info("General documentation construction orchestration completed")
            return {
                "markdown_sections": documentation_result.get("markdown_sections", []),
                "markdown_groupings": documentation_result.get("markdown_groupings", {}),
                "markdown_files": documentation_result.get("markdown_files", {}),
                "generated_docs": documentation_result.get("generated_docs", []),
            }

        except Exception as e:
            logger.exception(f"Error in general documentation construction orchestration: {e}")
            return {
                "markdown_sections": [],
                "markdown_groupings": {},
                "markdown_files": {"error": f"Documentation generation failed: {str(e)}"},
                "generated_docs": [],
                "error": str(e),
            }

    def run(self) -> dict:
        """Execute the complete documentation generation workflow."""
        try:
            logger.info("Starting documentation generation workflow")

            # Ensure graph is compiled
            if not self.__compiled_graph:
                self.compile_graph()

            # Initialize state with new dual-format fields
            initial_state = DocumentationState(
                # Fine-grained InformationNode data
                information_nodes=[],
                semantic_relationships=[],
                code_references=[],
                # Comprehensive markdown data
                markdown_sections=[],
                markdown_groupings={},
                markdown_files={},
                # Shared analysis data
                analyzed_nodes=[],
                repo_structure={},
                dependencies={},
                root_codebase_skeleton="",
                detected_framework={},
                system_overview={},
                doc_skeleton={},
                key_components=[],
                # New fields for bottoms-up approach
                leaf_node_descriptions=[],
                # Workflow analysis fields
                discovered_workflows=[],
                workflow_analysis_results=[],
                workflow_relationships=[],
            )

            # Execute workflow
            response = self.__compiled_graph.invoke(initial_state)

            logger.info("Documentation generation workflow completed successfully")
            return response

        except Exception as e:
            logger.exception(f"Error running documentation workflow: {e}")
            return {
                "markdown_files": {"error": f"Workflow execution failed: {str(e)}"},
                "information_nodes": [],
                "error": str(e),
            }
