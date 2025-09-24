"""
Bottom-up batch processor for analyzing code hierarchies using query-based processing.

This module implements a scalable approach to documentation generation that processes
nodes in batches using database queries, avoiding memory exhaustion for large codebases.
"""

import logging
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field, ConfigDict
from typing import Union
from pydantic import field_validator

from blarify.agents.llm_provider import LLMProvider
from blarify.agents.prompt_templates import (
    LEAF_NODE_ANALYSIS_TEMPLATE,
    PARENT_NODE_ANALYSIS_TEMPLATE,
    FUNCTION_WITH_CALLS_ANALYSIS_TEMPLATE,
)
from blarify.documentation.queries.batch_processing_queries import (
    get_child_descriptions_query,
    get_leaf_nodes_under_node_query,
    get_remaining_pending_functions_query,
)
from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager
from blarify.repositories.graph_db_manager.dtos.node_with_content_dto import NodeWithContentDto
from blarify.repositories.graph_db_manager.queries import (
    get_node_by_path,
)
from blarify.graph.node.documentation_node import DocumentationNode
from blarify.graph.relationship.relationship_creator import RelationshipCreator
from blarify.documentation.queries import (
    get_processable_nodes_with_descriptions_query,
    mark_nodes_completed_query,
    check_pending_nodes_query,
)

# Note: We don't import concrete Node classes as we work with DTOs in documentation layer
from blarify.graph.graph_environment import GraphEnvironment

logger = logging.getLogger(__name__)


class ProcessingResult(BaseModel):
    """Result of processing a node (folder or file) with query-based processing."""

    model_config = ConfigDict(arbitrary_types_allowed=True)  # Allow Node objects

    node_path: str
    node_relationships: List[Dict[str, Any]] = Field(default_factory=list)
    hierarchical_analysis: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    total_nodes_processed: int = 0
    save_status: Optional[Dict[str, Any]] = None  # Optional save status information
    information_nodes: List[Dict[str, Any]] = Field(default_factory=list)  # DocumentationNode objects (as dicts)

    # New fields for proper Node object handling
    documentation_nodes: List[DocumentationNode] = Field(default_factory=list)  # Actual DocumentationNode objects
    source_nodes: List[NodeWithContentDto] = Field(default_factory=list)  # Source code DTOs

    @field_validator("source_nodes", mode="before")
    @classmethod
    def validate_source_nodes(cls, v: Any) -> List[Union[NodeWithContentDto, Dict[str, Any]]]:
        """Convert NodeWithContentDto instances or dicts to the expected format."""
        if not v:
            return []

        result = []
        for item in v:
            if isinstance(item, dict):
                # If it's a dict, create a NodeWithContentDto from it
                result.append(NodeWithContentDto(**item))
            elif isinstance(item, NodeWithContentDto):
                # If it's already a NodeWithContentDto, keep it
                result.append(item)
            else:
                # For any other type, try to convert it
                result.append(item)
        return result


