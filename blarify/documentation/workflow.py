"""
Documentation Generator Workflow for creating comprehensive documentation.

This module provides a LangGraph workflow that generates comprehensive documentation
for LLM agents by analyzing codebase structure and creating structured documentation content.
"""

from operator import add
from typing import Annotated, TypedDict, Dict, Any, Optional
import logging

from langgraph.graph import START, StateGraph

from ..agents.llm_provider import LLMProvider
from ..agents.prompt_templates import (
    FRAMEWORK_DETECTION_TEMPLATE,
    SYSTEM_OVERVIEW_TEMPLATE,
)
from ..agents.prompt_templates.leaf_node_analysis import LEAF_NODE_ANALYSIS_TEMPLATE
from ..agents.schemas import FrameworkAnalysisResponse
from ..db_managers.db_manager import AbstractDbManager
from ..db_managers.queries import get_codebase_skeleton, get_all_leaf_nodes

logger = logging.getLogger(__name__)


class DocumentationState(TypedDict):
    """State management for the documentation generation workflow."""

    # Fine-grained InformationNode data (for graph database)
    information_nodes: Annotated[list, add]        # Atomic InformationNode objects
    semantic_relationships: Annotated[list, add]   # Relationships between nodes
    code_references: Annotated[list, add]          # Precise code location mappings
    
    # Comprehensive markdown data (for file system)
    markdown_sections: Annotated[list, add]        # Narrative markdown content
    markdown_groupings: dict                       # Logical groupings for .md files
    markdown_files: dict                           # Final .md file contents
    
    # Shared analysis data
    analyzed_nodes: Annotated[list, add]           # Analyzed code components
    repo_structure: dict                           # Repository structure info
    dependencies: dict                             # Component relationships
    root_codebase_skeleton: str                   # AST tree structure
    detected_framework: dict                       # Framework info (Django, Next.js, etc.)
    system_overview: dict                          # Business context & purpose
    doc_skeleton: dict                             # Documentation template
    key_components: list                           # Priority components to analyze
    
    # New fields for bottoms-up approach
    leaf_node_descriptions: Annotated[list, add]   # Initial descriptions of all leaf nodes
    main_folders: list                             # Framework-identified main folders to analyze


