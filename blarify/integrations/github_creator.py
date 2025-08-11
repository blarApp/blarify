"""GitHub integration creator for building PR and commit nodes."""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from blarify.db_managers.abstract_db_manager import AbstractDbManager
from blarify.db_managers.repositories.github_repository import GitHubRepository
from blarify.graph.node.integration_node import IntegrationNode
from blarify.graph.relationship.relationship_creator import RelationshipCreator
from blarify.graph.relationship.relationship_type import RelationshipType
from blarify.graph.environment.graph_environment import GraphEnvironment

logger = logging.getLogger(__name__)


@dataclass
class GitHubIntegrationResult:
    """Result of GitHub integration processing."""
    
    pr_nodes: List[IntegrationNode]
    commit_nodes: List[IntegrationNode]
    relationships: List[Dict[str, Any]]
    errors: List[str]
    stats: Dict[str, int]


class GitHubCreator:
    """
    Creates GitHub integration nodes and relationships.
    
    Following the pattern of DocumentationCreator and WorkflowCreator,
    this class orchestrates the creation of GitHub PR and commit nodes
    and their relationships to code.
    """
    
    def __init__(
        self,
        db_manager: AbstractDbManager,
        graph_environment: GraphEnvironment,
        github_token: Optional[str] = None,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None,
    ):
        """
        Initialize GitHub creator.
        
        Args:
            db_manager: Database manager for saving nodes
            graph_environment: Graph environment
            github_token: GitHub API token
            repo_owner: Repository owner
            repo_name: Repository name
        """
        self.db_manager = db_manager
        self.graph_environment = graph_environment
        self.github_repo = GitHubRepository(
            token=github_token,
            repo_owner=repo_owner,
            repo_name=repo_name
        )
        
    def create_github_integration(
        self,
        pr_limit: int = 50,
        since_date: Optional[str] = None,
        save_to_database: bool = True,
    ) -> GitHubIntegrationResult:
        """
        Create GitHub integration nodes and relationships.
        
        Args:
            pr_limit: Maximum number of PRs to process
            since_date: Process PRs since this date (ISO format)
            save_to_database: Whether to save to database
            
        Returns:
            GitHubIntegrationResult with created nodes and relationships
        """
        logger.info(f"Starting GitHub integration (limit={pr_limit}, since={since_date})")
        
        pr_nodes = []
        commit_nodes = []
        all_relationships = []
        errors = []
        
        try:
            # Test connection first
            if not self.github_repo.test_connection():
                error_msg = "Failed to connect to GitHub API"
                logger.error(error_msg)
                errors.append(error_msg)
                return GitHubIntegrationResult([], [], [], errors, {})
            
            # Fetch PRs
            logger.info("Fetching pull requests...")
            prs_data = self.github_repo.fetch_prs(limit=pr_limit, since_date=since_date)
            logger.info(f"Found {len(prs_data)} pull requests")
            
            # Process each PR
            for pr_data in prs_data:
                try:
                    # Create PR node
                    pr_node = self._create_pr_node(pr_data)
                    pr_nodes.append(pr_node)
                    
                    # Fetch and process commits for this PR
                    pr_commits, pr_relationships = self._process_pr_commits(pr_node, pr_data)
                    commit_nodes.extend(pr_commits)
                    all_relationships.extend(pr_relationships)
                    
                except Exception as e:
                    error_msg = f"Error processing PR {pr_data.get('number', 'unknown')}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Map commits to code nodes
            logger.info("Mapping commits to code nodes...")
            code_relationships = self._map_commits_to_code(commit_nodes)
            all_relationships.extend(code_relationships)
            
            # Save to database if requested
            if save_to_database:
                logger.info("Saving to database...")
                self._save_to_database(pr_nodes, commit_nodes, all_relationships)
            
            # Prepare stats
            stats = {
                "prs_processed": len(pr_nodes),
                "commits_processed": len(commit_nodes),
                "relationships_created": len(all_relationships),
                "errors": len(errors)
            }
            
            logger.info(f"GitHub integration complete: {stats}")
            
            return GitHubIntegrationResult(
                pr_nodes=pr_nodes,
                commit_nodes=commit_nodes,
                relationships=all_relationships,
                errors=errors,
                stats=stats
            )
            
        except Exception as e:
            error_msg = f"Fatal error in GitHub integration: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            return GitHubIntegrationResult([], [], [], errors, {})
    
    def _create_pr_node(self, pr_data: Dict[str, Any]) -> IntegrationNode:
        """
        Create IntegrationNode from PR data.
        
        Args:
            pr_data: Pull request data from GitHub API
            
        Returns:
            IntegrationNode representing the PR
        """
        return IntegrationNode(
            source="github",
            source_type="pull_request",
            external_id=str(pr_data["number"]),
            title=pr_data["title"],
            content=pr_data.get("body", ""),
            timestamp=pr_data["created_at"],
            author=pr_data["user"]["login"],
            url=pr_data["html_url"],
            graph_environment=self.graph_environment,
            metadata={
                "state": pr_data["state"],
                "merged": pr_data.get("merged", False),
                "merged_at": pr_data.get("merged_at"),
                "base_branch": pr_data["base"]["ref"],
                "head_branch": pr_data["head"]["ref"],
                "additions": pr_data.get("additions", 0),
                "deletions": pr_data.get("deletions", 0),
                "changed_files": pr_data.get("changed_files", 0),
            }
        )
    
    def _process_pr_commits(
        self,
        pr_node: IntegrationNode,
        pr_data: Dict[str, Any]
    ) -> Tuple[List[IntegrationNode], List[Dict[str, Any]]]:
        """
        Process commits for a PR and create relationships.
        
        Args:
            pr_node: The PR IntegrationNode
            pr_data: PR data from GitHub API
            
        Returns:
            Tuple of (commit nodes, relationships)
        """
        commit_nodes = []
        relationships = []
        
        # Fetch commits for this PR
        commits_data = self.github_repo.fetch_commits_for_pr(int(pr_data["number"]))
        
        for idx, commit_data in enumerate(commits_data):
            # Create commit node
            commit_node = self._create_commit_node(commit_data)
            commit_nodes.append(commit_node)
            
            # Create INTEGRATION_SEQUENCE relationship from PR to commit
            sequence_rel = self._create_integration_sequence_relationship(
                pr_node, commit_node, sequence_order=idx
            )
            relationships.append(sequence_rel)
        
        return commit_nodes, relationships
    
    def _create_commit_node(self, commit_data: Dict[str, Any]) -> IntegrationNode:
        """
        Create IntegrationNode from commit data.
        
        Args:
            commit_data: Commit data from GitHub API
            
        Returns:
            IntegrationNode representing the commit
        """
        # Extract commit details
        commit_info = commit_data.get("commit", commit_data)
        author_info = commit_info.get("author", {})
        
        return IntegrationNode(
            source="github",
            source_type="commit",
            external_id=commit_data["sha"],
            title=commit_info.get("message", "").split('\n')[0],  # First line of commit message
            content=commit_info.get("message", ""),
            timestamp=author_info.get("date", ""),
            author=author_info.get("name", "unknown"),
            url=commit_data.get("html_url", ""),
            graph_environment=self.graph_environment,
            metadata={
                "sha": commit_data["sha"],
                "parent_shas": [p["sha"] for p in commit_data.get("parents", [])],
                "author_email": author_info.get("email", ""),
                "committer": commit_info.get("committer", {}).get("name", ""),
                "additions": commit_data.get("stats", {}).get("additions", 0),
                "deletions": commit_data.get("stats", {}).get("deletions", 0),
                "total_changes": commit_data.get("stats", {}).get("total", 0),
            }
        )
    
    def _create_integration_sequence_relationship(
        self,
        pr_node: IntegrationNode,
        commit_node: IntegrationNode,
        sequence_order: int
    ) -> Dict[str, Any]:
        """
        Create INTEGRATION_SEQUENCE relationship between PR and commit.
        
        Args:
            pr_node: Pull request node
            commit_node: Commit node
            sequence_order: Order of commit in the PR
            
        Returns:
            Relationship dictionary
        """
        return {
            "start_node_id": pr_node.id,
            "end_node_id": commit_node.id,
            "type": RelationshipType.INTEGRATION_SEQUENCE.value,
            "properties": {
                "sequence_order": sequence_order,
                "relationship_type": "pr_contains_commit"
            }
        }
    
    def _map_commits_to_code(self, commit_nodes: List[IntegrationNode]) -> List[Dict[str, Any]]:
        """
        Map commits to existing code nodes via MODIFIED_BY relationships.
        
        Args:
            commit_nodes: List of commit IntegrationNodes
            
        Returns:
            List of MODIFIED_BY relationships
        """
        relationships = []
        
        for commit_node in commit_nodes:
            # Fetch detailed commit changes
            commit_details = self.github_repo.fetch_commit_changes(
                commit_node.metadata.get("sha", commit_node.external_id)
            )
            
            if not commit_details:
                continue
            
            # Process file changes
            for file_change in commit_details.get("files", []):
                file_path = file_change.get("filename", "")
                
                if not file_path:
                    continue
                
                # Query for code nodes at this path
                code_nodes = self._find_code_nodes_for_path(file_path)
                
                for code_node in code_nodes:
                    # Create MODIFIED_BY relationship
                    rel = self._create_modified_by_relationship(
                        code_node,
                        commit_node,
                        file_change
                    )
                    relationships.append(rel)
        
        return relationships
    
    def _find_code_nodes_for_path(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Find code nodes that match the given file path.
        
        Args:
            file_path: File path from GitHub
            
        Returns:
            List of code node dictionaries
        """
        # Query database for nodes at this path
        query = """
        MATCH (n)
        WHERE n.path CONTAINS $file_path
        AND n.label IN ['FILE', 'CLASS', 'FUNCTION', 'METHOD']
        RETURN n
        """
        
        try:
            results = self.db_manager.execute_query(query, {"file_path": file_path})
            return [record["n"] for record in results]
        except Exception as e:
            logger.error(f"Error finding code nodes for {file_path}: {e}")
            return []
    
    def _create_modified_by_relationship(
        self,
        code_node: Dict[str, Any],
        commit_node: IntegrationNode,
        file_change: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create MODIFIED_BY relationship between code and commit.
        
        Args:
            code_node: Code node dictionary
            commit_node: Commit IntegrationNode
            file_change: File change data from GitHub
            
        Returns:
            Relationship dictionary
        """
        return {
            "start_node_id": code_node.get("id"),
            "end_node_id": commit_node.id,
            "type": RelationshipType.MODIFIED_BY.value,
            "properties": {
                "additions": file_change.get("additions", 0),
                "deletions": file_change.get("deletions", 0),
                "changes": file_change.get("changes", 0),
                "patch": file_change.get("patch", "")[:500],  # Truncate large patches
                "status": file_change.get("status", "modified")
            }
        }
    
    def _save_to_database(
        self,
        pr_nodes: List[IntegrationNode],
        commit_nodes: List[IntegrationNode],
        relationships: List[Dict[str, Any]]
    ) -> None:
        """
        Save nodes and relationships to database.
        
        Args:
            pr_nodes: List of PR IntegrationNodes
            commit_nodes: List of commit IntegrationNodes
            relationships: List of relationship dictionaries
        """
        try:
            # Convert nodes to objects
            all_nodes = []
            all_nodes.extend([node.as_object() for node in pr_nodes])
            all_nodes.extend([node.as_object() for node in commit_nodes])
            
            # Save to database
            self.db_manager.save_graph(all_nodes, relationships)
            
            logger.info(f"Saved {len(all_nodes)} nodes and {len(relationships)} relationships to database")
            
        except Exception as e:
            logger.error(f"Error saving to database: {e}")
            raise