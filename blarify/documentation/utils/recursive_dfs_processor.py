"""
Recursive DFS processor for analyzing code hierarchies one branch at a time.

This module implements a depth-first search traversal of the code graph, processing
leaf nodes first and then building up understanding through parent nodes with
skeleton comment replacement.
"""

import re
import logging
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from ...agents.llm_provider import LLMProvider
from ...agents.prompt_templates import LEAF_NODE_ANALYSIS_TEMPLATE, PARENT_NODE_ANALYSIS_TEMPLATE
from ...db_managers.db_manager import AbstractDbManager
from ...db_managers.dtos.node_with_content_dto import NodeWithContentDto
from ...db_managers.queries import get_node_by_path, get_direct_children
from ...graph.node.information_node import InformationNode
from ...graph.graph_environment import GraphEnvironment

logger = logging.getLogger(__name__)


class ProcessingResult(BaseModel):
    """Result of processing a node (folder or file) with recursive DFS."""

    node_path: str
    node_relationships: List[Dict[str, Any]] = Field(default_factory=list)
    hierarchical_analysis: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    node_source_mapping: Dict[str, str] = Field(default_factory=dict)  # Maps info_node_id -> source_node_id
    save_status: Optional[Dict[str, Any]] = None  # Optional save status information
    information_nodes: List[Dict[str, Any]] = Field(default_factory=list)  # InformationNode objects