class DocumentationWorkflow:
    """
    Agentic workflow for generating comprehensive documentation for LLM agents.
    Analyzes a particular branch using the AST code graph to understand codebase structure.
    """

    __company_id: str
    __company_graph_manager: AbstractDbManager
    __repo_id: str
    __agent_caller: LLMProvider
    __agent_type: str
    __compiled_graph: Optional[Any]

    def __init__(
        self,
        company_id: str,
        company_graph_manager: AbstractDbManager,
        repo_id: str,
        agent_caller: Optional[LLMProvider] = None,
    ) -> None:
        self.__company_id = company_id
        self.__company_graph_manager = company_graph_manager
        self.__repo_id = repo_id
        self.__agent_caller = agent_caller if agent_caller else LLMProvider()
        self.__agent_type = "documentation_generator"
        self.__compiled_graph = None

    def compile_graph(self):
        """Compile the LangGraph workflow with new framework-guided bottoms-up approach."""
        workflow = StateGraph(DocumentationState)

        # Add workflow nodes for the new bottoms-up approach
        workflow.add_node("load_codebase", self.__load_codebase)
        workflow.add_node("detect_framework", self.__detect_framework)
        workflow.add_node("analyze_all_leaf_nodes", self.__analyze_all_leaf_nodes)
        workflow.add_node("iterate_directory_hierarchy_bottoms_up", self.__iterate_directory_hierarchy_bottoms_up)
        workflow.add_node("group_related_knowledge", self.__group_related_knowledge)
        workflow.add_node("compact_to_markdown_per_folder", self.__compact_to_markdown_per_folder)
        workflow.add_node("consolidate_final_markdown", self.__consolidate_final_markdown)

        # Add workflow edges for the new structure
        # Parallel execution: load_codebase and analyze_all_leaf_nodes can run in parallel
        workflow.add_edge(START, "load_codebase")
        workflow.add_edge(START, "analyze_all_leaf_nodes")
        
        # Sequential execution after parallel completion
        workflow.add_edge("load_codebase", "detect_framework")
        workflow.add_edge("detect_framework", "iterate_directory_hierarchy_bottoms_up")
        workflow.add_edge("analyze_all_leaf_nodes", "iterate_directory_hierarchy_bottoms_up")
        workflow.add_edge("iterate_directory_hierarchy_bottoms_up", "group_related_knowledge")
        workflow.add_edge("group_related_knowledge", "compact_to_markdown_per_folder")
        workflow.add_edge("compact_to_markdown_per_folder", "consolidate_final_markdown")

        self.__compiled_graph = workflow.compile()

    def __load_codebase(self, state: DocumentationState) -> Dict[str, Any]:
        """Load the root codebase skeleton from the AST code graph."""
        try:
            logger.info(f"Loading codebase skeleton for company_id: {self.__company_id}")

            root_skeleton = get_codebase_skeleton(
                db_manager=self.__company_graph_manager, entity_id=self.__company_id, repo_id=self.__repo_id
            )

            logger.info(f"Successfully loaded codebase skeleton ({len(root_skeleton)} characters)")
            return {"root_codebase_skeleton": root_skeleton}

        except Exception as e:
            logger.error(f"Error loading codebase: {e}")
            return {"root_codebase_skeleton": f"Error loading codebase: {str(e)}"}

    def __detect_framework(self, state: DocumentationState) -> Dict[str, Any]:
        """Detect the primary framework, technology stack, and identify main architectural folders using structured output."""
        try:
            logger.info("Detecting framework and main folders with structured output")

            # Get the codebase structure from the state (loaded in previous node)
            codebase_structure = state.get("root_codebase_skeleton", "")

            if not codebase_structure:
                logger.error("No codebase structure available - stopping workflow")
                raise ValueError("No codebase structure available")

            # Use the updated prompt template for combined framework detection and main folder identification
            system_prompt, input_prompt = FRAMEWORK_DETECTION_TEMPLATE.get_prompts(
                codebase_structure=codebase_structure
            )

            # Initialize only GetCodeByIdTool for config file reading
            tools = None
            try:
                from ..agents.tools import GetCodeByIdTool

                # Create code reader tool instance
                code_reader = GetCodeByIdTool(self.__company_graph_manager, self.__company_id)

                # Only provide the code reader tool
                tools = [code_reader]

                logger.info("GetCodeByIdTool initialized for config file reading")
            except Exception as e:
                logger.warning(f"Could not initialize GetCodeByIdTool: {e}. Running without tools.")
                tools = None

            # Use ReactAgent with structured output for framework detection and main folder identification
            response = self.__agent_caller.call_react_agent(
                system_prompt=system_prompt,
                tools=tools,
                input_dict={"codebase_structure": codebase_structure},
                messages=[("human", input_prompt)],
                output_schema=FrameworkAnalysisResponse,
            )

            # Extract structured response
            if hasattr(response, 'framework') and hasattr(response, 'main_folders'):
                # Direct structured output
                framework_analysis = response.framework
                main_folders = response.main_folders
            elif isinstance(response, dict) and "framework" in response and "main_folders" in response:
                # Dictionary response
                framework_analysis = response["framework"]
                main_folders = response["main_folders"]
            else:
                # Fallback: try to parse response content
                logger.warning("Unexpected response format, attempting to parse...")
                response_content = response.content if hasattr(response, "content") else str(response)
                
                # Parse JSON response manually if structured output failed
                import json
                try:
                    parsed_response = json.loads(response_content)
                    framework_analysis = parsed_response.get("framework", response_content)
                    main_folders = parsed_response.get("main_folders", [])
                except (json.JSONDecodeError, AttributeError):
                    logger.error("Failed to parse framework detection response - stopping workflow")
                    raise ValueError(f"Invalid framework detection response format: {response_content}")

            logger.info(f"Framework detection completed: {len(main_folders)} main folders identified")

            # Return both framework analysis and main folders
            return {
                "detected_framework": framework_analysis,
                "main_folders": main_folders
            }

        except Exception as e:
            logger.error(f"Error detecting framework: {e}")
            raise  # Re-raise exception to stop workflow

    def __analyze_all_leaf_nodes(self, state: DocumentationState) -> Dict[str, Any]:
        """Use dumb agent to create initial descriptions for ALL leaf nodes (functions, classes)."""
        try:
            logger.info("Starting analysis of all leaf nodes")

            # Get all leaf nodes from the database
            leaf_nodes = get_all_leaf_nodes(
                db_manager=self.__company_graph_manager,
                entity_id=self.__company_id,
                repo_id=self.__repo_id
            )

            if not leaf_nodes:
                logger.warning("No leaf nodes found in the codebase")
                return {"leaf_node_descriptions": []}

            logger.info(f"Found {len(leaf_nodes)} leaf nodes to analyze")

            # Process leaf nodes in batches for efficiency
            batch_size = 10  # Process 10 nodes at a time
            leaf_descriptions = []

            for i in range(0, len(leaf_nodes), batch_size):
                batch = leaf_nodes[i:i + batch_size]
                batch_results = self._process_leaf_node_batch(batch, i // batch_size + 1, (len(leaf_nodes) + batch_size - 1) // batch_size)
                leaf_descriptions.extend(batch_results)

            logger.info(f"Successfully analyzed {len(leaf_descriptions)} leaf nodes")
            return {"leaf_node_descriptions": leaf_descriptions}

        except Exception as e:
            logger.error(f"Error analyzing leaf nodes: {e}")
            return {"leaf_node_descriptions": []}

    def _process_leaf_node_batch(self, batch: list, batch_num: int, total_batches: int) -> list:
        """Process a batch of leaf nodes using the dumb agent."""
        batch_results = []

        logger.info(f"Processing batch {batch_num}/{total_batches} with {len(batch)} nodes")

        for node in batch:
            try:
                # Create the analysis prompt
                system_prompt, input_prompt = LEAF_NODE_ANALYSIS_TEMPLATE.get_prompts(
                    node_name=node.name,
                    node_labels=" | ".join(node.labels) if node.labels else "UNKNOWN",
                    node_path=node.path,
                    node_content=node.content[:2000] if node.content else "No content available"  # Limit content size
                )

                # Use call_dumb_agent for simple, fast processing
                response = self.__agent_caller.call_dumb_agent(
                    system_prompt=system_prompt,
                    input_dict={
                        "node_name": node.name,
                        "node_labels": " | ".join(node.labels) if node.labels else "UNKNOWN",
                        "node_path": node.path,
                        "node_content": node.content[:2000] if node.content else "No content available"
                    },
                    output_schema=None,
                    input_prompt=input_prompt
                )

                # Extract response content
                response_content = response.content if hasattr(response, "content") else str(response)

                # Create InformationNode description
                info_node_description = {
                    "node_id": f"info_{node.id}",
                    "title": f"Description of {node.name}",
                    "content": response_content,
                    "info_type": "node_description",
                    "source_node_id": node.id,
                    "source_path": node.path,
                    "source_labels": node.labels,
                    "source_type": "leaf_analysis",
                    "layer": "documentation"
                }

                batch_results.append(info_node_description)
                logger.debug(f"Successfully analyzed node: {node.name} ({node.id})")

            except Exception as e:
                logger.error(f"Error analyzing leaf node {node.name} ({node.id}): {e}")
                # Create a fallback description
                fallback_description = {
                    "node_id": f"info_{node.id}",
                    "title": f"Description of {node.name}",
                    "content": f"Error analyzing this {' | '.join(node.labels) if node.labels else 'code element'}: {str(e)}",
                    "info_type": "node_description",
                    "source_node_id": node.id,
                    "source_path": node.path,
                    "source_labels": node.labels,
                    "source_type": "error_fallback",
                    "layer": "documentation"
                }
                batch_results.append(fallback_description)

        return batch_results
        
    def __iterate_directory_hierarchy_bottoms_up(self, state: DocumentationState) -> Dict[str, Any]:
        """Per-folder hierarchical analysis from leaves up, grouping related knowledge."""
        raise NotImplementedError("iterate_directory_hierarchy_bottoms_up node needs to be implemented")
        
    def __group_related_knowledge(self, state: DocumentationState) -> Dict[str, Any]:
        """Group related InformationNodes within each folder hierarchy."""
        raise NotImplementedError("group_related_knowledge node needs to be implemented")
        
    def __compact_to_markdown_per_folder(self, state: DocumentationState) -> Dict[str, Any]:
        """Generate markdown sections for each main folder."""
        raise NotImplementedError("compact_to_markdown_per_folder node needs to be implemented")
        
    def __consolidate_final_markdown(self, state: DocumentationState) -> Dict[str, Any]:
        """Combine all folder-based markdown into comprehensive documentation."""
        raise NotImplementedError("consolidate_final_markdown node needs to be implemented")

    def __generate_overview(self, state: DocumentationState) -> Dict[str, Any]:
        """Generate comprehensive system overview with business context."""
        try:
            logger.info("Generating system overview")

            skeleton = state.get("root_codebase_skeleton", "")
            framework_info = state.get("detected_framework", {})

            if not skeleton:
                return {"system_overview": {"error": "No codebase skeleton available"}}

            # Convert framework info to string for prompt and escape curly braces
            import json

            framework_str = json.dumps(framework_info, indent=2)
            # Escape curly braces to prevent LangChain from interpreting them as template variables
            framework_str = framework_str.replace("{", "{{").replace("}", "}}")

            # Generate system overview prompt
            system_prompt, input_prompt = SYSTEM_OVERVIEW_TEMPLATE.get_prompts(
                codebase_skeleton=skeleton, framework_info=framework_str
            )

            # Get LLM response
            response = self.__agent_caller.call_agent_with_reasoning(
                input_dict={"codebase_skeleton": skeleton, "framework_info": framework_str},
                output_schema=None,
                system_prompt=system_prompt,
                input_prompt=input_prompt,
            )

            # Parse response
            try:
                response_content = response.content if hasattr(response, "content") else str(response)
                system_overview = json.loads(response_content)
            except (json.JSONDecodeError, AttributeError):
                response_content = response.content if hasattr(response, "content") else str(response)
                system_overview = {
                    "executive_summary": "Failed to parse structured response",
                    "business_domain": "unknown",
                    "primary_purpose": "unknown",
                    "raw_response": response_content,
                }

            logger.info("Successfully generated system overview")
            return {"system_overview": system_overview}

        except Exception as e:
            logger.error(f"Error generating overview: {e}")
            return {"system_overview": {"error": str(e)}}

    # Deprecated nodes - these were replaced by the bottoms-up approach
    def __create_doc_skeleton(self, state: DocumentationState) -> Dict[str, Any]:
        """DEPRECATED: Replaced by bottoms-up approach."""
        raise NotImplementedError("create_doc_skeleton is deprecated - replaced by bottoms-up markdown generation")

    def __identify_key_components(self, state: DocumentationState) -> Dict[str, Any]:
        """DEPRECATED: Replaced by bottoms-up approach."""
        raise NotImplementedError("identify_key_components is deprecated - replaced by bottoms-up analysis")

    def __analyze_component(self, state: DocumentationState) -> Dict[str, Any]:
        """DEPRECATED: Replaced by bottoms-up approach."""
        raise NotImplementedError("analyze_component is deprecated - replaced by bottoms-up leaf analysis")

    def __extract_relationships(self, state: DocumentationState) -> Dict[str, Any]:
        """DEPRECATED: Replaced by bottoms-up approach."""
        raise NotImplementedError("extract_relationships is deprecated - replaced by bottoms-up knowledge grouping")

    def __generate_component_docs(self, state: DocumentationState) -> Dict[str, Any]:
        """DEPRECATED: Replaced by bottoms-up approach."""
        raise NotImplementedError("generate_component_docs is deprecated - replaced by per-folder markdown generation")

    def __analyze_cross_component(self, state: DocumentationState) -> Dict[str, Any]:
        """DEPRECATED: Replaced by bottoms-up approach."""
        raise NotImplementedError("analyze_cross_component is deprecated - replaced by knowledge grouping")

    def __consolidate_with_skeleton(self, state: DocumentationState) -> Dict[str, Any]:
        """DEPRECATED: Replaced by bottoms-up approach."""
        raise NotImplementedError("consolidate_with_skeleton is deprecated - replaced by final markdown consolidation")

    def run(self) -> dict:
        """Execute the complete documentation generation workflow."""
        try:
            logger.info("Starting documentation generation workflow")

            # Ensure graph is compiled
            if not self.__compiled_graph:
                self.compile_graph()

            # Initialize state with new dual-format fields
            initial_state = DocumentationState(
                # Fine-grained InformationNode data
                information_nodes=[],
                semantic_relationships=[],
                code_references=[],
                
                # Comprehensive markdown data
                markdown_sections=[],
                markdown_groupings={},
                markdown_files={},
                
                # Shared analysis data
                analyzed_nodes=[],
                repo_structure={},
                dependencies={},
                root_codebase_skeleton="",
                detected_framework={},
                system_overview={},
                doc_skeleton={},
                key_components=[],
                
                # New fields for bottoms-up approach
                leaf_node_descriptions=[],
                main_folders=[],
            )

            # Execute workflow
            response = self.__compiled_graph.invoke(initial_state)

            logger.info("Documentation generation workflow completed successfully")
            return response

        except Exception as e:
            logger.error(f"Error running documentation workflow: {e}")
            return {
                "markdown_files": {"error": f"Workflow execution failed: {str(e)}"},
                "information_nodes": [],
                "error": str(e),
            }
