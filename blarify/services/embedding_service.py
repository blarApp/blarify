"""Embedding service for generating vector embeddings from text content."""

import hashlib
import os
import time
from typing import Dict, List, Optional

from langchain_openai import OpenAIEmbeddings

from blarify.graph.node.documentation_node import DocumentationNode


class EmbeddingService:
    """Service for generating and managing text embeddings using OpenAI's text-embedding-ada-002."""

    def __init__(self, batch_size: int = 100) -> None:
        """Initialize the EmbeddingService.

        Args:
            batch_size: Number of texts to embed in a single batch request
        """
        self.model = "text-embedding-ada-002"
        self.batch_size = batch_size
        self.cache: Dict[str, List[float]] = {}
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the OpenAI embeddings client."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        from pydantic import SecretStr

        self.client = OpenAIEmbeddings(model=self.model, api_key=SecretStr(api_key))

    def _get_content_hash(self, text: str) -> str:
        """Generate a hash for the given text for caching purposes.

        Args:
            text: The text content to hash

        Returns:
            SHA256 hash of the text
        """
        return hashlib.sha256(text.encode()).hexdigest()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts using OpenAI embeddings.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            try:
                batch_embeddings = self._embed_with_retry(batch)
                embeddings.extend(batch_embeddings)
            except Exception as e:
                # Log error but continue processing
                print(f"Error embedding batch {i // self.batch_size + 1}: {e}")
                # Return None embeddings for failed texts
                embeddings.extend([None] * len(batch))

        return embeddings

    def _embed_with_retry(self, texts: List[str], max_retries: int = 3) -> List[List[float]]:
        """Embed texts with retry logic for handling rate limits and failures.

        Args:
            texts: List of texts to embed
            max_retries: Maximum number of retry attempts

        Returns:
            List of embedding vectors
        """
        for attempt in range(max_retries):
            try:
                return self.client.embed_documents(texts)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                # Exponential backoff
                wait_time = 2**attempt
                print(f"Embedding attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)

        return []

    def embed_documentation_nodes(self, nodes: List[DocumentationNode]) -> Dict[str, List[float]]:
        """Generate embeddings for documentation nodes' content field.

        Only embeds the content field of each node. Uses caching to avoid
        re-embedding identical content.

        Args:
            nodes: List of DocumentationNode objects to embed

        Returns:
            Dictionary mapping node_id to embedding vector
        """
        node_embeddings: Dict[str, List[float]] = {}
        texts_to_embed = []
        content_to_node_ids: Dict[str, List[str]] = {}  # Map content to list of node IDs

        # Check cache and prepare texts for embedding
        for node in nodes:
            if not node.content:
                continue

            content_hash = self._get_content_hash(node.content)

            # Check if we have this content cached
            if content_hash in self.cache:
                node_embeddings[node.id] = self.cache[content_hash]
            else:
                # Track which nodes need this content embedded
                if node.content not in content_to_node_ids:
                    content_to_node_ids[node.content] = []
                    texts_to_embed.append(node.content)
                content_to_node_ids[node.content].append(node.id)

        # Embed uncached texts
        if texts_to_embed:
            embeddings = self.embed_batch(texts_to_embed)

            # Store embeddings and update cache
            for text, embedding in zip(texts_to_embed, embeddings):
                # Update cache
                content_hash = self._get_content_hash(text)
                self.cache[content_hash] = embedding

                # Map embedding to all nodes with this content
                for node_id in content_to_node_ids[text]:
                    node_embeddings[node_id] = embedding

        return node_embeddings

    def embed_single_text(self, text: str) -> Optional[List[float]]:
        """Embed a single text string.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if embedding fails
        """
        if not text:
            return None

        # Check cache
        content_hash = self._get_content_hash(text)
        if content_hash in self.cache:
            return self.cache[content_hash]

        try:
            embedding = self._embed_with_retry([text])[0]
            # Update cache
            self.cache[content_hash] = embedding
            return embedding
        except Exception as e:
            print(f"Error embedding text: {e}")
            return None
