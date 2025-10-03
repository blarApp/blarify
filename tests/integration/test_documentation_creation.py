"""
Integration tests for documentation creation functionality.

These tests verify that the documentation layer can successfully create
documentation nodes for various types of source code, including files
with direct code (no functions or classes).
"""

import pytest
from pathlib import Path
from typing import Any, Dict, Optional, List, Callable, Union, Type
from unittest.mock import Mock

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.graph.graph import Graph
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.documentation.documentation_creator import DocumentationCreator
from blarify.agents.llm_provider import LLMProvider
from tests.utils.graph_assertions import GraphAssertions
from pydantic import BaseModel


def make_llm_mock(
    dumb_response: Union[str, Callable[[Dict[str, Any]], str]],
) -> Mock:
    """Create a Mock that only mocks LLMProvider.call_dumb_agent.

    - call_dumb_agent returns the provided static string or the result of the callable with input_dict.
    """
    m = Mock(spec=LLMProvider)

    if callable(dumb_response):

        def _side_effect(
            system_prompt: str,
            input_dict: Dict[str, Any],
            output_schema: Optional[Type[BaseModel]] = None,
            ai_model: Optional[str] = None,
            input_prompt: str = "Start",
            config: Optional[Dict[str, Any]] = None,
            timeout: Optional[int] = None,
        ) -> Any:
            return dumb_response(input_dict)

        m.call_dumb_agent.side_effect = _side_effect
    else:
        m.call_dumb_agent.return_value = dumb_response

    return m


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestDocumentationCreation:
    """Test documentation creation functionality with various code structures."""

    async def test_documentation_for_file_with_direct_code(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
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
            uri=test_data_isolation["uri"],
            user="neo4j",
            password="test-password",
            entity_id=test_data_isolation["entity_id"],
            repo_id=test_data_isolation["repo_id"],
        )

        # Save the code graph
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Debug: Print graph summary to see what's in the database
        await graph_assertions.debug_print_graph_summary()

        # Verify the urls_example.py file node exists
        await graph_assertions.assert_node_exists("FILE", {"name": "urls_example.py"})

        # Step 3: Create documentation using DocumentationCreator
        # Create a mock LLM provider for testing
        llm_provider = make_llm_mock(
            dumb_response=(
                "This is a Django URL configuration file that defines URL patterns for the application. "
                "It contains direct variable assignments for urlpatterns, app_name, and configuration settings."
            )
        )

        # Create DocumentationCreator
        # Use the same GraphEnvironment that GraphBuilder created
        doc_creator = DocumentationCreator(
            db_manager=db_manager,
            agent_caller=llm_provider,
            graph_environment=builder.graph_environment,
        )

        # Don't specify target_paths so it processes all files in the graph
        result = doc_creator.create_documentation()

        # Verify documentation was created successfully
        assert result is not None
        assert result.error is None, f"Documentation creation failed: {result.error}"

        doc_nodes = await test_data_isolation["container"].execute_cypher(
            "MATCH (d:DOCUMENTATION) RETURN d.content as content, d.name as name"
        )

        # Check if our mock description is in any of the nodes
        mock_description_found = any("Django URL configuration" in node.get("content", "") for node in doc_nodes)
        assert mock_description_found, "Mock description not found in documentation nodes"

        # Clean up
        db_manager.close()

    async def test_documentation_for_duplicate_named_nodes(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """
        Test that nodes with the same name each get their own DESCRIBED documentation node.

        This test verifies that:
        - Two files named 'utils.py' in different modules each get separate documentation
        - Two functions named 'helper' in different modules each get separate documentation
        - Two classes named 'Config' in different modules each get separate documentation
        - No documentation node describes multiple source nodes (critical bug test)
        """
        # Use the duplicate_names examples from test_code_examples_path
        duplicate_names_path = test_code_examples_path / "duplicate_names"
        assert duplicate_names_path.exists(), f"Path {duplicate_names_path} does not exist"

        # Step 1: Create GraphBuilder and build the code graph
        builder = GraphBuilder(
            root_path=str(duplicate_names_path),
            extensions_to_skip=[".pyc", ".pyo"],
            names_to_skip=["__pycache__"],
        )

        graph = builder.build()
        assert isinstance(graph, Graph)
        assert graph is not None

        # Step 2: Save graph to Neo4j
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password="test-password",
            entity_id=test_data_isolation["entity_id"],
            repo_id=test_data_isolation["repo_id"],
        )

        # Save the code graph
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Debug: Print graph summary
        print("\n=== Initial Graph Summary ===")
        await graph_assertions.debug_print_graph_summary()

        # Verify duplicate named nodes exist
        utils_files = await test_data_isolation["container"].execute_cypher(
            "MATCH (f:FILE {name: 'utils.py'}) RETURN f.path as path, f.id as id ORDER BY f.path"
        )
        assert len(utils_files) == 2, f"Expected 2 utils.py files, found {len(utils_files)}"
        print(f"\nFound {len(utils_files)} utils.py files")

        helper_functions = await test_data_isolation["container"].execute_cypher(
            "MATCH (f:FUNCTION {name: 'helper'}) RETURN f.path as path, f.id as id ORDER BY f.path"
        )
        assert len(helper_functions) == 2, f"Expected 2 helper functions, found {len(helper_functions)}"
        print(f"Found {len(helper_functions)} helper functions")

        config_classes = await test_data_isolation["container"].execute_cypher(
            "MATCH (c:CLASS {name: 'Config'}) RETURN c.path as path, c.id as id ORDER BY c.path"
        )
        assert len(config_classes) == 2, f"Expected 2 Config classes, found {len(config_classes)}"
        print(f"Found {len(config_classes)} Config classes")

        # Step 3: Create documentation using DocumentationCreator with mock LLM
        def path_specific_desc(input_dict: Dict[str, Any]) -> str:
            path = input_dict.get("node_path", "")
            if "module1" in path:
                return f"Module1 documentation for: {path}"
            elif "module2" in path:
                return f"Module2 documentation for: {path}"
            else:
                return f"Generic documentation for: {path}"

        llm_provider = make_llm_mock(
            dumb_response=path_specific_desc,
        )

        # Create DocumentationCreator
        doc_creator = DocumentationCreator(
            db_manager=db_manager,
            agent_caller=llm_provider,
            graph_environment=builder.graph_environment,
        )

        # Generate documentation for all files
        result = doc_creator.create_documentation()

        # Verify documentation was created successfully
        assert result is not None
        assert result.error is None, f"Documentation creation failed: {result.error}"
        print(f"\nDocumentation created: {result.total_nodes_processed} nodes processed")

        # Step 4: CRITICAL TEST - Verify no documentation node describes multiple source nodes
        print("\n=== Checking for Shared Documentation Nodes (BUG TEST) ===")
        shared_doc_query = """
        MATCH (d:DOCUMENTATION)-[:DESCRIBES]->(n)
        WITH d, collect(DISTINCT n) as described_nodes
        WHERE size(described_nodes) > 1
        RETURN d.id as doc_id,
               d.source_name as source_name,
               size(described_nodes) as node_count,
               [n in described_nodes | n.name + ' at ' + n.path] as described_nodes
        """
        shared_docs = await test_data_isolation["container"].execute_cypher(shared_doc_query)

        # This assertion will fail if the bug exists
        assert len(shared_docs) == 0, (
            f"BUG: Found {len(shared_docs)} documentation nodes describing multiple source nodes. "
            f"Each source node should have its own unique documentation node. "
            f"The issue appears to be that nodes with the same name (e.g., 'utils.py', 'helper', 'Config') "
            f"are all connected to ONE documentation node instead of having their own."
        )

        # Additional verification: check each type of duplicate-named node
        print("\n=== Detailed Analysis ===")

        # Check utils.py files
        utils_analysis = await test_data_isolation["container"].execute_cypher("""
            MATCH (f:FILE {name: 'utils.py'})
            OPTIONAL MATCH (d:DOCUMENTATION)-[:DESCRIBES]->(f)
            RETURN f.path as path, count(DISTINCT d) as doc_count, collect(DISTINCT d.id) as doc_ids
            ORDER BY f.path
        """)
        print("\nUtils.py files:")
        for item in utils_analysis:
            print(f"  {item['path']}: {item['doc_count']} documentation node(s)")

        # Check helper functions
        helper_analysis = await test_data_isolation["container"].execute_cypher("""
            MATCH (f:FUNCTION {name: 'helper'})
            OPTIONAL MATCH (d:DOCUMENTATION)-[:DESCRIBES]->(f)
            RETURN f.path as path, count(DISTINCT d) as doc_count, collect(DISTINCT d.id) as doc_ids
            ORDER BY f.path
        """)
        print("\nHelper functions:")
        for item in helper_analysis:
            print(f"  {item['path']}: {item['doc_count']} documentation node(s)")

        # Check Config classes
        config_analysis = await test_data_isolation["container"].execute_cypher("""
            MATCH (c:CLASS {name: 'Config'})
            OPTIONAL MATCH (d:DOCUMENTATION)-[:DESCRIBES]->(c)
            RETURN c.path as path, count(DISTINCT d) as doc_count, collect(DISTINCT d.id) as doc_ids
            ORDER BY c.path
        """)
        print("\nConfig classes:")
        for item in config_analysis:
            print(f"  {item['path']}: {item['doc_count']} documentation node(s)")

        # Clean up
        db_manager.close()

    async def test_documentation_with_generate_embeddings_stores_on_neo4j(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """
        Test that when generate_embeddings is True in create_documentation,
        the embeddings are stored on neo4j documentation nodes.
        """
        # Use the Python examples directory
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
            uri=test_data_isolation["uri"],
            user="neo4j",
            password="test-password",
            entity_id=test_data_isolation["entity_id"],
            repo_id=test_data_isolation["repo_id"],
        )

        # Save the code graph
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Step 3: Create documentation with embeddings enabled
        # Mock LLM provider that returns meaningful documentation
        llm_provider = make_llm_mock(
            dumb_response="This is a test documentation content for embedding generation.",
        )

        # Mock the embedding service to return fake embeddings
        from unittest.mock import patch

        # Mock embed_batch method directly
        def mock_embed_batch(texts: List[str]) -> List[List[float]]:
            # Return unique embeddings for each text
            return [[0.1 + i * 0.01] * 1536 for i in range(len(texts))]

        with patch(
            "blarify.services.embedding_service.EmbeddingService.embed_batch", side_effect=mock_embed_batch
        ) as mock_embed:
            # Create DocumentationCreator
            doc_creator = DocumentationCreator(
                db_manager=db_manager,
                agent_caller=llm_provider,
                graph_environment=builder.graph_environment,
            )

            # Create documentation with embeddings enabled
            result = doc_creator.create_documentation(
                generate_embeddings=True,  # Enable embedding generation
            )

            # Verify documentation was created successfully
            assert result is not None
            assert result.error is None, f"Documentation creation failed: {result.error}"

            # Verify embed_batch was called
            assert mock_embed.called, "EmbeddingService.embed_batch should have been called"

        # Step 4: Verify embeddings are stored in Neo4j
        doc_nodes_with_embeddings = await test_data_isolation["container"].execute_cypher(
            """
            MATCH (d:DOCUMENTATION)
            WHERE d.content_embedding IS NOT NULL
            RETURN d.id as id,
                   d.name as name,
                   size(d.content_embedding) as embedding_size
            """
        )

        # Assert that embeddings were stored
        assert len(doc_nodes_with_embeddings) > 0, "No documentation nodes with embeddings found in Neo4j"

        # Verify embedding dimensions (should be 1536 for text-embedding-ada-002)
        for node in doc_nodes_with_embeddings:
            assert node["embedding_size"] == 1536, (
                f"Expected embedding size 1536, got {node['embedding_size']} for node {node['id']}"
            )

        # Clean up
        db_manager.close()

    async def test_embed_existing_documentation_adds_embeddings_to_nodes(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """
        Test that when you already have DOCUMENTATION nodes and you run
        embed_existing_documentation, it adds the content_embedding to the nodes on neo4j.
        """
        # Use the Python examples directory
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
            uri=test_data_isolation["uri"],
            user="neo4j",
            password="test-password",
            entity_id=test_data_isolation["entity_id"],
            repo_id=test_data_isolation["repo_id"],
        )

        code_nodes = graph.get_nodes_as_objects()
        relationships = graph.get_relationships_as_objects()
        code_nodes_amount = len(code_nodes)

        # Save the code graph
        db_manager.save_graph(code_nodes, relationships)

        # Step 3: Create documentation WITHOUT embeddings first
        # Mock LLM provider
        llm_provider = make_llm_mock(
            dumb_response="This is documentation content that will later receive embeddings.",
        )

        # Create DocumentationCreator
        doc_creator = DocumentationCreator(
            db_manager=db_manager,
            agent_caller=llm_provider,
            graph_environment=builder.graph_environment,
        )

        # Create documentation WITHOUT embeddings
        result = doc_creator.create_documentation(
            generate_embeddings=False,  # No embeddings initially
        )

        # Verify documentation was created successfully
        assert result is not None
        assert result.error is None, f"Documentation creation failed: {result.error}"

        # Verify no embeddings exist yet
        nodes_without_embeddings = await test_data_isolation["container"].execute_cypher(
            """
            MATCH (d:DOCUMENTATION)
            WHERE d.content_embedding IS NULL
            RETURN count(d) as count
            """
        )

        nodes_without_documentation = await test_data_isolation["container"].execute_cypher(
            """
            MATCH (n:NODE)
            WHERE NOT (n:DOCUMENTATION)
                AND NOT (:DOCUMENTATION)-[:DESCRIBES]->(n)
            RETURN count(n) AS count
            """
        )

        initial_nodes_without_embeddings = nodes_without_embeddings[0]["count"]
        assert initial_nodes_without_embeddings > 0, "Should have documentation nodes without embeddings initially"
        assert nodes_without_documentation[0]["count"] == 0, "All code nodes should have documentation nodes"
        assert initial_nodes_without_embeddings == code_nodes_amount, (
            "Expected documentation nodes to match code nodes amount"
        )

        # Step 4: Now run embed_existing_documentation to add embeddings
        from unittest.mock import patch

        # Mock only the embed_batch method, not the entire EmbeddingService class
        def mock_embed_batch(texts: List[str]) -> List[List[float]]:
            # Return unique embeddings for each text
            return [[0.1 + i * 0.01] * 1536 for i in range(len(texts))]

        with patch(
            "blarify.services.embedding_service.EmbeddingService.embed_batch", side_effect=mock_embed_batch
        ) as mock_embed:
            # Run embed_existing_documentation
            embed_result = doc_creator.embed_existing_documentation()

            # Verify the method completed successfully
            assert embed_result is not None
            assert embed_result["total_processed"] == 32
            assert embed_result["total_embedded"] == 32
            assert embed_result["total_skipped"] == 0

            # Verify embed_batch was called
            assert mock_embed.called, "EmbeddingService.embed_batch should have been called"

        # Step 5: Verify embeddings were added to existing nodes
        nodes_with_embeddings = await test_data_isolation["container"].execute_cypher(
            """
            MATCH (d:DOCUMENTATION)
            WHERE d.content_embedding IS NOT NULL
            RETURN count(d) as count,
                   collect(DISTINCT size(d.content_embedding))[0] as embedding_size
            """
        )

        if nodes_with_embeddings:
            embedded_count = nodes_with_embeddings[0]["count"]
            embedding_size = nodes_with_embeddings[0]["embedding_size"]

            assert embedded_count > 0, "No documentation nodes with embeddings found after embed_existing_documentation"

            assert embedding_size == 1536, f"Expected embedding size 1536, got {embedding_size}"

        # Clean up
        db_manager.close()

    async def test_parent_nodes_aggregate_child_documentation(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """
        Test that parent nodes properly aggregate documentation from their children.

        This test verifies that:
        - Folder nodes receive summaries of their file children
        - File nodes receive descriptions of their classes and functions
        - Class nodes receive descriptions of their methods
        - The _create_child_descriptions_summary method is called with correct parameters
        """
        # Use the Python examples directory which has rich hierarchy
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
            uri=test_data_isolation["uri"],
            user="neo4j",
            password="test-password",
            entity_id=test_data_isolation["entity_id"],
            repo_id=test_data_isolation["repo_id"],
        )

        # Save the code graph
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Step 3: Create mock LLM provider with hierarchy-aware responses
        def hierarchy_aware_response(input_dict: Dict[str, Any]) -> str:
            """Return unique, traceable descriptions based on node type and name."""
            node_name = input_dict.get("node_name", "")
            node_path = input_dict.get("node_path", "")
            node_labels = input_dict.get("node_labels", "")

            # Return specific descriptions for known nodes
            if "BaseProcessor" == node_name:
                return "Abstract base class for all processors with template method pattern"
            elif "TextProcessor" == node_name and "CLASS" in node_labels:
                return "Concrete text processor implementation with prefix support"
            elif "AdvancedTextProcessor" == node_name:
                return "Advanced processor extending TextProcessor with suffix support"
            elif "create_processor" == node_name:
                return "Factory function for creating processor instances"
            elif "example_usage" in node_name:
                return "Example demonstrating processor usage"
            elif "process" in node_name and "FUNCTION" in node_labels:
                if "batch" in node_name:
                    return "Method for batch processing multiple items"
                else:
                    return "Core method for processing single data items"
            elif "get_name" in node_name:
                return "Method to retrieve processor name"
            elif "__init__" in node_name:
                return f"Constructor for {node_path.split('/')[-1].split('.')[0]}"
            elif "class_with_inheritance.py" in node_path:
                return "Python module demonstrating class inheritance patterns"
            elif "simple_module.py" in node_path:
                return "Simple Python module with basic functionality"
            elif "imports_example.py" in node_path:
                return "Module showing various import patterns"
            elif "urls_example.py" in node_path:
                return "Django-style URL configuration module"
            elif "FOLDER" in node_labels:
                return f"Directory containing Python modules at {node_path}"
            else:
                return f"Generic documentation for {node_name} at {node_path}"

        llm_provider = make_llm_mock(dumb_response=hierarchy_aware_response)

        # Step 4: Spy on key methods to verify they're called correctly
        from unittest.mock import patch
        from blarify.documentation.utils.bottom_up_batch_processor import BottomUpBatchProcessor

        # Store original methods
        original_summary = BottomUpBatchProcessor._create_child_descriptions_summary  # type: ignore[attr-defined]
        original_replace = BottomUpBatchProcessor._replace_skeleton_comments_with_descriptions  # type: ignore[attr-defined]

        summary_calls_capture: List[Dict[str, Any]] = []
        replace_calls_capture: List[Dict[str, Any]] = []

        def capture_summary_call(self: Any, child_descriptions: List[Any]) -> str:
            """Wrapper to capture calls while still executing the method."""
            summary_calls_capture.append(
                {
                    "child_descriptions": child_descriptions,
                    "child_names": [d.source_name for d in child_descriptions],
                    "child_paths": [d.source_path for d in child_descriptions],
                    "child_contents": [d.content for d in child_descriptions],
                }
            )
            return original_summary(self, child_descriptions)

        def capture_replace_call(self: Any, parent_content: str, child_descriptions: List[Any]) -> str:
            """Wrapper to capture calls while still executing the method."""
            replace_calls_capture.append(
                {
                    "parent_content_snippet": parent_content[:100] if parent_content else None,
                    "child_descriptions": child_descriptions,
                    "child_names": [d.source_name for d in child_descriptions],
                    "child_contents": [d.content for d in child_descriptions],
                }
            )
            return original_replace(self, parent_content, child_descriptions)

        # Patch the methods
        with patch.object(BottomUpBatchProcessor, "_create_child_descriptions_summary", capture_summary_call):
            with patch.object(
                BottomUpBatchProcessor, "_replace_skeleton_comments_with_descriptions", capture_replace_call
            ):
                # Create DocumentationCreator
                doc_creator = DocumentationCreator(
                    db_manager=db_manager,
                    agent_caller=llm_provider,
                    graph_environment=builder.graph_environment,
                )

                # Generate documentation
                result = doc_creator.create_documentation()

                # Verify documentation was created successfully
                assert result is not None
                assert result.error is None, f"Documentation creation failed: {result.error}"

        # Step 5: Verify _create_child_descriptions_summary was called for folders
        # Should have at least one folder call (the python folder)
        assert len(summary_calls_capture) > 0, "Should have called _create_child_descriptions_summary for folder nodes"

        # Find the python folder call
        python_folder_calls = [
            call
            for call in summary_calls_capture
            if any("class_with_inheritance.py" in name for name in call["child_names"])
        ]

        assert len(python_folder_calls) > 0, "Should have processed the python folder"

        # Verify the content of the python folder call
        python_folder_call = python_folder_calls[0]

        # Check that all expected files are present as children
        expected_files = ["class_with_inheritance.py", "simple_module.py", "imports_example.py", "urls_example.py"]
        for expected_file in expected_files:
            assert expected_file in python_folder_call["child_names"], f"Missing {expected_file} in folder children"

        # Verify the descriptions match our mock responses
        for idx, child_name in enumerate(python_folder_call["child_names"]):
            child_content = python_folder_call["child_contents"][idx]
            if "class_with_inheritance.py" in child_name:
                assert "inheritance patterns" in child_content, f"Wrong content for {child_name}"
            elif "simple_module.py" in child_name:
                assert "basic functionality" in child_content, f"Wrong content for {child_name}"
            elif "imports_example.py" in child_name:
                assert "import patterns" in child_content, f"Wrong content for {child_name}"
            elif "urls_example.py" in child_name:
                assert "Django" in child_content or "URL configuration" in child_content, (
                    f"Wrong content for {child_name}"
                )

        # Step 6: Verify _replace_skeleton_comments_with_descriptions for files
        # Find calls for class_with_inheritance.py
        class_file_calls = [
            call
            for call in replace_calls_capture
            if "BaseProcessor" in call["child_names"] and "TextProcessor" in call["child_names"]
        ]

        assert len(class_file_calls) > 0, "Should have processed class_with_inheritance.py file"

        class_file_call = class_file_calls[0]

        # Verify all classes and functions are present
        expected_entities = [
            "BaseProcessor",
            "TextProcessor",
            "AdvancedTextProcessor",
            "create_processor",
            "example_usage",
        ]
        for entity in expected_entities:
            assert entity in class_file_call["child_names"], f"Missing {entity} in file children"

        # Verify specific content
        for idx, child_name in enumerate(class_file_call["child_names"]):
            child_content = class_file_call["child_contents"][idx]
            if child_name == "BaseProcessor":
                assert "Abstract base class" in child_content and "template method" in child_content
            elif child_name == "TextProcessor":
                assert "Concrete text processor" in child_content and "prefix" in child_content
            elif child_name == "AdvancedTextProcessor":
                assert "Advanced processor" in child_content and "suffix" in child_content
            elif child_name == "create_processor":
                assert "Factory function" in child_content
            elif child_name == "example_usage":
                assert "Example demonstrating" in child_content

        # Step 7: Verify class documentation includes methods
        # Find calls for TextProcessor class
        text_processor_calls = [
            call
            for call in replace_calls_capture
            if "process" in call["child_names"] and "batch_process" in call["child_names"]
        ]

        assert len(text_processor_calls) > 0, "Should have processed TextProcessor class with its methods"

        text_processor_call = text_processor_calls[0]

        # Verify methods are included
        expected_methods = ["__init__", "process", "batch_process"]
        for method in expected_methods:
            assert method in text_processor_call["child_names"], f"Missing {method} in TextProcessor methods"

        # Verify method descriptions
        for idx, child_name in enumerate(text_processor_call["child_names"]):
            child_content = text_processor_call["child_contents"][idx]
            if child_name == "process":
                assert "processing single data" in child_content
            elif child_name == "batch_process":
                assert "batch processing multiple" in child_content
            elif child_name == "__init__":
                assert "Constructor" in child_content

        # Step 8: Query database to verify final documentation structure
        # Check folder documentation
        folder_docs = await test_data_isolation["container"].execute_cypher("""
            MATCH (f:FOLDER)
            OPTIONAL MATCH (d:DOCUMENTATION)-[:DESCRIBES]->(f)
            RETURN f.name as name, d.content as content, d.children_count as children_count
        """)

        for doc in folder_docs:
            if doc["name"] == "python":
                assert doc["children_count"] >= 4, (
                    f"Python folder should have at least 4 children, got {doc['children_count']}"
                )
                assert "Python modules" in doc["content"], "Folder documentation should mention Python modules"

        # Check file documentation
        file_docs = await test_data_isolation["container"].execute_cypher("""
            MATCH (f:FILE {name: 'class_with_inheritance.py'})
            OPTIONAL MATCH (d:DOCUMENTATION)-[:DESCRIBES]->(f)
            RETURN f.name as name, d.content as content, d.children_count as children_count
        """)

        assert len(file_docs) > 0, "Should have documentation for class_with_inheritance.py"
        file_doc = file_docs[0]
        assert file_doc["children_count"] >= 5, (
            f"File should have at least 5 children (3 classes + 2 functions), got {file_doc['children_count']}"
        )

        # Check class documentation
        class_docs = await test_data_isolation["container"].execute_cypher("""
            MATCH (c:CLASS {name: 'TextProcessor'})
            OPTIONAL MATCH (d:DOCUMENTATION)-[:DESCRIBES]->(c)
            RETURN c.name as name, d.content as content, d.children_count as children_count
        """)

        assert len(class_docs) > 0, "Should have documentation for TextProcessor class"
        class_doc = class_docs[0]
        assert class_doc["children_count"] >= 3, (
            f"TextProcessor should have at least 3 methods, got {class_doc['children_count']}"
        )
        assert "Concrete text processor" in class_doc["content"], "Class documentation should have correct content"

        # Clean up
        db_manager.close()
