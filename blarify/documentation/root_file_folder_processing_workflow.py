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
from ..db_managers.db_manager import AbstractDbManager
from ..graph.graph_environment import GraphEnvironment
from .utils.recursive_dfs_processor import RecursiveDFSProcessor, ProcessingResult

logger = logging.getLogger(__name__)


class RootFileFolderProcessingState(TypedDict):
    """State for processing multiple root paths sequentially."""

    # Sequential root processing
    current_root_index: int
    root_paths: List[str]
    
    # Results aggregation
    all_information_nodes: List[Dict[str, Any]]
    
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
            processor = RecursiveDFSProcessor(
                db_manager=self.db_manager,
                agent_caller=self.agent_caller,
                company_id=self.company_id,
                repo_id=self.repo_id,
                graph_environment=self.graph_environment,
            )
            
            # Process the root path
            result = processor.process_node(root_path)
            
            if result.error:
                logger.error(f"Error processing root {root_path}: {result.error}")
                # Continue to next root despite error
                return Command(
                    update={"current_root_index": current_index + 1},
                    goto="process_next_root"
                )
            
            # Save results to database immediately
            if result.information_nodes:
                logger.info(f"Saving {len(result.information_nodes)} nodes for root: {root_path}")
                self._save_information_nodes(result.information_nodes, result.node_source_mapping)
                
            # Aggregate results
            current_nodes = state.get("all_information_nodes", [])
            updated_nodes = current_nodes + result.information_nodes
            
            logger.info(f"Completed processing for root: {root_path} ({len(result.information_nodes)} nodes)")
            
            return Command(
                update={
                    "current_root_index": current_index + 1,
                    "all_information_nodes": updated_nodes,
                },
                goto="process_next_root"
            )
            
        except Exception as e:
            logger.exception(f"Error processing root {root_path}: {e}")
            return Command(
                update={
                    "current_root_index": current_index + 1,
                    "error": str(e)
                },
                goto="process_next_root"
            )

    def save_final_results(self, state: RootFileFolderProcessingState) -> Command[None]:
        """Complete the workflow - all roots have been processed and saved."""
        all_nodes = state.get("all_information_nodes", [])
        logger.info(f"All root paths processed. Total nodes: {len(all_nodes)}")
        
        return Command(update={"complete": True}, goto=END)

    def _save_information_nodes(
        self, information_nodes: List[Dict[str, Any]], node_source_mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Save information nodes to the database and create DESCRIBES relationships.

        Args:
            information_nodes: List of InformationNode dictionaries (from .as_object())
            node_source_mapping: Mapping of info_node_id -> source_node_id

        Returns:
            Dictionary with save status including counts and any errors
        """
        save_status = {"nodes_saved": 0, "relationships_created": 0, "errors": [], "success": False}

        try:
            # Save nodes to database
            if information_nodes:
                logger.info(f"Saving {len(information_nodes)} information nodes to database")
                self.db_manager.create_nodes(information_nodes)
                save_status["nodes_saved"] = len(information_nodes)

                # Create DESCRIBES relationships
                edges_list = []
                for node_dict in information_nodes:
                    node_id = node_dict.get("attributes", {}).get("node_id")
                    if node_id and node_id in node_source_mapping:
                        edge = {
                            "sourceId": node_id,  # Information node
                            "targetId": node_source_mapping[node_id],  # Target code node
                            "type": "DESCRIBES",
                            "scopeText": "semantic_documentation",
                        }
                        edges_list.append(edge)

                if edges_list:
                    logger.info(f"Creating {len(edges_list)} DESCRIBES relationships")
                    self.db_manager.create_edges(edges_list)
                    save_status["relationships_created"] = len(edges_list)

            save_status["success"] = True
            logger.info(
                f"Successfully saved {save_status['nodes_saved']} nodes and created {save_status['relationships_created']} relationships"
            )

        except Exception as e:
            logger.exception(f"Error saving information nodes: {e}")
            save_status["errors"].append(f"Database save error: {str(e)}")
            save_status["success"] = False

        return save_status

    def run(self) -> ProcessingResult:
        """
        Execute the root processing workflow.

        Returns:
            ProcessingResult with combined analysis results from all root paths
        """
        try:
            logger.info(
                f"Starting root processing workflow for {len(self.root_paths)} root paths: {self.root_paths}"
            )

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
                error=None,
                complete=False,
            )

            # Execute workflow
            runnable_config = {"run_name": f"RootFolderProcessing_{len(self.root_paths)}_roots"}
            response = self._compiled_graph.invoke(input=initial_state, config=runnable_config)

            # Check for errors
            if response.get("error"):
                return ProcessingResult(node_path="root_processing", error=response["error"])

            # Get aggregated information nodes
            all_information_nodes = response.get("all_information_nodes", [])

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
            )

            return result

        except Exception as e:
            logger.exception(f"Error running root processing workflow: {e}")
            return ProcessingResult(node_path="root_processing", error=str(e))