class BottomUpBatchProcessor:
    """
    Processes code hierarchies using query-based batch processing.

    This processor analyzes leaf nodes first, then builds up understanding
    through parent nodes, using database queries to manage processing state
    and avoid memory exhaustion for large codebases.
    """

    def __init__(
        self,
        db_manager: AbstractDbManager,
        agent_caller: LLMProvider,
        graph_environment: GraphEnvironment,
        max_workers: int = 5,
        root_node: Optional[NodeWithContentDto] = None,
        overwrite_documentation: bool = False,
        batch_size: int = 1000,
        generate_embeddings: bool = False,
    ):
        """
        Initialize the query-based batch processor.

        Args:
            db_manager: Database manager for querying nodes
            agent_caller: LLM provider for generating descriptions
            company_id: Company/entity ID for database queries
            repo_id: Repository ID for database queries
            graph_environment: Graph environment for node ID generation
            max_workers: Maximum number of threads for parallel processing
            root_node: Optional root node to start processing from
            overwrite_documentation: Whether to overwrite existing documentation
            batch_size: Number of nodes to process in each batch
        """
        self.db_manager = db_manager
        self.agent_caller = agent_caller
        self.graph_environment = graph_environment
        self.max_workers = max_workers
        self.root_node = root_node
        self.overwrite_documentation = overwrite_documentation
        self.batch_size = batch_size
        self.generate_embeddings = generate_embeddings

        # Unique ID for this processing run
        self.processing_run_id = str(uuid.uuid4())

        # Initialize embedding service if needed
        self.embedding_service = None
        if self.generate_embeddings:
            from blarify.services.embedding_service import EmbeddingService

            self.embedding_service = EmbeddingService()

        # Remove ALL in-memory caches - we use database for state management

    def process_node(self, node_path: str) -> ProcessingResult:
        """
        Entry point - process using database queries only.

        Args:
            node_path: Path to the node (folder or file) to process

        Returns:
            ProcessingResult with processing statistics
        """
        try:
            # Get root node
            root_node = self.root_node
            if not root_node:
                root_node = get_node_by_path(self.db_manager, node_path)
                if not root_node:
                    return ProcessingResult(node_path=node_path, error=f"Node not found: {node_path}")

            # Process using queries
            total_processed = self._process_node_query_based(root_node)

            return ProcessingResult(
                node_path=node_path,
                hierarchical_analysis={"complete": True},
                total_nodes_processed=total_processed,
                error=None,
                # Don't return nodes - they're in the database
                information_nodes=[],
                documentation_nodes=[],
                source_nodes=[],
            )

        except Exception as e:
            logger.exception(f"Error in query-based processing: {e}")
            return ProcessingResult(node_path=node_path, error=str(e))

    def _process_node_query_based(self, root_node: NodeWithContentDto) -> int:
        """Process using database queries without memory storage."""

        total_processed = 0
        max_iterations = 1000  # Safety limit

        # Phase 1: Process all leaf nodes first
        iteration = 0
        while iteration < max_iterations:
            iteration += 1

            # Try to process leaf nodes first
            leaf_count = self._process_leaf_batch(root_node)
            if leaf_count == 0:
                break
            total_processed += leaf_count
            logger.debug(f"Processed {leaf_count} leaf nodes in iteration {iteration}")

        # Phase 2: Process parent nodes and handle cycles
        iteration = 0
        consecutive_stuck_iterations = 0

        while iteration < max_iterations:
            iteration += 1

            # Try to process parent nodes with completed children
            parent_count = self._process_parent_batch(root_node)
            if parent_count > 0:
                total_processed += parent_count
                consecutive_stuck_iterations = 0  # Reset stuck counter
                logger.debug(f"Processed {parent_count} parent nodes in iteration {iteration}")
                continue

            # Check if any nodes remain
            if not self._has_pending_nodes(root_node):
                logger.debug("No pending nodes remaining")
                break

            # If we're stuck (no parents processable but nodes remain),
            # process remaining functions (likely in cycles)
            consecutive_stuck_iterations += 1

            if consecutive_stuck_iterations >= 2:
                # Process remaining functions with whatever descriptions are available
                logger.info("Detected potential cycles - processing remaining functions")
                remaining_count = self._process_remaining_functions_batch(root_node)

                if remaining_count > 0:
                    total_processed += remaining_count
                    consecutive_stuck_iterations = 0  # Reset after progress
                    logger.debug(f"Processed {remaining_count} remaining functions")
                else:
                    # No functions left, might just be the root node
                    logger.debug("No remaining functions to process")
                    break

        # Phase 3: Process root node if needed
        root_count = self._process_root_node(root_node)
        if root_count > 0:
            total_processed += root_count
            logger.debug("Processed root node")

        return total_processed

    def _process_leaf_batch(self, root_node: NodeWithContentDto) -> int:
        """Process a batch of leaf nodes."""
        # Get leaf nodes from database
        query = get_leaf_nodes_under_node_query()
        params = {
            "run_id": self.processing_run_id,
            "batch_size": self.batch_size,
            "root_node_id": root_node.id,
        }

        batch_results = self.db_manager.query(query, params)
        if not batch_results:
            return 0

        # Process batch with thread pool
        documentation_nodes = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []

            for node_data in batch_results:
                # Create NodeWithContentDto from query result
                node = NodeWithContentDto(
                    id=node_data["id"],
                    name=node_data["name"],
                    labels=node_data["labels"],
                    path=node_data["path"],
                    start_line=node_data.get("start_line"),
                    end_line=node_data.get("end_line"),
                    content=node_data.get("content", ""),
                )
                future = executor.submit(self._process_leaf_node, node)
                futures.append((future, node.id))

            # Harvest results as they complete
            for future in as_completed([f[0] for f in futures]):
                try:
                    doc_node = future.result(timeout=30)
                    if doc_node:
                        documentation_nodes.append(doc_node)
                except Exception as e:
                    logger.error(f"Error processing leaf node: {e}")

        # Save batch to database immediately
        if documentation_nodes:
            self._save_documentation_batch(documentation_nodes)

        return len(batch_results)

    def _process_parent_batch(self, root_node: NodeWithContentDto) -> int:
        """Process a batch of parent nodes with child descriptions."""
        # Get parent nodes with descriptions from database
        query = get_processable_nodes_with_descriptions_query()
        params = {
            "run_id": self.processing_run_id,
            "root_node_id": root_node.id,
            "batch_size": self.batch_size,
        }

        batch_results = self.db_manager.query(query, params)
        if not batch_results:
            return 0

        # Process batch with thread pool
        documentation_nodes = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []

            for node_data in batch_results:
                # Extract node info
                node = NodeWithContentDto(
                    id=node_data["id"],
                    name=node_data["name"],
                    labels=node_data["labels"],
                    path=node_data["path"],
                    start_line=node_data.get("start_line"),
                    end_line=node_data.get("end_line"),
                    content=node_data.get("content", ""),
                )

                # Extract child descriptions
                hier_descriptions = node_data.get("hier_descriptions", [])
                call_descriptions = node_data.get("call_descriptions", [])

                # Convert descriptions to DocumentationNode-like objects for processing
                child_descriptions = []
                for desc in hier_descriptions + call_descriptions:
                    if desc and desc.get("description"):
                        # Create minimal DocumentationNode for child context
                        child_doc = DocumentationNode(
                            content=desc["description"],
                            info_type="child_description",
                            source_path=desc.get("path", ""),
                            source_name=desc.get("name", ""),
                            source_id=desc.get("id", ""),
                            source_labels=desc.get("labels", []),
                            source_type="child",
                            graph_environment=self.graph_environment,
                        )
                        child_descriptions.append(child_doc)

                future = executor.submit(self._process_parent_node, node, child_descriptions)
                futures.append((future, node.id))

            # Harvest results
            for future in as_completed([f[0] for f in futures]):
                try:
                    doc_node = future.result(timeout=30)
                    if doc_node:
                        documentation_nodes.append(doc_node)
                except Exception as e:
                    logger.error(f"Error processing parent node: {e}")

        # Save batch immediately
        if documentation_nodes:
            self._save_documentation_batch(documentation_nodes)

        return len(batch_results)

    def _process_remaining_functions_batch(self, root_node: NodeWithContentDto) -> int:
        """
        Process remaining FUNCTION nodes that may be in cycles.

        This method processes functions without requiring all their children to be completed,
        using whatever child descriptions are available.
        """
        # Get remaining functions from database
        query = get_remaining_pending_functions_query()
        params = {
            "run_id": self.processing_run_id,
            "batch_size": self.batch_size,
            "root_node_id": root_node.id,
        }

        batch_results = self.db_manager.query(query, params)
        if not batch_results:
            return 0

        logger.debug(f"Processing {len(batch_results)} remaining functions (potential cycles)")

        # Process batch with thread pool
        documentation_nodes = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []

            for node_data in batch_results:
                # Extract node info
                node = NodeWithContentDto(
                    id=node_data["id"],
                    name=node_data["name"],
                    labels=node_data["labels"],
                    path=node_data["path"],
                    start_line=node_data.get("start_line"),
                    end_line=node_data.get("end_line"),
                    content=node_data.get("content", ""),
                )

                # Extract child descriptions (may be incomplete due to cycles)
                hier_descriptions = node_data.get("hier_descriptions", [])
                call_descriptions = node_data.get("call_descriptions", [])

                # Convert descriptions to DocumentationNode-like objects for processing
                child_descriptions = []
                for desc in hier_descriptions + call_descriptions:
                    if desc and desc.get("description"):
                        # Create minimal DocumentationNode for child context
                        child_doc = DocumentationNode(
                            content=desc["description"],
                            info_type="child_description",
                            source_path=desc.get("path", ""),
                            source_name=desc.get("name", ""),
                            source_id=desc.get("id", ""),
                            source_labels=desc.get("labels", []),
                            source_type="child",
                            graph_environment=self.graph_environment,
                        )
                        child_descriptions.append(child_doc)

                # Reuse _process_parent_node for processing (no special cycle handling)
                future = executor.submit(self._process_parent_node, node, child_descriptions)
                futures.append((future, node.id))

            # Harvest results
            for future in as_completed([f[0] for f in futures]):
                try:
                    doc_node = future.result(timeout=30)
                    if doc_node:
                        documentation_nodes.append(doc_node)
                except Exception as e:
                    logger.error(f"Error processing remaining function: {e}")

        # Save batch immediately
        if documentation_nodes:
            self._save_documentation_batch(documentation_nodes)

        return len(batch_results)

    def _process_root_node(self, root_node: NodeWithContentDto) -> int:
        """
        Process the root node and its children.

        Args:
            root_node: The root node DTO to process

        Returns:
            Number of processed nodes
        """
        try:
            # Process the root node
            child_query = get_child_descriptions_query()

            result = self.db_manager.query(
                child_query,
                {
                    "parent_node_id": root_node.id,
                },
            )

            child_descriptions = []
            for desc in result:
                if desc and desc.get("description"):
                    # Create minimal DocumentationNode for child context
                    child_doc = DocumentationNode(
                        content=desc["description"],
                        info_type="child_description",
                        source_path=desc.get("path", ""),
                        source_name=desc.get("name", ""),
                        source_id=desc.get("id", ""),
                        source_labels=desc.get("labels", []),
                        source_type="child",
                        graph_environment=self.graph_environment,
                    )
                    child_descriptions.append(child_doc)

            root_doc = self._process_parent_node(root_node, child_descriptions=child_descriptions)
            if root_doc:
                self._save_documentation_batch([root_doc])
                return 1
            return 0
        except Exception as e:
            logger.error(f"Error processing root node: {e}")
            return 0

    def _save_documentation_batch(self, documentation_nodes: List[DocumentationNode]):
        """Save documentation to database using create_nodes and mark nodes completed."""
        if not documentation_nodes:
            return

        # Generate embeddings if requested
        if self.generate_embeddings and self.embedding_service:
            logger.debug(f"Generating embeddings for {len(documentation_nodes)} documentation nodes")
            embeddings_dict = self.embedding_service.embed_documentation_nodes(documentation_nodes)

            # Update nodes with embeddings
            for node in documentation_nodes:
                if node.id in embeddings_dict:
                    node.content_embedding = embeddings_dict[node.id]

        # Convert DocumentationNode objects to dictionaries for create_nodes
        node_objects = [node.as_object() for node in documentation_nodes]

        # Create DOCUMENTATION nodes and DESCRIBES relationships
        try:
            self.db_manager.create_nodes(node_objects)
        except Exception as e:
            logger.error(f"Error creating nodes: {e}")

        # Create DESCRIBES relationships
        relationships = RelationshipCreator.create_describes_relationships(documentation_nodes)

        # Create relationships
        if relationships:
            self.db_manager.create_edges(relationships)

        # Extract node IDs for marking as completed
        node_ids = [doc_node.source_id for doc_node in documentation_nodes]

        # Mark source nodes as completed
        if node_ids:
            query = mark_nodes_completed_query()
            params = {
                "node_ids": node_ids,
                "run_id": self.processing_run_id,
            }
            result = self.db_manager.query(query, params)
            if result:
                completed_count = result[0].get("completed_count", 0)
                logger.debug(f"Marked {completed_count} nodes as completed")

        logger.debug(f"Saved {len(documentation_nodes)} documentation nodes to database")

    def _has_pending_nodes(self, root_node: NodeWithContentDto) -> bool:
        """Check if there are still pending nodes under the root node."""
        query = check_pending_nodes_query()
        params = {"root_node_id": root_node.id}

        result = self.db_manager.query(query, params)
        if result:
            pending_count = result[0].get("pending_count", 0)
            return pending_count > 0
        return False

    def _process_leaf_node(self, node: NodeWithContentDto) -> Optional[DocumentationNode]:
        """
        Process a leaf node (FUNCTION with no calls or FILE with no children).
        Leaf nodes cannot be part of cycles since they don't make any calls.

        Args:
            node: The node DTO to process

        Returns:
            DocumentationNode with generated description
        """
        try:
            # Use standard leaf template for both functions and files
            # No cycle detection needed - leaf nodes can't be in cycles
            system_prompt, input_prompt = LEAF_NODE_ANALYSIS_TEMPLATE.get_prompts()
            prompt_dict = {
                "node_name": node.name,
                "node_labels": " | ".join(node.labels),
                "node_path": node.path,
                "node_content": node.content or "",
            }

            # Generate description using LLM
            description = self.agent_caller.call_dumb_agent(
                system_prompt=system_prompt, input_dict=prompt_dict, input_prompt=input_prompt
            )

            # Create DocumentationNode
            doc_node = DocumentationNode(
                content=description,
                info_type="leaf_analysis",
                source_type="code",
                source_path=node.path,
                source_name=node.name,
                source_id=node.id,
                source_labels=node.labels,
                graph_environment=self.graph_environment,
            )

            return doc_node

        except Exception as e:
            logger.error(f"Error processing leaf node {node.name}: {e}")
            # Create fallback documentation
            return DocumentationNode(
                content=f"Error processing {node.name}: {str(e)}",
                info_type="error",
                source_type="code",
                source_path=node.path,
                source_name=node.name,
                source_id=node.id,
                source_labels=node.labels,
                metadata={"error": str(e)},
                graph_environment=self.graph_environment,
            )

    def _process_parent_node(
        self, node: NodeWithContentDto, child_descriptions: List[DocumentationNode]
    ) -> Optional[DocumentationNode]:
        """
        Process a parent node with child descriptions.

        Args:
            node: The parent node DTO to process
            child_descriptions: List of child documentation nodes

        Returns:
            DocumentationNode with generated description
        """
        try:
            # Check if it's a function with calls
            is_function_with_calls = "FUNCTION" in node.labels and child_descriptions

            if is_function_with_calls:
                # Use function calls context for functions
                child_calls_context = self._create_function_calls_context(child_descriptions)

                # Always use FUNCTION_WITH_CALLS_ANALYSIS_TEMPLATE (no cycle checking)
                system_prompt, input_prompt = FUNCTION_WITH_CALLS_ANALYSIS_TEMPLATE.get_prompts()
                prompt_dict = {
                    "node_name": node.name,
                    "node_labels": " | ".join(node.labels),
                    "node_path": node.path,
                    "start_line": str(node.start_line) if node.start_line else "Unknown",
                    "end_line": str(node.end_line) if node.end_line else "Unknown",
                    "node_content": node.content or "",
                    "child_calls_context": child_calls_context,
                }
            else:
                # Parent node (class, file, folder)
                system_prompt, input_prompt = PARENT_NODE_ANALYSIS_TEMPLATE.get_prompts()

                # Create enhanced content based on node type
                if "FOLDER" in node.labels:
                    enhanced_content = self._create_child_descriptions_summary(child_descriptions)
                else:
                    # For files and code nodes with actual content, replace skeleton comments
                    enhanced_content = self._replace_skeleton_comments_with_descriptions(
                        node.content, child_descriptions
                    )

                prompt_dict = {
                    "node_name": node.name,
                    "node_labels": " | ".join(node.labels),
                    "node_path": node.path,
                    "node_content": enhanced_content,
                }

            # Generate description using LLM
            description = self.agent_caller.call_dumb_agent(
                system_prompt=system_prompt, input_dict=prompt_dict, input_prompt=input_prompt
            )

            # Create DocumentationNode
            doc_node = DocumentationNode(
                content=description,
                info_type="parent_analysis",
                source_type="code",
                source_path=node.path,
                source_name=node.name,
                source_id=node.id,
                source_labels=node.labels,
                children_count=len(child_descriptions),
                graph_environment=self.graph_environment,
            )

            return doc_node

        except Exception as e:
            logger.error(f"Error processing parent node {node.name}: {e}")
            # Create fallback documentation
            return DocumentationNode(
                content=f"Error processing {node.name}: {str(e)}",
                info_type="error",
                source_type="code",
                source_path=node.path,
                source_name=node.name,
                source_id=node.id,
                source_labels=node.labels,
                metadata={"error": str(e)},
                graph_environment=self.graph_environment,
            )

    def _create_child_descriptions_summary(self, child_descriptions: List[DocumentationNode]) -> str:
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

    def _create_function_calls_context(self, child_descriptions: List[DocumentationNode]) -> str:
        """
        Create formatted context from child function descriptions for call stack analysis.

        Deduplicates functions that are called multiple times to avoid repetition.

        Args:
            child_descriptions: List of descriptions for called/used functions

        Returns:
            Formatted string describing called functions and their purposes
        """
        if not child_descriptions:
            return "This function does not call any other functions or use dependencies."

        # Deduplicate by function name and source path to avoid repeating same function multiple times
        unique_functions = {}

        for desc in child_descriptions:
            # Get function name from source name or path
            function_name = desc.source_name or "Unknown function"
            source_path = desc.source_path or ""

            # Create unique key combining name and path to handle functions with same name in different files
            unique_key = f"{function_name}|{source_path}"

            # Store first occurrence (they should all have same description)
            if unique_key not in unique_functions:
                unique_functions[unique_key] = desc

        context_parts = []

        for desc in unique_functions.values():
            function_name = desc.source_name or "Unknown function"
            context_parts.append(f"- **{function_name}**: {desc.content}")

        return "\nCalled functions and dependencies:\n" + "\n".join(context_parts)

    def _replace_skeleton_comments_with_descriptions(
        self, parent_content: str, child_descriptions: List[DocumentationNode]
    ) -> str:
        """
        Replace skeleton comments with LLM-generated descriptions and add a section
        for child descriptions that don't have corresponding skeleton comments.

        Args:
            parent_content: The parent node's content with skeleton comments
            child_descriptions: List of child descriptions to insert

        Returns:
            Enhanced content with descriptions replacing skeleton comments and an
            additional section listing other important relationships and dependencies
        """
        if not parent_content:
            return ""

        enhanced_content = parent_content

        # Build a mapping of source IDs to descriptions
        child_lookup = {}
        for desc in child_descriptions:
            if desc.source_id:
                child_lookup[desc.source_id] = desc.content

        # Pattern to match skeleton comments
        # Example: # Code replaced for brevity, see node: 6fd101f9571073a44fed7c085c94eec2
        skeleton_pattern = r"# Code replaced for brevity, see node: ([a-f0-9]+)"

        # Track which child descriptions were used in skeleton replacements
        used_child_ids = set()

        def replace_comment(match: re.Match[str]) -> str:
            node_id = match.group(1)
            if node_id in child_lookup:
                used_child_ids.add(node_id)
                description = child_lookup[node_id]
                # Format as a proper docstring
                # Indent the description to match the original comment's indentation
                indent_match = re.search(r"^(\s*)", match.group(0))
                indent = indent_match.group(1) if indent_match else ""
                return f"{indent}# {description}"
            return match.group(0)  # Keep original if no description found

        # Replace all skeleton comments with descriptions
        enhanced_content = re.sub(skeleton_pattern, replace_comment, enhanced_content)

        # Add section for child descriptions that weren't replaced in skeleton comments
        unused_descriptions = []
        for desc in child_descriptions:
            if desc.source_id and desc.source_id not in used_child_ids:
                # Get the name from source_name or extract from source_path
                name = desc.source_name or (desc.source_path.split("/")[-1] if desc.source_path else "Unknown")
                unused_descriptions.append(f"{name}: {desc.content}")

        # Append the additional relationships section if there are unused descriptions
        if unused_descriptions:
            enhanced_content += "\n\n# " + "-" * 60 + "\n"
            enhanced_content += "# Other important relationships and dependencies:\n"
            enhanced_content += "# " + "-" * 60 + "\n"
            for description in unused_descriptions:
                enhanced_content += f"# {description}\n"

        return enhanced_content
