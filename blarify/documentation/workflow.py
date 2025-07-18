"""
Documentation Generator Workflow for creating comprehensive documentation.

This module provides a LangGraph workflow that generates comprehensive documentation
for LLM agents by analyzing codebase structure and creating structured documentation content.
"""

from operator import add
from typing import Annotated, TypedDict, Dict, Any, Optional
import logging

from langgraph.graph import START, StateGraph

from blarify.agents.prompt_templates.component_analysis import COMPONENT_ANALYSIS_TEMPLATE

from ..agents.llm_provider import LLMProvider
from ..agents.prompt_templates import (
    FRAMEWORK_DETECTION_TEMPLATE,
    SYSTEM_OVERVIEW_TEMPLATE,
    CROSS_COMPONENT_ANALYSIS_TEMPLATE,
    COMPONENT_IDENTIFICATION_TEMPLATE,
    RELATIONSHIP_EXTRACTION_TEMPLATE,
)
from ..db_managers.db_manager import AbstractDbManager
from ..db_managers.queries import get_codebase_skeleton

logger = logging.getLogger(__name__)


class DocumentationState(TypedDict):
    """State management for the documentation generation workflow."""

    generated_docs: Annotated[list, add]
    analyzed_nodes: Annotated[list, add]
    repo_structure: dict
    dependencies: dict
    root_codebase_skeleton: str
    detected_framework: dict
    system_overview: dict
    doc_skeleton: dict
    key_components: list


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
        """Compile the LangGraph workflow."""
        workflow = StateGraph(DocumentationState)

        # Add all workflow nodes
        workflow.add_node("load_codebase", self.__load_codebase)
        workflow.add_node("detect_framework", self.__detect_framework)
        workflow.add_node("generate_overview", self.__generate_overview)
        workflow.add_node("create_doc_skeleton", self.__create_doc_skeleton)
        workflow.add_node("identify_key_components", self.__identify_key_components)
        workflow.add_node("analyze_component", self.__analyze_component)
        workflow.add_node("extract_relationships", self.__extract_relationships)
        workflow.add_node("generate_component_docs", self.__generate_component_docs)
        workflow.add_node("analyze_cross_component", self.__analyze_cross_component)
        workflow.add_node("consolidate_with_skeleton", self.__consolidate_with_skeleton)

        # Add workflow edges
        workflow.add_edge(START, "load_codebase")
        workflow.add_edge("load_codebase", "detect_framework")
        workflow.add_edge("detect_framework", "generate_overview")
        workflow.add_edge("generate_overview", "create_doc_skeleton")
        workflow.add_edge("create_doc_skeleton", "identify_key_components")
        workflow.add_edge("identify_key_components", "analyze_component")
        workflow.add_edge("analyze_component", "extract_relationships")
        workflow.add_edge("extract_relationships", "generate_component_docs")
        workflow.add_edge("generate_component_docs", "analyze_cross_component")
        workflow.add_edge("analyze_cross_component", "consolidate_with_skeleton")

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

    def __create_doc_skeleton(self, state: DocumentationState) -> Dict[str, Any]:
        """Create documentation skeleton structure based on overview."""
        try:
            logger.info("Creating documentation skeleton")

            framework_info = state.get("detected_framework", {})
            system_overview = state.get("system_overview", {})

            # Create documentation skeleton based on framework and overview
            doc_skeleton = {
                "sections": [
                    {
                        "title": "System Overview",
                        "content": system_overview.get("executive_summary", ""),
                        "subsections": ["Business Domain", "Primary Purpose", "Architecture"],
                    },
                    {
                        "title": "Technical Architecture",
                        "content": f"Built with {framework_info.get('framework', {}).get('name', 'unknown framework')}",
                        "subsections": ["Framework Details", "Dependencies", "Structure"],
                    },
                    {
                        "title": "Key Components",
                        "content": "Main components and their responsibilities",
                        "subsections": ["Core Components", "Utilities", "Interfaces"],
                    },
                    {
                        "title": "API Reference",
                        "content": "Detailed API documentation",
                        "subsections": ["Public APIs", "Internal APIs", "Data Models"],
                    },
                ],
                "structure": {
                    "format": "markdown",
                    "sections_order": ["overview", "architecture", "components", "api"],
                    "include_examples": True,
                    "include_diagrams": False,
                },
            }

            logger.info("Successfully created documentation skeleton")
            return {"doc_skeleton": doc_skeleton}

        except Exception as e:
            logger.error(f"Error creating documentation skeleton: {e}")
            return {"doc_skeleton": {"error": str(e)}}

    def __identify_key_components(self, state: DocumentationState) -> Dict[str, Any]:
        """Identify key components to analyze based on framework and overview."""
        try:
            logger.info("Identifying key components")

            skeleton = state.get("root_codebase_skeleton", "")
            framework_info = state.get("detected_framework", {})
            system_overview = state.get("system_overview", {})

            if not skeleton:
                return {"key_components": []}

            # Convert data to safe string format and escape curly braces
            import json

            framework_str = json.dumps(framework_info, indent=2).replace("{", "{{").replace("}", "}}")
            system_overview_str = json.dumps(system_overview, indent=2).replace("{", "{{").replace("}", "}}")

            # Use the new prompt template system
            system_prompt, input_prompt = COMPONENT_IDENTIFICATION_TEMPLATE.get_prompts(
                codebase_structure=skeleton, framework_info=framework_str, system_overview=system_overview_str
            )

            response = self.__agent_caller.call_agent_with_reasoning(
                input_dict={
                    "codebase_structure": skeleton,
                    "framework_info": framework_info,
                    "system_overview": system_overview,
                },
                output_schema=None,
                system_prompt=system_prompt,
                input_prompt=input_prompt,
            )

            # Parse response
            try:
                import json

                response_content = response.content if hasattr(response, "content") else str(response)
                key_components = json.loads(response_content)
                if not isinstance(key_components, list):
                    key_components = []
            except (json.JSONDecodeError, AttributeError):
                key_components = []

            logger.info(f"Identified {len(key_components)} key components")
            return {"key_components": key_components}

        except Exception as e:
            logger.error(f"Error identifying key components: {e}")
            return {"key_components": []}

    def __analyze_component(self, state: DocumentationState) -> Dict[str, Any]:
        """Analyze individual component structure and responsibilities."""
        try:
            logger.info("Analyzing components")

            key_components = state.get("key_components", [])
            skeleton = state.get("root_codebase_skeleton", "")

            analyzed_nodes = []

            for component in key_components:
                try:
                    # Convert component to safe string format
                    import json

                    component_str = json.dumps(component, indent=2).replace("{", "{{").replace("}", "}}")

                    # Use the new prompt template system
                    system_prompt, input_prompt = COMPONENT_ANALYSIS_TEMPLATE.get_prompts(
                        component_code=component_str, context=skeleton
                    )

                    response = self.__agent_caller.call_agent_with_reasoning(
                        input_dict={"component_code": component, "context": skeleton},
                        output_schema=None,
                        system_prompt=system_prompt,
                        input_prompt=input_prompt,
                    )

                    # Parse and store analysis
                    try:
                        import json

                        response_content = response.content if hasattr(response, "content") else str(response)
                        analysis = json.loads(response_content)
                        analyzed_nodes.append({"component": component, "analysis": analysis})
                    except (json.JSONDecodeError, AttributeError):
                        analyzed_nodes.append(
                            {
                                "component": component,
                                "analysis": {"error": "Failed to parse analysis", "raw": str(response)},
                            }
                        )

                except Exception as e:
                    logger.error(f"Error analyzing component {component}: {e}")
                    analyzed_nodes.append({"component": component, "analysis": {"error": str(e)}})

            logger.info(f"Analyzed {len(analyzed_nodes)} components")
            return {"analyzed_nodes": analyzed_nodes}

        except Exception as e:
            logger.error(f"Error analyzing components: {e}")
            return {"analyzed_nodes": []}

    def __extract_relationships(self, state: DocumentationState) -> Dict[str, Any]:
        """Extract relationships and dependencies between components."""
        try:
            logger.info("Extracting relationships")

            analyzed_nodes = state.get("analyzed_nodes", [])
            skeleton = state.get("root_codebase_skeleton", "")

            # Convert data to safe string format and escape curly braces
            import json

            components_list = [node.get("component") for node in analyzed_nodes]
            components_str = json.dumps(components_list, indent=2).replace("{", "{{").replace("}", "}}")
            analyses_str = json.dumps(analyzed_nodes, indent=2).replace("{", "{{").replace("}", "}}")

            # Use the new prompt template system
            system_prompt, input_prompt = RELATIONSHIP_EXTRACTION_TEMPLATE.get_prompts(
                components=components_str, codebase_structure=skeleton, component_analyses=analyses_str
            )

            response = self.__agent_caller.call_agent_with_reasoning(
                input_dict={
                    "components": components_list,
                    "codebase_structure": skeleton,
                    "component_analyses": analyzed_nodes,
                },
                output_schema=None,
                system_prompt=system_prompt,
                input_prompt=input_prompt,
            )

            # Parse response
            try:
                import json

                response_content = response.content if hasattr(response, "content") else str(response)
                dependencies = json.loads(response_content)
            except (json.JSONDecodeError, AttributeError):
                dependencies = {"error": "Failed to parse dependencies", "raw": str(response)}

            logger.info("Successfully extracted relationships")
            return {"dependencies": dependencies}

        except Exception as e:
            logger.error(f"Error extracting relationships: {e}")
            return {"dependencies": {"error": str(e)}}

    def __generate_component_docs(self, state: DocumentationState) -> Dict[str, Any]:
        """Generate detailed documentation for analyzed components."""
        try:
            logger.info("Generating component documentation")

            analyzed_nodes = state.get("analyzed_nodes", [])
            doc_skeleton = state.get("doc_skeleton", {})
            dependencies = state.get("dependencies", {})

            generated_docs = []

            for node in analyzed_nodes:
                try:
                    component = node.get("component", {})
                    analysis = node.get("analysis", {})

                    # Create documentation for this component
                    prompt = f"""
                    Generate comprehensive documentation for this component:
                    
                    Component: {component}
                    Analysis: {analysis}
                    Dependencies: {dependencies}
                    
                    Following this structure: {doc_skeleton}
                    
                    Create detailed documentation including:
                    - Overview and purpose
                    - Key features and capabilities
                    - Usage examples
                    - API reference
                    - Integration points
                    - Best practices
                    
                    Return well-structured markdown documentation.
                    """

                    response = self.__agent_caller.call_agent_with_reasoning(
                        input_dict={"prompt": prompt},
                        output_schema=None,
                        system_prompt="You are a technical documentation expert. Create comprehensive, clear documentation.",
                        input_prompt=prompt,
                    )

                    response_content = response.content if hasattr(response, "content") else str(response)

                    generated_docs.append(
                        {"component": component, "documentation": response_content, "type": "component_doc"}
                    )

                except Exception as e:
                    logger.error(f"Error generating documentation for component {component}: {e}")
                    generated_docs.append(
                        {
                            "component": component,
                            "documentation": f"Error generating documentation: {str(e)}",
                            "type": "error",
                        }
                    )

            logger.info(f"Generated documentation for {len(generated_docs)} components")
            return {"generated_docs": generated_docs}

        except Exception as e:
            logger.error(f"Error generating component documentation: {e}")
            return {"generated_docs": []}

    def __analyze_cross_component(self, state: DocumentationState) -> Dict[str, Any]:
        """Analyze patterns and interactions across components."""
        try:
            logger.info("Analyzing cross-component patterns")

            analyzed_nodes = state.get("analyzed_nodes", [])
            dependencies = state.get("dependencies", {})
            system_overview = state.get("system_overview", {})

            # Convert data to safe string format to avoid JSON curly brace issues
            import json

            try:
                system_overview_str = json.dumps(system_overview, indent=2)
                analyzed_nodes_str = json.dumps(analyzed_nodes, indent=2)
                dependencies_str = json.dumps(dependencies, indent=2)

                # Escape curly braces to prevent LangChain from interpreting them as template variables
                system_overview_str = system_overview_str.replace("{", "{{").replace("}", "}}")
                analyzed_nodes_str = analyzed_nodes_str.replace("{", "{{").replace("}", "}}")
                dependencies_str = dependencies_str.replace("{", "{{").replace("}", "}}")
            except (TypeError, ValueError):
                # Fallback to string representation if JSON serialization fails
                system_overview_str = str(system_overview).replace("{", "{{").replace("}", "}}")
                analyzed_nodes_str = str(analyzed_nodes).replace("{", "{{").replace("}", "}}")
                dependencies_str = str(dependencies).replace("{", "{{").replace("}", "}}")

            # Use the new prompt template system
            system_prompt, input_prompt = CROSS_COMPONENT_ANALYSIS_TEMPLATE.get_prompts(
                system_overview=system_overview_str, analyzed_nodes=analyzed_nodes_str, dependencies=dependencies_str
            )

            response = self.__agent_caller.call_agent_with_reasoning(
                input_dict={
                    "system_overview": system_overview,
                    "analyzed_nodes": analyzed_nodes,
                    "dependencies": dependencies,
                },
                output_schema=None,
                system_prompt=system_prompt,
                input_prompt=input_prompt,
            )

            # Parse response
            try:
                import json

                response_content = response.content if hasattr(response, "content") else str(response)
                repo_structure = json.loads(response_content)
            except (json.JSONDecodeError, AttributeError):
                repo_structure = {"error": "Failed to parse cross-component analysis", "raw": str(response)}

            logger.info("Successfully analyzed cross-component patterns")
            return {"repo_structure": repo_structure}

        except Exception as e:
            logger.error(f"Error analyzing cross-component patterns: {e}")
            return {"repo_structure": {"error": str(e)}}

    def __consolidate_with_skeleton(self, state: DocumentationState) -> Dict[str, Any]:
        """Consolidate all documentation using the skeleton structure."""
        try:
            logger.info("Consolidating documentation with skeleton")

            generated_docs = state.get("generated_docs", [])
            doc_skeleton = state.get("doc_skeleton", {})
            repo_structure = state.get("repo_structure", {})
            system_overview = state.get("system_overview", {})

            # Create final consolidated documentation
            prompt = f"""
            Consolidate all documentation into a final comprehensive guide:
            
            Documentation Structure: {doc_skeleton}
            Component Documentation: {generated_docs}
            System Patterns: {repo_structure}
            System Overview: {system_overview}
            
            Create a final, well-organized documentation that:
            - Follows the skeleton structure
            - Integrates all component documentation
            - Includes system-wide patterns
            - Provides clear navigation
            - Is optimized for LLM agent consumption
            
            Return the final consolidated documentation.
            """

            response = self.__agent_caller.call_agent_with_reasoning(
                input_dict={"prompt": prompt},
                output_schema=None,
                system_prompt="You are a documentation expert. Create final, comprehensive documentation.",
                input_prompt=prompt,
            )

            response_content = response.content if hasattr(response, "content") else str(response)

            # Add the consolidated documentation to the generated docs
            final_doc = {
                "type": "consolidated_documentation",
                "title": "Complete System Documentation",
                "content": response_content,
                "timestamp": "2024-01-01",  # This would be actual timestamp
                "sections": doc_skeleton.get("sections", []),
            }

            logger.info("Successfully consolidated documentation")
            return {"generated_docs": [final_doc]}

        except Exception as e:
            logger.error(f"Error consolidating documentation: {e}")
            return {"generated_docs": [{"type": "error", "content": f"Error consolidating documentation: {str(e)}"}]}

    def run(self) -> dict:
        """Execute the complete documentation generation workflow."""
        try:
            logger.info("Starting documentation generation workflow")

            # Ensure graph is compiled
            if not self.__compiled_graph:
                self.compile_graph()

            # Initialize state
            initial_state = DocumentationState(
                generated_docs=[],
                analyzed_nodes=[],
                repo_structure={},
                dependencies={},
                root_codebase_skeleton="",
                detected_framework={},
                system_overview={},
                doc_skeleton={},
                key_components=[],
            )

            # Execute workflow
            response = self.__compiled_graph.invoke(initial_state)

            logger.info("Documentation generation workflow completed successfully")
            return response

        except Exception as e:
            logger.error(f"Error running documentation workflow: {e}")
            return {
                "generated_docs": [{"type": "error", "content": f"Workflow execution failed: {str(e)}"}],
                "error": str(e),
            }
