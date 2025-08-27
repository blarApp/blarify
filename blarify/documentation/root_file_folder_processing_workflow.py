"""
Folder Processing Workflow for analyzing individual folders with recursive DFS.

This module provides a dedicated LangGraph workflow for processing multiple root paths
using the existing RecursiveDFSProcessor for each root, providing better LangSmith tracking.
"""

from typing import TypedDict, Dict, Any, Optional, List, Literal
import logging

from langgraph.graph import START, END, StateGraph
from langgraph.types import Command

from ..agents.llm_provider import LLMProvider
from ..repositories.graph_db_manager.db_manager import AbstractDbManager
from ..graph.graph_environment import GraphEnvironment
from .utils.recursive_dfs_processor import BottomUpBatchProcessor, ProcessingResult

logger = logging.getLogger(__name__)


class RootFileFolderProcessingState(TypedDict):
    """State for processing multiple root paths sequentially."""

    # Sequential root processing
    current_root_index: int
    root_paths: List[str]

    # Results aggregation
    all_information_nodes: List[Dict[str, Any]]
    all_documentation_nodes: List[Any]  # Will store actual DocumentationNode objects
    all_source_nodes: List[Any]  # Will store actual Node objects

    # Control flow
    error: Optional[str]
    complete: bool


class RooFileFolderProcessingWorkflow:
    """
    Simplified workflow for processing multiple root folders using RecursiveDFSProcessor.

    This workflow processes each root path using the existing RecursiveDFSProcessor,
    providing better LangSmith tracking and avoiding workflow recursion limits.
    """

    def __init__(
        self,
        db_manager: AbstractDbManager,
        agent_caller: LLMProvider,
        company_id: str,
        repo_id: str,
        root_paths: List[str],
        graph_environment: GraphEnvironment,
        max_workers: int,
    ):
        """
        Initialize folder processing workflow for multiple root paths.

        Args:
            db_manager: Database manager for querying nodes
            agent_caller: LLM provider for generating descriptions
            company_id: Company/entity ID for database queries
            repo_id: Repository ID for database queries
            root_paths: List of root paths to process sequentially
            graph_environment: Graph environment for node ID generation
        """
        self.db_manager = db_manager
        self.agent_caller = agent_caller
        self.company_id = company_id
        self.repo_id = repo_id
        self.root_paths = root_paths
        self.graph_environment = graph_environment
        self._compiled_graph = None
        self.max_workers = max_workers

    def compile_graph(self):
        """Compile simple workflow for sequential root processing."""
        workflow = StateGraph(RootFileFolderProcessingState)

        # Simple workflow nodes
        workflow.add_node("process_next_root", self.process_next_root)
        workflow.add_node("save_final_results", self.save_final_results)

        # Entry point
        workflow.add_edge(START, "process_next_root")

        # All routing handled by Command/goto
        self._compiled_graph = workflow.compile()

    def process_next_root(
        self, state: RootFileFolderProcessingState
    ) -> Command[Literal["process_next_root", "save_final_results"]]:
        """Process roots sequentially using RecursiveDFSProcessor."""
        current_index = state.get("current_root_index", 0)

        if current_index >= len(self.root_paths):
            return Command(update={"complete": True}, goto="save_final_results")

        root_path = self.root_paths[current_index]
        logger.info(f"Starting processing for root: {root_path}")

        try:
            # Use RecursiveDFSProcessor for this root
            processor = BottomUpBatchProcessor(
                db_manager=self.db_manager,
                agent_caller=self.agent_caller,
                company_id=self.company_id,
                repo_id=self.repo_id,
                graph_environment=self.graph_environment,
                max_workers=self.max_workers,
            )

            # Process the root path
            result = processor.process_node(root_path)

            if result.error:
                logger.error(f"Error processing root {root_path}: {result.error}")
                # Continue to next root despite error
                return Command(update={"current_root_index": current_index + 1}, goto="process_next_root")

            # Results will be saved by DocumentationCreator, no need to save here

            # Aggregate results
            current_info_nodes = state.get("all_information_nodes", [])
            current_doc_nodes = state.get("all_documentation_nodes", [])
            current_source_nodes = state.get("all_source_nodes", [])

            updated_info_nodes = current_info_nodes + result.information_nodes
            updated_doc_nodes = current_doc_nodes + result.documentation_nodes
            updated_source_nodes = current_source_nodes + result.source_nodes

            logger.info(f"Completed processing for root: {root_path} ({len(result.information_nodes)} nodes)")

            return Command(
                update={
                    "current_root_index": current_index + 1,
                    "all_information_nodes": updated_info_nodes,
                    "all_documentation_nodes": updated_doc_nodes,
                    "all_source_nodes": updated_source_nodes,
                },
                goto="process_next_root",
            )

        except Exception as e:
            logger.exception(f"Error processing root {root_path}: {e}")
            return Command(update={"current_root_index": current_index + 1, "error": str(e)}, goto="process_next_root")

    def save_final_results(self, state: RootFileFolderProcessingState) -> Command[None]:
        """Complete the workflow - all roots have been processed and saved."""
        all_nodes = state.get("all_information_nodes", [])
        logger.info(f"All root paths processed. Total nodes: {len(all_nodes)}")

        return Command(update={"complete": True}, goto=END)

    def run(self) -> ProcessingResult:
        """
        Execute the root processing workflow.

        Returns:
            ProcessingResult with combined analysis results from all root paths
        """
        try:
            logger.info(f"Starting root processing workflow for {len(self.root_paths)} root paths: {self.root_paths}")

            if not self.root_paths:
                logger.warning("No root paths provided for processing")
                return ProcessingResult(node_path="", error="No root paths provided")

            # Ensure graph is compiled
            if not self._compiled_graph:
                self.compile_graph()

            # Initialize state
            initial_state = RootFileFolderProcessingState(
                current_root_index=0,
                root_paths=self.root_paths,
                all_information_nodes=[],
                all_documentation_nodes=[],
                all_source_nodes=[],
                error=None,
                complete=False,
            )

            # Execute workflow
            runnable_config = {"run_name": f"RootFolderProcessing_{len(self.root_paths)}_roots"}
            response = self._compiled_graph.invoke(input=initial_state, config=runnable_config)

            # Check for errors
            if response.get("error"):
                return ProcessingResult(node_path="root_processing", error=response["error"])

            # Get aggregated nodes
            all_information_nodes = response.get("all_information_nodes", [])
            all_documentation_nodes = response.get("all_documentation_nodes", [])
            all_source_nodes = response.get("all_source_nodes", [])

            logger.info(
                f"Root processing completed: {len(all_information_nodes)} total information nodes from {len(self.root_paths)} root paths"
            )

            # Create combined result
            result = ProcessingResult(
                node_path="root_processing",
                node_relationships=[],  # Not tracked at this level
                hierarchical_analysis={},  # Not tracked at this level
                error=None,
                node_source_mapping={},  # Not aggregated at this level
                information_nodes=all_information_nodes,
                documentation_nodes=all_documentation_nodes,
                source_nodes=all_source_nodes,
            )

            return result

        except Exception as e:
            logger.exception(f"Error running root processing workflow: {e}")
            return ProcessingResult(node_path="root_processing", error=str(e))
