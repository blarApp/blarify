"""
Documentation Creator for generating comprehensive documentation without LangGraph.

This module provides a clean, method-based approach to documentation generation,
replacing the complex LangGraph orchestration with simple method calls following
ProjectGraphCreator patterns.
"""

import time
import logging
from typing import List, Dict, Any, Optional

from ..agents.llm_provider import LLMProvider
from ..agents.prompt_templates import FRAMEWORK_DETECTION_TEMPLATE
from ..db_managers.db_manager import AbstractDbManager
from ..db_managers.queries import get_codebase_skeleton, get_root_folders_and_files
from ..graph.graph_environment import GraphEnvironment
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
        include_framework_detection: bool = True,
        save_to_database: bool = True,
    ) -> DocumentationResult:
        """
        Main entry point - creates documentation using simple method orchestration.
        
        Args:
            target_paths: Optional list of specific paths to document (for SWE benchmarks)
            include_framework_detection: Whether to run framework detection
            save_to_database: Whether to save results to database
            
        Returns:
            DocumentationResult with all generated documentation
        """
        start_time = time.time()
        
        try:
            logger.info("Starting documentation creation")
            
            # Step 1: Load codebase structure
            codebase_info = self._load_codebase()
            if codebase_info.get("error"):
                return DocumentationResult(error=codebase_info["error"])
            
            # Step 2: Detect framework (optional)
            framework_info = {}
            if include_framework_detection:
                framework_detection = self._detect_framework(codebase_info)
                if framework_detection.error:
                    logger.warning(f"Framework detection failed: {framework_detection.error}")
                else:
                    framework_info = framework_detection.model_dump()
            
            # Step 3: Create documentation based on mode
            if target_paths:
                result = self._create_targeted_documentation(target_paths, framework_info)
            else:
                result = self._create_full_documentation(framework_info)
            
            # Step 4: Save to database if requested
            if save_to_database and result.information_nodes:
                self._save_documentation_to_database(result.information_nodes)
            
            # Add timing and metadata
            result.processing_time_seconds = time.time() - start_time
            result.detected_framework = framework_info
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
    
    def _load_codebase(self) -> Dict[str, Any]:
        """Load the root codebase skeleton from the AST code graph."""
        try:
            logger.info(f"Loading codebase skeleton for company_id: {self.company_id}")
            
            root_skeleton = get_codebase_skeleton(
                db_manager=self.db_manager,
                entity_id=self.company_id,
                repo_id=self.repo_id
            )
            
            logger.info(f"Successfully loaded codebase skeleton ({len(root_skeleton)} characters)")
            return {"root_codebase_skeleton": root_skeleton}
            
        except Exception as e:
            logger.exception(f"Error loading codebase: {e}")
            return {"error": f"Error loading codebase: {str(e)}"}
    
    def _detect_framework(self, codebase_info: Dict[str, Any]) -> FrameworkDetectionResult:
        """
        Detect the primary framework and technology stack.
        
        Args:
            codebase_info: Information about the codebase structure
            
        Returns:
            FrameworkDetectionResult with framework information
        """
        try:
            logger.info("Detecting framework and technology stack")
            
            codebase_structure = codebase_info.get("root_codebase_skeleton", "")
            if not codebase_structure:
                return FrameworkDetectionResult(
                    error="No codebase structure available for framework detection"
                )
            
            # Get framework detection prompts
            system_prompt, input_prompt = FRAMEWORK_DETECTION_TEMPLATE.get_prompts()
            
            # Initialize code reader tool for config file analysis
            tools = None
            try:
                from ..agents.tools import GetCodeByIdTool
                code_reader = GetCodeByIdTool(self.db_manager, self.company_id)
                tools = [code_reader]
                logger.debug("GetCodeByIdTool initialized for framework detection")
            except Exception as e:
                logger.warning(f"Could not initialize GetCodeByIdTool: {e}. Running without tools.")
            
            # Use ReactAgent for framework detection
            response = self.agent_caller.call_react_agent(
                system_prompt=system_prompt,
                tools=tools,
                input_dict={"codebase_structure": codebase_structure},
                input_prompt=input_prompt,
            )
            
            # Extract response content
            raw_analysis = response.content if hasattr(response, "content") else str(response)
            
            # Parse the framework information (basic parsing - could be enhanced)
            framework_result = self._parse_framework_analysis(raw_analysis)
            framework_result.raw_analysis = raw_analysis
            
            logger.info("Framework detection completed")
            return framework_result
            
        except Exception as e:
            logger.exception(f"Error detecting framework: {e}")
            return FrameworkDetectionResult(error=str(e))
    
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
    
    def _create_targeted_documentation(
        self, target_paths: List[str], framework_info: Dict[str, Any]
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
            analyzed_nodes = []
            warnings = []
            
            for path in target_paths:
                try:
                    # Use RecursiveDFSProcessor for each target path
                    processor_result = self.recursive_processor.process_node(path)
                    
                    if processor_result.error:
                        warnings.append(f"Error processing {path}: {processor_result.error}")
                        continue
                    
                    # Collect results
                    all_information_nodes.extend(processor_result.information_nodes)
                    analyzed_nodes.append({
                        "path": path,
                        "node_count": len(processor_result.information_nodes),
                        "hierarchical_analysis": processor_result.hierarchical_analysis,
                    })
                    
                    logger.info(f"Processed {path}: {len(processor_result.information_nodes)} nodes")
                    
                except Exception as e:
                    error_msg = f"Error processing path {path}: {str(e)}"
                    logger.exception(error_msg)
                    warnings.append(error_msg)
            
            logger.info(f"Targeted documentation completed: {len(all_information_nodes)} total nodes")
            
            return DocumentationResult(
                information_nodes=all_information_nodes,
                analyzed_nodes=analyzed_nodes,
                warnings=warnings,
            )
            
        except Exception as e:
            logger.exception(f"Error in targeted documentation creation: {e}")
            return DocumentationResult(error=str(e))
    
    def _create_full_documentation(self, framework_info: Dict[str, Any]) -> DocumentationResult:
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
                return DocumentationResult(
                    warnings=["No root folders and files found for documentation"]
                )
            
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
            
            # Get all information nodes from parallel processing
            all_information_nodes = workflow_result.information_nodes or []
            
            logger.info(
                f"Full documentation completed: {len(all_information_nodes)} nodes "
                f"from {len(root_paths)} root paths"
            )
            
            return DocumentationResult(
                information_nodes=all_information_nodes,
                analyzed_nodes=[{
                    "type": "full_codebase",
                    "root_paths_count": len(root_paths),
                    "total_nodes": len(all_information_nodes),
                }],
            )
            
        except Exception as e:
            logger.exception(f"Error in full documentation creation: {e}")
            return DocumentationResult(error=str(e))
    
    def _save_documentation_to_database(self, information_nodes: List[Dict[str, Any]]) -> None:
        """
        Save documentation nodes to the database.
        
        Args:
            information_nodes: List of DocumentationNode objects as dictionaries
        """
        try:
            if not information_nodes:
                return
            
            logger.info(f"Saving {len(information_nodes)} documentation nodes to database")
            
            # Use batch processing for better performance
            batch_size = 100
            for i in range(0, len(information_nodes), batch_size):
                batch = information_nodes[i:i + batch_size]
                self.db_manager.create_nodes(batch)
                logger.debug(f"Saved batch {i//batch_size + 1}: {len(batch)} nodes")
            
            logger.info("Documentation nodes saved to database successfully")
            
        except Exception as e:
            logger.exception(f"Error saving documentation to database: {e}")
            # Don't raise - this is not critical for the documentation creation process