"""
Integration tests for embedding and vector search functionality.

Tests the end-to-end functionality of generating embeddings for documentation nodes
and performing vector similarity search using Neo4j's native vector index.
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from typing import List, Dict, Any, Optional
import random

from blarify.documentation.documentation_creator import DocumentationCreator
from blarify.graph.node.documentation_node import DocumentationNode
from blarify.graph.graph_environment import GraphEnvironment
from blarify.repositories.graph_db_manager.dtos.documentation_search_result_dto import DocumentationSearchResultDto
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.repositories.graph_db_manager.queries import (
    create_vector_index_query,
    hybrid_search_query,
    vector_similarity_search_query,
)
from blarify.services.embedding_service import EmbeddingService
from neo4j_container_manager.types import Neo4jContainerInstance
from tests.utils.graph_assertions import GraphAssertions
from blarify.agents.llm_provider import LLMProvider
from pydantic import BaseModel
from langchain_core.tools import BaseTool


@pytest.mark.neo4j_integration
class TestEmbeddingVectorSearch:
    """Test suite for embedding generation and vector search capabilities."""

    @pytest.fixture
    def test_graph_environment(self) -> GraphEnvironment:
        """Create a test GraphEnvironment."""
        return GraphEnvironment(
            environment="test-entity/test-repo", diff_identifier="test-diff", root_path="/test/path"
        )

    @pytest.fixture
    def test_llm_provider(self) -> Mock:
        """Create a mock LLM provider for testing."""
        mock = Mock()
        mock.call_dumb_agent.return_value = "Test documentation content"
        return mock

    @pytest.fixture
    def mock_embeddings(self) -> Dict[str, List[float]]:
        """Create mock embeddings for testing."""
        # Generate 1536-dimensional vectors (ada-002 dimensions)
        random.seed(42)
        return {
            "doc1": [random.gauss(0, 1) for _ in range(1536)],
            "doc2": [random.gauss(0, 1) for _ in range(1536)],
            "doc3": [random.gauss(0, 1) for _ in range(1536)],
        }

    @pytest.fixture
    def sample_documentation_nodes(self, test_graph_environment: GraphEnvironment) -> List[DocumentationNode]:
        """Create sample documentation nodes for testing."""
        nodes = [
            DocumentationNode(
                content="This function processes user authentication using JWT tokens",
                info_type="function",
                source_type="docstring",
                source_path="file:///src/auth/handler.py",
                source_name="authenticate_user",
                source_id="auth_handler_123",
                source_labels=["FUNCTION", "PYTHON"],
                graph_environment=test_graph_environment,
            ),
            DocumentationNode(
                content="Module for managing database connections with connection pooling",
                info_type="module",
                source_type="comment",
                source_path="file:///src/db/connection.py",
                source_name="connection",
                source_id="db_connection_456",
                source_labels=["MODULE", "PYTHON"],
                graph_environment=test_graph_environment,
            ),
            DocumentationNode(
                content="Implements rate limiting for API endpoints using Redis",
                info_type="class",
                source_type="docstring",
                source_path="file:///src/api/rate_limiter.py",
                source_name="RateLimiter",
                source_id="rate_limiter_789",
                source_labels=["CLASS", "PYTHON"],
                graph_environment=test_graph_environment,
            ),
        ]

        # Note: node IDs are automatically generated from source_id

        return nodes

    @pytest.mark.asyncio
    async def test_vector_similarity_search(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_graph_environment: GraphEnvironment,
        sample_documentation_nodes: List[DocumentationNode],
        mock_embeddings: Dict[str, List[float]],
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test vector similarity search on DOCUMENTATION nodes."""
        # Create Neo4j manager
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
            entity_id="test-entity",
            repo_id="test-repo",
        )

        # Setup: Create documentation nodes with embeddings
        nodes_to_create = []
        for i, node in enumerate(sample_documentation_nodes):
            # Use a simple key for mock embeddings
            mock_key = f"doc{i + 1}"
            if mock_key in mock_embeddings:
                node.content_embedding = mock_embeddings[mock_key]
            nodes_to_create.append(node.as_object())

        # Save nodes to database
        db_manager.create_nodes(nodes_to_create)

        # Create vector index
        try:
            db_manager.query(cypher_query=create_vector_index_query(), parameters={})
        except Exception:
            pass  # Index might already exist

        # Generate query embedding (similar to first node)
        query_embedding = mock_embeddings["doc1"].copy()
        # Add small noise to make it slightly different
        query_embedding[0] += 0.1

        # Execute vector search
        query = vector_similarity_search_query()
        parameters = {
            "query_embedding": query_embedding,
            "top_k": 10,
            "min_similarity": 0.5,
        }

        results = db_manager.query(cypher_query=query, parameters=parameters)

        # Assertions
        assert len(results) > 0, "Should find similar documentation nodes"

        # Clean up
        db_manager.close()

    @pytest.mark.asyncio
    async def test_hybrid_search(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_graph_environment: GraphEnvironment,
        sample_documentation_nodes: List[DocumentationNode],
        mock_embeddings: Dict[str, List[float]],
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test hybrid search combining vector and keyword similarity."""
        # Create Neo4j manager
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
            entity_id="test-entity",
            repo_id="test-repo",
        )

        # Setup: Create documentation nodes with embeddings
        nodes_to_create = []
        for i, node in enumerate(sample_documentation_nodes):
            # Use a simple key for mock embeddings
            mock_key = f"doc{i + 1}"
            if mock_key in mock_embeddings:
                node.content_embedding = mock_embeddings[mock_key]
            nodes_to_create.append(node.as_object())

        # Save nodes to database
        db_manager.create_nodes(nodes_to_create)

        # Create vector index
        try:
            db_manager.query(cypher_query=create_vector_index_query(), parameters={})
        except Exception:
            pass  # Index might already exist

        # Search with both vector and keyword
        query_embedding = mock_embeddings["doc2"].copy()

        query = hybrid_search_query()
        parameters = {
            "query_embedding": query_embedding,
            "keyword": "database",  # Should match doc2
            "top_k": 10,
            "vector_weight": 0.5,
            "keyword_weight": 0.5,
            "min_score": 0.3,
            "limit": 5,
        }

        results = db_manager.query(cypher_query=query, parameters=parameters)

        # Assertions
        assert len(results) > 0, "Should find matching nodes"

        # Clean up
        db_manager.close()

    @patch("blarify.services.embedding_service.OpenAIEmbeddings")
    @pytest.mark.asyncio
    async def test_retroactive_embedding_generation(
        self,
        mock_openai_embeddings: MagicMock,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_llm_provider: Mock,
        test_graph_environment: GraphEnvironment,
        sample_documentation_nodes: List[DocumentationNode],
        mock_embeddings: Dict[str, List[float]],
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test retroactive embedding generation using embed_existing_documentation."""
        # Mock OpenAI embeddings
        mock_client = MagicMock()
        mock_client.embed_documents.return_value = [
            mock_embeddings["doc1"],
            mock_embeddings["doc2"],
            mock_embeddings["doc3"],
        ]
        mock_openai_embeddings.return_value = mock_client

        # Create Neo4j manager
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
            entity_id="test-entity",
            repo_id="test-repo",
        )

        # Create documentation nodes WITHOUT embeddings
        nodes_to_create = []
        for node in sample_documentation_nodes:
            node.content_embedding = None  # No embeddings initially
            nodes_to_create.append(node.as_object())

        # Save nodes to database
        db_manager.create_nodes(nodes_to_create)

        # Create DocumentationCreator
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
                return "Test documentation content"

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
                return {"framework": "Python", "main_folders": ["/test/path"]}

        llm_provider = MockLLMProvider()

        doc_creator = DocumentationCreator(
            db_manager=db_manager,
            agent_caller=llm_provider,
            graph_environment=test_graph_environment,
        )

        # Run retroactive embedding
        stats = doc_creator.embed_existing_documentation(batch_size=10, skip_existing=True)

        # Assertions
        assert stats["success"] is True
        assert stats["total_processed"] == 3
        assert stats["total_embedded"] == 3
        assert stats["total_skipped"] == 0
        assert len(stats["errors"]) == 0

        # Verify embeddings were saved to database
        query = """
        MATCH (n:DOCUMENTATION)
        WHERE n.content_embedding IS NOT NULL
        RETURN count(n) as count
        """
        result = await graph_assertions.neo4j_instance.execute_cypher(query)

        assert result[0]["count"] == 3, "All nodes should have embeddings"

        # Clean up
        db_manager.close()

    @patch("blarify.services.embedding_service.OpenAIEmbeddings")
    @pytest.mark.asyncio
    async def test_skip_existing_embeddings(
        self,
        mock_openai_embeddings: MagicMock,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_llm_provider: Mock,
        test_graph_environment: GraphEnvironment,
        sample_documentation_nodes: List[DocumentationNode],
        mock_embeddings: Dict[str, List[float]],
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that existing embeddings are skipped when skip_existing=True."""
        # Mock OpenAI embeddings
        mock_client = MagicMock()
        mock_client.embed_documents.return_value = [mock_embeddings["doc3"]]
        mock_openai_embeddings.return_value = mock_client

        # Create Neo4j manager
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
            entity_id="test-entity",
            repo_id="test_skip_existing_embeddings",
        )

        # Create nodes with mixed embedding status
        nodes_to_create = []
        for i, node in enumerate(sample_documentation_nodes):
            if i < 2:  # First two nodes have embeddings
                mock_key = f"doc{i + 1}"
                node.content_embedding = mock_embeddings[mock_key]
            else:  # Last node doesn't have embedding
                node.content_embedding = None
            nodes_to_create.append(node.as_object())

        # Save nodes to database
        db_manager.create_nodes(nodes_to_create)

        # Create DocumentationCreator
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
                return "Test documentation content"

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
                return {"framework": "Python", "main_folders": ["/test/path"]}

        llm_provider = MockLLMProvider()

        doc_creator = DocumentationCreator(
            db_manager=db_manager,
            agent_caller=llm_provider,
            graph_environment=test_graph_environment,
        )

        # Run retroactive embedding with skip_existing=True
        stats = doc_creator.embed_existing_documentation(batch_size=10, skip_existing=True)

        # Assertions
        assert stats["success"] is True
        assert stats["total_processed"] == 1  # Only processed the one without embedding
        assert stats["total_embedded"] == 1
        assert stats["total_skipped"] == 2  # Skipped the two with embeddings

        # Verify only one API call was made
        mock_client.embed_documents.assert_called_once()

        # Clean up
        db_manager.close()

    @patch("blarify.services.embedding_service.OpenAIEmbeddings")
    def test_embedding_caching(
        self,
        mock_openai_embeddings: MagicMock,
        test_graph_environment: GraphEnvironment,
    ) -> None:
        """Test that identical content is only embedded once (caching behavior)."""
        # Mock OpenAI embeddings
        mock_client = MagicMock()
        mock_client.embed_documents.return_value = [[random.gauss(0, 1) for _ in range(1536)]]
        mock_openai_embeddings.return_value = mock_client

        # Create embedding service
        embedding_service = EmbeddingService()

        # Create nodes with identical content but different source_ids
        identical_content = "This is the same content for all nodes"
        nodes = []
        for i in range(3):
            node = DocumentationNode(
                content=identical_content,  # Same content
                info_type="function",
                source_type="docstring",
                source_path=f"file:///src/file{i}.py",
                source_name=f"func{i}",
                source_id=f"unique_id_{i}",  # Different source_ids for unique node IDs
                graph_environment=test_graph_environment,
            )
            nodes.append(node)

        # Generate embeddings
        embeddings = embedding_service.embed_documentation_nodes(nodes)

        # Assertions
        assert len(embeddings) == 3  # All nodes get embeddings
        # But only one API call should be made (due to caching)
        mock_client.embed_documents.assert_called_once_with([identical_content])

        # All embeddings should be identical (from cache)
        embedding_values = list(embeddings.values())
        assert all(emb == embedding_values[0] for emb in embedding_values)

    @pytest.mark.asyncio
    async def test_finding_similar_documentation_nodes(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_graph_environment: GraphEnvironment,
        sample_documentation_nodes: List[DocumentationNode],
        mock_embeddings: Dict[str, List[float]],
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test finding similar documentation nodes based on vector similarity."""
        # Create Neo4j manager
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
            entity_id="test-entity",
            repo_id="test-repo",
        )

        # Setup: Create documentation nodes with embeddings
        nodes_to_create = []
        for i, node in enumerate(sample_documentation_nodes):
            # Use a simple key for mock embeddings
            mock_key = f"doc{i + 1}"
            if mock_key in mock_embeddings:
                node.content_embedding = mock_embeddings[mock_key]
            nodes_to_create.append(node.as_object())

        # Save nodes to database
        db_manager.create_nodes(nodes_to_create)

        # Create vector index
        try:
            db_manager.query(cypher_query=create_vector_index_query(), parameters={})
        except Exception:
            pass  # Index might already exist

        # Find nodes similar to "authentication" concept
        # Use embedding from doc1 (authentication-related)
        query_embedding = mock_embeddings["doc1"]

        query = vector_similarity_search_query()
        parameters = {
            "query_embedding": query_embedding,
            "top_k": 2,  # Find top 2 similar
            "min_similarity": 0.0,  # Accept all similarities
        }

        results = db_manager.query(cypher_query=query, parameters=parameters)

        # Convert to DTOs for easier handling
        search_results = []
        for r in results:
            dto = DocumentationSearchResultDto(
                title=r["title"],
                node_id=r["node_id"],
                content=r["content"],
                similarity_score=r["similarity_score"],
                source_path=r["source_path"],
                source_labels=r["source_labels"],
                info_type=r["info_type"],
                enhanced_content=r.get("enhanced_content"),
            )
            search_results.append(dto)

        # Assertions
        assert len(search_results) >= 1

        if len(search_results) > 1:
            # Other results should have lower or equal similarity
            assert all(r.similarity_score <= search_results[0].similarity_score for r in search_results[1:])

        # Clean up
        db_manager.close()
