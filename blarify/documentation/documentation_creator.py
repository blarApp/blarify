"""
Documentation Creator for generating comprehensive documentation without LangGraph.

This module provides a clean, method-based approach to documentation generation,
replacing the complex LangGraph orchestration with simple method calls following
ProjectGraphCreator patterns.
"""

import time
import logging
from typing import List, Optional, TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    from blarify.graph.node.documentation_node import DocumentationNode
    from blarify.repositories.graph_db_manager.dtos.node_with_content_dto import NodeWithContentDto

from ..agents.llm_provider import LLMProvider
from ..repositories.graph_db_manager.db_manager import AbstractDbManager
from ..repositories.graph_db_manager.queries import (
    find_all_entry_points,
    find_entry_points_for_node_path,
    get_root_path,
    get_documentation_nodes_for_embedding_query,
    update_documentation_embeddings_query,
    create_vector_index_query,
)
from ..graph.graph_environment import GraphEnvironment
from ..graph.relationship.relationship_creator import RelationshipCreator
from ..services.embedding_service import EmbeddingService
from .utils.bottom_up_batch_processor import BottomUpBatchProcessor
from .result_models import DocumentationResult, FrameworkDetectionResult

logger = logging.getLogger(__name__)


class DocumentationCreator:
    """
    Creates comprehensive documentation using method-based orchestration.

    This class replaces the LangGraph DocumentationWorkflow with a clean,
    simple approach that follows ProjectGraphCreator patterns while preserving
    all the valuable RecursiveDFSProcessor functionality.
    """

    def __init__(
        self,
        db_manager: AbstractDbManager,
        agent_caller: LLMProvider,
        graph_environment: GraphEnvironment,
        max_workers: int = 5,
        overwrite_documentation: bool = False,
    ) -> None:
        """
        Initialize the documentation creator.

        Args:
            db_manager: Database manager for querying nodes and saving results
            agent_caller: LLM provider for generating descriptions
            graph_environment: Graph environment for node ID generation
            company_id: Company/entity ID for database queries
            repo_id: Repository ID for database queries
            max_workers: Maximum number of threads for parallel processing
        """
        self.db_manager = db_manager
        self.agent_caller = agent_caller
        self.graph_environment = graph_environment
        self.max_workers = max_workers
        self.overwrite_documentation = overwrite_documentation

    def create_documentation(
        self,
        target_paths: Optional[List[str]] = None,
        generate_embeddings: bool = False,
    ) -> DocumentationResult:
        """
        Main entry point - creates documentation using simple method orchestration.

        Args:
            target_paths: Optional list of specific paths to nodes (for SWE benchmarks)
            save_to_database: Whether to save results to database
            generate_embeddings: Whether to generate embeddings for documentation nodes

        Returns:
            DocumentationResult with all generated documentation
        """
        start_time = time.time()

        try:
            logger.info("Starting documentation creation")

            # Create documentation based on mode
            if target_paths:
                result = self._create_targeted_documentation(target_paths, generate_embeddings=generate_embeddings)
            else:
                result = self._create_full_documentation(generate_embeddings=generate_embeddings)

            # Add timing and metadata
            result.processing_time_seconds = time.time() - start_time
            result.total_nodes_processed = len(result.information_nodes)

            logger.info(
                f"Documentation creation completed: {result.total_nodes_processed} nodes "
                f"in {result.processing_time_seconds:.2f} seconds"
            )

            return result

        except Exception as e:
            logger.exception(f"Error in documentation creation: {e}")
            return DocumentationResult(
                error=str(e),
                processing_time_seconds=time.time() - start_time,
            )

    def _parse_framework_analysis(self, analysis: str) -> FrameworkDetectionResult:
        """
        Parse the LLM framework analysis into structured data.

        This is a basic implementation - could be enhanced with more sophisticated parsing.
        """
        # Basic parsing logic - extract common framework names
        analysis_lower = analysis.lower()

        primary_framework = None
        technology_stack = []
        confidence = 0.5  # Default confidence

        # Common framework patterns
        frameworks = {
            "django": ["django", "django rest framework", "drf"],
            "react": ["react", "reactjs", "react.js"],
            "angular": ["angular", "angularjs"],
            "vue": ["vue", "vuejs", "vue.js"],
            "next.js": ["next.js", "nextjs", "next"],
            "express": ["express", "expressjs", "express.js"],
            "flask": ["flask"],
            "fastapi": ["fastapi", "fast api"],
            "spring": ["spring", "spring boot", "springframework"],
        }

        for framework, patterns in frameworks.items():
            if any(pattern in analysis_lower for pattern in patterns):
                if not primary_framework:
                    primary_framework = framework
                    confidence = 0.8
                if framework not in technology_stack:
                    technology_stack.append(framework)

        # Extract technology stack items
        technologies = ["python", "javascript", "typescript", "java", "go", "rust", "php", "ruby"]
        for tech in technologies:
            if tech in analysis_lower and tech not in technology_stack:
                technology_stack.append(tech)

        return FrameworkDetectionResult(
            primary_framework=primary_framework,
            technology_stack=technology_stack,
            confidence_score=confidence,
            analysis_method="llm_analysis_basic_parsing",
        )

    def _discover_entry_points(self, node_path: Optional[str] = None) -> List[str]:
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
                # Convert to standard format
                standardized_entry_points = []
                for ep in entry_points:
                    standardized_entry_points.append(ep.get("path", ""))

                logger.info(f"Discovered {len(standardized_entry_points)} targeted entry points")
                return standardized_entry_points
            else:
                logger.info("Discovering entry points using hybrid approach")

                entry_points = find_all_entry_points(db_manager=self.db_manager)

                # Convert to standard format
                standardized_entry_points = []
                for ep in entry_points:
                    standardized_entry_points.append(ep.get("path", ""))

                logger.info(f"Discovered {len(standardized_entry_points)} entry points")
                return standardized_entry_points

        except Exception as e:
            logger.exception(f"Error discovering entry points: {e}")
            return []

    def _create_targeted_documentation(
        self,
        target_paths: List[str],
        generate_embeddings: bool = False,
    ) -> DocumentationResult:
        """
        Create documentation for specific paths - optimized for SWE benchmarks.

        Args:
            target_paths: List of specific paths to document
            framework_info: Framework detection results

        Returns:
            DocumentationResult with targeted documentation
        """
        try:
            logger.info(f"Creating targeted documentation for {len(target_paths)} paths")

            all_information_nodes = []
            all_documentation_nodes = []
            all_source_nodes = []
            analyzed_nodes = []
            warnings = []

            for path in target_paths:
                try:
                    entry_points_paths = self._discover_entry_points(node_path=path)

                    # Use BottomUpBatchProcessor for each target path
                    for entry_point in entry_points_paths:
                        processor = BottomUpBatchProcessor(
                            db_manager=self.db_manager,
                            agent_caller=self.agent_caller,
                            graph_environment=self.graph_environment,
                            max_workers=self.max_workers,
                            overwrite_documentation=self.overwrite_documentation,
                            generate_embeddings=generate_embeddings,
                        )
                        processor_result = processor.process_node(entry_point)

                        if processor_result.error:
                            warnings.append(
                                f"Error processing path {path} entry point {entry_point}: {processor_result.error}"
                            )
                            continue

                        # Collect results
                        all_information_nodes.extend(processor_result.information_nodes)
                        all_documentation_nodes.extend(processor_result.documentation_nodes)
                        all_source_nodes.extend(processor_result.source_nodes)
                        analyzed_nodes.append(
                            {
                                "path": entry_point,
                                "node_count": len(processor_result.information_nodes),
                                "hierarchical_analysis": processor_result.hierarchical_analysis,
                            }
                        )

                        logger.info(f"Processed {path}: {len(processor_result.information_nodes)} nodes")

                except Exception as e:
                    error_msg = f"Error processing path {path}: {str(e)}"
                    logger.exception(error_msg)
                    warnings.append(error_msg)

            logger.info(f"Targeted documentation completed: {len(all_information_nodes)} total nodes")

            return DocumentationResult(
                information_nodes=all_information_nodes,
                documentation_nodes=all_documentation_nodes,
                source_nodes=all_source_nodes,
                analyzed_nodes=analyzed_nodes,
                warnings=warnings,
            )

        except Exception as e:
            logger.exception(f"Error in targeted documentation creation: {e}")
            return DocumentationResult(error=str(e))

    def _create_full_documentation(self, generate_embeddings: bool = False) -> DocumentationResult:
        """
        Create documentation for the entire codebase.

        Args:
            framework_info: Framework detection results

        Returns:
            DocumentationResult with full codebase documentation
        """
        try:
            logger.info("Creating full codebase documentation")

            # Get all root folders and files from database
            root_path = get_root_path(db_manager=self.db_manager)

            if not root_path:
                logger.warning("No root folders and files found")
                return DocumentationResult(warnings=["No root folders and files found for documentation"])

            total_processed = 0

            processor = BottomUpBatchProcessor(
                db_manager=self.db_manager,
                agent_caller=self.agent_caller,
                graph_environment=self.graph_environment,
                max_workers=self.max_workers,
                overwrite_documentation=self.overwrite_documentation,
                generate_embeddings=generate_embeddings,
            )

            result = processor.process_node(root_path)

            if result.error:
                logger.warning(f"Error processing {root_path}: {result.error}")
            else:
                total_processed += result.total_nodes_processed

            logger.info(f"Full documentation completed: {total_processed} nodes processed")

            return DocumentationResult(
                information_nodes=result.information_nodes,
                documentation_nodes=result.documentation_nodes,
                source_nodes=result.source_nodes,
                total_nodes_processed=total_processed,
                analyzed_nodes=[
                    {
                        "type": "full_codebase",
                        "total_nodes": total_processed,
                    }
                ],
            )

        except Exception as e:
            logger.exception(f"Error in full documentation creation: {e}")
            return DocumentationResult(error=str(e))

    def _save_documentation_to_database(
        self, documentation_nodes: List["DocumentationNode"], source_nodes: List["NodeWithContentDto"]
    ) -> None:
        """
        Save documentation nodes to the database and create DESCRIBES relationships using RelationshipCreator.

        Args:
            documentation_nodes: List of actual DocumentationNode objects
            source_nodes: List of actual source code Node objects
        """
        try:
            if not documentation_nodes:
                return

            logger.info(f"Saving {len(documentation_nodes)} documentation nodes to database")

            # Convert DocumentationNode objects to dictionaries for database storage
            information_node_dicts = [node.as_object() for node in documentation_nodes]

            # Batch save nodes
            self.db_manager.create_nodes(information_node_dicts)
            logger.info(f"Saved {len(information_node_dicts)} documentation nodes")

            # Create DESCRIBES relationships using the existing RelationshipCreator method
            describes_relationships = RelationshipCreator.create_describes_relationships(
                documentation_nodes=documentation_nodes
            )

            # Save relationships to database (already as dictionaries)
            if describes_relationships:
                self.db_manager.create_edges(describes_relationships)
                logger.info(f"Created {len(describes_relationships)} DESCRIBES relationships")

            logger.info("Documentation nodes and relationships saved to database successfully")

        except Exception as e:
            logger.exception(f"Error saving documentation to database: {e}")
            # Don't raise - this is not critical for the documentation creation process

    def embed_existing_documentation(self, batch_size: int = 100, skip_existing: bool = True) -> Dict[str, Any]:
        """
        Embed all existing documentation nodes in the database.

        This method queries existing documentation nodes and generates embeddings
        for their content field, then updates the database with the embeddings.

        Args:
            batch_size: Number of nodes to process in each batch
            skip_existing: If True, skip nodes that already have embeddings

        Returns:
            Dictionary with statistics about the embedding process
        """
        # Initialize statistics
        total_processed: int = 0
        total_embedded: int = 0
        total_skipped: int = 0
        errors: List[str] = []

        try:
            logger.info("Starting retroactive embedding of existing documentation")

            # Create vector index if it doesn't exist
            try:
                self.db_manager.query(cypher_query=create_vector_index_query(), parameters={})
                logger.info("Vector index created or already exists")
            except Exception as e:
                logger.warning(f"Could not create vector index (may already exist): {e}")

            # Initialize embedding service
            embedding_service = EmbeddingService(batch_size=batch_size)

            # Track processed nodes to avoid infinite loops
            processed_node_ids = set()

            while True:
                # Query batch of documentation nodes
                query = get_documentation_nodes_for_embedding_query()
                parameters = {
                    "batch_size": batch_size,
                }

                result = self.db_manager.query(cypher_query=query, parameters=parameters)

                if not result:
                    break  # No more nodes to process

                # Convert query results to DocumentationNode objects
                from blarify.graph.node.documentation_node import DocumentationNode

                documentation_nodes: list[DocumentationNode] = []
                node_id_mapping = {}  # Map from node object to actual database node_id
                any_new_nodes = False  # Track if we found any new nodes in this batch

                for record in result:
                    node_id = record.get("node_id", "")

                    # Skip if we've already processed this node in this run
                    if node_id in processed_node_ids:
                        continue

                    # Apply skip_existing logic here in the application layer
                    has_embedding = record.get("content_embedding") is not None

                    if skip_existing and has_embedding:
                        total_skipped += 1
                        processed_node_ids.add(node_id)
                        continue

                    any_new_nodes = True

                    # Create DocumentationNode object
                    # Use the database node_id as source_id to ensure uniqueness
                    node = DocumentationNode(
                        content=record.get("content", ""),
                        info_type=record.get("info_type", ""),
                        source_type=record.get("source_type", ""),
                        source_path=record.get("source_path", ""),
                        source_name=record.get("source_name", ""),  # Include source_name if available
                        source_id=node_id,  # Use the unique database node_id instead of source_id
                        source_labels=record.get("source_labels", []),
                        graph_environment=self.graph_environment,
                    )
                    # Store the actual database node_id for this node
                    node_id_mapping[node] = node_id
                    documentation_nodes.append(node)
                    processed_node_ids.add(node_id)

                if not documentation_nodes:
                    if not any_new_nodes:
                        break  # No new nodes found, we're done
                    else:
                        continue  # All were skipped, try next batch

                # Generate embeddings
                logger.info(f"Generating embeddings for batch of {len(documentation_nodes)} nodes")
                node_embeddings = embedding_service.embed_documentation_nodes(documentation_nodes)

                # Prepare updates for database using actual database node_ids
                updates = []
                for node in documentation_nodes:
                    node_id_for_lookup = node.id  # This is what embed_documentation_nodes uses as key
                    actual_db_node_id = node_id_mapping[node]  # This is the actual database node_id
                    embedding = node_embeddings.get(node_id_for_lookup)
                    if embedding:
                        updates.append({"node_id": actual_db_node_id, "embedding": embedding})
                        total_embedded += 1

                # Update database with embeddings
                if updates:
                    update_query = update_documentation_embeddings_query()
                    update_parameters = {"updates": updates}

                    self.db_manager.query(cypher_query=update_query, parameters=update_parameters)
                    logger.info(f"Updated {len(updates)} nodes with embeddings")

                total_processed += len(documentation_nodes)

                # Break if we processed less than a full batch (no more nodes)
                if len(result) < batch_size:
                    break

            # Return statistics
            stats = {
                "total_processed": total_processed,
                "total_embedded": total_embedded,
                "total_skipped": total_skipped,
                "errors": errors,
                "success": True,
            }

            logger.info(
                f"Embedding complete: processed={total_processed}, embedded={total_embedded}, skipped={total_skipped}"
            )

            return stats

        except Exception as e:
            logger.exception(f"Error in embed_existing_documentation: {e}")
            return {
                "total_processed": total_processed,
                "total_embedded": total_embedded,
                "total_skipped": total_skipped,
                "errors": [str(e)],
                "success": False,
            }
