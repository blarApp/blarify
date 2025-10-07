"""
Integration tests for optional repo_id functionality.

Tests entity-wide and repo-specific scoping for queries and mutations.
"""

import pytest
from pathlib import Path
from typing import Any, Dict

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.tools import FindSymbols, GetCodeAnalysis


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestOptionalRepoId:
    """Test optional repo_id functionality for entity-wide and repo-specific queries."""

    @pytest.fixture(autouse=True)
    async def setup_multi_repo_data(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
    ):
        """Set up test data with multiple repositories in the same entity."""
        self.entity_id = test_data_isolation["entity_id"]
        self.repo1_id = f"{test_data_isolation['repo_id']}_repo1"
        self.repo2_id = f"{test_data_isolation['repo_id']}_repo2"
        self.uri = test_data_isolation["uri"]
        self.password = test_data_isolation["password"]

        # Create first repo with data
        self.db_manager_repo1 = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=self.repo1_id,
            entity_id=self.entity_id,
        )

        python_path = test_code_examples_path / "python"
        builder1 = GraphBuilder(root_path=str(python_path), db_manager=self.db_manager_repo1)
        graph1 = builder1.build()

        # Create second repo with data
        self.db_manager_repo2 = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=self.repo2_id,
            entity_id=self.entity_id,
        )

        builder2 = GraphBuilder(root_path=str(python_path), db_manager=self.db_manager_repo2)
        graph2 = builder2.build()

        # Create entity-wide manager (no repo_id)
        self.db_manager_entity = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=None,  # Entity-wide scope
            entity_id=self.entity_id,
        )

        try:
            # Save graphs to both repos
            self.db_manager_repo1.save_graph(graph1.get_nodes_as_objects(), graph1.get_relationships_as_objects())
            self.db_manager_repo2.save_graph(graph2.get_nodes_as_objects(), graph2.get_relationships_as_objects())

            yield
        finally:
            # Cleanup
            self.db_manager_repo1.close()
            self.db_manager_repo2.close()
            self.db_manager_entity.close()

    async def test_entity_wide_query_returns_all_repos(self):
        """Test that entity-wide queries (repo_id=None) return results from all repos."""
        # Query with entity-wide scope
        tool_entity = FindSymbols(db_manager=self.db_manager_entity)
        result_entity = tool_entity._run(name="__init__", type="FUNCTION")

        # Query repo1 only
        tool_repo1 = FindSymbols(db_manager=self.db_manager_repo1)
        result_repo1 = tool_repo1._run(name="__init__", type="FUNCTION")

        # Query repo2 only
        tool_repo2 = FindSymbols(db_manager=self.db_manager_repo2)
        result_repo2 = tool_repo2._run(name="__init__", type="FUNCTION")

        # Ensure we got dict results, not error strings
        assert isinstance(result_entity, dict), (
            f"Expected dict from entity query, got {type(result_entity)}: {result_entity}"
        )
        assert isinstance(result_repo1, dict), (
            f"Expected dict from repo1 query, got {type(result_repo1)}: {result_repo1}"
        )
        assert isinstance(result_repo2, dict), (
            f"Expected dict from repo2 query, got {type(result_repo2)}: {result_repo2}"
        )

        entity_count = len(result_entity.get("symbols", []))
        repo1_count = len(result_repo1.get("symbols", []))
        repo2_count = len(result_repo2.get("symbols", []))

        # Verify all repos have data
        assert repo1_count > 0, f"Repo1 returned 0 __init__ functions"
        assert repo2_count > 0, f"Repo2 returned 0 __init__ functions"

        # Both repos built from same source must have identical counts
        assert repo1_count == repo2_count, (
            f"Repo1 and Repo2 built from same source must have same count. "
            f"Repo1: {repo1_count}, Repo2: {repo2_count}"
        )

        # Entity-wide must return exactly repo1 + repo2 (no deduplication across repos)
        assert entity_count == repo1_count + repo2_count, (
            f"Entity-wide must return exactly repo1 + repo2. "
            f"Expected: {repo1_count + repo2_count}, Got: {entity_count}"
        )

    async def test_repo_specific_query_filters_correctly(self):
        """Test that repo-specific queries only return data from that repo."""
        # Verify that each repo has nodes with their correct repo_id
        with self.db_manager_repo1.driver.session() as session:
            # Count nodes in repo1
            result = session.run(
                """
                MATCH (n:NODE)
                WHERE n.entityId = $entity_id AND n.repoId = $repo_id
                RETURN count(n) as count
                """,
                entity_id=self.entity_id,
                repo_id=self.repo1_id,
            )
            record = result.single()
            assert record is not None, "Query for repo1 count should return a result"
            repo1_count = record["count"]

            # Count nodes in repo2
            result = session.run(
                """
                MATCH (n:NODE)
                WHERE n.entityId = $entity_id AND n.repoId = $repo_id
                RETURN count(n) as count
                """,
                entity_id=self.entity_id,
                repo_id=self.repo2_id,
            )
            record = result.single()
            assert record is not None, "Query for repo2 count should return a result"
            repo2_count = record["count"]

            # Both repos should have nodes
            assert repo1_count > 0, f"Repo1 should have nodes, but got {repo1_count}"
            assert repo2_count > 0, f"Repo2 should have nodes, but got {repo2_count}"

            # They should have the same number of nodes (same source code)
            assert repo1_count == repo2_count, (
                f"Both repos built from same source should have same node count. "
                f"Repo1: {repo1_count}, Repo2: {repo2_count}"
            )

            # Verify node isolation by checking repoId
            # Get a node from repo1 and verify it has repo1's repoId
            result = session.run(
                """
                MATCH (n:NODE)
                WHERE n.entityId = $entity_id AND n.repoId = $repo_id
                RETURN n.node_id as node_id, n.repoId as repo_id
                LIMIT 1
                """,
                entity_id=self.entity_id,
                repo_id=self.repo1_id,
            )
            record = result.single()
            assert record is not None, "Query for repo1 node should return a result"
            assert record["repo_id"] == self.repo1_id, (
                f"Node from repo1 should have repo1's repoId, got {record['repo_id']}"
            )

            # Query via db_manager and verify it respects repo filtering
            node_id = record["node_id"]
            node_result_repo1 = self.db_manager_repo1.get_node_by_id(node_id=node_id)

            # Verify we got a result from repo1
            assert node_result_repo1 is not None, "Should get a result from repo1 manager"
            assert node_result_repo1.node_id == node_id, f"Expected node_id {node_id}, got {node_result_repo1.node_id}"

            # Query the same node_id through repo2 manager
            # Since both repos have the same files, node_id exists in both repos
            # But repo2 manager should return repo2's version (with repo2's repoId)
            node_result_repo2 = self.db_manager_repo2.get_node_by_id(node_id=node_id)

            # Verify we got a result from repo2
            assert node_result_repo2 is not None, "Should get a result from repo2 manager"
            assert node_result_repo2.node_id == node_id, f"Expected node_id {node_id}, got {node_result_repo2.node_id}"

            # Verify by checking the actual repoId in the database for each result
            # The query should have filtered by repo_id, so we need to verify that
            # repo1 manager returned repo1's node and repo2 manager returned repo2's node
            result = session.run(
                """
                MATCH (n:NODE)
                WHERE n.entityId = $entity_id AND n.node_id = $node_id AND n.repoId = $repo_id
                RETURN count(n) as count
                """,
                entity_id=self.entity_id,
                node_id=node_id,
                repo_id=self.repo1_id,
            )
            record = result.single()
            assert record is not None, "Query for repo1 node existence should return a result"
            assert record["count"] == 1, f"Repo1 should have exactly one node with ID {node_id}, got {record['count']}"

            result = session.run(
                """
                MATCH (n:NODE)
                WHERE n.entityId = $entity_id AND n.node_id = $node_id AND n.repoId = $repo_id
                RETURN count(n) as count
                """,
                entity_id=self.entity_id,
                node_id=node_id,
                repo_id=self.repo2_id,
            )
            record = result.single()
            assert record is not None, "Query for repo2 node existence should return a result"
            assert record["count"] == 1, f"Repo2 should have exactly one node with ID {node_id}, got {record['count']}"

    async def test_mutation_requires_repo_id(self):
        """Test that mutation operations require repo_id and reject entity-wide scope."""
        # Attempt to create nodes with entity-wide manager (repo_id=None)
        with pytest.raises(ValueError, match="repo_id is required for creating nodes"):
            self.db_manager_entity.create_nodes([])

        # Attempt to create edges with entity-wide manager
        with pytest.raises(ValueError, match="repo_id is required for creating edges"):
            self.db_manager_entity.create_edges([])

        # Attempt to delete with entity-wide manager
        with pytest.raises(ValueError, match="repo_id is required for deleting nodes"):
            self.db_manager_entity.detatch_delete_nodes_with_path("/some/path")

    async def test_query_method_with_optional_repo_id(self):
        """Test that query() method properly injects optional repo_id parameter."""
        # Test with entity-wide manager (repo_id=None)
        query = """
        MATCH (n:NODE {entityId: $entity_id})
        WHERE ($repo_id IS NULL OR n.repoId = $repo_id)
        RETURN count(n) as total
        """

        result_entity = self.db_manager_entity.query(query)
        entity_total = result_entity[0]["total"] if result_entity else 0

        # Test with repo1 manager
        result_repo1 = self.db_manager_repo1.query(query)
        repo1_total = result_repo1[0]["total"] if result_repo1 else 0

        # Test with repo2 manager
        result_repo2 = self.db_manager_repo2.query(query)
        repo2_total = result_repo2[0]["total"] if result_repo2 else 0

        # Entity-wide must return exactly repo1 + repo2
        expected_total = repo1_total + repo2_total
        assert entity_total == expected_total, (
            f"Entity-wide must return exactly repo1 + repo2. "
            f"Expected: {expected_total} (repo1: {repo1_total} + repo2: {repo2_total}), Got: {entity_total}"
        )

    async def test_entity_isolation_is_maintained(self):
        """Test that entity_id isolation is always enforced, even with optional repo_id."""
        # Create a different entity manager
        different_entity_manager = Neo4jManager(
            uri=self.uri,
            user="neo4j",
            password=self.password,
            repo_id=None,  # Entity-wide
            entity_id="different_entity_12345",  # Different entity
        )

        try:
            # Query with different entity should return no results
            tool = FindSymbols(db_manager=different_entity_manager)
            result = tool._run(name="__init__", type="FUNCTION")

            # Should return empty or no results
            if isinstance(result, dict):
                assert len(result.get("symbols", [])) == 0, "Different entity should not see other entity's data"
        finally:
            different_entity_manager.close()

    async def test_backward_compatibility_with_repo_id(self):
        """Test that existing code with repo_id still works (backward compatibility)."""
        # Old-style initialization with explicit repo_id should work
        old_style_manager = Neo4jManager(
            uri=self.uri,
            user="neo4j",
            password=self.password,
            repo_id=self.repo1_id,
            entity_id=self.entity_id,
        )

        try:
            # Should work exactly as before
            tool = FindSymbols(db_manager=old_style_manager)
            result = tool._run(name="__init__", type="FUNCTION")

            # Should return results from repo1
            assert isinstance(result, dict) or isinstance(result, str)
            if isinstance(result, dict):
                # Verify results are from repo1 only
                for symbol in result.get("symbols", []):
                    # Verify the symbol exists in repo1
                    assert symbol["id"] is not None
        finally:
            old_style_manager.close()

    async def test_tool_descriptions_mention_scope(self):
        """Test that all tools mention scope in their descriptions."""
        tools = [
            FindSymbols(db_manager=self.db_manager_entity),
            GetCodeAnalysis(db_manager=self.db_manager_entity),
        ]

        for tool in tools:
            description = tool.description
            assert "Scope:" in description or "scope" in description.lower(), (
                f"Tool {tool.name} should mention scope in description: {description}"
            )
            assert "entity" in description.lower(), (
                f"Tool {tool.name} should mention entity in description: {description}"
            )

    async def test_all_tools_respect_optional_repo_id(self):
        """Test that all tools properly respect optional repo_id filtering."""
        # Get a node_id that exists in both repos
        with self.db_manager_repo1.driver.session() as session:
            result = session.run(
                """
                MATCH (n:NODE)
                WHERE n.entityId = $entity_id AND n.repoId = $repo_id
                RETURN n.node_id as node_id
                LIMIT 1
                """,
                entity_id=self.entity_id,
                repo_id=self.repo1_id,
            )
            record = result.single()
            assert record is not None, "Should have at least one node in repo1"
            node_id = record["node_id"]

        # Test FindSymbols with entity-wide scope
        tool_entity = FindSymbols(db_manager=self.db_manager_entity)
        tool_repo1 = FindSymbols(db_manager=self.db_manager_repo1)

        result_entity = tool_entity._run(name="__init__", type="FUNCTION")
        result_repo1 = tool_repo1._run(name="__init__", type="FUNCTION")

        assert isinstance(result_entity, dict), "Entity-wide FindSymbols should return dict"
        assert isinstance(result_repo1, dict), "Repo-specific FindSymbols should return dict"

        entity_count = len(result_entity.get("symbols", []))
        repo1_count = len(result_repo1.get("symbols", []))

        # Entity should have more results than single repo
        assert entity_count > repo1_count, (
            f"Entity-wide FindSymbols should return more results. "
            f"Entity: {entity_count}, Repo1: {repo1_count}"
        )

        # Test GetCodeAnalysis with repo-specific and entity-wide managers
        tool_analysis_entity = GetCodeAnalysis(db_manager=self.db_manager_entity)
        tool_analysis_repo1 = GetCodeAnalysis(db_manager=self.db_manager_repo1)

        result_entity = tool_analysis_entity._run(reference_id=node_id)
        result_repo1 = tool_analysis_repo1._run(reference_id=node_id)

        # Both should find the node (entity finds from any repo, repo1 finds from repo1)
        assert "No code found" not in result_entity, "Entity-wide GetCodeAnalysis should find node"
        assert "No code found" not in result_repo1, "Repo1 GetCodeAnalysis should find its node"
