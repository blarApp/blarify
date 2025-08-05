"""
Documentation Creator for generating comprehensive documentation without LangGraph.

This module provides a clean, method-based approach to documentation generation,
replacing the complex LangGraph orchestration with simple method calls following
ProjectGraphCreator patterns.
"""

import time
import logging
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from blarify.graph.node import Node
    from blarify.graph.node.documentation_node import DocumentationNode

from ..agents.llm_provider import LLMProvider
from ..db_managers.db_manager import AbstractDbManager
from ..db_managers.queries import find_all_entry_points, find_entry_points_for_node_path, get_root_folders_and_files
from ..graph.graph_environment import GraphEnvironment
from ..graph.relationship.relationship_creator import RelationshipCreator
from .utils.recursive_dfs_processor import RecursiveDFSProcessor
from .root_file_folder_processing_workflow import RooFileFolderProcessingWorkflow
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
        company_id: str,
        repo_id: str,
        max_workers: int = 75,
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
        self.company_id = company_id
        self.repo_id = repo_id
        self.max_workers = max_workers

        # Initialize the recursive processor (the valuable component we're preserving)
        self.recursive_processor = RecursiveDFSProcessor(
            db_manager=db_manager,
            agent_caller=agent_caller,
            company_id=company_id,
            repo_id=repo_id,
            graph_environment=graph_environment,
            max_workers=max_workers,
        )

    def create_documentation(
        self,
        target_paths: Optional[List[str]] = None,
        save_to_database: bool = True,
    ) -> DocumentationResult:
        """
        Main entry point - creates documentation using simple method orchestration.

        Args:
            target_paths: Optional list of specific paths to nodes (for SWE benchmarks)
            include_framework_detection: Whether to run framework detection
            save_to_database: Whether to save results to database

        Returns:
            DocumentationResult with all generated documentation
        """
        start_time = time.time()

        try:
            logger.info("Starting documentation creation")

            # Create documentation based on mode
            if target_paths:
                result = self._create_targeted_documentation(target_paths)
            else:
                result = self._create_full_documentation()

            # Step 4: Save to database if requested
            if save_to_database and result.documentation_nodes:
                self._save_documentation_to_database(result.documentation_nodes, result.source_nodes)

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
                entry_points = find_entry_points_for_node_path(
                    db_manager=self.db_manager, entity_id=self.company_id, repo_id=self.repo_id, node_path=node_path
                )
                # Convert to standard format
                standardized_entry_points = []
                for ep in entry_points:
                    standardized_entry_points.append(ep.get("path", ""))

                logger.info(f"Discovered {len(standardized_entry_points)} targeted entry points")
                return standardized_entry_points
            else:
                logger.info("Discovering entry points using hybrid approach")

                entry_points = find_all_entry_points(
                    db_manager=self.db_manager, entity_id=self.company_id, repo_id=self.repo_id
                )

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

                    # Use RecursiveDFSProcessor for each target path
                    for entry_point in entry_points_paths:
                        processor_result = self.recursive_processor.process_node(entry_point)

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

    def _create_full_documentation(self) -> DocumentationResult:
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
            root_paths = get_root_folders_and_files(
                db_manager=self.db_manager,
                entity_id=self.company_id,
                repo_id=self.repo_id,
            )

            if not root_paths:
                logger.warning("No root folders and files found")
                return DocumentationResult(warnings=["No root folders and files found for documentation"])

            # Use the existing RooFileFolderProcessingWorkflow for parallel processing
            # This preserves the existing functionality while removing LangGraph
            parallel_workflow = RooFileFolderProcessingWorkflow(
                db_manager=self.db_manager,
                agent_caller=self.agent_caller,
                company_id=self.company_id,
                repo_id=self.repo_id,
                root_paths=root_paths,
                graph_environment=self.graph_environment,
            )

            # Run the parallel workflow
            workflow_result = parallel_workflow.run()

            if workflow_result.error:
                logger.exception(f"Error in parallel root processing workflow: {workflow_result.error}")
                return DocumentationResult(error=workflow_result.error)

            # Get all nodes from parallel processing
            all_information_nodes = workflow_result.information_nodes or []
            all_documentation_nodes = workflow_result.documentation_nodes or []
            all_source_nodes = workflow_result.source_nodes or []

            logger.info(
                f"Full documentation completed: {len(all_information_nodes)} nodes from {len(root_paths)} root paths"
            )

            return DocumentationResult(
                information_nodes=all_information_nodes,
                documentation_nodes=all_documentation_nodes,
                source_nodes=all_source_nodes,
                analyzed_nodes=[
                    {
                        "type": "full_codebase",
                        "root_paths_count": len(root_paths),
                        "total_nodes": len(all_information_nodes),
                    }
                ],
            )

        except Exception as e:
            logger.exception(f"Error in full documentation creation: {e}")
            return DocumentationResult(error=str(e))

    def _save_documentation_to_database(
        self, documentation_nodes: List["DocumentationNode"], source_nodes: List["Node"]
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
                documentation_nodes=documentation_nodes, source_nodes=source_nodes
            )

            # Save relationships to database (already as dictionaries)
            if describes_relationships:
                self.db_manager.create_edges(describes_relationships)
                logger.info(f"Created {len(describes_relationships)} DESCRIBES relationships")

            logger.info("Documentation nodes and relationships saved to database successfully")

        except Exception as e:
            logger.exception(f"Error saving documentation to database: {e}")
            # Don't raise - this is not critical for the documentation creation process
