"""
Integration tests for documentation creation functionality.

These tests verify that the documentation layer can successfully create
documentation nodes for various types of source code, including files
with direct code (no functions or classes).
"""

import pytest
from pathlib import Path
from typing import Any, Dict, Optional, List

from blarify.graph.node.documentation_node import DocumentationNode
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

    async def test_documentation_for_duplicate_named_nodes(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
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
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
            entity_id="test-entity",
            repo_id="test-repo",
        )

        # Save the code graph
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Debug: Print graph summary
        print("\n=== Initial Graph Summary ===")
        await graph_assertions.debug_print_graph_summary()

        # Verify duplicate named nodes exist
        utils_files = await graph_assertions.neo4j_instance.execute_cypher(
            "MATCH (f:FILE {name: 'utils.py'}) RETURN f.path as path, f.id as id ORDER BY f.path"
        )
        assert len(utils_files) == 2, f"Expected 2 utils.py files, found {len(utils_files)}"
        print(f"\nFound {len(utils_files)} utils.py files")

        helper_functions = await graph_assertions.neo4j_instance.execute_cypher(
            "MATCH (f:FUNCTION {name: 'helper'}) RETURN f.path as path, f.id as id ORDER BY f.path"
        )
        assert len(helper_functions) == 2, f"Expected 2 helper functions, found {len(helper_functions)}"
        print(f"Found {len(helper_functions)} helper functions")

        config_classes = await graph_assertions.neo4j_instance.execute_cypher(
            "MATCH (c:CLASS {name: 'Config'}) RETURN c.path as path, c.id as id ORDER BY c.path"
        )
        assert len(config_classes) == 2, f"Expected 2 Config classes, found {len(config_classes)}"
        print(f"Found {len(config_classes)} Config classes")

        # Step 3: Create documentation using DocumentationCreator with mock LLM
        class MockLLMProvider(LLMProvider):
            def call_dumb_agent(
                self,
                system_prompt: str,  # noqa: ARG002
                input_dict: Dict[str, Any],
                output_schema: Optional[BaseModel] = None,  # noqa: ARG002
                ai_model: Optional[str] = None,  # noqa: ARG002
                input_prompt: Optional[str] = "Start",  # noqa: ARG002
                config: Optional[Dict[str, Any]] = None,  # noqa: ARG002
                timeout: Optional[int] = None,  # noqa: ARG002
            ) -> Any:
                """Mock LLM response that returns path-specific descriptions."""
                path = input_dict.get("node_path", "")

                # Return different descriptions based on module path
                if "module1" in path:
                    return f"Module1 documentation for: {path}"
                elif "module2" in path:
                    return f"Module2 documentation for: {path}"
                else:
                    return f"Generic documentation for: {path}"

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
                return {"framework": "Python", "main_folders": [str(duplicate_names_path)]}

        llm_provider = MockLLMProvider()

        # Create DocumentationCreator
        doc_creator = DocumentationCreator(
            db_manager=db_manager,
            agent_caller=llm_provider,
            graph_environment=builder.graph_environment,
            company_id="test-entity",
            repo_id="test-repo",
        )

        # Generate documentation for all files
        result = doc_creator.create_documentation(save_to_database=True)

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
        shared_docs = await graph_assertions.neo4j_instance.execute_cypher(shared_doc_query)

        if shared_docs:
            print("\n❌ BUG DETECTED: Found documentation nodes describing multiple source nodes:")
            for shared in shared_docs:
                print(f"\n  Documentation node (source_name: {shared['source_name']}):")
                print(f"    - ID: {shared['doc_id']}")
                print(f"    - Describes {shared['node_count']} different nodes:")
                for node_desc in shared["described_nodes"]:
                    print(f"      • {node_desc}")
        else:
            print("✓ No shared documentation nodes found (expected behavior)")

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
        utils_analysis = await graph_assertions.neo4j_instance.execute_cypher("""
            MATCH (f:FILE {name: 'utils.py'})
            OPTIONAL MATCH (d:DOCUMENTATION)-[:DESCRIBES]->(f)
            RETURN f.path as path, count(DISTINCT d) as doc_count, collect(DISTINCT d.id) as doc_ids
            ORDER BY f.path
        """)
        print("\nUtils.py files:")
        for item in utils_analysis:
            print(f"  {item['path']}: {item['doc_count']} documentation node(s)")

        # Check helper functions
        helper_analysis = await graph_assertions.neo4j_instance.execute_cypher("""
            MATCH (f:FUNCTION {name: 'helper'})
            OPTIONAL MATCH (d:DOCUMENTATION)-[:DESCRIBES]->(f)
            RETURN f.path as path, count(DISTINCT d) as doc_count, collect(DISTINCT d.id) as doc_ids
            ORDER BY f.path
        """)
        print("\nHelper functions:")
        for item in helper_analysis:
            print(f"  {item['path']}: {item['doc_count']} documentation node(s)")

        # Check Config classes
        config_analysis = await graph_assertions.neo4j_instance.execute_cypher("""
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
        neo4j_instance: Neo4jContainerInstance,
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
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
            entity_id="test-entity",
            repo_id="test-repo",
        )

        # Save the code graph
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Step 3: Create documentation with embeddings enabled
        # Mock LLM provider that returns meaningful documentation
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
                return "This is a test documentation content for embedding generation."

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
                return {"framework": "Python", "main_folders": [str(python_examples_path)]}

        llm_provider = MockLLMProvider()

        # Mock the embedding service to return fake embeddings
        from unittest.mock import patch, MagicMock

        with patch("blarify.documentation.documentation_creator.EmbeddingService") as MockEmbeddingService:
            # Configure the mock to return fake embeddings
            mock_embedding_service = MagicMock()

            # Mock embed_documentation_nodes to return a dict with node IDs and embeddings
            def mock_embed_documentation_nodes(nodes: list[DocumentationNode]):
                # Return embeddings for each node with proper Python lists
                result = {}
                for i, node in enumerate(nodes):
                    # Use node.id if available, otherwise create a dummy ID
                    node_id = getattr(node, "id", f"node_{i}")
                    # Return actual Python list of floats (not MagicMock)
                    result[node_id] = [0.1 + i * 0.01] * 1536
                return result

            mock_embedding_service.embed_documentation_nodes = MagicMock(side_effect=mock_embed_documentation_nodes)
            MockEmbeddingService.return_value = mock_embedding_service

            # Create DocumentationCreator
            doc_creator = DocumentationCreator(
                db_manager=db_manager,
                agent_caller=llm_provider,
                graph_environment=builder.graph_environment,
                company_id="test-entity",
                repo_id="test-repo",
            )

            # Create documentation with embeddings enabled
            result = doc_creator.create_documentation(
                save_to_database=True,
                generate_embeddings=True,  # Enable embedding generation
            )

            # Verify documentation was created successfully
            assert result is not None
            assert result.error is None, f"Documentation creation failed: {result.error}"

            # Verify embed_documentation_nodes was called
            assert mock_embedding_service.embed_documentation_nodes.called, (
                "EmbeddingService.embed_documentation_nodes should have been called"
            )

        # Step 4: Verify embeddings are stored in Neo4j
        doc_nodes_with_embeddings = await graph_assertions.neo4j_instance.execute_cypher(
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
            print(f"✓ Documentation node {node['name'][:50]}... has embedding of size {node['embedding_size']}")

        print(f"\\n✓ Successfully stored embeddings for {len(doc_nodes_with_embeddings)} documentation nodes")

        # Clean up
        db_manager.close()

    async def test_embed_existing_documentation_adds_embeddings_to_nodes(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
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
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
            entity_id="test-entity",
            repo_id="test-repo",
        )

        # Save the code graph
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Step 3: Create documentation WITHOUT embeddings first
        # Mock LLM provider
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
                return "This is documentation content that will later receive embeddings."

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
                return {"framework": "Python", "main_folders": [str(python_examples_path)]}

        llm_provider = MockLLMProvider()

        # Create DocumentationCreator
        doc_creator = DocumentationCreator(
            db_manager=db_manager,
            agent_caller=llm_provider,
            graph_environment=builder.graph_environment,
            company_id="test-entity",
            repo_id="test-repo",
        )

        # Create documentation WITHOUT embeddings
        result = doc_creator.create_documentation(
            save_to_database=True,
            generate_embeddings=False,  # No embeddings initially
        )

        # Verify documentation was created successfully
        assert result is not None
        assert result.error is None, f"Documentation creation failed: {result.error}"

        # Verify no embeddings exist yet
        nodes_without_embeddings = await graph_assertions.neo4j_instance.execute_cypher(
            """
            MATCH (d:DOCUMENTATION)
            WHERE d.content_embedding IS NULL
            RETURN count(d) as count
            """
        )
        initial_nodes_without_embeddings = nodes_without_embeddings[0]["count"]
        assert initial_nodes_without_embeddings > 0, "Should have documentation nodes without embeddings initially"

        print(f"\\n✓ Created {initial_nodes_without_embeddings} documentation nodes without embeddings")

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
            assert embed_result["total_processed"] == 29
            assert embed_result["total_embedded"] == 29

            # Verify embed_batch was called
            assert mock_embed.called, "EmbeddingService.embed_batch should have been called"

        # Step 5: Verify embeddings were added to existing nodes
        nodes_with_embeddings = await graph_assertions.neo4j_instance.execute_cypher(
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

            print(f"\\n✓ Successfully added embeddings to {embedded_count} existing documentation nodes")
            print(f"✓ Each embedding has {embedding_size} dimensions (text-embedding-ada-002)")

        # Clean up
        db_manager.close()
