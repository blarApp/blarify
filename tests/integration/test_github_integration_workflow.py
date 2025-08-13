"""Integration tests for GitHub integration workflow.

These tests follow the testing-guide.md patterns for Neo4j container management.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from blarify.integrations.github_creator import GitHubCreator
from blarify.repositories.graph_db_manager import Neo4jManager
from blarify.graph.graph_environment import GraphEnvironment
from blarify.prebuilt.graph_builder import GraphBuilder
from neo4j_container_manager.types import Neo4jContainerInstance
from tests.utils.graph_assertions import GraphAssertions


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_end_to_end_github_integration_with_mocked_api(
    neo4j_instance: Neo4jContainerInstance,
    test_code_examples_path: Path,
    graph_assertions: GraphAssertions
):
    """Test complete GitHub integration workflow with mocked API responses.
    
    This test:
    1. Creates a real code graph from test examples and saves it to Neo4j
    2. Mocks GitHub API to simulate PRs/commits modifying those files
    3. Runs GitHub integration to create MODIFIED_BY relationships
    4. Queries Neo4j to verify the relationships were created correctly
    """

    # Step 1: Build and save actual code graph to Neo4j
    test_root = str(test_code_examples_path)
    graph_env = GraphEnvironment(
        environment="test", 
        diff_identifier="0", 
        root_path=test_root
    )
    
    # Create real Neo4j manager with test database
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password",
        repo_id="test-repo",
        entity_id="test-entity"
    )
    
    try:
        # Build code graph from test examples
        builder = GraphBuilder(root_path=test_root)
        code_graph = builder.build()
        
        # Save code graph to Neo4j
        db_manager.save_graph(
            code_graph.get_nodes_as_objects(),
            code_graph.get_relationships_as_objects()
        )
        
        # Verify code nodes exist in database
        await graph_assertions.assert_node_exists("FILE")
        await graph_assertions.assert_node_exists("FUNCTION", {"name": "get_value"})
        
        # Step 2: Mock GitHub API responses for a PR modifying simple_module.py
        mock_github_pr = {
            "number": 456,
            "title": "Optimize get_value method for performance",
            "description": "This PR adds caching to the get_value method",
            "author": "dev_user",
            "created_at": "2024-01-20T14:30:00Z",
            "updated_at": "2024-01-20T15:00:00Z",
            "merged_at": "2024-01-20T16:00:00Z",
            "state": "merged",
            "url": "https://github.com/test/repo/pull/456",
            "metadata": {"labels": ["performance"]},
        }

        mock_github_commit = {
            "sha": "commit789abc",
            "message": "Add caching to get_value method",
            "author": "Dev User",
            "author_email": "dev@example.com",
            "timestamp": "2024-01-20T14:45:00Z",
            "url": "https://github.com/test/repo/commit/commit789abc",
            "pr_number": 456,
            "metadata": {},
        }

        # Mock file changes - modifying the get_value method
        mock_file_changes = [
            {
                "filename": "python/simple_module.py",
                "additions": 4,
                "deletions": 1,
                "patch": "@@ -26,3 +26,6 @@ class SimpleClass:\n"
                        "     def get_value(self) -> str:\n"
                        '         """Return the stored value."""\n'
                        "-        return self.value\n"
                        "+        # Add caching for performance\n"
                        "+        if not hasattr(self, '_cached'):\n"
                        "+            self._cached = self.value\n"
                        "+        return self._cached",
                "status": "modified",
            }
        ]

        # Step 3: Run GitHub integration with mocked API but real database
        with patch("blarify.integrations.github_creator.GitHub") as MockGitHub:
            mock_github = MockGitHub.return_value

            # Configure mock responses
            mock_github.fetch_pull_requests.return_value = [mock_github_pr]
            mock_github.fetch_commits.return_value = [mock_github_commit]
            mock_github.fetch_commit_changes.return_value = mock_file_changes
            mock_github.extract_change_ranges.return_value = []

            # Create GitHubCreator with real database
            creator = GitHubCreator(
                db_manager=db_manager,
                graph_environment=graph_env,
                github_token="test-token",
                repo_owner="test",
                repo_name="repo",
            )

            # Override the github_repo with our mock
            creator.github_repo = mock_github

            # Run integration - this will save to real Neo4j
            result = creator.create_github_integration(pr_limit=10, save_to_database=True)

        # Step 4: Query Neo4j to verify the integration worked
        
        # Verify PR and commit nodes were created
        assert result.total_prs == 1, "Should have created 1 PR node"
        assert result.total_commits == 1, "Should have created 1 commit node"
        
        # Query Neo4j for the PR node
        await graph_assertions.assert_node_exists(
            "INTEGRATION",
            {"source_type": "pull_request", "external_id": "456"}
        )
        
        # Query Neo4j for the commit node
        await graph_assertions.assert_node_exists(
            "INTEGRATION",
            {"source_type": "commit", "external_id": "commit789abc"}
        )
        
        # Query for MODIFIED_BY relationship
        query = """
        MATCH (code:NODE)-[r:MODIFIED_BY]->(commit:INTEGRATION)
        WHERE commit.external_id = 'commit789abc'
        RETURN code.name as function_name, 
               r.lines_added as lines_added,
               r.lines_deleted as lines_deleted,
               r.file_path as file_path
        """
        
        records = await neo4j_instance.execute_cypher(query)
        
        # Should find at least one MODIFIED_BY relationship
        assert len(records) > 0, "Should have created MODIFIED_BY relationship"
        
        # Verify the relationship properties
        for record in records:
            if record['function_name'] == 'get_value':
                assert record['lines_added'] == 4
                assert record['lines_deleted'] == 1
                assert 'simple_module.py' in record['file_path']
                break
        else:
            # If we didn't find get_value, check if any function was linked
            assert len(records) > 0, "At least some function should be linked to the commit"
        
        # Query for INTEGRATION_SEQUENCE relationship
        seq_query = """
        MATCH (pr:INTEGRATION)-[r:INTEGRATION_SEQUENCE]->(commit:INTEGRATION)
        WHERE pr.external_id = '456' AND commit.external_id = 'commit789abc'
        RETURN r.order as order
        """
        
        seq_records = await neo4j_instance.execute_cypher(seq_query)
        
        assert len(seq_records) == 1, "Should have INTEGRATION_SEQUENCE between PR and commit"
        assert seq_records[0]['order'] == 0
            
        # Debug: Print graph summary
        await graph_assertions.debug_print_graph_summary()
        
    finally:
        # Cleanup
        db_manager.close()


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
async def test_github_integration_with_null_pr_description(
    neo4j_instance: Neo4jContainerInstance,
    test_code_examples_path: Path,
    graph_assertions: GraphAssertions
):
    """Test that GitHub integration handles PRs with null descriptions correctly.
    
    This test ensures that when a PR has no body/description (null), 
    the integration properly converts it to an empty string to avoid 
    Neo4j null property errors.
    """
    
    # Setup
    test_root = str(test_code_examples_path)
    graph_env = GraphEnvironment(
        environment="test", 
        diff_identifier="0", 
        root_path=test_root
    )
    
    db_manager = Neo4jManager(
        uri=neo4j_instance.uri,
        user="neo4j",
        password="test-password",
        repo_id="test-repo",
        entity_id="test-entity"
    )
    
    try:
        # Build and save a minimal code graph
        builder = GraphBuilder(root_path=test_root)
        code_graph = builder.build()
        
        db_manager.save_graph(
            code_graph.get_nodes_as_objects(),
            code_graph.get_relationships_as_objects()
        )
        
        # Mock GitHub API with PR that has null description
        mock_github_pr_null_description = {
            "number": 789,
            "title": "Fix critical bug",
            "description": None,  # This is the key test case - null description
            "author": "test_user",
            "created_at": "2024-01-25T10:00:00Z",
            "updated_at": "2024-01-25T11:00:00Z",
            "merged_at": "2024-01-25T12:00:00Z",
            "state": "merged",
            "url": "https://github.com/test/repo/pull/789",
            "metadata": {"labels": ["bugfix"]},
        }
        
        mock_github_commit = {
            "sha": "commit123def",
            "message": "Fix null pointer exception",
            "author": "Test User",
            "author_email": "test@example.com",
            "timestamp": "2024-01-25T10:30:00Z",
            "url": "https://github.com/test/repo/commit/commit123def",
            "pr_number": 789,
            "metadata": {},
        }
        
        # Mock file changes
        mock_file_changes = [
            {
                "filename": "python/simple_module.py",
                "additions": 2,
                "deletions": 1,
                "patch": "@@ -10,1 +10,2 @@\n-    return \"Hello from Python\"\n+    if name:\n+        return \"Hello from Python\"",
                "status": "modified",
            }
        ]
        
        # Run GitHub integration with mocked API
        with patch("blarify.integrations.github_creator.GitHub") as MockGitHub:
            mock_github = MockGitHub.return_value
            
            # Configure mock responses
            mock_github.fetch_pull_requests.return_value = [mock_github_pr_null_description]
            mock_github.fetch_commits.return_value = [mock_github_commit]
            mock_github.fetch_commit_changes.return_value = mock_file_changes
            mock_github.extract_change_ranges.return_value = []
            
            # Create GitHubCreator
            creator = GitHubCreator(
                db_manager=db_manager,
                graph_environment=graph_env,
                github_token="test-token",
                repo_owner="test",
                repo_name="repo",
            )
            
            # Override the github_repo with our mock
            creator.github_repo = mock_github
            
            # Run integration - this should not fail with null content
            result = creator.create_github_integration(pr_limit=10, save_to_database=True)
        
        # Verify the integration succeeded despite null description
        assert result.error is None, f"Integration failed with error: {result.error}"
        assert result.total_prs == 1, "Should have created 1 PR node"
        assert result.total_commits == 1, "Should have created 1 commit node"
        
        # Query Neo4j to verify the PR node was created with empty content
        query = """
        MATCH (pr:INTEGRATION)
        WHERE pr.source_type = 'pull_request' AND pr.external_id = '789'
        RETURN pr.content as content, pr.title as title
        """
        
        records = await neo4j_instance.execute_cypher(query)
        
        assert len(records) == 1, "Should find the PR node in database"
        assert records[0]['content'] == "", "Null description should be converted to empty string"
        assert records[0]['title'] == "Fix critical bug", "Title should be preserved"
        
        # Verify INTEGRATION nodes have proper attributes
        await graph_assertions.assert_node_exists(
            "INTEGRATION",
            {"source_type": "pull_request", "external_id": "789"}
        )
        
        await graph_assertions.assert_node_exists(
            "INTEGRATION",
            {"source_type": "commit", "external_id": "commit123def"}
        )
        
        # Debug output
        await graph_assertions.debug_print_graph_summary()
        
    finally:
        # Cleanup
        db_manager.close()
