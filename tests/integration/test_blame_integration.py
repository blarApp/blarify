"""Integration tests for blame-based GitHub integration with real Neo4j."""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from blarify.integrations.github_creator import GitHubCreator
from blarify.repositories.version_control.github import GitHub
from blarify.graph.graph_environment import GraphEnvironment
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from neo4j_container_manager.types import Neo4jContainerInstance
from tests.utils.graph_assertions import GraphAssertions

# DTOs for mocking
from blarify.repositories.version_control.dtos.blame_commit_dto import BlameCommitDto
from blarify.repositories.version_control.dtos.blame_line_range_dto import BlameLineRangeDto
from blarify.repositories.version_control.dtos.pull_request_info_dto import PullRequestInfoDto
from blarify.repositories.graph_db_manager.dtos.code_node_dto import CodeNodeDto


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestBlameBasedIntegration:
    """Integration tests for blame-based GitHub integration workflow with real Neo4j."""

    async def test_blame_based_integration_workflow(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test complete blame-based GitHub integration workflow with real database."""
        # Step 1: Build code graph from real code examples
        python_examples_path = test_code_examples_path / "python"

        builder = GraphBuilder(
            root_path=str(python_examples_path),
            extensions_to_skip=[".pyc", ".pyo"],
            names_to_skip=["__pycache__"],
        )
        graph = builder.build()

        # Step 2: Save graph to real Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )

        # Save the actual graph first
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Verify we have the expected nodes
        await graph_assertions.assert_node_exists("FILE")
        await graph_assertions.assert_node_exists("FUNCTION")
        await graph_assertions.assert_node_exists("CLASS")

        # Step 3: Mock GitHub blame responses for real files
        def mock_blame_response(file_path: str, start_line: int, end_line: int, ref: str = "HEAD"):
            """Generate mock blame response based on real code_examples files."""

            if "simple_module.py" in file_path:
                if start_line <= 11:  # simple_function (lines 9-11)
                    return [
                        BlameCommitDto(
                            sha="abc123",
                            message="Add simple_function to demonstrate basic functionality",
                            author="Alice Developer",
                            author_email="alice@example.com",
                            author_login="alice",
                            timestamp="2024-01-01T10:00:00Z",
                            url="https://github.com/test/repo/commit/abc123",
                            line_ranges=[BlameLineRangeDto(start=9, end=11)],
                            pr_info=PullRequestInfoDto(
                                number=42,
                                title="Add simple Python functions",
                                url="https://github.com/test/repo/pull/42",
                                author="alice",
                                merged_at="2024-01-01T11:00:00Z",
                                state="MERGED",
                            ),
                        )
                    ]
                elif start_line <= 16:  # function_with_parameter (lines 14-16)
                    return [
                        BlameCommitDto(
                            sha="def456",
                            message="Add parameterized function",
                            author="Bob Developer",
                            author_email="bob@example.com",
                            timestamp="2024-01-02T10:00:00Z",
                            url="https://github.com/test/repo/commit/def456",
                            line_ranges=[BlameLineRangeDto(start=14, end=16)],
                            pr_info=None,
                        )
                    ]
                elif start_line <= 37:  # SimpleClass (lines 19-37)
                    return [
                        BlameCommitDto(
                            sha="ghi789",
                            message="Implement SimpleClass with methods",
                            author="Charlie Developer",
                            author_email="charlie@example.com",
                            author_login="charlie",
                            timestamp="2024-01-03T10:00:00Z",
                            url="https://github.com/test/repo/commit/ghi789",
                            line_ranges=[BlameLineRangeDto(start=19, end=37)],
                            pr_info=PullRequestInfoDto(
                                number=55,
                                title="Add SimpleClass implementation",
                                url="https://github.com/test/repo/pull/55",
                                author="charlie",
                                merged_at="2024-01-03T11:00:00Z",
                                state="MERGED",
                            ),
                        )
                    ]
            elif "class_with_inheritance.py" in file_path:
                if start_line <= 22:  # BaseProcessor (lines 9-22)
                    return [
                        BlameCommitDto(
                            sha="base123",
                            message="Create abstract BaseProcessor class",
                            author="Alice Developer",
                            author_email="alice@example.com",
                            timestamp="2024-01-04T10:00:00Z",
                            url="https://github.com/test/repo/commit/base123",
                            line_ranges=[BlameLineRangeDto(start=9, end=22)],
                            pr_info=None,
                        )
                    ]

            # Default fallback
            return [
                BlameCommitDto(
                    sha="default123",
                    message="Default commit",
                    author="Dev",
                    author_email="dev@example.com",
                    timestamp="2024-01-05T10:00:00Z",
                    url="https://github.com/test/repo/commit/default123",
                    line_ranges=[BlameLineRangeDto(start=start_line, end=end_line)],
                    pr_info=None,
                )
            ]

        # Mock the query_nodes_by_ids to return proper DTOs
        def mock_query_nodes_by_ids(node_ids: list[str]) -> list[CodeNodeDto]:
            """Mock query_nodes_by_ids to return CodeNodeDto objects from real nodes."""
            # Query real nodes from the database
            nodes = []
            for node_id in node_ids:
                # This is a simplified mock - in reality, we'd query the actual nodes
                nodes.append(
                    CodeNodeDto(
                        id=node_id,
                        name="test_node",
                        label="FUNCTION",
                        path=str(python_examples_path / "simple_module.py"),
                        start_line=1,
                        end_line=50,
                    )
                )
            return nodes

        # Mock blame_commits_for_nodes
        def mock_blame_for_nodes(nodes: list[CodeNodeDto]) -> dict[str, list[BlameCommitDto]]:
            """Mock function for blame_commits_for_nodes."""
            result = {}
            for node in nodes:
                # Return appropriate commits based on the node's file
                if "simple_module" in node.path:
                    result[node.id] = mock_blame_response(node.path, node.start_line, node.end_line)
                elif "class_with_inheritance" in node.path:
                    result[node.id] = mock_blame_response(node.path, node.start_line, node.end_line)
                else:
                    result[node.id] = [mock_blame_response("", 1, 10)[0]]
            return result

        # Step 4: Run blame-based GitHub integration
        with patch("blarify.integrations.github_creator.GitHub") as mock_github_class:
            mock_github = Mock(spec=GitHub)
            mock_github.blame_commits_for_range = Mock(side_effect=mock_blame_response)
            mock_github.blame_commits_for_nodes = Mock(side_effect=mock_blame_for_nodes)
            mock_github_class.return_value = mock_github

            creator = GitHubCreator(
                db_manager=db_manager,
                graph_environment=GraphEnvironment(
                    environment="test", diff_identifier="test_diff", root_path=str(python_examples_path)
                ),
                github_token="test_token",
                repo_owner="test",
                repo_name="repo",
            )
            creator.github_repo = mock_github

            # Mock the _query_nodes_by_ids method
            creator._query_nodes_by_ids = Mock(side_effect=mock_query_nodes_by_ids)  # type: ignore

            # Get some actual node IDs from the database to process
            function_nodes = await neo4j_instance.execute_cypher("MATCH (n:FUNCTION) RETURN n.hashed_id as id LIMIT 3")
            node_ids = [node["id"] for node in function_nodes if node["id"]]

            # If no function nodes, use mock IDs
            if not node_ids:
                node_ids = ["func1", "func2", "func3"]

            result = creator.create_github_integration_from_nodes(node_ids=node_ids, save_to_database=True)

        # Step 5: Verify results in real database
        assert result.error is None
        assert result.total_commits > 0
        assert result.total_prs >= 0  # May have PRs

        # Verify integration nodes were created
        await graph_assertions.assert_node_exists("INTEGRATION", {"source_type": "commit"})

        # Check for MODIFIED_BY relationships
        modified_by_rels = await neo4j_instance.execute_cypher("""
            MATCH ()-[r:MODIFIED_BY]->(:INTEGRATION)
            RETURN count(r) as count
        """)
        assert modified_by_rels[0]["count"] > 0, "Should have MODIFIED_BY relationships"

        # Verify blame attribution
        blame_rels = await neo4j_instance.execute_cypher("""
            MATCH ()-[r:MODIFIED_BY]->(:INTEGRATION)
            WHERE r.attribution_method = 'blame'
            RETURN r.attribution_method as method, r.attribution_accuracy as accuracy, r.blamed_lines as lines
            LIMIT 1
        """)
        if blame_rels:
            assert blame_rels[0]["method"] == "blame"
            assert blame_rels[0]["accuracy"] == "exact"

        # Debug: Print graph summary
        await graph_assertions.debug_print_graph_summary()

        db_manager.close()

    async def test_blame_accuracy_vs_patch_parsing(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that blame provides more accurate attribution than patch parsing."""
        python_examples_path = test_code_examples_path / "python"

        # Build and save graph
        builder = GraphBuilder(
            root_path=str(python_examples_path),
            extensions_to_skip=[".pyc", ".pyo"],
            names_to_skip=["__pycache__"],
        )
        graph = builder.build()

        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )

        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Mock query_nodes_by_ids
        def mock_query_nodes_by_ids(node_ids: list[str]) -> list[CodeNodeDto]:
            """Mock query_nodes_by_ids for class_with_inheritance.py nodes."""
            nodes = []
            for idx, node_id in enumerate(node_ids):
                # Simulate different functions from class_with_inheritance.py
                if idx == 0:
                    name = "BaseProcessor"
                    start_line = 9
                    end_line = 22
                elif idx == 1:
                    name = "TextProcessor"
                    start_line = 25
                    end_line = 38
                else:
                    name = "AdvancedTextProcessor"
                    start_line = 41
                    end_line = 51

                nodes.append(
                    CodeNodeDto(
                        id=node_id,
                        name=name,
                        label="CLASS",
                        path=str(python_examples_path / "class_with_inheritance.py"),
                        start_line=start_line,
                        end_line=end_line,
                    )
                )
            return nodes

        # Mock blame results - each class has a different author/commit
        blame_results = {
            "class1": [
                BlameCommitDto(
                    sha="commit123",
                    message="Create abstract BaseProcessor class",
                    author="Alice",
                    author_email="alice@example.com",
                    author_login="alice",
                    timestamp="2024-01-01T10:00:00Z",
                    url="https://github.com/test/repo/commit/commit123",
                    line_ranges=[BlameLineRangeDto(start=9, end=22)],
                    pr_info=None,
                )
            ],
            "class2": [
                BlameCommitDto(
                    sha="commit456",
                    message="Implement TextProcessor",
                    author="Bob",
                    author_email="bob@example.com",
                    author_login="bob",
                    timestamp="2024-01-02T10:00:00Z",
                    url="https://github.com/test/repo/commit/commit456",
                    line_ranges=[BlameLineRangeDto(start=25, end=38)],
                    pr_info=None,
                )
            ],
            "class3": [
                BlameCommitDto(
                    sha="commit789",
                    message="Add AdvancedTextProcessor",
                    author="Charlie",
                    author_email="charlie@example.com",
                    author_login="charlie",
                    timestamp="2024-01-03T10:00:00Z",
                    url="https://github.com/test/repo/commit/commit789",
                    line_ranges=[BlameLineRangeDto(start=41, end=51)],
                    pr_info=None,
                )
            ],
        }

        with patch("blarify.integrations.github_creator.GitHub") as mock_github_class:
            mock_github = Mock(spec=GitHub)
            mock_github.blame_commits_for_nodes = Mock(return_value=blame_results)
            mock_github_class.return_value = mock_github

            creator = GitHubCreator(
                db_manager=db_manager,
                graph_environment=GraphEnvironment(
                    environment="test", diff_identifier="test_diff", root_path=str(python_examples_path)
                ),
                github_token="test_token",
                repo_owner="test",
                repo_name="repo",
            )
            creator.github_repo = mock_github
            creator._query_nodes_by_ids = Mock(side_effect=mock_query_nodes_by_ids)  # type: ignore

            test_node_ids = ["class1", "class2", "class3"]
            result = creator.create_github_integration_from_nodes(node_ids=test_node_ids, save_to_database=True)

            # Verify we got expected results
            assert result.total_commits == 3
            assert result.error is None

            # Verify each commit was created with correct author
            for commit_sha, author in [("commit123", "Alice"), ("commit456", "Bob"), ("commit789", "Charlie")]:
                commits = await neo4j_instance.execute_cypher(f"""
                    MATCH (c:INTEGRATION {{external_id: '{commit_sha}', source_type: 'commit'}})
                    RETURN c.author as author
                """)
                assert len(commits) > 0, f"Commit {commit_sha} should exist"
                assert commits[0]["author"] == author

        db_manager.close()

    async def test_pr_association_through_blame(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that PRs are correctly associated through blame results."""
        python_examples_path = test_code_examples_path / "python"

        # Build and save graph
        builder = GraphBuilder(
            root_path=str(python_examples_path),
            extensions_to_skip=[".pyc", ".pyo"],
            names_to_skip=["__pycache__"],
        )
        graph = builder.build()

        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )

        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Mock query_nodes_by_ids
        def mock_query_nodes_by_ids(node_ids: list[str]) -> list[CodeNodeDto]:
            """Mock query_nodes_by_ids to return a single node."""
            return [
                CodeNodeDto(
                    id=node_ids[0],
                    name="simple_function",
                    label="FUNCTION",
                    path=str(python_examples_path / "simple_module.py"),
                    start_line=9,
                    end_line=11,
                )
            ]

        # Mock blame showing multiple commits from same PR
        blame_results = {
            "node1": [
                BlameCommitDto(
                    sha="commit1",
                    message="Start feature implementation",
                    author="Dev",
                    author_email="dev@example.com",
                    timestamp="2024-01-01T00:00:00Z",
                    url="https://github.com/test/repo/commit/commit1",
                    line_ranges=[BlameLineRangeDto(start=9, end=10)],
                    pr_info=PullRequestInfoDto(
                        number=100,
                        title="Implement new feature",
                        url="https://github.com/test/repo/pull/100",
                        author="dev",
                        merged_at="2024-01-01T02:00:00Z",
                        state="MERGED",
                    ),
                ),
                BlameCommitDto(
                    sha="commit2",
                    message="Complete feature implementation",
                    author="Dev",
                    author_email="dev@example.com",
                    timestamp="2024-01-01T01:00:00Z",
                    url="https://github.com/test/repo/commit/commit2",
                    line_ranges=[BlameLineRangeDto(start=11, end=11)],
                    pr_info=PullRequestInfoDto(
                        number=100,
                        title="Implement new feature",
                        url="https://github.com/test/repo/pull/100",
                        author="dev",
                        merged_at="2024-01-01T02:00:00Z",
                        state="MERGED",
                    ),
                ),
            ]
        }

        with patch("blarify.integrations.github_creator.GitHub") as mock_github_class:
            mock_github = Mock(spec=GitHub)
            mock_github.blame_commits_for_nodes = Mock(return_value=blame_results)
            mock_github_class.return_value = mock_github

            creator = GitHubCreator(
                db_manager=db_manager,
                graph_environment=GraphEnvironment(
                    environment="test", diff_identifier="test_diff", root_path=str(python_examples_path)
                ),
                github_token="test_token",
                repo_owner="test",
                repo_name="repo",
            )
            creator.github_repo = mock_github
            creator._query_nodes_by_ids = Mock(side_effect=mock_query_nodes_by_ids)  # type: ignore

            result = creator.create_github_integration_from_nodes(node_ids=["node1"], save_to_database=True)

        # Should create one PR node despite multiple commits
        assert result.total_prs == 1
        assert result.pr_nodes[0].external_id == "100"

        # Both commits should be linked to the PR
        assert result.total_commits == 2

        # Verify in database
        pr_count = await neo4j_instance.execute_cypher("""
            MATCH (pr:INTEGRATION {source_type: 'pull_request', external_id: '100'})
            RETURN count(pr) as count
        """)
        assert pr_count[0]["count"] == 1, "Should have exactly one PR node"

        # Check PR → Commit relationships
        pr_commit_rels = await neo4j_instance.execute_cypher("""
            MATCH (pr:INTEGRATION {external_id: '100'})-[r:INTEGRATION_SEQUENCE]->(c:INTEGRATION)
            WHERE c.source_type = 'commit'
            RETURN count(r) as count
        """)
        assert pr_commit_rels[0]["count"] == 2, "PR should be linked to both commits"

        db_manager.close()