class RecursiveDFSProcessor:
    """
    Processes code hierarchies using recursive depth-first search.

    This processor analyzes leaf nodes first, then builds up understanding
    through parent nodes, replacing skeleton comments with LLM-generated
    descriptions as it traverses up the hierarchy.
    """

    def __init__(
        self,
        db_manager: AbstractDbManager,
        agent_caller: LLMProvider,
        company_id: str,
        repo_id: str,
        graph_environment: GraphEnvironment,
    ):
        """
        Initialize the recursive DFS processor.

        Args:
            db_manager: Database manager for querying nodes
            agent_caller: LLM provider for generating descriptions
            company_id: Company/entity ID for database queries
            repo_id: Repository ID for database queries
            graph_environment: Graph environment for node ID generation
        """
        self.db_manager = db_manager
        self.agent_caller = agent_caller
        self.company_id = company_id
        self.repo_id = repo_id
        self.graph_environment = graph_environment
        self.node_descriptions: Dict[str, InformationNode] = {}  # Cache processed nodes
        self.node_source_mapping: Dict[str, str] = {}  # Maps info_node_id -> source_node_id
        self.source_to_description: Dict[str, str] = {}  # Maps source_node_id -> description content

    def process_node(self, node_path: str) -> ProcessingResult:
        """
        Entry point - processes a node (folder or file) recursively.

        For folders, this performs recursive DFS processing of all children.
        For files, this processes the file as a leaf node.

        Args:
            node_path: Path to the node (folder or file) to process

        Returns:
            ProcessingResult with all information nodes and relationships
        """
        try:
            logger.info(f"Starting recursive DFS processing for node: {node_path}")

            # Get the root node (folder or file)
            root_node = get_node_by_path(self.db_manager, self.company_id, self.repo_id, node_path)

            if not root_node:
                logger.exception(f"Node not found for path: {node_path}")
                return ProcessingResult(node_path=node_path, error=f"Node not found: {node_path}")

            # Process the node recursively
            root_description = self._process_node_recursive(root_node)

            # Collect all processed descriptions and convert to dicts
            all_descriptions_as_dicts = [node.as_object() for node in self.node_descriptions.values()]

            logger.info(f"Completed recursive DFS processing. Generated {len(all_descriptions_as_dicts)} descriptions")

            return ProcessingResult(
                node_path=node_path,
                hierarchical_analysis={"complete": True, "root_description": root_description.as_object()},
                node_source_mapping=self.node_source_mapping,
                information_nodes=all_descriptions_as_dicts,
            )

        except Exception as e:
            logger.exception(f"Error in recursive DFS processing: {e}")
            return ProcessingResult(node_path=node_path, error=str(e))

    def _process_node_recursive(self, node: NodeWithContentDto) -> InformationNode:
        """
        Core recursive method - processes a node and all its children.

        Args:
            node: The node to process

        Returns:
            InformationNodeDescription for this node
        """
        # Check cache to avoid reprocessing
        if node.id in self.node_descriptions:
            return self.node_descriptions[node.id]

        logger.debug(f"Processing node: {node.name} ({node.id})")

        # Get immediate children
        children = get_direct_children(self.db_manager, self.company_id, self.repo_id, node.id)

        if not children:  # LEAF NODE
            logger.debug(f"Processing leaf node: {node.name}")
            description = self._process_leaf_node(node)
        else:  # PARENT NODE
            logger.debug(f"Processing parent node: {node.name} with {len(children)} children")

            # Process ALL children first (recursive calls)
            child_descriptions = []
            for child in children:
                child_desc = self._process_node_recursive(child)  # RECURSION
                child_descriptions.append(child_desc)

            # Process parent with complete child context
            description = self._process_parent_node(node, child_descriptions)

        # Cache the result
        self.node_descriptions[node.id] = description
        return description

    def _process_leaf_node(self, node: NodeWithContentDto) -> InformationNode:
        """
        Process a leaf node using the dumb agent.

        Args:
            node: The leaf node to process

        Returns:
            InformationNodeDescription for the leaf node
        """
        try:
            # Get raw templates and let LLM provider handle formatting
            system_prompt, input_prompt = LEAF_NODE_ANALYSIS_TEMPLATE.get_prompts()

            # Use call_dumb_agent for simple, fast processing with 5s timeout
            runnable_config = {"run_name": node.name}
            response = self.agent_caller.call_dumb_agent(
                system_prompt=system_prompt,
                input_dict={
                    "node_name": node.name,
                    "node_labels": " | ".join(node.labels) if node.labels else "UNKNOWN",
                    "node_path": node.path,
                    "node_content": node.content,
                },
                output_schema=None,
                input_prompt=input_prompt,
                config=runnable_config,
                timeout=5,
            )

            # Extract response content
            response_content = response.content if hasattr(response, "content") else str(response)

            # Create InformationNode
            info_node = InformationNode(
                title=f"Description of {node.name}",
                content=response_content,
                info_type="leaf_description",
                source_path=node.path,
                source_name=node.name,
                source_labels=node.labels,
                source_type="recursive_leaf_analysis",
                graph_environment=self.graph_environment,
            )

            # Track mapping using the node's hashed_id
            self.node_source_mapping[info_node.hashed_id] = node.id
            # Also track for efficient child lookup during skeleton replacement
            self.source_to_description[node.id] = response_content

            return info_node

        except Exception as e:
            logger.exception(f"Error analyzing leaf node {node.name} ({node.id}): {e}")
            # Return fallback description
            info_node = InformationNode(
                title=f"Description of {node.name}",
                content=f"Error analyzing this {' | '.join(node.labels) if node.labels else 'code element'}: {str(e)}",
                info_type="leaf_description",
                source_path=node.path,
                source_name=node.name,
                source_labels=node.labels,
                source_type="error_fallback",
                graph_environment=self.graph_environment,
            )

            # Track mapping using the node's hashed_id
            self.node_source_mapping[info_node.hashed_id] = node.id
            # Also track for efficient child lookup during skeleton replacement
            self.source_to_description[node.id] = (
                f"Error analyzing this {' | '.join(node.labels) if node.labels else 'code element'}: {str(e)}"
            )

            return info_node

    def _process_parent_node(
        self, node: NodeWithContentDto, child_descriptions: List[InformationNode]
    ) -> InformationNode:
        """
        Process a parent node with context from all its children.

        Args:
            node: The parent node to process
            child_descriptions: List of child descriptions

        Returns:
            InformationNodeDescription for the parent node
        """
        try:
            # Get raw templates and let LLM provider handle formatting
            system_prompt, input_prompt = PARENT_NODE_ANALYSIS_TEMPLATE.get_prompts()

            # Create enhanced content based on node type
            if "FOLDER" in node.labels:
                enhanced_content = self._create_child_descriptions_summary(child_descriptions)
            else:
                # For files and code nodes with actual content, replace skeleton comments
                enhanced_content = self._replace_skeleton_comments_with_descriptions(node.content, child_descriptions)

            # Use call_dumb_agent for simple, fast processing with 5s timeout
            runnable_config = {"run_name": node.name}
            response = self.agent_caller.call_dumb_agent(
                system_prompt=system_prompt,
                input_dict={
                    "node_name": node.name,
                    "node_labels": " | ".join(node.labels) if node.labels else "UNKNOWN",
                    "node_path": node.path,
                    "node_content": enhanced_content,
                },
                output_schema=None,
                input_prompt=input_prompt,
                config=runnable_config,
                timeout=5,
            )

            # Extract response content
            response_content = response.content if hasattr(response, "content") else str(response)

            # Create InformationNode
            info_node = InformationNode(
                title=f"Description of {node.name}",
                content=response_content,
                info_type="parent_description",
                source_path=node.path,
                source_name=node.name,
                source_labels=node.labels,
                source_type="recursive_parent_analysis",
                enhanced_content=enhanced_content,
                children_count=len(child_descriptions),
                graph_environment=self.graph_environment,
            )

            # Track mapping using the node's hashed_id
            self.node_source_mapping[info_node.hashed_id] = node.id
            # Also track for efficient child lookup during skeleton replacement
            self.source_to_description[node.id] = response_content

            return info_node

        except Exception as e:
            logger.exception(f"Error analyzing parent node {node.name} ({node.id}): {e}")
            # Return fallback description
            info_node = InformationNode(
                title=f"Description of {node.name}",
                content=f"Error analyzing this {' | '.join(node.labels) if node.labels else 'code element'}: {str(e)}",
                info_type="parent_description",
                source_path=node.path,
                source_name=node.name,
                source_labels=node.labels,
                source_type="error_fallback",
                children_count=len(child_descriptions),
                graph_environment=self.graph_environment,
            )

            # Track mapping using the node's hashed_id
            self.node_source_mapping[info_node.hashed_id] = node.id
            # Also track for efficient child lookup during skeleton replacement
            self.source_to_description[node.id] = (
                f"Error analyzing this {' | '.join(node.labels) if node.labels else 'code element'}: {str(e)}"
            )

            return info_node

    def _replace_skeleton_comments_with_descriptions(
        self, parent_content: str, child_descriptions: List[InformationNode]
    ) -> str:
        """
        Replace skeleton comments with LLM-generated descriptions.

        Args:
            parent_content: The parent node's content with skeleton comments
            child_descriptions: List of child descriptions to insert

        Returns:
            Enhanced content with descriptions replacing skeleton comments
        """
        if not parent_content:
            return ""

        enhanced_content = parent_content

        # Use the pre-built source_to_description mapping for efficient lookup
        child_lookup = self.source_to_description

        # Pattern to match skeleton comments
        # Example: # Code replaced for brevity, see node: 6fd101f9571073a44fed7c085c94eec2
        skeleton_pattern = r"# Code replaced for brevity, see node: ([a-f0-9]+)"

        def replace_comment(match):
            node_id = match.group(1)
            if node_id in child_lookup:
                description = child_lookup[node_id]
                # Format as a proper docstring
                # Indent the description to match the original comment's indentation
                indent = re.search(r"^(\s*)", match.group(0)).group(1)
                formatted_desc = f'{indent}"""\n'
                for line in description.split("\n"):
                    formatted_desc += f"{indent}{line}\n"
                formatted_desc += f'{indent}"""'
                return formatted_desc
            else:
                # Keep original if no description found
                return match.group(0)

        enhanced_content = re.sub(skeleton_pattern, replace_comment, enhanced_content, flags=re.MULTILINE)

        return enhanced_content

    def _create_child_descriptions_summary(self, child_descriptions: List[InformationNode]) -> str:
        """
        Create enhanced content for folder nodes by summarizing child descriptions.

        Args:
            child_descriptions: List of child descriptions

        Returns:
            Structured summary of all child elements
        """
        if not child_descriptions:
            return "Empty folder with no child elements."

        content_parts = ["Folder containing the following elements:\n"]

        for desc in child_descriptions:
            # Extract node type from source labels
            node_type = " | ".join(desc.source_labels) if desc.source_labels else "UNKNOWN"

            # Get just the filename/component name from path
            component_name = desc.source_path.split("/")[-1] if desc.source_path else "unknown"

            content_parts.append(f"- **{component_name}** ({node_type}): {desc.content}")

        return "\n".join(content_parts)
