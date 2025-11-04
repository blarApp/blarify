#!/usr/bin/env python3
"""
Vector Search Tool for Code Scope Descriptions

Performs semantic search over AI-generated descriptions of code scopes (functions, classes, files)
using vector similarity with embeddings stored in Neo4j.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager
from blarify.repositories.graph_db_manager.queries import vector_similarity_search_query
from blarify.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class VectorSearchInput(BaseModel):
    """Input schema for vector search."""

    query: str = Field(description="The search query to find similar code scope descriptions")
    top_k: int = Field(default=5, description="Number of top results to return (default: 5)", ge=1, le=20)
    min_similarity: float = Field(
        default=0.7, description="Minimum similarity threshold (default: 0.7)", ge=0.0, le=1.0
    )


class VectorSearch(BaseTool):
    """Tool for semantic search over code scope descriptions using vector similarity."""

    name: str = "vector_search"
    description: str = (
        "Semantic search over AI-generated descriptions of code scopes (functions, classes, files, folders). "
        "Use this for exploratory searches when you don't know exact symbol names but understand the functionality you're looking for "
        "(e.g., 'email sending', 'authentication logic', 'database connection'). "
        "Returns relevant code scopes with reference IDs, file paths, and their AI-generated descriptions."
    )

    args_schema: type[BaseModel] = VectorSearchInput  # type: ignore[assignment]

    db_manager: AbstractDbManager = Field(description="Database manager for queries")
    embedding_service: Optional[EmbeddingService] = Field(
        default=None, description="Embedding service for query vectorization"
    )

    def __init__(
        self,
        db_manager: Any,
        handle_validation_error: bool = False,
    ):
        """Initialize the vector search tool."""
        super().__init__(
            db_manager=db_manager,
            handle_validation_error=handle_validation_error,
        )
        # Initialize embedding service
        try:
            self.embedding_service = EmbeddingService()
        except ValueError as e:
            logger.warning(f"Could not initialize embedding service: {e}")
            self.embedding_service = None
        logger.info("VectorSearch tool initialized")

    def _run(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.7,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """
        Search for documentation using vector similarity.

        Args:
            query: The search query text
            top_k: Number of top results to return
            min_similarity: Minimum similarity threshold for results
            run_manager: Callback manager for tool execution

        Returns:
            Formatted string with search results
        """
        try:
            # Check if embedding service is available
            if not self.embedding_service:
                return "Vector search unavailable: OPENAI_API_KEY not configured"

            # Generate embedding for the query
            query_embedding = self.embedding_service.embed_single_text(query)
            if not query_embedding:
                return f"Failed to generate embedding for query: '{query}'"

            # Perform vector search using Neo4j manager
            vector_query = vector_similarity_search_query()
            parameters = {
                "query_embedding": query_embedding,
                "top_k": top_k,
                "min_similarity": min_similarity,
            }
            results = self.db_manager.query(vector_query, parameters)

            if not results:
                return (
                    f"No code scopes found matching\n"
                    f"Suggestions:\n"
                    f"- Try simplifying your query to use more general terms\n"
                    f"- Lower the min_similarity threshold (current: {min_similarity})"
                )

            # Format the results
            output = self._format_results(results, query)

            logger.info(f"Vector search found {len(results)} results for query: {query[:50]}...")
            return output

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return f"Error performing vector search: {str(e)}"

    def _format_results(self, results: List[Dict[str, Any]], query: str) -> str:
        """
        Format search results into a readable string.

        Args:
            results: List of search results from Neo4j
            query: Original search query

        Returns:
            Formatted string representation
        """
        output = "=" * 80 + "\n"
        output += "🔍 VECTOR SEARCH RESULTS\n"
        output += f'Query: "{query}"\n'
        output += f"Found {len(results)} relevant code scopes\n"
        output += "=" * 80 + "\n\n"

        for i, result in enumerate(results, 1):
            node_id = result.get("node_id", "Unknown")
            title = result.get("title", "Unnamed")
            score = result.get("similarity_score", 0.0)
            content = result.get("content", "No content available")
            source_path = result.get("source_path", "")
            source_labels = result.get("source_labels", [])

            # Build a descriptive name from title or source info
            if title and title != "Unnamed":
                name = title
            elif source_labels and isinstance(source_labels, list):
                # Use source labels to build a name (e.g., "Class: ClassName" or "Function: functionName")
                name = " | ".join(source_labels) if source_labels else "Code Scope"
            else:
                name = "Code Scope"

            # Truncate content if too long
            if len(content) > 500:
                content = content[:497] + "..."

            output += f"### {i}. {name}\n"
            if source_path:
                output += f"**File:** {source_path}\n"
            output += f"**Relevance Score:** {score:.3f}\n"
            output += f"**ID:** {node_id}\n"
            output += "**Description:**\n"
            output += f"```\n{content}\n```\n"
            output += "-" * 40 + "\n\n"

        output += "=" * 80 + "\n"
        output += "Tip: Higher relevance scores (>0.8) indicate more relevant matches\n"

        return output
