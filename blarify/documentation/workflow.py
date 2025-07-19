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
from ..db_managers.db_manager import AbstractDbManager
from ..db_managers.queries import get_codebase_skeleton

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
        workflow.add_node("identify_main_folders_by_framework", self.__identify_main_folders_by_framework)
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
        workflow.add_edge("detect_framework", "identify_main_folders_by_framework")
        workflow.add_edge("analyze_all_leaf_nodes", "identify_main_folders_by_framework")
        workflow.add_edge("identify_main_folders_by_framework", "iterate_directory_hierarchy_bottoms_up")
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
        """Detect the primary framework and technology stack using LLM provider with strategic analysis."""
        try:
            logger.info("Detecting framework and technology stack with LLM provider")

            # Get the codebase structure from the state (loaded in previous node)
            codebase_structure = state.get("root_codebase_skeleton", "")

            if not codebase_structure:
                return {"detected_framework": {"error": "No codebase structure available"}}

            # Use the updated prompt template that provides text output with strategic insights
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

            # Use custom ReactAgent for strategic framework detection
            response = self.__agent_caller.call_react_agent(
                system_prompt=system_prompt,
                tools=tools,
                input_dict={"codebase_structure": codebase_structure},
                messages=[("human", input_prompt)],
                output_schema=None,
            )

            # Extract the response content from custom ReactAgent
            if isinstance(response, dict) and "messages" in response:
                final_message = response["messages"][-1]
                response_content = final_message.content if hasattr(final_message, "content") else str(final_message)
            else:
                response_content = response.content if hasattr(response, "content") else str(response)
            logger.info("LLM framework detection completed successfully")

            # Return the LLM response directly as the framework detection result
            return {"detected_framework": response_content}

        except Exception as e:
            logger.error(f"Error detecting framework: {e}")
            return {"detected_framework": {"error": str(e)}}

    def __analyze_all_leaf_nodes(self, state: DocumentationState) -> Dict[str, Any]:
        """Use dumb agent to create initial descriptions for ALL leaf nodes (functions, classes)."""
        raise NotImplementedError("analyze_all_leaf_nodes node needs to be implemented")
        
    def __identify_main_folders_by_framework(self, state: DocumentationState) -> Dict[str, Any]:
        """Use framework info to identify main folders to analyze (e.g., models/, views/, components/)."""
        raise NotImplementedError("identify_main_folders_by_framework node needs to be implemented")
        
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
