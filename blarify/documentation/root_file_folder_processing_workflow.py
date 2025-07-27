"""
Folder Processing Workflow for analyzing individual folders with recursive DFS.

This module provides a dedicated LangGraph workflow for processing a single folder,
making it easier to track individual folder processing in LangSmith and enabling
parallel processing of multiple folders.
"""

from operator import add
from typing import TypedDict, Dict, Any, Optional, List, Annotated
import logging
from pathlib import Path

from langgraph.graph import START, StateGraph

from ..agents.llm_provider import LLMProvider
from ..db_managers.db_manager import AbstractDbManager
from ..graph.graph_environment import GraphEnvironment
from .utils.recursive_dfs_processor import RecursiveDFSProcessor, ProcessingResult

logger = logging.getLogger(__name__)


class RootFileFolderProcessingState(TypedDict):
    """State management for parallel root item processing workflow."""

    root_paths: List[str]  # All root paths to process
    information_nodes: Annotated[List[Dict[str, Any]], add]  # Aggregated information nodes
    error: Optional[str]
    save_status: Dict[str, Any]  # Status of database save operations


class RooFileFolderProcessingWorkflow:
    """
    Dedicated workflow for processing multiple root folders with parallel DFS analysis.

    This workflow creates individual RecursiveDFSProcessor nodes for each root path,
    providing better LangSmith tracking and parallel execution.
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
            root_paths: List of root paths to process in parallel
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
        """Compile the parallel root processing workflow graph."""
        workflow = StateGraph(RootFileFolderProcessingState)

        # Create one processing node per root path for individual LangSmith tracking
        for i, root_path in enumerate(self.root_paths):
            node_name = f"process_root_{i}_{Path(root_path).name}"
            workflow.add_node(node_name, self._create_processor_node(root_path))
            workflow.add_edge(START, node_name)  # Fan-out

        # Add aggregation node if we have multiple roots
        if len(self.root_paths) > 1:
            workflow.add_node("aggregate_results", self._aggregate_information_nodes)
            
            # Fan-in: all processor nodes to aggregator
            for i, root_path in enumerate(self.root_paths):
                node_name = f"process_root_{i}_{Path(root_path).name}"
                workflow.add_edge(node_name, "aggregate_results")
        
        self._compiled_graph = workflow.compile()

    def _create_processor_node(self, root_path: str):
        """Create a dedicated node function for processing a specific root path."""
        def process_single_root(state: RootFileFolderProcessingState) -> Dict[str, Any]:
            logger.info(f"Processing root item: {root_path}")
            
            try:
                # Create RecursiveDFSProcessor for this specific root
                processor = RecursiveDFSProcessor(
                    db_manager=self.db_manager,
                    agent_caller=self.agent_caller,
                    company_id=self.company_id,
                    repo_id=self.repo_id,
                    graph_environment=self.graph_environment,
                )
                
                # Process this root item
                result = processor.process_node(root_path)
                
                if result.error:
                    logger.error(f"Error processing {root_path}: {result.error}")
                    return {"information_nodes": []}
                
                # Save to database immediately
                save_status = self._save_information_nodes(
                    result.information_nodes, 
                    result.node_source_mapping
                )
                
                logger.info(f"Completed {root_path}: {len(result.information_nodes)} nodes, save status: {save_status}")
                return {"information_nodes": result.information_nodes}
                
            except Exception as e:
                logger.exception(f"Error in processor node for {root_path}: {e}")
                return {"information_nodes": []}
        
        return process_single_root

    def _aggregate_information_nodes(self, state: RootFileFolderProcessingState) -> Dict[str, Any]:
        """Aggregate results from all parallel root processing nodes."""
        all_info_nodes = state.get("information_nodes", [])
        logger.info(f"Aggregated {len(all_info_nodes)} total information nodes from all parallel root processors")
        return {"information_nodes": all_info_nodes}

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
            # The information_nodes are already in the correct format from InformationNode.as_object()
            info_node_objects = information_nodes

            # Save nodes to database
            if info_node_objects:
                logger.info(f"Saving {len(info_node_objects)} information nodes to database")
                self.db_manager.create_nodes(info_node_objects)
                save_status["nodes_saved"] = len(info_node_objects)

                # Only create relationships for successfully converted nodes
                # Create DESCRIBES relationships
                edges_list = []
                for node_dict in information_nodes:
                    node_id = node_dict.get("attributes", {}).get("node_id")
                    if node_id:
                        # Only create edge if node was successfully converted
                        if any(obj["attributes"]["node_id"] == node_id for obj in info_node_objects):
                            if node_id in node_source_mapping:
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
            else:
                # If no nodes were converted, still try to create relationships from mapping
                # This handles the case where all mappings should be created regardless
                edges_list = []
                for info_node_id, source_node_id in node_source_mapping.items():
                    edge = {
                        "sourceId": info_node_id,  # Information node
                        "targetId": source_node_id,  # Target code node
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
        Execute the parallel root processing workflow.

        Returns:
            ProcessingResult with combined analysis results from all root paths
        """
        try:
            logger.info(f"Starting parallel root processing workflow for {len(self.root_paths)} root paths: {self.root_paths}")

            if not self.root_paths:
                logger.warning("No root paths provided for processing")
                return ProcessingResult(node_path="", error="No root paths provided")

            # Ensure graph is compiled
            if not self._compiled_graph:
                self.compile_graph()

            # Initialize state
            initial_state = RootFileFolderProcessingState(
                root_paths=self.root_paths,
                information_nodes=[],
                error=None,
                save_status={}
            )

            # Execute workflow
            runnable_config = {"run_name": f"parallel_root_processing_{len(self.root_paths)}_paths"}
            response = self._compiled_graph.invoke(input=initial_state, config=runnable_config)

            # Check for errors
            if response.get("error"):
                return ProcessingResult(node_path="parallel_processing", error=response["error"])

            # Get aggregated information nodes
            all_information_nodes = response.get("information_nodes", [])
            
            logger.info(f"Parallel root processing completed: {len(all_information_nodes)} total information nodes from {len(self.root_paths)} root paths")

            # Create combined result
            result = ProcessingResult(
                node_path="parallel_root_processing",
                node_relationships=[],  # Not tracked at this level
                hierarchical_analysis={},  # Not tracked at this level  
                error=None,
                node_source_mapping={},  # Not aggregated at this level
                information_nodes=all_information_nodes,
            )

            # Add save status from response
            result.save_status = response.get("save_status", {"success": True})

            return result

        except Exception as e:
            logger.exception(f"Error running parallel root processing workflow: {e}")
            return ProcessingResult(node_path="parallel_processing", error=str(e))
