"""
Integration tests for documentation creation functionality.

These tests verify that the documentation layer can successfully create
documentation nodes for various types of source code, including files
with direct code (no functions or classes).
"""

import pytest
from pathlib import Path
from typing import Any, Dict, Optional, List

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.graph.graph import Graph
from blarify.db_managers.neo4j_manager import Neo4jManager
from blarify.documentation.documentation_creator import DocumentationCreator
from blarify.agents.llm_provider import LLMProvider
from neo4j_container_manager.types import Neo4jContainerInstance
from tests.utils.graph_assertions import GraphAssertions
from pydantic import BaseModel
from langchain_core.tools import BaseTool


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestDocumentationCreation:
    """Test documentation creation functionality with various code structures."""

    async def test_documentation_for_file_with_direct_code(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """
        Test that documentation can be created for files with direct code (no functions/classes).
        This tests the specific case of files like Django's urls.py that have only
        variable assignments and direct code execution.
        """
        # Use the Python examples directory that contains urls_example.py
        python_examples_path = test_code_examples_path / "python"

        # Step 1: Create GraphBuilder and build the code graph
        builder = GraphBuilder(
            root_path=str(python_examples_path),
            extensions_to_skip=[".pyc", ".pyo"],
            names_to_skip=["__pycache__"],
        )

        graph = builder.build()
        assert isinstance(graph, Graph)
        assert graph is not None

        # Step 2: Save graph to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
            entity_id="test-entity",
            repo_id="test-repo",
        )

        # Save the code graph
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Debug: Print graph summary to see what's in the database
        await graph_assertions.debug_print_graph_summary()

        # Verify the urls_example.py file node exists
        await graph_assertions.assert_node_exists("FILE", {"name": "urls_example.py"})

        # Step 3: Create documentation using DocumentationCreator
        # Create a mock LLM provider for testing
        class MockLLMProvider(LLMProvider):
            def call_dumb_agent(
                self,
                system_prompt: str,  # noqa: ARG002
                input_dict: Dict[str, Any],  # noqa: ARG002
                output_schema: Optional[BaseModel] = None,  # noqa: ARG002
                ai_model: Optional[str] = None,  # noqa: ARG002
                input_prompt: Optional[str] = "Start",  # noqa: ARG002
                config: Optional[Dict[str, Any]] = None,  # noqa: ARG002
                timeout: Optional[int] = None,  # noqa: ARG002
            ) -> Any:
                """Mock LLM response for testing."""
                # Return a meaningful description that will trigger processing
                return "This is a Django URL configuration file that defines URL patterns for the application. It contains direct variable assignments for urlpatterns, app_name, and configuration settings."

            def call_react_agent(
                self,
                system_prompt: str,  # noqa: ARG002
                tools: List[BaseTool],  # noqa: ARG002
                input_dict: Dict[str, Any],  # noqa: ARG002
                input_prompt: Optional[str],  # noqa: ARG002
                output_schema: Optional[BaseModel] = None,  # noqa: ARG002
                main_model: Optional[str] = "gpt-4.1",  # noqa: ARG002
            ) -> Any:
                """Mock React agent response."""
                return {"framework": "Django", "main_folders": [str(python_examples_path)]}

        llm_provider = MockLLMProvider()

        # Create DocumentationCreator
        # Use the same GraphEnvironment that GraphBuilder created
        doc_creator = DocumentationCreator(
            db_manager=db_manager,
            agent_caller=llm_provider,
            graph_environment=builder.graph_environment,
            company_id="test-entity",
            repo_id="test-repo",
        )

        # Don't specify target_paths so it processes all files in the graph
        result = doc_creator.create_documentation(save_to_database=True)

        # Verify documentation was created successfully
        assert result is not None
        assert result.error is None, f"Documentation creation failed: {result.error}"

        doc_nodes = await graph_assertions.neo4j_instance.execute_cypher(
            "MATCH (d:DOCUMENTATION) RETURN d.content as content, d.name as name"
        )
        print(f"Found {len(doc_nodes)} documentation nodes in database")
        for node in doc_nodes:
            print(f"Documentation node: {node['name'][:50]}... - Content: {node['content'][:100]}...")

        # Check if our mock description is in any of the nodes
        mock_description_found = any("Django URL configuration" in node.get("content", "") for node in doc_nodes)
        assert mock_description_found, "Mock description not found in documentation nodes"

        # Clean up
        db_manager.close()
