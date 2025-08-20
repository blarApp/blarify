"""
Integration tests for embedding and vector search functionality.

Tests the end-to-end functionality of generating embeddings for documentation nodes
and performing vector similarity search using Neo4j's native vector index.
"""

import pytest
from unittest.mock import patch, MagicMock
import numpy as np
from typing import List, Dict, Any

from blarify.documentation.documentation_creator import DocumentationCreator
from blarify.services.embedding_service import EmbeddingService
from blarify.graph.node.documentation_node import DocumentationNode
from blarify.db_managers.queries import (
    vector_similarity_search_query,
    hybrid_search_query,
    create_vector_index_query,
)
from blarify.db_managers.dtos.documentation_search_result_dto import DocumentationSearchResultDto


class TestEmbeddingVectorSearch:
    """Test suite for embedding generation and vector search capabilities."""

    @pytest.fixture
    def mock_embeddings(self) -> Dict[str, List[float]]:
        """Create mock embeddings for testing."""
        # Generate 1536-dimensional vectors (ada-002 dimensions)
        np.random.seed(42)
        return {
            "doc1": np.random.randn(1536).tolist(),
            "doc2": np.random.randn(1536).tolist(),
            "doc3": np.random.randn(1536).tolist(),
        }

    @pytest.fixture
    def sample_documentation_nodes(self, test_graph_environment) -> List[DocumentationNode]:
        """Create sample documentation nodes for testing."""
        nodes = [
            DocumentationNode(
                title="Python Function Documentation",
                content="This function processes user authentication using JWT tokens",
                info_type="function",
                source_type="docstring",
                source_path="/src/auth/handler.py",
                source_name="authenticate_user",
                source_id="auth_handler_123",
                source_labels=["FUNCTION", "PYTHON"],
                graph_environment=test_graph_environment,
            ),
            DocumentationNode(
                title="Database Connection Module",
                content="Module for managing database connections with connection pooling",
                info_type="module",
                source_type="comment",
                source_path="/src/db/connection.py",
                source_name="connection",
                source_id="db_connection_456",
                source_labels=["MODULE", "PYTHON"],
                graph_environment=test_graph_environment,
            ),
            DocumentationNode(
                title="API Rate Limiting",
                content="Implements rate limiting for API endpoints using Redis",
                info_type="class",
                source_type="docstring",
                source_path="/src/api/rate_limiter.py",
                source_name="RateLimiter",
                source_id="rate_limiter_789",
                source_labels=["CLASS", "PYTHON"],
                graph_environment=test_graph_environment,
            ),
        ]
        
        # Set node IDs
        for i, node in enumerate(nodes):
            node.node_id = f"doc{i+1}"
        
        return nodes

    def test_vector_similarity_search(
        self,
        neo4j_instance,
        test_graph_environment,
        sample_documentation_nodes,
        mock_embeddings,
        graph_assertions,
    ):
        """Test vector similarity search on DOCUMENTATION nodes."""
        # Setup: Create documentation nodes with embeddings
        for node in sample_documentation_nodes:
            if node.node_id in mock_embeddings:
                node.content_embedding = mock_embeddings[node.node_id]
            node_dict = node.as_object()
            neo4j_instance.create_nodes([node_dict])

        # Create vector index
        try:
            neo4j_instance.query(
                cypher_query=create_vector_index_query(),
                parameters={}
            )
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

        results = neo4j_instance.query(cypher_query=query, parameters=parameters)

        # Assertions
        assert len(results) > 0, "Should find similar documentation nodes"
        
        # First result should be most similar (doc1)
        first_result = results[0]
        assert first_result["node_id"] == "doc1"
        assert first_result["title"] == "Python Function Documentation"
        assert first_result["similarity_score"] > 0.9  # Should be very similar
        
        # Results should be ordered by similarity
        scores = [r["similarity_score"] for r in results]
        assert scores == sorted(scores, reverse=True), "Results should be ordered by similarity"

    def test_hybrid_search(
        self,
        neo4j_instance,
        test_graph_environment,
        sample_documentation_nodes,
        mock_embeddings,
    ):
        """Test hybrid search combining vector and keyword similarity."""
        # Setup: Create documentation nodes with embeddings
        for node in sample_documentation_nodes:
            if node.node_id in mock_embeddings:
                node.content_embedding = mock_embeddings[node.node_id]
            node_dict = node.as_object()
            neo4j_instance.create_nodes([node_dict])

        # Create vector index
        try:
            neo4j_instance.query(
                cypher_query=create_vector_index_query(),
                parameters={}
            )
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

        results = neo4j_instance.query(cypher_query=query, parameters=parameters)

        # Assertions
        assert len(results) > 0, "Should find matching nodes"
        
        # First result should be doc2 (matches both vector and keyword)
        first_result = results[0]
        assert first_result["node_id"] == "doc2"
        assert "database" in first_result["content"].lower()

    @patch("blarify.services.embedding_service.OpenAIEmbeddings")
    def test_retroactive_embedding_generation(
        self,
        mock_openai_embeddings,
        neo4j_instance,
        test_llm_provider,
        test_graph_environment,
        sample_documentation_nodes,
        mock_embeddings,
    ):
        """Test retroactive embedding generation using embed_existing_documentation."""
        # Mock OpenAI embeddings
        mock_client = MagicMock()
        mock_client.embed_documents.return_value = [
            mock_embeddings["doc1"],
            mock_embeddings["doc2"],
            mock_embeddings["doc3"],
        ]
        mock_openai_embeddings.return_value = mock_client

        # Create documentation nodes WITHOUT embeddings
        for node in sample_documentation_nodes:
            node.content_embedding = None  # No embeddings initially
            node_dict = node.as_object()
            neo4j_instance.create_nodes([node_dict])

        # Create DocumentationCreator
        doc_creator = DocumentationCreator(
            db_manager=neo4j_instance,
            agent_caller=test_llm_provider,
            graph_environment=test_graph_environment,
            company_id=test_graph_environment.entity_id,
            repo_id=test_graph_environment.repo_id,
        )

        # Run retroactive embedding
        stats = doc_creator.embed_existing_documentation(
            batch_size=10,
            skip_existing=True
        )

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
        result = neo4j_instance.query(
            cypher_query=query,
            parameters={"entity_id": test_graph_environment.entity_id}
        )
        
        assert result[0]["count"] == 3, "All nodes should have embeddings"

    @patch("blarify.services.embedding_service.OpenAIEmbeddings")
    def test_skip_existing_embeddings(
        self,
        mock_openai_embeddings,
        neo4j_instance,
        test_llm_provider,
        test_graph_environment,
        sample_documentation_nodes,
        mock_embeddings,
    ):
        """Test that existing embeddings are skipped when skip_existing=True."""
        # Mock OpenAI embeddings
        mock_client = MagicMock()
        mock_client.embed_documents.return_value = [mock_embeddings["doc3"]]
        mock_openai_embeddings.return_value = mock_client

        # Create nodes with mixed embedding status
        for i, node in enumerate(sample_documentation_nodes):
            if i < 2:  # First two nodes have embeddings
                node.content_embedding = mock_embeddings[node.node_id]
            else:  # Last node doesn't have embedding
                node.content_embedding = None
            node_dict = node.as_object()
            neo4j_instance.create_nodes([node_dict])

        # Create DocumentationCreator
        doc_creator = DocumentationCreator(
            db_manager=neo4j_instance,
            agent_caller=test_llm_provider,
            graph_environment=test_graph_environment,
            company_id=test_graph_environment.entity_id,
            repo_id=test_graph_environment.repo_id,
        )

        # Run retroactive embedding with skip_existing=True
        stats = doc_creator.embed_existing_documentation(
            batch_size=10,
            skip_existing=True
        )

        # Assertions
        assert stats["success"] is True
        assert stats["total_processed"] == 1  # Only processed the one without embedding
        assert stats["total_embedded"] == 1
        assert stats["total_skipped"] == 2  # Skipped the two with embeddings

        # Verify only one API call was made
        mock_client.embed_documents.assert_called_once()

    @patch("blarify.services.embedding_service.OpenAIEmbeddings")
    def test_embedding_caching(
        self,
        mock_openai_embeddings,
        test_graph_environment,
    ):
        """Test that identical content is only embedded once (caching behavior)."""
        # Mock OpenAI embeddings
        mock_client = MagicMock()
        mock_client.embed_documents.return_value = [np.random.randn(1536).tolist()]
        mock_openai_embeddings.return_value = mock_client

        # Create embedding service
        embedding_service = EmbeddingService()

        # Create nodes with identical content
        identical_content = "This is the same content for all nodes"
        nodes = []
        for i in range(3):
            node = DocumentationNode(
                title=f"Node {i}",
                content=identical_content,  # Same content
                info_type="function",
                source_type="docstring",
                source_path=f"/src/file{i}.py",
                source_name=f"func{i}",
                source_id=f"id{i}",
                graph_environment=test_graph_environment,
            )
            node.node_id = f"node{i}"
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

    def test_finding_similar_documentation_nodes(
        self,
        neo4j_instance,
        test_graph_environment,
        sample_documentation_nodes,
        mock_embeddings,
    ):
        """Test finding similar documentation nodes based on vector similarity."""
        # Setup: Create documentation nodes with embeddings
        for node in sample_documentation_nodes:
            if node.node_id in mock_embeddings:
                node.content_embedding = mock_embeddings[node.node_id]
            node_dict = node.as_object()
            neo4j_instance.create_nodes([node_dict])

        # Create vector index
        try:
            neo4j_instance.query(
                cypher_query=create_vector_index_query(),
                parameters={}
            )
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

        results = neo4j_instance.query(cypher_query=query, parameters=parameters)

        # Convert to DTOs for easier handling
        search_results = []
        for r in results:
            dto = DocumentationSearchResultDto(
                node_id=r["node_id"],
                title=r["title"],
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
        assert search_results[0].node_id == "doc1"  # Exact match should be first
        assert search_results[0].similarity_score == 1.0  # Perfect match

        if len(search_results) > 1:
            # Other results should have lower similarity
            assert all(r.similarity_score < 1.0 for r in search_results[1:])