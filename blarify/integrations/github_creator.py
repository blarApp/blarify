"""GitHub integration creator for Blarify.

This module provides the GitHubCreator class that orchestrates the creation
of GitHub integration nodes and relationships in the graph database.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, cast, Sequence
from dataclasses import dataclass, field

from blarify.graph.node.commit_node import CommitNode
from blarify.graph.node.pr_node import PullRequestNode
from blarify.repositories.graph_db_manager import AbstractDbManager
from blarify.repositories.graph_db_manager.queries import get_code_nodes_by_ids_query
from blarify.repositories.graph_db_manager.dtos.code_node_dto import CodeNodeDto
from blarify.repositories.version_control.dtos.blame_commit_dto import BlameCommitDto
from blarify.repositories.version_control.github import GitHub
from blarify.graph.graph_environment import GraphEnvironment
from blarify.graph.node.types.integration_node import IntegrationNode
from blarify.graph.relationship.relationship_creator import RelationshipCreator

logger = logging.getLogger(__name__)


@dataclass
class GitHubIntegrationResult:
    """Result of GitHub integration creation."""

    total_prs: int = 0
    total_commits: int = 0
    pr_nodes: List[PullRequestNode] = field(default_factory=list)
    commit_nodes: List[CommitNode] = field(default_factory=list)
    relationships: List[Any] = field(default_factory=list)
    error: Optional[str] = None


class GitHubCreator:
    """Orchestrates GitHub integration creation in the graph database.

    This class follows the pattern of DocumentationCreator and WorkflowCreator,
    operating independently and assuming the code graph already exists.
    """

    def __init__(
        self,
        db_manager: AbstractDbManager,
        graph_environment: GraphEnvironment,
        repo_owner: str,
        repo_name: str,
        github_token: Optional[str] = None,
        ref: str = "HEAD",
    ):
        """Initialize GitHubCreator.

        Args:
            db_manager: Database manager for graph operations
            graph_environment: Graph environment configuration
            github_token: GitHub personal access token
            repo_owner: Repository owner/organization
            repo_name: Repository name
            ref: Git ref (branch, tag, commit SHA) to blame at
        """
        self.db_manager = db_manager
        self.graph_environment = graph_environment
        self.ref = ref
        self.github_repo = GitHub(token=github_token, repo_owner=repo_owner, repo_name=repo_name, ref=ref)

    def create_github_integration(
        self,
        pr_limit: int = 50,
        since_date: Optional[str] = None,
        save_to_database: bool = True,
    ) -> GitHubIntegrationResult:
        """Create GitHub integration nodes and relationships.

        Main orchestration method that fetches GitHub data and creates
        integration nodes in the graph database.

        Args:
            pr_limit: Maximum number of PRs to process
            since_date: Process PRs created after this date
            save_to_database: Whether to save to database

        Returns:
            GitHubIntegrationResult with created nodes and relationships
        """
        result = GitHubIntegrationResult()

        try:
            all_pr_nodes = []
            all_commit_nodes = []
            all_relationships = []

            # Fetch PRs from GitHub if requested
            if pr_limit > 0:
                logger.info(f"Fetching up to {pr_limit} pull requests from GitHub")
                prs = self.github_repo.fetch_pull_requests(limit=pr_limit)

                # Process each PR
                for pr_data in prs:
                    logger.info(f"Processing PR #{pr_data['number']}: {pr_data['title']}")

                    pr_node, commit_nodes = self._process_pr(pr_data)
                    all_pr_nodes.append(pr_node)
                    all_commit_nodes.extend(commit_nodes)

                    # Create PR → Commit relationships
                    if commit_nodes:
                        sequence_rels = RelationshipCreator.create_integration_sequence_relationships(
                            pr_node, cast(List[Any], commit_nodes)
                        )
                        all_relationships.extend(sequence_rels)

                if not prs:
                    logger.info("No pull requests found")
            else:
                # If pr_limit is 0, we might want to fetch direct commits
                logger.info("Fetching commits without PRs")
                commits = self.github_repo.fetch_commits(limit=100)

                for commit_data in commits:
                    commit_node = IntegrationNode(
                        source="github",
                        source_type="commit",
                        external_id=commit_data["sha"],
                        title=commit_data["message"].split("\n")[0],
                        content=commit_data["message"],
                        timestamp=commit_data["timestamp"],
                        author=commit_data["author"],
                        url=commit_data["url"],
                        metadata=commit_data.get("metadata", {}),
                        graph_environment=self.graph_environment,
                        level=0,
                    )
                    all_commit_nodes.append(commit_node)

            # Map commits to code nodes
            logger.info("Mapping commits to existing code nodes")
            code_relationships = self._map_commits_to_code(all_commit_nodes)
            all_relationships.extend(code_relationships)

            # Save to database if requested
            if save_to_database:
                logger.info("Saving integration nodes and relationships to database")
                self._save_to_database(all_pr_nodes + all_commit_nodes, all_relationships)

            # Populate result
            result.total_prs = len(all_pr_nodes)
            result.total_commits = len(all_commit_nodes)
            result.pr_nodes = all_pr_nodes
            result.commit_nodes = all_commit_nodes
            result.relationships = all_relationships

            logger.info(f"Successfully created {result.total_prs} PRs and {result.total_commits} commits")

        except Exception as e:
            logger.error(f"Error creating GitHub integration: {e}")
            result.error = str(e)

        return result

    def _process_pr(self, pr_data: Dict[str, Any]) -> Tuple[IntegrationNode, List[IntegrationNode]]:
        """Process a single PR and its commits.

        Args:
            pr_data: PR data from GitHub API

        Returns:
            Tuple of (pr_node, list of commit_nodes)
        """
        # Create PR node
        pr_node = PullRequestNode(
            external_id=str(pr_data["number"]),
            title=pr_data["title"],
            description=pr_data.get("description") or "",
            timestamp=pr_data["created_at"],
            author=pr_data["author"],
            url=pr_data["url"],
            metadata={
                "state": pr_data["state"],
                "merged_at": pr_data.get("merged_at"),
                "updated_at": pr_data["updated_at"],
                **pr_data.get("metadata", {}),
            },
            graph_environment=self.graph_environment,
        )

        # Fetch commits for this PR
        commits_data = self.github_repo.fetch_commits(pr_number=pr_data["number"])
        commit_nodes = []

        for commit_data in commits_data:
            # Fetch the full patch for this commit
            patch_text = self.github_repo.fetch_commit_patch(commit_data["sha"])

            commit_node = CommitNode(
                external_id=commit_data["sha"],
                title=commit_data["message"].split("\n")[0],  # First line of message
                diff_text=patch_text if patch_text else "",  # Use patch as diff_text
                timestamp=commit_data["timestamp"],
                author=commit_data["author"],
                url=commit_data["url"],
                metadata={
                    "pr_number": pr_data["number"],
                    "author_email": commit_data.get("author_email"),
                    "commit_message": commit_data["message"],  # Store full message in metadata
                    "has_patch": bool(patch_text),
                    **commit_data.get("metadata", {}),
                },
                graph_environment=self.graph_environment,
            )
            commit_nodes.append(commit_node)

        logger.info(f"Created PR node and {len(commit_nodes)} commit nodes for PR #{pr_data['number']}")
        return pr_node, commit_nodes

    def _map_commits_to_code(self, commit_nodes: List[IntegrationNode]) -> List[Any]:
        """Map commits to existing code nodes and create MODIFIED_BY relationships.

        Args:
            commit_nodes: List of commit IntegrationNodes

        Returns:
            List of MODIFIED_BY relationships
        """
        relationships = []

        for commit_node in commit_nodes:
            try:
                # Fetch file changes for this commit
                file_changes = self.github_repo.fetch_commit_changes(commit_node.external_id)

                for file_change in file_changes:
                    # Find ALL code nodes affected by this file change
                    affected_nodes = self._find_affected_code_nodes(file_change["filename"], file_change)

                    if affected_nodes:
                        # Create MODIFIED_BY relationships for all affected nodes
                        for code_node in affected_nodes:
                            rel = RelationshipCreator.create_modified_by_relationships(
                                commit_node, [code_node], [file_change]
                            )
                            relationships.extend(rel)

            except Exception as e:
                logger.error(f"Error mapping commit {commit_node.external_id} to code: {e}")

        logger.info(f"Created {len(relationships)} MODIFIED_BY relationships")
        return relationships

    def _find_affected_code_nodes(self, file_path: str, file_change: Dict[str, Any]) -> List[Any]:
        """Find ALL code nodes affected by file changes.

        Uses the patch to identify specific line ranges that were changed,
        then queries for all nodes that overlap with those ranges.

        Args:
            file_path: Path to the changed file
            file_change: File change data with patch information

        Returns:
            List of affected code nodes
        """
        affected_nodes = []
        seen_node_ids = set()  # Track which nodes we've already found

        # Extract line ranges from the patch
        change_ranges = []
        if "patch" in file_change:
            change_ranges = self.github_repo.extract_change_ranges(file_change["patch"])

        if not change_ranges:
            # If no patch, just return the FILE node
            query = """
            MATCH (n:NODE)
            WHERE n.path CONTAINS $file_path
              AND n.layer = 'code'
              AND n.label = 'FILE'
            RETURN n.node_id as node_id,
                   n.name as name,
                   n.label as label,
                   n.path as path,
                   n.start_line as start_line,
                   n.end_line as end_line
            """
            params = {"file_path": file_path}
            results = self.db_manager.query(query, params)

            for node_data in results:
                # Create mock node object
                mock_node = type(
                    "MockNode",
                    (),
                    {
                        "hashed_id": node_data["node_id"],
                        "name": node_data["name"],
                        "label": node_data["label"],
                        "path": node_data["path"],
                        "start_line": node_data.get("start_line"),
                        "end_line": node_data.get("end_line"),
                    },
                )()

                affected_nodes.append(mock_node)

            return affected_nodes

        # Query for each change range
        for change in change_ranges:
            # Use addition ranges since they represent the new file state
            if change["type"] == "addition":
                change_start = change.get("line_start", 0)
                change_end = change.get("line_end", 0)

                # Query for nodes that overlap with this change range
                query = """
                MATCH (n:NODE)
                WHERE n.path CONTAINS $file_path
                  AND n.layer = 'code'
                  AND n.label IN ['FUNCTION', 'CLASS']
                  AND n.start_line <= $change_end
                  AND n.end_line >= $change_start
                RETURN n.node_id as node_id,
                       n.name as name,
                       n.label as label,
                       n.path as path,
                       n.start_line as start_line,
                       n.end_line as end_line
                ORDER BY 
                  CASE n.label
                    WHEN 'FUNCTION' THEN 1
                    WHEN 'CLASS' THEN 2
                    ELSE 3
                  END
                """

                params = {"file_path": file_path, "change_start": change_start, "change_end": change_end}

                results = self.db_manager.query(query, params)

                for node_data in results:
                    # Skip if we've already found this node
                    if node_data["node_id"] in seen_node_ids:
                        continue

                    seen_node_ids.add(node_data["node_id"])

                    # Create mock node object
                    mock_node = type(
                        "MockNode",
                        (),
                        {
                            "hashed_id": node_data["node_id"],
                            "name": node_data["name"],
                            "label": node_data["label"],
                            "path": node_data["path"],
                            "start_line": node_data.get("start_line"),
                            "end_line": node_data.get("end_line"),
                        },
                    )()

                    affected_nodes.append(mock_node)
                    logger.debug(
                        f"  Found affected {node_data['label']} {node_data['name']} for lines {change_start}-{change_end}"
                    )

        if not affected_nodes:
            logger.warning(f"No code nodes found for changes in file: {file_path}")
        else:
            logger.debug(f"Found {len(affected_nodes)} total affected nodes in {file_path}")

        return affected_nodes

    def _save_to_database(self, nodes: Sequence[IntegrationNode], relationships: List[Any]):
        """Save integration nodes and relationships to the database.

        Args:
            nodes: Sequence of IntegrationNodes to save
            relationships: List of relationships to save
        """
        # Convert nodes to objects for database
        node_objects = [node.as_object() for node in nodes]

        # Convert relationships to objects
        rel_objects = []
        for rel in relationships:
            if hasattr(rel, "as_object"):
                rel_objects.append(rel.as_object())
            else:
                # Handle raw relationship dictionaries
                rel_objects.append(rel)

        # Save to database
        self.db_manager.save_graph(node_objects, rel_objects)

        logger.info(f"Saved {len(node_objects)} nodes and {len(rel_objects)} relationships to database")

    def _query_all_code_nodes(self) -> List[CodeNodeDto]:
        """Query all code nodes from database.

        Returns:
            List of CodeNodeDto objects
        """
        query = """
        MATCH (n:NODE)
        WHERE n.layer = 'code'
          AND n.label IN ['FUNCTION', 'CLASS']
        RETURN n.node_id as node_id,
               n.path as path,
               n.start_line as start_line,
               n.end_line as end_line,
               n.name as name,
               n.label as label
        """

        results = self.db_manager.query(query)
        logger.info(f"Found {len(results)} code nodes in database")

        # Convert to DTOs
        nodes = []
        for row in results:
            nodes.append(
                CodeNodeDto(
                    id=row["node_id"],
                    name=row["name"],
                    label=row["label"],
                    path=row["path"],
                    start_line=row["start_line"],
                    end_line=row["end_line"],
                )
            )
        return nodes

    def _query_nodes_by_ids(self, node_ids: List[str]) -> List[CodeNodeDto]:
        """Query specific code nodes by their IDs.

        Args:
            node_ids: List of node IDs to query

        Returns:
            List of CodeNodeDto objects
        """
        if not node_ids:
            return []

        query = get_code_nodes_by_ids_query()
        params = {
            "node_ids": node_ids,
        }

        results = self.db_manager.query(query, params)
        logger.info(f"Found {len(results)} code nodes for {len(node_ids)} IDs")

        # Convert to DTOs
        nodes = []
        for row in results:
            nodes.append(
                CodeNodeDto(
                    id=row["id"],
                    name=row["name"],
                    label=row["label"],
                    path=row["path"],
                    start_line=row["start_line"],
                    end_line=row["end_line"],
                )
            )
        return nodes

    def create_github_integration_from_nodes(
        self, node_ids: Optional[List[str]] = None, save_to_database: bool = True
    ) -> GitHubIntegrationResult:
        """Create GitHub integration for specific code nodes using blame.

        This is the new approach that starts with existing code nodes
        and uses GitHub's blame API to find exactly which commits
        modified those nodes.

        Args:
            node_ids: List of node IDs to process (if None, queries all from DB)
            save_to_database: Whether to save results to database

        Returns:
            GitHubIntegrationResult with created nodes and relationships
        """
        result = GitHubIntegrationResult()

        try:
            # Get nodes to process
            if node_ids is None:
                nodes = self._query_all_code_nodes()
            else:
                # Query nodes by IDs
                nodes = self._query_nodes_by_ids(node_ids)

            if not nodes:
                logger.info("No code nodes to process")
                return result

            logger.info(f"Processing {len(nodes)} code nodes with blame")

            # Get blame commits for all nodes
            blame_results = self.github_repo.blame_commits_for_nodes(nodes)

            # Create integration nodes from blame results
            pr_nodes, commit_nodes = self._create_integration_nodes_from_blame(blame_results)

            # Create relationships
            relationships = []

            # Create MODIFIED_BY relationships with exact blame attribution
            for node_id, commits in blame_results.items():
                node = next((n for n in nodes if n.id == node_id), None)
                if not node:
                    continue

                for commit_data in commits:
                    commit_node = next((c for c in commit_nodes if c.external_id == commit_data.sha), None)
                    if not commit_node:
                        continue

                    # Extract relevant patch for this specific node
                    relevant_patch = ""
                    if commit_node.content:  # diff_text is stored as content
                        relevant_patch = self.github_repo.extract_relevant_patch(
                            commit_node.content, node.path, node.start_line, node.end_line
                        )

                    rel = RelationshipCreator.create_modified_by_with_blame(
                        commit_node=commit_node,
                        code_node=node,
                        line_ranges=commit_data.line_ranges,
                        relevant_patch=relevant_patch,
                    )
                    relationships.append(rel)

            # Create PR → Commit relationships
            for pr_node in pr_nodes:
                pr_commits = [c for c in commit_nodes if c.metadata.get("pr_number") == int(pr_node.external_id)]
                if pr_commits:
                    sequence_rels = RelationshipCreator.create_integration_sequence_relationships(
                        pr_node, cast(List[Any], pr_commits)
                    )
                    relationships.extend(sequence_rels)

            # Save to database
            if save_to_database:
                self._save_to_database(pr_nodes + commit_nodes, relationships)

            # Populate result
            result.total_prs = len(pr_nodes)
            result.total_commits = len(commit_nodes)
            result.pr_nodes = pr_nodes
            result.commit_nodes = commit_nodes
            result.relationships = relationships

            logger.info(f"Created {result.total_prs} PRs and {result.total_commits} commits from blame")

        except Exception as e:
            logger.error(f"Error creating GitHub integration from nodes: {e}")
            result.error = str(e)

        return result

    def _create_integration_nodes_from_blame(
        self, blame_results: Dict[str, List[BlameCommitDto]]
    ) -> Tuple[List[PullRequestNode], List[CommitNode]]:
        """Create PR and commit nodes from blame results.

        Args:
            blame_results: Dictionary mapping node IDs to commit lists

        Returns:
            Tuple of (pr_nodes, commit_nodes)
        """
        pr_nodes: List[PullRequestNode] = []
        commit_nodes: List[CommitNode] = []
        seen_prs = set()
        seen_commits = set()

        for _, commits in blame_results.items():
            for commit_data in commits:
                # Create commit node if not seen
                sha = commit_data.sha
                if sha not in seen_commits:
                    seen_commits.add(sha)

                    # Fetch the patch for this commit
                    patch_text = self.github_repo.fetch_commit_patch(sha)

                    # Store PR number in metadata if available
                    metadata = {
                        "author_email": commit_data.author_email,
                        "author_login": commit_data.author_login,
                        "additions": commit_data.additions,
                        "deletions": commit_data.deletions,
                        "commit_message": commit_data.message,
                        "has_patch": bool(patch_text),
                    }
                    if commit_data.pr_info:
                        metadata["pr_number"] = commit_data.pr_info.number

                    commit_node = CommitNode(
                        external_id=sha,
                        title=commit_data.message.split("\n")[0] if commit_data.message else "No message",
                        diff_text=patch_text if patch_text else "",  # Use actual patch
                        timestamp=commit_data.timestamp or "",
                        author=commit_data.author or "Unknown",
                        url=commit_data.url or "",
                        metadata=metadata,
                        graph_environment=self.graph_environment,
                    )
                    commit_nodes.append(commit_node)

                # Create PR node if not seen
                pr_info = commit_data.pr_info
                if pr_info and pr_info.number not in seen_prs:
                    seen_prs.add(pr_info.number)

                    pr_node = PullRequestNode(
                        external_id=str(pr_info.number),
                        title=pr_info.title,
                        description=pr_info.body_text or "",  # Use bodyText from GraphQL
                        timestamp=pr_info.merged_at or "",
                        author=pr_info.author or "",
                        url=pr_info.url,
                        metadata={"state": pr_info.state or "MERGED"},
                        graph_environment=self.graph_environment,
                    )
                    pr_nodes.append(pr_node)

        logger.info(f"Created {len(pr_nodes)} PR nodes and {len(commit_nodes)} commit nodes from blame")
        return pr_nodes, commit_nodes

    def create_github_integration_from_latest_prs(
        self, pr_limit: int = 50, since_date: Optional[str] = None, save_to_database: bool = True
    ) -> GitHubIntegrationResult:
        """Create GitHub integration by fetching N latest merged PRs.

        This is the legacy approach that fetches the most recent PRs
        from the repository and attempts to map them to code nodes.

        Args:
            pr_limit: Maximum number of PRs to fetch
            since_date: Process PRs created after this date
            save_to_database: Whether to save results

        Returns:
            GitHubIntegrationResult
        """
        # This is just a renamed version of the original create_github_integration
        return self.create_github_integration(
            pr_limit=pr_limit, since_date=since_date, save_to_database=save_to_database
        )
