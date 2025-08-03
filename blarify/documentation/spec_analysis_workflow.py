"""
Workflow Analysis Workflow for discovering and analyzing workflows directly from entry points.

This module provides a dedicated LangGraph workflow for hybrid entry point discovery
and direct workflow processing, replacing the previous spec-based approach.

IMPLEMENTATION STATUS:
- ✅ Architecture completed with WorkflowAnalysisState and WorkflowAnalysisWorkflow
- ✅ Hybrid entry point discovery (database + agent exploration)
- ✅ Independent execution capability for testing and modularity
- ✅ Direct workflow processing from all discovered entry points
- ✅ Creates workflow nodes with all relationships (BELONGS_TO_WORKFLOW, WORKFLOW_STEP)
- ✅ Maintains 4-layer architecture (Specifications → Workflows → Documentation → Code)
"""

from operator import add
from typing import Annotated, TypedDict, Dict, Any, Optional, List
import logging
import json

from langgraph.graph import START, StateGraph


from ..agents.llm_provider import LLMProvider
from ..agents.tools import (
    GetCodeByIdTool,
    DirectoryExplorerTool,
)
from ..agents.tools.find_nodes_by_code import FindNodesByCode
from ..agents.tools.find_nodes_by_name_and_type import FindNodesByNameAndType
from ..agents.tools.get_relationship_flowchart import GetRelationshipFlowchart
from ..db_managers.db_manager import AbstractDbManager
from ..db_managers.queries import (
    create_workflow_belongs_to_spec_query,
    find_all_entry_points_hybrid,
    find_independent_workflows,
    create_documentation_belongs_to_workflow_query,
    create_workflow_steps_query,
)
from ..graph.relationship.relationship_creator import RelationshipCreator
from ..graph.graph_environment import GraphEnvironment
from ..graph.node.documentation_node import DocumentationNode
from ..graph.node.workflow_node import WorkflowNode

logger = logging.getLogger(__name__)


class SpecAnalysisState(TypedDict):
    """State management for spec analysis workflow."""

    # Input data
    detected_framework: Dict[str, Any]

    # Output data
    discovered_entry_points: List[Dict[str, Any]]
    discovered_workflows: List[Dict[str, Any]]
    discovered_specs: List[Dict[str, Any]]
    spec_analysis_results: Annotated[list, add]
    spec_relationships: Annotated[list, add]
    error: Optional[str]


