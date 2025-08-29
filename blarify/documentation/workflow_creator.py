"""
Workflow Creator for discovering and analyzing workflows without documentation dependencies.

This module provides workflow-first discovery that works directly with code structure,
eliminating the need for expensive documentation creation before workflow analysis.
"""

import time
import logging
from typing import List, Dict, Any, Optional

from ..repositories.graph_db_manager.db_manager import AbstractDbManager
from ..repositories.graph_db_manager.queries import (
    find_all_entry_points,
    find_code_workflows,
    find_entry_points_for_node_path,
)
from ..graph.graph_environment import GraphEnvironment
from ..graph.node.workflow_node import WorkflowNode
from ..graph.relationship.relationship_creator import RelationshipCreator
from .result_models import WorkflowResult, WorkflowDiscoveryResult

logger = logging.getLogger(__name__)


class WorkflowCreator:
    """
    Creates and analyzes workflows using direct code structure analysis.

    This class provides workflow-first discovery without requiring DocumentationNodes
    to exist first, making it much faster for SWE benchmarks and targeted analysis.
    """

    def __init__(
        self,
        db_manager: AbstractDbManager,
        graph_environment: GraphEnvironment,
    ) -> None:
        """
        Initialize the workflow creator.

        Args:
            db_manager: Database manager for querying nodes and saving results
            graph_environment: Graph environment for node ID generation
            company_id: Company/entity ID for database queries
            repo_id: Repository ID for database queries
        """
        self.db_manager = db_manager
        self.graph_environment = graph_environment

    def discover_workflows(
        self,
        entry_points: Optional[List[str]] = None,
        max_depth: int = 20,
        save_to_database: bool = True,
        node_path: Optional[str] = None,
    ) -> WorkflowDiscoveryResult:
        """
        Discover workflows without requiring DocumentationNodes first.

        This is the main entry point that provides fast workflow discovery
        optimized for SWE benchmarks and targeted analysis.

        Args:
            entry_points: Optional list of entry point IDs to analyze
            max_depth: Maximum depth for workflow traversal
            save_to_database: Whether to save discovered workflows to database
            node_path: Optional path to a specific node (directory/file/class/function).
                      When provided, discovers workflows that eventually reach this node.
                      When None, discovers all workflows in the repository.

        Returns:
            WorkflowDiscoveryResult with all discovered workflows
        """
        start_time = time.time()

        try:
            logger.info("Starting workflow discovery")

            # Step 1: Discover entry points if not provided
            if not entry_points:
                entry_points_data = self._discover_entry_points(node_path)
                entry_point_ids = [ep.get("id", "") for ep in entry_points_data if ep.get("id")]
            else:
                entry_point_ids = entry_points
                entry_points_data = [{"id": ep_id} for ep_id in entry_points]

            if not entry_point_ids:
                return WorkflowDiscoveryResult(error="No entry points found for workflow discovery")

            logger.info(f"Analyzing {len(entry_point_ids)} entry points for workflows")

            # Step 2: Discover workflows from each entry point
            all_workflows = []
            warnings = []

            for entry_point_id in entry_point_ids:
                try:
                    workflows = self._analyze_workflow_from_entry_point(entry_point_id, max_depth)
                    all_workflows.extend(workflows)

                except Exception as e:
                    error_msg = f"Error analyzing workflows from entry point {entry_point_id}: {str(e)}"
                    logger.exception(error_msg)
                    warnings.append(error_msg)

            # Step 3: Save workflows to database if requested
            if save_to_database and all_workflows:
                self._save_workflows_to_database(all_workflows)

            # Prepare result
            discovery_time = time.time() - start_time

            logger.info(
                f"Workflow discovery completed: {len(all_workflows)} workflows "
                f"from {len(entry_point_ids)} entry points in {discovery_time:.2f} seconds"
            )

            return WorkflowDiscoveryResult(
                discovered_workflows=all_workflows,
                entry_points=entry_points_data,
                total_entry_points=len(entry_point_ids),
                total_workflows=len(all_workflows),
                discovery_time_seconds=discovery_time,
                warnings=warnings,
            )

        except Exception as e:
            logger.exception(f"Error in workflow discovery: {e}")
            return WorkflowDiscoveryResult(
                error=str(e),
                discovery_time_seconds=time.time() - start_time,
            )

    def _discover_entry_points(self, node_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Discover entry points using hybrid approach from existing implementation.

        This uses the existing find_all_entry_points_hybrid function which combines
        database relationship analysis with potential for agent exploration.
        When node_path is provided, uses targeted discovery for that specific path.

        Args:
            node_path: Optional path to a specific node. When provided, finds entry points
                      that eventually reach this node. When None, finds all entry points.

        Returns:
            List of entry point dictionaries with id, name, path, etc.
        """
        try:
            if node_path is not None:
                logger.info(f"Discovering entry points for node path: {node_path}")
                entry_points = find_entry_points_for_node_path(db_manager=self.db_manager, node_path=node_path)

                # Convert to standard format (only id is returned from targeted search)
                standardized_entry_points = []
                for ep in entry_points:
                    standardized_entry_points.append(
                        {
                            "id": ep.get("id", ""),
                            "name": f"Entry for {node_path}",
                            "path": "",
                            "labels": [],
                            "description": f"Entry point that reaches: {node_path}",
                            "discovery_method": "targeted_node_path_analysis",
                        }
                    )

                logger.info(f"Discovered {len(standardized_entry_points)} targeted entry points")
                return standardized_entry_points
            else:
                logger.info("Discovering entry points using hybrid approach")

                entry_points = find_all_entry_points(db_manager=self.db_manager)

                # Convert to standard format
                standardized_entry_points = []
                for ep in entry_points:
                    standardized_entry_points.append(
                        {
                            "id": ep.get("id", ""),
                            "name": ep.get("name", ""),
                            "path": ep.get("path", ""),
                            "labels": ep.get("labels", []),
                            "description": f"Entry point: {ep.get('name', 'Unknown')}",
                            "discovery_method": "hybrid_database_analysis",
                        }
                    )

                logger.info(f"Discovered {len(standardized_entry_points)} entry points")
                return standardized_entry_points

        except Exception as e:
            logger.exception(f"Error discovering entry points: {e}")
            return []

    def _analyze_workflow_from_entry_point(self, entry_point_id: str, max_depth: int = 20) -> List[WorkflowResult]:
        """
        Analyze workflows from a specific entry point using new code-based query.

        Args:
            entry_point_id: ID of the entry point to analyze
            max_depth: Maximum depth for workflow traversal

        Returns:
            List of WorkflowResult objects for this entry point
        """
        try:
            logger.debug(f"Analyzing workflows from entry point: {entry_point_id}")

            # Use the new find_code_workflows_query that works without documentation dependencies
            workflows_data = self._execute_code_workflows_query(entry_point_id, max_depth)

            workflows = []
            for workflow_data in workflows_data:
                try:
                    # Convert to WorkflowResult
                    workflow_result = self._convert_to_workflow_result(workflow_data)
                    workflows.append(workflow_result)

                except Exception as e:
                    logger.exception(f"Error converting workflow data for entry {entry_point_id}: {e}")
                    continue

            logger.debug(f"Found {len(workflows)} workflows for entry point {entry_point_id}")
            return workflows

        except Exception as e:
            logger.exception(f"Error analyzing workflows from entry point {entry_point_id}: {e}")
            return []

    def _execute_code_workflows_query(self, entry_point_id: str, max_depth: int = 20) -> List[Dict[str, Any]]:
        """
        Execute the new code-based workflow query that doesn't require documentation.

        Uses the find_code_workflows function to get workflows directly from code structure.

        Args:
            entry_point_id: ID of the entry point
            max_depth: Maximum traversal depth

        Returns:
            List of workflow data dictionaries
        """
        try:
            # Use the new find_code_workflows function
            workflows = find_code_workflows(
                db_manager=self.db_manager,
                entry_point_id=entry_point_id,
                max_depth=max_depth,
            )

            return workflows

        except Exception as e:
            logger.exception(f"Error executing code workflows query for {entry_point_id}: {e}")
            return []

    def _convert_to_workflow_result(self, workflow_data: Dict[str, Any]) -> WorkflowResult:
        """
        Convert raw workflow data to WorkflowResult model.

        Args:
            workflow_data: Raw workflow data from database query

        Returns:
            WorkflowResult model instance
        """
        workflow_nodes = workflow_data.get("workflowNodes", [])
        workflow_edges = workflow_data.get("workflowEdges", [])

        # Determine end point (last node in the workflow)
        end_point_id = None
        end_point_name = None
        end_point_path = None

        if workflow_nodes:
            end_node = workflow_nodes[-1]
            end_point_id = end_node.get("id")
            end_point_name = end_node.get("name")
            end_point_path = end_node.get("path")

        # Check for cycles (basic detection)
        node_ids = [node.get("id") for node in workflow_nodes]
        has_cycles = len(node_ids) != len(set(node_ids))

        return WorkflowResult(
            entry_point_id=workflow_data.get("entryPointId", ""),
            entry_point_name=workflow_data.get("entryPointName", ""),
            entry_point_path=workflow_data.get("entryPointPath", ""),
            end_point_id=end_point_id,
            end_point_name=end_point_name,
            end_point_path=end_point_path,
            workflow_nodes=workflow_nodes,
            workflow_edges=workflow_edges,
            workflow_type=workflow_data.get("workflowType", "code_based_workflow"),
            total_execution_steps=len(workflow_nodes),
            path_length=workflow_data.get("pathLength", 0),
            discovered_by=workflow_data.get("discoveredBy", "code_workflow_discovery"),
            has_cycles=has_cycles,
        )

    def _save_workflows_to_database(self, workflows: List[WorkflowResult]) -> None:
        """
        Save discovered workflows to the database as WorkflowNode objects.

        Args:
            workflows: List of WorkflowResult objects to save
        """
        try:
            if not workflows:
                return

            logger.info(f"Saving {len(workflows)} workflows to database")

            # Create WorkflowNode objects
            workflow_nodes = []
            all_relationships = []

            for workflow_result in workflows:
                try:
                    # Create WorkflowNode
                    workflow_node = self._create_workflow_node(workflow_result)
                    workflow_nodes.append(workflow_node)

                    # Create relationships for this workflow
                    relationships = self._create_workflow_relationships(workflow_node, workflow_result)
                    all_relationships.extend(relationships)

                except Exception as e:
                    logger.exception(f"Error creating workflow node for {workflow_result.entry_point_name}: {e}")
                    continue

            # Batch save nodes
            if workflow_nodes:
                node_objects = [node.as_object() for node in workflow_nodes]
                self.db_manager.create_nodes(node_objects)
                logger.info(f"Saved {len(workflow_nodes)} workflow nodes")

            # Batch save relationships
            if all_relationships:
                self.db_manager.create_edges(all_relationships)
                logger.info(f"Saved {len(all_relationships)} workflow relationships")

        except Exception as e:
            logger.exception(f"Error saving workflows to database: {e}")

    def _create_workflow_node(self, workflow_result: WorkflowResult) -> WorkflowNode:
        """
        Create a WorkflowNode from a WorkflowResult.

        Args:
            workflow_result: The workflow result to convert

        Returns:
            WorkflowNode instance
        """
        import json

        # Create workflow title
        workflow_title = f"Code Workflow: {workflow_result.entry_point_name}"
        if workflow_result.total_execution_steps > 1:
            workflow_title += f" ({workflow_result.total_execution_steps} steps)"

        # Create synthetic path
        synthetic_path = f"file:///workflows/code/{workflow_result.entry_point_name.replace(' ', '_').lower()}"

        # Prepare content data
        content_data = {
            "workflow_type": workflow_result.workflow_type,
            "entry_point_id": workflow_result.entry_point_id,
            "entry_point_name": workflow_result.entry_point_name,
            "entry_point_path": workflow_result.entry_point_path,
            "end_point_id": workflow_result.end_point_id,
            "end_point_name": workflow_result.end_point_name,
            "end_point_path": workflow_result.end_point_path,
            "total_execution_steps": workflow_result.total_execution_steps,
            "path_length": workflow_result.path_length,
            "has_cycles": workflow_result.has_cycles,
            "discovered_by": workflow_result.discovered_by,
            "workflow_nodes": workflow_result.workflow_nodes,
            "workflow_edges": workflow_result.workflow_edges,
        }

        # Create unique source name
        source_name = f"code_workflow_{workflow_result.entry_point_id}"
        if workflow_result.end_point_id:
            source_name += f"_{workflow_result.end_point_id}"

        return WorkflowNode(
            title=workflow_title,
            content=json.dumps(content_data, indent=2),
            entry_point_id=workflow_result.entry_point_id,
            entry_point_name=workflow_result.entry_point_name,
            entry_point_path=workflow_result.entry_point_path,
            end_point_id=workflow_result.end_point_id or "",
            end_point_name=workflow_result.end_point_name or "",
            end_point_path=workflow_result.end_point_path or "",
            workflow_nodes=workflow_result.workflow_nodes,
            source_type="code_workflow_discovery",
            source_path=synthetic_path,
            source_name=source_name,
            source_labels=["WORKFLOW"],
            graph_environment=self.graph_environment,
            level=0,
            parent=None,
        )

    def _create_workflow_relationships(
        self, workflow_node: WorkflowNode, workflow_result: WorkflowResult
    ) -> List[Dict[str, Any]]:
        """
        Create relationships for a workflow.

        This creates both WORKFLOW_STEP relationships and BELONGS_TO_WORKFLOW
        relationships connecting all participant nodes to the workflow node.

        Args:
            workflow_node: The WorkflowNode instance
            workflow_result: The workflow result data

        Returns:
            List of relationship objects
        """
        relationships = []

        try:
            # Create WORKFLOW_STEP relationships from workflow edges
            if workflow_result.workflow_edges:
                workflow_step_relationships = (
                    RelationshipCreator.create_workflow_step_relationships_from_execution_edges(
                        workflow_node=workflow_node,
                        execution_edges=[
                            {
                                "caller_id": edge.get("caller_id"),
                                "callee_id": edge.get("callee_id"),
                                "relationship_type": edge.get("relationship_type"),
                                "depth": edge.get("depth"),
                                "call_line": edge.get("call_line"),
                                "call_character": edge.get("call_character"),
                            }
                            for edge in workflow_result.workflow_edges
                        ],
                    )
                )
                relationships.extend(workflow_step_relationships)

            # Create BELONGS_TO_WORKFLOW relationships for all participant nodes
            if workflow_result.workflow_nodes:
                # Extract unique node IDs from workflow participants
                node_ids = []
                for node in workflow_result.workflow_nodes:
                    node_id = node.get("id")
                    if node_id and node_id not in node_ids:
                        node_ids.append(node_id)

                # Create BELONGS_TO_WORKFLOW relationships
                if node_ids:
                    belongs_to_relationships = (
                        RelationshipCreator.create_belongs_to_workflow_relationships_for_workflow_nodes(
                            workflow_node=workflow_node, workflow_node_ids=node_ids
                        )
                    )
                    relationships.extend(belongs_to_relationships)
                    logger.debug(
                        f"Created {len(belongs_to_relationships)} BELONGS_TO_WORKFLOW relationships "
                        f"for workflow {workflow_node.entry_point_name}"
                    )

        except Exception as e:
            logger.exception(f"Error creating workflow relationships: {e}")

        return relationships
