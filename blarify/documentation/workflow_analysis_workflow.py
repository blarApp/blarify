"""
Workflow Analysis Workflow for discovering and analyzing business workflows.

This module provides a dedicated LangGraph workflow for analyzing InformationNodes
to discover business workflows that span multiple components.

IMPLEMENTATION STATUS:
- ✅ Architecture completed with WorkflowAnalysisState and WorkflowAnalysisWorkflow
- ✅ Workflow discovery implemented with framework-guided analysis
- ✅ Independent execution capability for testing and modularity
- ❌ Workflow processing implementation (NotImplementedError stub for future work)
"""

from operator import add
from typing import Annotated, TypedDict, Dict, Any, Optional, List
import logging
import json

from langgraph.graph import START, StateGraph

from ..agents.llm_provider import LLMProvider
from ..agents.prompt_templates import WORKFLOW_DISCOVERY_TEMPLATE
from ..agents.schemas import WorkflowDiscoveryResponse
from ..agents.tools import (
    InformationNodeSearchTool,
    InformationNodeRelationshipTraversalTool,
    InformationNodesByFolderTool,
)
from ..db_managers.db_manager import AbstractDbManager
from ..db_managers.queries import get_root_information_nodes
from ..graph.graph_environment import GraphEnvironment

logger = logging.getLogger(__name__)


class WorkflowAnalysisState(TypedDict):
    """State management for workflow analysis workflow."""

    # Input data
    detected_framework: Dict[str, Any]

    # Output data
    discovered_workflows: List[Dict[str, Any]]
    workflow_analysis_results: Annotated[list, add]
    workflow_relationships: Annotated[list, add]
    error: Optional[str]


