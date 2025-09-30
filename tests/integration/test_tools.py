"""
Integration tests for Blarify tools.

Tests the tools with real Neo4j database and actual graph data.
"""

import os
import pytest
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch, MagicMock

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.tools import (
    FindSymbols,
    SearchDocumentation,
    GetCodeAnalysis,
    GetExpandedContext,
    GetDependencyGraph,
    GetNodeWorkflowsTool,
)
from tests.utils.graph_assertions import GraphAssertions


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestToolsIntegration:
    """Integration tests for Blarify tools with real Neo4j database."""

    @pytest.fixture(autouse=True)
    async def setup_test_data(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
    ):
        """Set up test data in Neo4j before each test."""
        # Build graph from test code
        python_path = test_code_examples_path / "python"
        builder = GraphBuilder(root_path=str(python_path))
        graph = builder.build()

        # Save to Neo4j with isolated IDs
        self.db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        try:
            # Store test isolation data for use in tests
            self.test_isolation = test_data_isolation

            self.db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

            # Create documentation nodes for vector search testing
            self._create_documentation_nodes()

            yield
        finally:
            self.db_manager.close()

    def _create_documentation_nodes(self):
        """Create documentation nodes with embeddings for testing vector search."""
        # Create sample documentation nodes
        docs = [
            {
                "node_id": "doc001",
                "title": "Calculator Class",
                "content": "The Calculator class provides basic arithmetic operations including addition, subtraction, multiplication, and division.",
                "source_path": "calculator.py",
                "source_labels": ["CLASS", "Calculator"],
                "info_type": "class_documentation",
            },
            {
                "node_id": "doc002",
                "title": "DataProcessor Module",
                "content": "Module for processing and transforming data with support for various formats including JSON, CSV, and XML.",
                "source_path": "data_processor.py",
                "source_labels": ["MODULE", "DataProcessor"],
                "info_type": "module_documentation",
            },
            {
                "node_id": "doc003",
                "title": "APIClient Service",
                "content": "Service class for making HTTP requests to external APIs with retry logic and error handling.",
                "source_path": "api_client.py",
                "source_labels": ["CLASS", "APIClient"],
                "info_type": "class_documentation",
            },
        ]

        # Insert documentation nodes
        with self.db_manager.driver.session() as session:
            for doc in docs:
                session.run(
                    """
                    CREATE (n:DOCUMENTATION:NODE {
                        node_id: $node_id,
                        title: $title,
                        content: $content,
                        source_path: $source_path,
                        source_labels: $source_labels,
                        info_type: $info_type,
                        entityId: $entity_id,
                        repoId: $repo_id,
                        environment: 'main'
                    })
                    """,
                    node_id=doc["node_id"],
                    title=doc["title"],
                    content=doc["content"],
                    source_path=doc["source_path"],
                    source_labels=doc["source_labels"],
                    info_type=doc["info_type"],
                    entity_id=self.test_isolation["entity_id"],
                    repo_id=self.test_isolation["repo_id"],
                )

    async def test_find_symbols_tool(self, graph_assertions: GraphAssertions):
        """Test FindSymbols tool finds symbols in the graph."""
        tool = FindSymbols(db_manager=self.db_manager)

        # Search for functions
        result = tool._run(name="__init__", type="FUNCTION")

        # Verify results - should return a dict with symbols
        assert isinstance(result, dict)
        assert "symbols" in result

    async def test_search_documentation_with_mock_embedding(self):
        """Test SearchDocumentation tool with mocked embedding service."""
        # Mock the embedding service
        with patch("blarify.tools.search_documentation.EmbeddingService") as mock_service_class:
            mock_instance = MagicMock()
            # Return a fake embedding vector
            mock_instance.embed_single_text.return_value = [0.1] * 1536
            mock_service_class.return_value = mock_instance

            # Set mock environment variable
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                tool = SearchDocumentation(db_manager=self.db_manager)
                tool.embedding_service = mock_instance

                # Mock the query to return our test documentation
                original_query = self.db_manager.query

                def mock_query(cypher_query, parameters=None, **kwargs):
                    if "db.index.vector.queryNodes" in cypher_query:
                        # Return mock vector search results
                        return [
                            {
                                "node_id": "doc001",
                                "title": "Calculator Class",
                                "content": "The Calculator class provides basic arithmetic operations...",
                                "similarity_score": 0.95,
                                "source_path": "calculator.py",
                                "source_labels": ["CLASS", "Calculator"],
                                "info_type": "class_documentation",
                                "enhanced_content": None,
                            }
                        ]
                    return original_query(cypher_query, parameters, **kwargs)

                self.db_manager.query = mock_query

                # Execute search
                result = tool._run(query="calculator arithmetic operations", top_k=5)

                # Verify results
                assert "DOCUMENTATION SEARCH RESULTS" in result
                assert "Calculator Class" in result
                assert "calculator.py" in result
                assert "0.950" in result  # Similarity score

                # Verify embedding was generated
                mock_instance.embed_single_text.assert_called_once_with("calculator arithmetic operations")

    async def test_search_documentation_without_api_key(self):
        """Test SearchDocumentation tool handles missing API key gracefully."""
        # Remove OPENAI_API_KEY
        with patch.dict(os.environ, {}, clear=True):
            tool = SearchDocumentation(db_manager=self.db_manager)

            # Execute search
            result = tool._run(query="test query", top_k=5)

            # Should return error message
            assert "Vector search unavailable: OPENAI_API_KEY not configured" in result

    async def test_get_code_analysis_tool(self):
        """Test GetCodeAnalysis tool retrieves code with analysis for a class node."""
        tool = GetCodeAnalysis(db_manager=self.db_manager)

        # Get a class node to test with using test isolation
        with self.db_manager.driver.session() as session:
            result = session.run(
                """
                MATCH (n:CLASS)
                WHERE n.entityId = $entity_id AND n.repoId = $repo_id
                RETURN n.node_id as node_id, n.name as class_name
                LIMIT 1
                """,
                entity_id=self.test_isolation["entity_id"],
                repo_id=self.test_isolation["repo_id"],
            )
            record = result.single()

            if record:
                node_id = record["node_id"]
                class_name = record["class_name"]

                # Analyze the class
                result = tool._run(reference_id=node_id)

                # Verify results contain expected content for a class
                assert "FILE:" in result or "No code found" in result
                if "FILE:" in result:
                    assert node_id in result
                    assert "CLASS" in result  # Should show CLASS in labels
                    assert class_name in result  # Should show the class name

                    # Verify NODE label is not exposed in output
                    assert "NODE: ID:" not in result
                    assert "RELATION NODE ID:" not in result
                    assert "RELATION NODE TYPE:" not in result

                    # Verify NODE is not in the Labels display (check all possible positions)
                    # Extract labels line for precise checking
                    import re
                    labels_match = re.search(r"🏷️  Labels: ([^\n]+)", result)
                    if labels_match:
                        labels_text = labels_match.group(1)
                        assert "NODE" not in labels_text, f"NODE found in labels: {labels_text}"

                    # Verify NODE is not in relationship types (e.g., "(NODE, CLASS)" or "(CLASS, NODE)")
                    if "RELATIONSHIP" in result:
                        # Check that NODE doesn't appear in relationship type lists
                        assert "(NODE, " not in result
                        assert ", NODE)" not in result
                        assert "(NODE)" not in result

    async def test_get_expanded_context_tool(self):
        """Test GetExpandedContext tool retrieves full file context."""
        tool = GetExpandedContext(db_manager=self.db_manager)

        # Get a function node to test with
        with self.db_manager.driver.session() as session:
            result = session.run(
                """
                MATCH (n:FUNCTION)
                WHERE n.entityId = $entity_id AND n.repoId = $repo_id
                RETURN n.node_id as node_id, n.file_path as file_path, n.name as name
                LIMIT 1
                """,
                entity_id=self.test_isolation["entity_id"],
                repo_id=self.test_isolation["repo_id"],
            )
            record = result.single()

            if record:
                node_id = record["node_id"]

                # Get expanded context
                result = tool._run(reference_id=node_id)

                # Verify results
                assert "FILE:" in result or "No code found" in result
                if "FILE:" in result:
                    assert "ID:" in result
                    assert node_id in result

                    # Verify NODE label is not exposed in output
                    assert "RELATION NODE ID:" not in result
                    assert "RELATION NODE TYPE:" not in result

                    # Verify NODE is not in the Type display (check all possible positions)
                    import re
                    type_match = re.search(r"🏷️  Type: ([^\n]+)", result)
                    if type_match:
                        type_text = type_match.group(1)
                        assert "NODE" not in type_text, f"NODE found in type: {type_text}"

                    # Verify NODE is not in relationship types
                    if "RELATIONSHIP" in result:
                        assert "(NODE, " not in result
                        assert ", NODE)" not in result
                        assert "(NODE)" not in result

    async def test_get_dependency_graph_tool(self):
        """Test GetDependencyGraph tool generates dependency visualization."""
        tool = GetDependencyGraph(db_manager=self.db_manager)

        # Get a node to analyze dependencies
        with self.db_manager.driver.session() as session:
            result = session.run(
                """
                MATCH (n:NODE)
                WHERE n.entityId = $entity_id AND n.repoId = $repo_id
                RETURN n.node_id as node_id
                LIMIT 1
                """,
                entity_id=self.test_isolation["entity_id"],
                repo_id=self.test_isolation["repo_id"],
            )
            record = result.single()

            if record:
                node_id = record["node_id"]

                # Get dependency graph
                result = tool._run(reference_id=node_id)

                # Verify results - should return mermaid flowchart, dependency graph, no dependencies, or node not found
                assert (
                    "flowchart" in result
                    or "DEPENDENCY GRAPH" in result
                    or "No dependencies found" in result
                    or "not found" in result
                )

    async def test_find_symbols_with_filters(self):
        """Test FindSymbols tool with various filters."""
        tool = FindSymbols(db_manager=self.db_manager)

        # Test with class type
        result = tool._run(name="BaseProcessor", type="CLASS")
        assert isinstance(result, dict) or "Too many nodes found" in result

        # Test with function name
        result = tool._run(name="__init__", type="FUNCTION")
        assert isinstance(result, dict) or "Too many nodes found" in result

    async def test_tools_handle_invalid_input(self):
        """Test that tools handle invalid input gracefully."""
        # Test GetCodeAnalysis with invalid node_id
        tool = GetCodeAnalysis(db_manager=self.db_manager)
        result = tool._run(reference_id="invalid_node_id_12345")
        assert "No code found" in result or "not found" in result.lower()

        # Test GetExpandedContext with invalid node_id
        tool = GetExpandedContext(db_manager=self.db_manager)
        result = tool._run(reference_id="invalid_node_id_67890")
        assert "No code found" in result or "not found" in result.lower()

    async def test_tools_with_empty_database(self):
        """Test tools behavior with empty database (no matching data)."""
        # Create a new db_manager with different isolation IDs (empty data)
        empty_db_manager = Neo4jManager(
            uri=self.test_isolation["uri"],
            user="neo4j",
            password=self.test_isolation["password"],
            repo_id="empty_repo_id",
            entity_id="empty_entity_id",
        )

        try:
            # Test FindSymbols with empty data
            tool = FindSymbols(db_manager=empty_db_manager)
            result = tool._run(name="nonexistent", type="FUNCTION")
            # Should return empty nodes list or error message
            assert isinstance(result, dict) and len(result.get("nodes", [])) == 0

            # Test GetCodeAnalysis with empty data
            tool = GetCodeAnalysis(db_manager=empty_db_manager)
            result = tool._run(reference_id="any_id")
            assert "No code found" in result or "not found" in result.lower()

        finally:
            empty_db_manager.close()

    async def test_search_documentation_result_formatting(self):
        """Test that SearchDocumentation formats results correctly."""
        with patch("blarify.tools.search_documentation.EmbeddingService") as mock_service_class:
            mock_instance = MagicMock()
            mock_instance.embed_single_text.return_value = [0.1] * 1536
            mock_service_class.return_value = mock_instance

            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                tool = SearchDocumentation(db_manager=self.db_manager)
                tool.embedding_service = mock_instance

                # Mock query to return formatted results
                original_query = self.db_manager.query

                def mock_query(cypher_query, parameters=None, **kwargs):
                    if "db.index.vector.queryNodes" in cypher_query:
                        return [
                            {
                                "node_id": "test123",
                                "title": "TestClass",
                                "content": "A" * 600,  # Long content to test truncation
                                "similarity_score": 0.923,
                                "source_path": "test/file.py",
                                "source_labels": ["CLASS", "TestClass"],
                                "info_type": "class_documentation",
                                "enhanced_content": None,
                            },
                            {
                                "node_id": "test456",
                                "title": None,  # No title, should use source_labels
                                "content": "Short content",
                                "similarity_score": 0.812,
                                "source_path": "test/utils.py",
                                "source_labels": ["FUNCTION", "helperFunc"],
                                "info_type": "function_documentation",
                                "enhanced_content": None,
                            },
                        ]
                    return original_query(cypher_query, parameters, **kwargs)

                self.db_manager.query = mock_query

                # Execute search
                result = tool._run(query="test", top_k=10)

                # Verify formatting
                assert "### 1. TestClass" in result
                assert "### 2. FUNCTION | helperFunc" in result
                assert "**File:** test/file.py" in result
                assert "**Relevance Score:** 0.923" in result
                assert "**Relevance Score:** 0.812" in result
                assert "**ID:** test123" in result
                assert "**ID:** test456" in result

                # Check content truncation
                assert ("A" * 497 + "...") in result  # Should be truncated
                assert "Short content" in result  # Should not be truncated

    async def test_node_workflows_tool_output_format(self):
        """Test GetNodeWorkflowsTool does not expose NODE label in output."""
        tool = GetNodeWorkflowsTool(db_manager=self.db_manager)

        # Get any node to test with
        with self.db_manager.driver.session() as session:
            result = session.run(
                """
                MATCH (n)
                WHERE n.entityId = $entity_id AND n.repoId = $repo_id AND n.layer = 'code'
                RETURN n.node_id as node_id, n.name as name
                LIMIT 1
                """,
                entity_id=self.test_isolation["entity_id"],
                repo_id=self.test_isolation["repo_id"],
            )
            record = result.single()

            if record:
                node_id = record["node_id"]

                # Get workflows for the node
                result = tool._run(node_id=node_id)

                # Verify NODE label is not exposed in output
                assert "WORKFLOWS FOR NODE:" not in result

                # Verify correct format is used
                if "WORKFLOWS FOR:" in result:
                    # Format should be "WORKFLOWS FOR: {name}" not "WORKFLOWS FOR NODE: {name}"
                    assert "🔄 WORKFLOWS FOR:" in result