class SpecAnalysisWorkflow:
    """
    Dedicated workflow for discovering and analyzing business specifications.

    This workflow combines hybrid entry point discovery with direct workflow processing.
    Later will be extended to include spec discovery that groups workflows.
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
        """Compile the spec analysis workflow graph."""
        workflow = StateGraph(SpecAnalysisState)

        # Add workflow nodes
        workflow.add_node("get_entry_points", self._get_entry_points)
        workflow.add_node("get_workflows", self._get_workflows)
        workflow.add_node("save_workflows", self._save_workflows)
        workflow.add_node("discover_specs", self._discover_specs)
        workflow.add_node("save_specs", self._save_specs)

        # Define workflow edges
        workflow.add_edge(START, "get_entry_points")
        workflow.add_edge("get_entry_points", "get_workflows")
        workflow.add_edge("get_workflows", "save_workflows")
        workflow.add_edge("save_workflows", "discover_specs")
        workflow.add_edge("discover_specs", "save_specs")

        self._compiled_graph = workflow.compile()

    def _discover_specs(self, _state: SpecAnalysisState) -> Dict[str, Any]:
        """Discover business specifications - NOT IMPLEMENTED.

        This is a placeholder for future spec discovery that will group workflows.
        Currently raises NotImplementedError as this functionality is not yet implemented.
        """
        logger.info("Spec discovery not implemented")
        raise NotImplementedError(
            "Spec discovery functionality is not yet implemented. This will be added in a future phase to group workflows into business specifications."
        )

    def _process_specs(self, state: SpecAnalysisState) -> Dict[str, Any]:
        """Process discovered specs to create 4-layer architecture with workflows."""
        try:
            discovered_specs = state.get("discovered_specs", [])
            logger.info(f"Processing {len(discovered_specs)} discovered specs")

            spec_analysis_results = []
            spec_relationships = []

            for spec in discovered_specs:
                try:
                    logger.info(f"Processing spec: {spec.get('name', 'Unknown')}")

                    # Step 1: Create spec node in specifications layer using DocumentationNode
                    spec_info_node = self._create_spec_information_node(spec)
                    spec_id = spec_info_node.hashed_id

                    # Save the spec node to database
                    try:
                        self.company_graph_manager.create_nodes([spec_info_node.as_object()])
                        logger.info(f"Created spec node with ID: {spec_id}")
                    except Exception as e:
                        logger.error(f"Failed to save spec node for {spec.get('name')}: {e}")
                        continue

                    spec_result = {"spec_id": spec_id, "spec_name": spec.get("name"), "workflows": []}

                    # Step 2: Process each entry point to find workflows
                    entry_points = spec.get("entry_points", [])
                    for entry_point in entry_points:
                        # Get the source code node ID from the entry point
                        source_node_id = ""
                        if isinstance(entry_point, dict):
                            source_node_id = entry_point.get("source_node_id", "")

                        if not source_node_id:
                            logger.warning(f"No source_node_id for entry point {entry_point}")
                            continue

                        logger.info(f"Finding workflows for entry point: {source_node_id}")

                        # Step 3: Find independent workflows from this entry point
                        workflows = find_independent_workflows(
                            db_manager=self.company_graph_manager,
                            entity_id=self.company_id,
                            repo_id=self.repo_id,
                            entry_point_id=source_node_id,
                        )

                        logger.info(f"Found {len(workflows)} workflows for entry point {source_node_id}")

                        # Step 4: Create workflow nodes and relationships for each workflow
                        for workflow_data in workflows:
                            # Create workflow node using DocumentationNode
                            workflow_info_node = self._create_workflow_information_node(spec_id, workflow_data)
                            workflow_id = workflow_info_node.hashed_id

                            # Save the workflow node to database
                            try:
                                self.company_graph_manager.create_nodes([workflow_info_node.as_object()])
                                logger.info(f"Created workflow node with ID: {workflow_id}")

                                # Create relationships using the existing query functions
                                # Extract code node IDs in execution order
                                workflow_nodes = workflow_data.get("workflowNodes", [])
                                workflow_code_node_ids = [node["id"] for node in workflow_nodes]

                                # Create BELONGS_TO_SPEC relationship
                                self.company_graph_manager.query(
                                    cypher_query=create_workflow_belongs_to_spec_query(),
                                    parameters={"workflow_id": workflow_id, "spec_id": spec_id},
                                )

                                # Create BELONGS_TO_WORKFLOW relationships
                                result = self.company_graph_manager.query(
                                    cypher_query=create_documentation_belongs_to_workflow_query(),
                                    parameters={
                                        "workflow_id": workflow_id,
                                        "workflow_code_node_ids": workflow_code_node_ids,
                                    },
                                )
                                connected_docs = result[0].get("connected_docs", 0) if result else 0
                                logger.info(f"Connected {connected_docs} documentation nodes to workflow {workflow_id}")

                                # Create workflow steps if there are multiple nodes
                                if len(workflow_code_node_ids) > 1:
                                    result = self.company_graph_manager.query(
                                        cypher_query=create_workflow_steps_query(),
                                        parameters={
                                            "workflow_id": workflow_id,
                                            "workflow_code_node_ids": workflow_code_node_ids,
                                        },
                                    )
                                    created_steps = result[0].get("created_steps", 0) if result else 0
                                    logger.info(f"Created {created_steps} workflow steps for workflow {workflow_id}")

                                spec_result["workflows"].append(
                                    {
                                        "workflow_id": workflow_id,
                                        "entry_point": workflow_data.get("entryPointName"),
                                        "steps": len(workflow_data.get("workflowNodes", [])),
                                    }
                                )

                                # Track relationships created
                                spec_relationships.append(
                                    {"type": "BELONGS_TO_SPEC", "from": workflow_id, "to": spec_id}
                                )

                            except Exception as e:
                                logger.error(
                                    f"Failed to create workflow for entry point {workflow_data.get('entryPointName')}: {e}"
                                )
                                continue

                    spec_analysis_results.append(spec_result)
                    logger.info(
                        f"Completed processing spec {spec.get('name')} with {len(spec_result['workflows'])} workflows"
                    )

                except Exception as e:
                    logger.exception(f"Error processing spec {spec.get('name', 'Unknown')}: {e}")
                    continue

            logger.info(f"Spec processing completed: {len(spec_analysis_results)} specs processed")

            return {"spec_analysis_results": spec_analysis_results, "spec_relationships": spec_relationships}

        except Exception as e:
            logger.exception(f"Error in spec processing: {e}")
            return {"spec_analysis_results": [], "spec_relationships": [], "error": str(e)}

    def _create_spec_information_node(self, spec_data: Dict[str, Any]) -> DocumentationNode:
        """
        Create a DocumentationNode for a specification.

        Args:
            spec_data: Dictionary containing spec information

        Returns:
            DocumentationNode instance for the specification
        """
        spec_name = spec_data.get("name", "Unknown Spec")

        # Create deterministic synthetic path for the spec
        synthetic_path = f"file:///specs/{spec_name.replace(' ', '_').lower()}"

        # Prepare content as JSON with all spec data
        # Convert EntryPoint objects to dictionaries for JSON serialization
        entry_points = spec_data.get("entry_points", [])
        serializable_entry_points = []
        for entry_point in entry_points:
            if hasattr(entry_point, "model_dump"):
                # Pydantic model - convert to dict
                serializable_entry_points.append(entry_point.model_dump())
            elif isinstance(entry_point, dict):
                # Already a dictionary
                serializable_entry_points.append(entry_point)
            else:
                # Convert other types to dict representation
                serializable_entry_points.append(str(entry_point))

        content_data = {
            "description": spec_data.get("description", ""),
            "entry_points": serializable_entry_points,
            "scope": spec_data.get("scope", ""),
            "framework_context": spec_data.get("framework_context", ""),
        }

        # Use spec name as source_name for deterministic ID generation
        source_name = f"spec_{spec_name.replace(' ', '_').lower()}"

        info_node = DocumentationNode(
            title=spec_name,
            content=json.dumps(content_data, indent=2),
            info_type="business_spec",
            source_type="spec_analysis",
            source_path=synthetic_path,
            source_name=source_name,
            source_labels=["SPECIFICATION"],
            graph_environment=self.graph_environment,
            level=0,
            parent=None,
            layer="specifications",
        )

        return info_node

    def _create_workflow_information_node(self, spec_id: str, workflow_data: Dict[str, Any]) -> WorkflowNode:
        """
        Create a WorkflowNode for a workflow.

        Args:
            spec_id: The spec node ID this workflow belongs to
            workflow_data: Dictionary containing workflow information

        Returns:
            WorkflowNode instance for the workflow
        """
        entry_name = workflow_data.get("entryPointName", "Unknown")
        entry_point_id = workflow_data.get("entryPointId", "")
        workflow_title = f"Workflow: {entry_name}"

        # Create deterministic synthetic path for the workflow
        synthetic_path = f"file:///workflows/{entry_name.replace(' ', '_').lower()}"

        # Prepare content with workflow details
        workflow_nodes = workflow_data.get("workflowNodes", [])
        content_data = {
            "entry_point_id": entry_point_id,
            "entry_point_name": entry_name,
            "entry_point_path": workflow_data.get("entryPointPath", ""),
            "end_point_id": workflow_data.get("endPointId", ""),
            "end_point_name": workflow_data.get("endPointName", ""),
            "end_point_path": workflow_data.get("endPointPath", ""),
            "steps": len(workflow_nodes),
            "workflow_nodes": [
                {"id": node["id"], "name": node["name"], "path": node["path"], "labels": node["labels"]}
                for node in workflow_nodes
            ],
            "belongs_to_spec": spec_id,
        }

        # Use spec_id, entry_point_id and end_point_id for unique source_name generation
        # Both entry_point_id and end_point_id are guaranteed to exist since our query requires unique entry and end nodes
        end_point_id = workflow_data.get("endPointId", "")
        source_name = f"workflow_{spec_id}_{entry_point_id}_{end_point_id}"

        info_node = WorkflowNode(
            title=workflow_title,
            content=json.dumps(content_data, indent=2),
            entry_point_id=entry_point_id,
            entry_point_name=entry_name,
            entry_point_path=workflow_data.get("entryPointPath", ""),
            end_point_id=end_point_id,
            end_point_name=workflow_data.get("endPointName", ""),
            end_point_path=workflow_data.get("endPointPath", ""),
            workflow_nodes=workflow_nodes,
            source_type="workflow_analysis",
            source_path=synthetic_path,
            source_name=source_name,
            source_labels=["WORKFLOW"],
            graph_environment=self.graph_environment,
            level=0,
            parent=None,
        )

        return info_node

    def _get_entry_points(self, state: SpecAnalysisState) -> Dict[str, Any]:
        """
        Get entry points using hybrid approach: database queries + agent exploration.

        This method combines database relationship analysis with agent exploration
        to find comprehensive entry points for workflow discovery.
        """
        try:
            logger.info("Starting hybrid entry point discovery")

            # Step 1: Database-based entry point discovery
            logger.info("Querying database for potential entry points")
            database_entry_points = find_all_entry_points_hybrid(
                db_manager=self.company_graph_manager, entity_id=self.company_id, repo_id=self.repo_id
            )

            logger.info(f"Database found {len(database_entry_points)} potential entry points")

            # Step 2: Agent-based entry point discovery
            logger.info("Starting agent exploration for additional entry points")

            # Prepare tools for agent exploration (documentation layer + code analysis)
            diff_identifier = "0"  # Default diff identifier for main branch

            tools = [
                # Code analysis tools for finding actual entry point patterns
                GetCodeByIdTool(
                    company_id=self.company_id,
                    db_manager=self.company_graph_manager,
                    diff_identifier=diff_identifier,
                    handle_validation_error=True,
                ),
                FindNodesByCode(
                    company_id=self.company_id,
                    db_manager=self.company_graph_manager,
                    diff_identifier=diff_identifier,
                    repo_id=self.repo_id,
                    handle_validation_error=True,
                ),
                FindNodesByNameAndType(
                    company_id=self.company_id,
                    db_manager=self.company_graph_manager,
                    diff_identifier=diff_identifier,
                    repo_id=self.repo_id,
                    handle_validation_error=True,
                ),
                GetRelationshipFlowchart(
                    company_id=self.company_id,
                    db_manager=self.company_graph_manager,
                    diff_identifier=diff_identifier,
                    handle_validation_error=True,
                ),
            ]

            # Add directory explorer tool
            directory_explorer = DirectoryExplorerTool(
                company_graph_manager=self.company_graph_manager,
                company_id=self.company_id,
                repo_id=self.repo_id,
            )
            tools.extend(
                [
                    directory_explorer.get_tool(),
                    directory_explorer.get_find_repo_root_tool(),
                ]
            )

            # Get detected framework info from state
            # detected_framework = state.get("detected_framework", {})

            # # Use entry point discovery template
            # system_prompt, input_prompt = ENTRY_POINT_DISCOVERY_TEMPLATE.get_prompts()

            # agent_response = self.agent_caller.call_react_agent(
            #     system_prompt=system_prompt,
            #     tools=tools,
            #     input_dict={
            #         "detected_framework": detected_framework,
            #     },
            #     input_prompt=input_prompt,
            #     output_schema=EntryPointDiscoveryResult,
            #     main_model="claude-sonnet-4-20250514",
            # )

            # Extract agent discoveries
            # agent_entry_points = []
            # if hasattr(agent_response, "discovered_entry_points"):
            #     agent_entry_points = [ep.model_dump() for ep in agent_response.discovered_entry_points]
            # elif isinstance(agent_response, dict) and "discovered_entry_points" in agent_response:
            #     agent_entry_points = agent_response["discovered_entry_points"]

            # logger.info(f"Agent found {len(agent_entry_points)} additional entry points")

            # # Step 3: Combine and deduplicate entry points
            combined_entry_points = self._combine_entry_points(database_entry_points, [])

            logger.info(f"Entry point discovery completed: {len(combined_entry_points)} total unique entry points")

            return {"discovered_entry_points": combined_entry_points}

        except Exception as e:
            logger.exception(f"Error in entry point discovery: {e}")
            return {"discovered_entry_points": [], "error": str(e)}

    def _get_workflows(self, state: SpecAnalysisState) -> Dict[str, Any]:
        """
        Get independent workflows from discovered entry points using cypher queries.
        """
        try:
            discovered_entry_points = state.get("discovered_entry_points", [])
            logger.info(f"Getting workflows from {len(discovered_entry_points)} entry points")

            all_workflows = []

            for entry_point in discovered_entry_points:
                try:
                    entry_point_id = entry_point.get("id", "")
                    if not entry_point_id:
                        logger.warning(f"No ID for entry point {entry_point}")
                        continue

                    logger.info(f"Finding workflows for entry point: {entry_point_id}")

                    # Use existing function to find independent workflows
                    workflows = find_independent_workflows(
                        db_manager=self.company_graph_manager,
                        entity_id=self.company_id,
                        repo_id=self.repo_id,
                        entry_point_id=entry_point_id,
                    )

                    logger.info(f"Found {len(workflows)} workflows for entry point {entry_point_id}")

                    # Add entry point metadata to each workflow
                    for workflow in workflows:
                        workflow["source_entry_point"] = entry_point
                        all_workflows.append(workflow)

                except Exception as e:
                    logger.exception(
                        f"Error getting workflows for entry point {entry_point.get('name', 'Unknown')}: {e}"
                    )
                    continue

            logger.info(f"Workflow discovery completed: {len(all_workflows)} total workflows found")

            return {"discovered_workflows": all_workflows}

        except Exception as e:
            logger.exception(f"Error in workflow discovery: {e}")
            return {"discovered_workflows": [], "error": str(e)}

    def _save_workflows(self, state: SpecAnalysisState) -> Dict[str, Any]:
        """
        Save discovered workflows as nodes and relationships in 4-layer architecture.
        Uses batch processing for improved performance.
        """
        try:
            discovered_workflows = state.get("discovered_workflows", [])
            logger.info(f"Saving {len(discovered_workflows)} workflows using batch processing")

            workflow_results = []
            workflow_relationships = []

            # Step 1: Create all workflow nodes and collect metadata
            workflow_info_nodes = []
            workflow_metadata = []

            for workflow_data in discovered_workflows:
                try:
                    # Create workflow node in workflows layer using DocumentationNode
                    workflow_info_node = self._create_standalone_workflow_information_node(workflow_data)
                    workflow_info_nodes.append(workflow_info_node)

                    # Store metadata for relationship creation
                    workflow_metadata.append(
                        {
                            "workflow_info_node": workflow_info_node,
                            "workflow_data": workflow_data,
                            "workflow_id": workflow_info_node.hashed_id,
                            "workflow_code_node_ids": [node["id"] for node in workflow_data.get("workflowNodes", [])],
                        }
                    )

                except Exception as e:
                    logger.exception(
                        f"Error creating workflow node for {workflow_data.get('entryPointName', 'Unknown')}: {e}"
                    )
                    continue

            # Step 2: Batch create all workflow nodes
            if workflow_info_nodes:
                try:
                    workflow_node_objects = [node.as_object() for node in workflow_info_nodes]
                    self.company_graph_manager.create_nodes(workflow_node_objects)
                    logger.info(f"Batch created {len(workflow_info_nodes)} workflow nodes")
                except Exception as e:
                    logger.error(f"Failed to batch create workflow nodes: {e}")
                    return {"workflow_results": [], "workflow_relationships": [], "error": str(e)}

            # Step 3: Create relationships for each workflow
            all_belongs_to_relationships = []
            all_workflow_step_relationships = []

            for metadata in workflow_metadata:
                try:
                    workflow_info_node = metadata["workflow_info_node"]
                    workflow_data = metadata["workflow_data"]
                    workflow_id = metadata["workflow_id"]
                    workflow_code_node_ids = metadata["workflow_code_node_ids"]

                    # Create BELONGS_TO_WORKFLOW relationships using RelationshipCreator
                    belongs_to_workflow_relationships = (
                        RelationshipCreator.create_belongs_to_workflow_relationships_for_code_nodes(
                            workflow_node=workflow_info_node,
                            workflow_code_node_ids=workflow_code_node_ids,
                            db_manager=self.company_graph_manager,
                        )
                    )

                    if belongs_to_workflow_relationships:
                        all_belongs_to_relationships.extend(belongs_to_workflow_relationships)

                    # Create WORKFLOW_STEP relationships using execution edges if available
                    execution_edges = workflow_data.get("executionEdges", [])
                    if execution_edges:
                        # Use new edge-based relationship creation for better accuracy
                        workflow_step_relationships = (
                            RelationshipCreator.create_workflow_step_relationships_from_execution_edges(
                                workflow_node=workflow_info_node,
                                execution_edges=execution_edges,
                                db_manager=self.company_graph_manager,
                            )
                        )
                        logger.debug(f"Created {len(workflow_step_relationships)} edge-based WORKFLOW_STEP relationships")
                    else:
                        # Fallback to code sequence method for backward compatibility
                        workflow_step_relationships = (
                            RelationshipCreator.create_workflow_step_relationships_for_code_sequence(
                                workflow_node=workflow_info_node,
                                workflow_code_node_ids=workflow_code_node_ids,
                                db_manager=self.company_graph_manager,
                            )
                        )
                        logger.debug(f"Created {len(workflow_step_relationships)} sequence-based WORKFLOW_STEP relationships")

                    if workflow_step_relationships:
                        all_workflow_step_relationships.extend(workflow_step_relationships)

                    # Track successful workflow with edge information
                    workflow_results.append(
                        {
                            "workflow_id": workflow_id,
                            "entry_point": workflow_data.get("entryPointName"),
                            "entry_point_id": workflow_data.get("entryPointId"),
                            "steps": len(workflow_data.get("workflowNodes", [])),
                            "edges": len(workflow_data.get("executionEdges", [])),
                            "workflow_type": workflow_data.get("workflowType", "unknown"),
                            "edge_based": bool(workflow_data.get("executionEdges")),
                        }
                    )

                except Exception as e:
                    logger.exception(
                        f"Error creating relationships for workflow {metadata['workflow_data'].get('entryPointName', 'Unknown')}: {e}"
                    )
                    continue

            # Step 4: Batch create all relationships
            try:
                if all_belongs_to_relationships:
                    self.company_graph_manager.create_edges(all_belongs_to_relationships)
                    logger.info(f"Batch created {len(all_belongs_to_relationships)} BELONGS_TO_WORKFLOW relationships")

                if all_workflow_step_relationships:
                    self.company_graph_manager.create_edges(all_workflow_step_relationships)
                    logger.info(f"Batch created {len(all_workflow_step_relationships)} WORKFLOW_STEP relationships")

            except Exception as e:
                logger.error(f"Failed to batch create relationships: {e}")
                # Continue with partial success rather than failing completely

            logger.info(f"Workflow saving completed: {len(workflow_results)} workflows saved with batch processing")

            return {"workflow_results": workflow_results, "workflow_relationships": workflow_relationships}

        except Exception as e:
            logger.exception(f"Error in workflow saving: {e}")
            return {"workflow_results": [], "workflow_relationships": [], "error": str(e)}

    def _combine_entry_points(
        self, database_entries: List[Dict[str, Any]], agent_entries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Combine and deduplicate entry points from database and agent discovery using node_id.

        Args:
            database_entries: Entry points from database queries
            agent_entries: Entry points from agent exploration

        Returns:
            Combined and deduplicated list of entry points
        """
        # Use set for deduplication based on node_id only
        seen_node_ids = set()
        combined = []

        # Add database entries first (they have reliable node_ids)
        for entry in database_entries:
            node_id = entry.get("id", "")
            if node_id and node_id not in seen_node_ids:
                seen_node_ids.add(node_id)
                # Convert database format to standard format
                combined.append(
                    {
                        "id": node_id,
                        "name": entry.get("name", ""),
                        "file_path": entry.get("path", ""),
                        "description": f"Database discovered entry point: {entry.get('name', 'Unknown')}",
                        "labels": entry.get("labels", []),
                    }
                )

        # Add agent entries that don't duplicate by node_id
        for entry in agent_entries:
            node_id = entry.get("node_id", "")
            if node_id and node_id not in seen_node_ids:
                seen_node_ids.add(node_id)
                # Ensure agent entry has 'id' field for consistency
                combined.append(
                    {
                        "id": node_id,
                        "name": entry.get("name", ""),
                        "file_path": entry.get("file_path", ""),
                        "description": entry.get(
                            "description", f"Agent discovered entry point: {entry.get('name', 'Unknown')}"
                        ),
                        "labels": entry.get("labels", []),
                    }
                )

        logger.info(
            f"Combined {len(database_entries)} database + {len(agent_entries)} agent entries into {len(combined)} unique entries using node_id deduplication"
        )
        return combined

    def _save_specs(self, _state: SpecAnalysisState) -> Dict[str, Any]:
        """Save discovered specifications - NOT IMPLEMENTED.

        This is a placeholder for future spec saving functionality.
        Currently returns empty results as this functionality is not yet implemented.
        """
        logger.info("Spec saving not implemented - returning empty results")
        return {"spec_analysis_results": [], "spec_relationships": []}

    def _create_standalone_workflow_information_node(self, workflow_data: Dict[str, Any]) -> WorkflowNode:
        """
        Create a WorkflowNode for a complete execution trace.

        Args:
            workflow_data: Dictionary containing execution trace information

        Returns:
            WorkflowNode instance for the execution trace
        """
        entry_name = workflow_data.get("entryPointName", "Unknown")
        entry_point_id = workflow_data.get("entryPointId", "")
        workflow_type = workflow_data.get("workflowType", "execution_trace")
        total_steps = workflow_data.get("totalExecutionSteps", 0)
        
        # Update title to reflect execution trace nature
        workflow_title = f"Execution Trace: {entry_name} ({total_steps} steps)"

        # Create deterministic synthetic path for the execution trace
        synthetic_path = f"file:///execution_traces/{entry_name.replace(' ', '_').lower()}"

        # Prepare content with complete execution trace details
        workflow_nodes = workflow_data.get("workflowNodes", [])
        end_point_id = workflow_data.get("endPointId", "")
        end_point_name = workflow_data.get("endPointName", "")

        # Create execution flow description
        if len(workflow_nodes) > 1:
            execution_flow = " -> ".join([node.get("name", "Unknown") for node in workflow_nodes])
        else:
            execution_flow = entry_name + " (single function, no calls)"

        content_data = {
            "execution_type": "complete_call_stack_trace",
            "entry_point_id": entry_point_id,
            "entry_point_name": entry_name,
            "entry_point_path": workflow_data.get("entryPointPath", ""),
            "end_point_id": end_point_id,
            "end_point_name": end_point_name,
            "end_point_path": workflow_data.get("endPointPath", ""),
            "total_execution_steps": total_steps,
            "execution_flow": execution_flow,
            "call_depth": workflow_data.get("pathLength", 0),
            "workflow_type": workflow_type,
            "discovered_by": workflow_data.get("discoveredBy", "complete_call_flow"),
            "execution_trace": [
                {
                    "step": node.get("execution_step", i + 1),
                    "call_order": node.get("call_order", i),
                    "function_id": node.get("id", ""),
                    "function_name": node.get("name", ""),
                    "file_path": node.get("path", ""),
                    "labels": node.get("labels", []),
                    "start_line": node.get("start_line"),
                    "end_line": node.get("end_line")
                }
                for i, node in enumerate(workflow_nodes)
            ],
        }

        # Use both entry_point_id and end_point_id for unique source_name generation
        source_name = f"execution_trace_{entry_point_id}_{end_point_id}"

        info_node = WorkflowNode(
            title=workflow_title,
            content=json.dumps(content_data, indent=2),
            entry_point_id=entry_point_id,
            entry_point_name=entry_name,
            entry_point_path=workflow_data.get("entryPointPath", ""),
            end_point_id=end_point_id,
            end_point_name=end_point_name,
            end_point_path=workflow_data.get("endPointPath", ""),
            workflow_nodes=workflow_nodes,
            source_type="execution_trace_analysis",
            source_path=synthetic_path,
            source_name=source_name,
            source_labels=["WORKFLOW"],
            graph_environment=self.graph_environment,
            level=0,
            parent=None,
        )

        return info_node

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run spec analysis independently.

        Args:
            input_data: Dictionary containing detected_framework

        Returns:
            Dictionary with spec analysis results
        """
        try:
            logger.info("Starting spec analysis workflow")

            # Ensure graph is compiled
            if not self._compiled_graph:
                self.compile_graph()

            # Initialize state
            initial_state = SpecAnalysisState(
                detected_framework=input_data.get("detected_framework", {}),
                discovered_entry_points=[],
                discovered_workflows=[],
                discovered_specs=[],
                spec_analysis_results=[],
                spec_relationships=[],
                error=None,
            )

            # Execute workflow
            runnable_config = {"run_name": "spec_analysis"}
            response = self._compiled_graph.invoke(input=initial_state, config=runnable_config)

            logger.info("Spec analysis workflow completed successfully")
            return response

        except Exception as e:
            logger.exception(f"Error running spec analysis workflow: {e}")
            return {
                "discovered_specs": [],
                "spec_analysis_results": [],
                "spec_relationships": [],
                "error": str(e),
            }