class WorkflowAnalysisWorkflow:
    """
    Dedicated workflow for discovering and analyzing business workflows.

    This workflow takes InformationNodes and discovers business workflows
    that span multiple components, then processes each workflow for detailed analysis.
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
        """Compile the workflow analysis workflow graph."""
        workflow = StateGraph(WorkflowAnalysisState)

        # Add workflow analysis nodes
        workflow.add_node("discover_workflows", self._discover_workflows)
        workflow.add_node("process_workflows", self._process_workflows)

        # Linear flow: discover workflows -> process workflows
        workflow.add_edge(START, "discover_workflows")
        workflow.add_edge("discover_workflows", "process_workflows")

        self._compiled_graph = workflow.compile()

    def _discover_workflows(self, state: WorkflowAnalysisState) -> Dict[str, Any]:
        """Discover business workflows by analyzing all root-level InformationNodes."""
        try:
            logger.info("Starting workflow discovery analysis")

            # Get required data from state
            detected_framework = state.get("detected_framework", {})

            logger.info("Analyzing all root-level information nodes for workflow discovery")

            # Query all root information nodes from database
            root_information_nodes_raw = get_root_information_nodes(
                db_manager=self.company_graph_manager,
                entity_id=self.company_id,
                repo_id=self.repo_id,
            )

            if not root_information_nodes_raw:
                logger.warning("No root information nodes available for workflow discovery")
                return {"discovered_workflows": []}

            # Convert to simplified format for LLM processing
            root_information_nodes = []
            for node in root_information_nodes_raw:
                root_information_nodes.append(
                    {
                        "node_id": node.get("attributes", {}).get("node_id", ""),
                        "title": node.get("attributes", {}).get("title", ""),
                        "content": node.get("attributes", {}).get("content", ""),
                        "source_path": node.get("attributes", {}).get("source_path", ""),
                    }
                )

            # Prepare input for the workflow discovery prompt
            system_prompt, input_prompt = WORKFLOW_DISCOVERY_TEMPLATE.get_prompts()

            # Format root information nodes for the prompt (flat structure)
            root_info_formatted = "\n## Root-Level Information Nodes\n"
            for node in root_information_nodes:
                root_info_formatted += f"### {node['title']}\n"
                root_info_formatted += f"Node ID: {node['node_id']}\n"
                root_info_formatted += f"Path: {node['source_path']}\n"
                root_info_formatted += f"Description: {node['content']}\n\n"

            # Use ReactAgent for workflow discovery with InformationNode exploration tools
            tools = [
                InformationNodeSearchTool(
                    db_manager=self.company_graph_manager, company_id=self.company_id, repo_id=self.repo_id
                ),
                InformationNodeRelationshipTraversalTool(
                    db_manager=self.company_graph_manager, company_id=self.company_id, repo_id=self.repo_id
                ),
                InformationNodesByFolderTool(
                    db_manager=self.company_graph_manager, company_id=self.company_id, repo_id=self.repo_id
                ),
            ]

            response = self.agent_caller.call_react_agent(
                system_prompt=system_prompt,
                tools=tools,
                input_dict={
                    "framework_analysis": detected_framework,
                    "root_information_nodes": root_info_formatted,
                },
                input_prompt=input_prompt,
                output_schema=WorkflowDiscoveryResponse,
            )

            # Extract workflows from response
            discovered_workflows = []
            if hasattr(response, "workflows"):
                # Direct structured output
                for workflow in response.workflows:
                    discovered_workflows.append(
                        {
                            "name": workflow.name,
                            "description": workflow.description,
                            "entry_points": workflow.entry_points,
                            "scope": workflow.scope,
                            "framework_context": workflow.framework_context,
                        }
                    )
            elif isinstance(response, dict) and "workflows" in response:
                # Dictionary response
                discovered_workflows = response["workflows"]
            else:
                # Fallback parsing
                logger.warning("Unexpected workflow discovery response format, attempting to parse...")
                try:
                    response_content = response.content if hasattr(response, "content") else str(response)
                    parsed_response = json.loads(response_content)
                    discovered_workflows = parsed_response.get("workflows", [])
                except (json.JSONDecodeError, AttributeError) as e:
                    logger.exception(f"Failed to parse workflow discovery response: {e}")
                    discovered_workflows = []

            logger.info(f"Workflow discovery completed: {len(discovered_workflows)} workflows discovered")
            for workflow in discovered_workflows:
                logger.info(
                    f"- {workflow.get('name', 'Unknown')}: {workflow.get('description', 'No description')[:100]}..."
                )

            return {"discovered_workflows": discovered_workflows}

        except Exception as e:
            logger.exception(f"Error in workflow discovery: {e}")
            return {"discovered_workflows": [], "error": str(e)}

    def _process_workflows(self, state: WorkflowAnalysisState) -> Dict[str, Any]:
        """Process discovered workflows using dedicated WorkflowAnalysisWorkflow (stub for now)."""
        discovered_workflows = state.get("discovered_workflows", [])
        logger.info(
            f"Workflow processing node called with {len(discovered_workflows)} discovered workflows - raising NotImplementedError as planned"
        )

    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run workflow analysis independently.

        Args:
            input_data: Dictionary containing detected_framework

        Returns:
            Dictionary with workflow analysis results
        """
        try:
            logger.info("Starting workflow analysis workflow")

            # Ensure graph is compiled
            if not self._compiled_graph:
                self.compile_graph()

            # Initialize state
            initial_state = WorkflowAnalysisState(
                detected_framework=input_data.get("detected_framework", {}),
                discovered_workflows=[],
                workflow_analysis_results=[],
                workflow_relationships=[],
                error=None,
            )

            # Execute workflow
            runnable_config = {"run_name": "workflow_analysis"}
            response = self._compiled_graph.invoke(input=initial_state, config=runnable_config)

            logger.info("Workflow analysis workflow completed successfully")
            return response

        except Exception as e:
            logger.exception(f"Error running workflow analysis workflow: {e}")
            return {
                "discovered_workflows": [],
                "workflow_analysis_results": [],
                "workflow_relationships": [],
                "error": str(e),
            }
