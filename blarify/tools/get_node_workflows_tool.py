#!/usr/bin/env python3
"""Tool to get workflows that a code node belongs to."""

import logging
from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.documentation.workflow_creator import WorkflowCreator
from blarify.graph.graph_environment import GraphEnvironment

logger = logging.getLogger(__name__)


class NodeWorkflowsInput(BaseModel):
    """Input schema for getting node workflows."""

    node_id: str = Field(description="The node id (a 32-character UUID-like hash) of the node to get workflows for")

    @field_validator("node_id", mode="before")
    @classmethod
    def format_node_id(cls, value: Any) -> Any:
        """Validate that node_id is a 32 character string."""
        if isinstance(value, str) and len(value) == 32:
            return value
        raise ValueError("Node id must be a 32 character string UUID like hash id")


class GetNodeWorkflowsTool(BaseTool):
    """Tool to discover which workflows a code node participates in."""

    name: str = "get_node_workflows"
    description: str = (
        "Discovers which workflows and execution paths a code node participates in. "
        "Shows how the node is called, what calls it, and its role in larger workflows. "
        "This tool helps you understand how the code you are querying interacts with other parts "
        "of the codebase, how it fits into the overall architecture, and the role it plays in "
        "the system's functionality."
    )

    args_schema: type[BaseModel] = NodeWorkflowsInput  # type: ignore[assignment]

    db_manager: Neo4jManager = Field(description="Neo4jManager object to interact with the database")
    auto_generate: bool = Field(default=True, description="Whether to auto-generate workflows when missing")
    _workflow_creator: Optional[Any] = None

    def __init__(
        self,
        db_manager: Neo4jManager,
        handle_validation_error: bool = False,
        auto_generate: bool = True,
    ):
        """Initialize the tool with database connection."""
        super().__init__(
            db_manager=db_manager,
            handle_validation_error=handle_validation_error,
            auto_generate=auto_generate,
        )

        # Initialize WorkflowCreator if auto_generate is enabled
        if self.auto_generate:
            self._workflow_creator = WorkflowCreator(
                db_manager=self.db_manager,
                graph_environment=GraphEnvironment(environment="main", diff_identifier="0", root_path="/"),
            )
        else:
            self._workflow_creator = None

    def _generate_workflows_for_node(self, node_id: str, node_path: str) -> list[dict[str, Any]]:
        """Generate workflows for a specific node."""
        try:
            if not self.auto_generate or not self._workflow_creator:
                return []

            logger.debug(f"Auto-generating workflows for node {node_id}")

            # Generate workflows targeting this specific node
            result = self._workflow_creator.discover_workflows(node_path=node_path, max_depth=20, save_to_database=True)

            if result.error:
                logger.error(f"Workflow generation error: {result.error}")
                return []

            # Re-query for workflows after generation
            return self._get_workflows_with_chains(node_id)

        except Exception as e:
            logger.error(f"Failed to auto-generate workflows: {e}")
            return []

    def _run(
        self,
        node_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """
        Get workflows that include the specified node.

        Args:
            node_id: The ID of the node to analyze
            run_manager: Optional callback manager

        Returns:
            String representation of the workflows the node belongs to
        """
        try:
            # First, get basic node information
            node_info = self._get_node_info(node_id)
            if not node_info:
                return f"Node with ID '{node_id}' not found in the database."

            output = "=" * 80 + "\n"
            output += f"🔄 WORKFLOWS FOR NODE: {node_info['name']}\n"
            output += "=" * 80 + "\n"
            output += f"📄 File: {node_info.get('path', 'Unknown')}\n"
            output += f"🏷️  Type: {', '.join(node_info.get('labels', ['Unknown']))}\n"
            output += f"🆔 Node ID: {node_id}\n"

            # Get all workflows and their execution chains
            workflows = self._get_workflows_with_chains(node_id)

            if not workflows and self.auto_generate:
                # Try to generate workflows
                node_path = node_info.get("path") or node_info.get("node_path", "")
                if node_path:
                    workflows = self._generate_workflows_for_node(node_id, node_path)

            if not workflows:
                output += "\n" + "━" * 80 + "\n"
                output += "⚠️ WARNING: No workflows found for this node!\n"
                output += "\n"
                if self.auto_generate:
                    output += "Auto-generation was attempted but no workflows were discovered.\n"
                else:
                    output += "This is likely a data issue. Every code node should belong to at least one workflow.\n"
                output += "Possible causes:\n"
                output += "  • Workflow layer not properly generated for this repository\n"
                output += "  • Missing BELONGS_TO_WORKFLOW relationships in the graph\n"
                output += "  • Node exists but workflow discovery hasn't been run\n"
                output += "\n"
                output += "The node exists and is valid, but workflow tracking data is missing.\n"
                output += "You can still explore this node using other tools like:\n"
                output += "  • get_code_by_id to see the implementation\n"
                output += "  • get_relationship_flowchart to see direct relationships\n"
                return output

            # Format each workflow
            for workflow in workflows:
                output += self._format_workflow_section(workflow)

            # Add summary
            output += self._format_summary(workflows)

            return output

        except Exception as e:
            logger.error(f"Error getting workflows for node {node_id}: {e}")
            import traceback

            logger.debug(f"Full traceback: {traceback.format_exc()}")
            return f"Error getting workflows: {str(e)}"

    def _get_node_info(self, node_id: str) -> Optional[dict[str, Any]]:
        """Get basic information about a node."""
        try:
            query = """
            MATCH (n:NODE {node_id: $node_id, entityId: $entity_id})
            RETURN n.node_id as node_id,
                   n.name as name,
                   n.path as path,
                   n.node_path as node_path,
                   labels(n) as labels
            """

            result = self.db_manager.query(query, {"node_id": node_id})

            return result[0] if result else None

        except Exception as e:
            logger.error(f"Error getting node info: {e}")
            return None

    def _get_workflows_with_chains(self, node_id: str) -> list[dict[str, Any]]:
        """Get all workflows this node belongs to with their execution chains."""
        try:
            # First, let's check if the node has any BELONGS_TO_WORKFLOW relationships
            check_query = """
            MATCH (n:NODE {node_id: $node_id, entityId: $entity_id})
            OPTIONAL MATCH (n)-[:BELONGS_TO_WORKFLOW]->(w:NODE)
            RETURN count(w) as workflow_count, 
                   collect(DISTINCT w.layer) as workflow_layers,
                   collect(DISTINCT w.node_id) as workflow_ids
            """

            check_result = self.db_manager.query(check_query, {"node_id": node_id})

            workflow_count = 0  # Default value
            if check_result:
                workflow_count = check_result[0].get("workflow_count", 0)
                workflow_layers = check_result[0].get("workflow_layers", [])
                workflow_ids = check_result[0].get("workflow_ids", [])

                if workflow_count == 0:
                    logger.warning(f"Node {node_id} has no BELONGS_TO_WORKFLOW relationships")
                else:
                    logger.info(f"Node {node_id} belongs to {workflow_count} workflows")
                    logger.debug(f"Workflow layers: {workflow_layers}")
                    logger.debug(f"Workflow IDs: {workflow_ids[:3]}...")  # Log first 3 IDs

            # Query 1: Get workflow metadata
            query = """
            MATCH (n:NODE {node_id: $node_id, entityId: $entity_id})-[:BELONGS_TO_WORKFLOW]->(w:NODE)
            WHERE w.layer = 'workflows'
            OPTIONAL MATCH (entry:NODE {node_id: w.entry_point_id})
            RETURN 
                w.node_id as workflow_id,
                w.title as workflow_name,
                w.entry_point_name as entry_point,
                w.end_point_name as exit_point,
                w.steps as total_steps,
                w.entry_point_path as entry_path,
                w.end_point_path as exit_path,
                entry.name as entry_node_name
            ORDER BY w.title
            """

            result = self.db_manager.query(query, {"node_id": node_id})

            if not result and workflow_count > 0:
                logger.warning(f"Found {workflow_count} workflows but couldn't retrieve workflow details")

            # Process each workflow and get its execution chain
            processed_workflows = []
            for workflow in result:
                try:
                    workflow_id = workflow.get("workflow_id")

                    # Query 2: Get the execution chain for this workflow
                    chain_query = """
                    MATCH (n1:NODE)-[r:WORKFLOW_STEP]->(n2:NODE)
                    WHERE r.scopeText CONTAINS ('workflow_id:' + $workflow_id)
                    WITH n1, n2, r
                    ORDER BY r.step_order, r.depth
                    RETURN COLLECT(DISTINCT {
                        from_id: n1.node_id,
                        from_name: n1.name,
                        from_path: n1.path,
                        to_id: n2.node_id,
                        to_name: n2.name,
                        to_path: n2.path,
                        step_order: r.step_order,
                        depth: r.depth,
                        call_line: r.call_line,
                        call_character: r.call_character
                    }) as steps
                    """

                    chain_result = self.db_manager.query(chain_query, {"workflow_id": workflow_id})

                    # Build execution chain from the steps
                    execution_chain = []
                    if chain_result and chain_result[0].get("steps"):
                        steps = chain_result[0]["steps"]

                        # Build a node sequence from the steps
                        node_sequence = []
                        nodes_seen = set()

                        # Add nodes in order based on steps
                        for step in sorted(steps, key=lambda x: (x.get("step_order", 0), x.get("depth", 0))):
                            # Add from node if not seen
                            from_id = step.get("from_id")
                            if from_id and from_id not in nodes_seen:
                                node_sequence.append(
                                    {
                                        "node_id": from_id,
                                        "name": step.get("from_name", "Unknown"),
                                        "path": step.get("from_path", ""),
                                        "is_target": from_id == node_id,
                                        "step_order": len(node_sequence),
                                        "depth": step.get("depth", 0),
                                        "call_line": None,
                                        "call_character": None,
                                    }
                                )
                                nodes_seen.add(from_id)

                            # Add to node if not seen
                            to_id = step.get("to_id")
                            if to_id and to_id not in nodes_seen:
                                node_sequence.append(
                                    {
                                        "node_id": to_id,
                                        "name": step.get("to_name", "Unknown"),
                                        "path": step.get("to_path", ""),
                                        "is_target": to_id == node_id,
                                        "step_order": len(node_sequence),
                                        "depth": step.get("depth", 0) + 1 if step.get("depth") is not None else 0,
                                        "call_line": step.get("call_line"),
                                        "call_character": step.get("call_character"),
                                    }
                                )
                                nodes_seen.add(to_id)

                        execution_chain = node_sequence

                    workflow["execution_chain"] = execution_chain
                    processed_workflows.append(workflow)

                except Exception as e:
                    logger.warning(f"Error processing workflow {workflow.get('workflow_id')}: {e}")
                    workflow["execution_chain"] = []
                    processed_workflows.append(workflow)

            return processed_workflows

        except Exception as e:
            logger.error(f"Error getting workflows with chains: {e}")
            import traceback

            logger.debug(f"Full traceback: {traceback.format_exc()}")
            return []

    def _format_workflow_section(self, workflow: dict[str, Any]) -> str:
        """Format a single workflow section."""
        output = "\n" + "━" * 80 + "\n"
        output += f"📊 WORKFLOW: {workflow.get('workflow_name', 'Unnamed Workflow')}\n"
        output += "━" * 80 + "\n\n"

        # Add workflow metadata
        entry = workflow.get("entry_point") or workflow.get("chain_start", "Unknown")
        exit_point = workflow.get("exit_point") or workflow.get("chain_end", "Unknown")
        steps_count = workflow.get("total_steps", len(workflow.get("execution_chain", [])))
        entry_path = workflow.get("entry_path", "")
        exit_path = workflow.get("exit_path", "")

        output += f"🎯 Entry: {entry}() → Exit: {exit_point}()\n"
        if entry_path and entry_path != exit_path:
            output += f"📁 Entry Path: {entry_path}\n"
            output += f"📁 Exit Path: {exit_path}\n"
        elif entry_path:
            output += f"📁 Path: {entry_path}\n"
        output += f"📈 Total Steps: {steps_count}\n\n"

        # Format execution chain
        chain = workflow.get("execution_chain", [])

        if not chain:
            # If no chain, at least show the entry and exit points
            output += "Execution Flow:\n"
            output += f"  Entry: {workflow.get('entry_point', 'Unknown')}()\n"
            if workflow.get("entry_point") != workflow.get("exit_point"):
                output += f"  Exit: {workflow.get('exit_point', 'Unknown')}()\n"
            output += "\n💡 Note: Detailed execution chain not available. Use other tools to explore relationships.\n"
            return output

        output += "Execution Chain:\n"

        target_step = None
        for i, step in enumerate(chain):
            if step.get("is_target"):
                target_step = i
                break

        for i, step in enumerate(chain):
            depth = step.get("depth", 0)
            indent = "  " + "    " * depth

            # Build step info with full node ID
            step_info = f"[{i}] {step['name']}()"

            # Add call location if available
            call_details = []
            if depth > 0:
                call_details.append(f"depth:{depth}")
            if step.get("call_line"):
                call_details.append(f"line:{step['call_line']}")
            if step.get("call_character"):
                call_details.append(f"char:{step['call_character']}")

            if call_details:
                step_info += f" ({', '.join(call_details)})"

            # Add node ID on same line
            step_info += f"\n{indent}    ID: {step.get('node_id', 'Unknown')}"

            # Highlight target node
            if step.get("is_target"):
                output += f"{indent}{step_info} ← 【YOU ARE HERE】\n"
            else:
                # Add tree structure
                if i > 0 and step.get("depth", 0) > chain[i - 1].get("depth", 0):
                    output += f"{indent[:-4]}└─> {step_info}\n"
                else:
                    output += f"{indent}{step_info}\n"

        # Add position summary
        if target_step is not None:
            output += f"\nPosition: Step {target_step} of {len(chain)} | "
            target = chain[target_step]
            output += f"Depth: {target.get('depth', 0)}"
            if target_step > 0:
                caller = chain[target_step - 1]
                output += f" | Called from: {caller['name']}()"
                if target.get("call_line"):
                    output += f" at line {target['call_line']}"
            output += "\n"

        return output

    def _format_summary(self, workflows: list[dict[str, Any]]) -> str:
        """Format a summary section."""
        output = "\n" + "=" * 80 + "\n"
        output += "📊 SUMMARY:\n"
        output += "=" * 80 + "\n"

        output += f"• Total Workflows: {len(workflows)}\n"

        if workflows:
            # Analyze node's role across workflows
            avg_depth = 0
            positions = []

            for workflow in workflows:
                chain = workflow.get("execution_chain", [])
                for i, step in enumerate(chain):
                    if step.get("is_target"):
                        positions.append(i + 1)
                        avg_depth += step.get("depth", 0)
                        break

            if positions:
                avg_position = sum(positions) / len(positions)
                avg_depth = avg_depth / len(positions)

                output += f"• Average Position in Workflows: Step {avg_position:.1f}\n"
                output += f"• Average Call Depth: {avg_depth:.1f}\n"

            # List workflow names
            output += "\n• Participating Workflows:\n"
            for workflow in workflows:
                name = workflow.get("workflow_name", "Unnamed")
                entry = workflow.get("entry_point") or workflow.get("chain_start", "Unknown")
                output += f"  - {name} (entry: {entry})\n"

        return output
