"""Tool for getting GitHub-style blame information for code nodes."""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.graph.graph_environment import GraphEnvironment
from blarify.integrations.github_creator import GitHubCreator
from blarify.repositories.graph_db_manager import AbstractDbManager

logger = logging.getLogger(__name__)


class NodeIdInput(BaseModel):
    """Input schema for GetBlameByIdTool."""

    node_id: str = Field(description="The node id (an UUID like hash id) of the node to get blame information for.")


class GetBlameByIdTool(BaseTool):
    """Tool for retrieving GitHub-style blame information for a code node.

    This tool displays blame information in a format similar to GitHub's blame view,
    showing each line of code with commit information beside it. It can create
    integration nodes on-demand if they don't exist.
    """

    name: str = "get_blame_by_id"
    description: str = "Get historical Git change information for a code node, showing commit history and which commits modified each line of code over time"
    args_schema: type[BaseModel] = NodeIdInput

    db_manager: AbstractDbManager = Field(description="Database manager for graph operations")
    repo_owner: str = Field(description="GitHub repository owner")
    repo_name: str = Field(description="GitHub repository name")
    github_token: Optional[str] = Field(default=None, description="GitHub personal access token")
    ref: str = Field(default="HEAD", description="Git ref (branch, tag, commit SHA) to blame at")
    auto_create_integration: bool = Field(
        default=True, description="Whether to create integration nodes if they don't exist"
    )

    def __init__(
        self,
        db_manager: Any,
        repo_owner: str,
        repo_name: str,
        github_token: Optional[str] = None,
        ref: str = "HEAD",
        auto_create_integration: bool = True,
        handle_validation_error: bool = False,
    ):
        """Initialize GetBlameByIdTool.

        Args:
            db_manager: Database manager for graph operations
            repo_owner: GitHub repository owner
            repo_name: GitHub repository name
            github_token: GitHub personal access token (uses GITHUB_TOKEN env var if not provided)
            ref: Git ref (branch, tag, commit SHA) to blame at
            auto_create_integration: Whether to create integration nodes if they don't exist
            handle_validation_error: Whether to handle validation errors
        """
        # Get GitHub token from environment if not provided
        if github_token is None:
            github_token = os.getenv("GITHUB_TOKEN")

        super().__init__(
            db_manager=db_manager,
            repo_owner=repo_owner,
            repo_name=repo_name,
            github_token=github_token,
            ref=ref,
            auto_create_integration=auto_create_integration,
            handle_validation_error=handle_validation_error,
        )

        self._graph_environment = GraphEnvironment(environment="production", diff_identifier="main", root_path="/")
        self._github_creator: Optional[GitHubCreator] = None

    def _run(
        self,
        node_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Execute the tool to get blame information.

        Args:
            node_id: The ID of the node to get blame for
            run_manager: Optional callback manager

        Returns:
            GitHub-style formatted blame information as a string
        """
        try:
            # Get node information
            node_info = self._get_node_info(node_id)
            if not node_info:
                return f"Error: Node with ID {node_id} not found"

            # Check for existing blame data
            blame_data = self._get_existing_blame(node_id)

            # If no blame data exists and auto-create is enabled
            if not blame_data and self.auto_create_integration:
                logger.info(f"No existing blame data for node {node_id}, creating integration nodes...")
                created = self._create_integration_if_needed(node_id, self.ref)
                if created:
                    # Re-query for newly created blame data
                    blame_data = self._get_existing_blame(node_id)
                else:
                    logger.warning(f"Failed to create integration nodes for node {node_id}")

            # Format and return GitHub-style blame output
            return self._format_github_style_blame(node_info, blame_data)

        except Exception as e:
            logger.error(f"Error getting blame for node {node_id}: {e}")
            return f"Error: Failed to get blame information - {str(e)}"

    def _get_node_info(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get basic information about the node.

        Args:
            node_id: The node ID

        Returns:
            Dictionary with node information or None if not found
        """
        query = """
        MATCH (n:NODE {node_id: $node_id})
        RETURN n.name as node_name,
               n.path as node_path,
               n.start_line as start_line,
               n.end_line as end_line,
               n.text as code,
               n.label as node_type
        """

        results = self.db_manager.query(query, {"node_id": node_id})
        if results and len(results) > 0:
            return results[0]
        return None

    def _get_existing_blame(self, node_id: str) -> List[Dict[str, Any]]:
        """Get existing MODIFIED_BY relationships with blame attribution.

        Args:
            node_id: The node ID

        Returns:
            List of blame data dictionaries
        """
        query = """
        MATCH (n:NODE {node_id: $node_id})-[r:MODIFIED_BY]->(c:NODE)
        WHERE c.source_type = 'commit' AND c.layer = 'integrations'
        OPTIONAL MATCH (pr:NODE)-[:INTEGRATION_SEQUENCE]->(c)
        WHERE pr.source_type = 'pull_request' AND pr.layer = 'integrations'
        RETURN c.external_id as commit_sha,
               c.title as commit_message,
               c.author as commit_author,
               c.timestamp as commit_timestamp,
               c.url as commit_url,
               r.blamed_lines as line_ranges,
               r.attribution_method as attribution_method,
               r.relevant_patch as relevant_patch,
               pr.external_id as pr_number,
               pr.title as pr_title,
               pr.url as pr_url
        ORDER BY c.timestamp DESC
        """

        results = self.db_manager.query(query, {"node_id": node_id})
        return results if results else []

    def _create_integration_if_needed(self, node_id: str, ref: str = "HEAD") -> bool:
        """Create integration nodes using GitHubCreator if they don't exist.

        Args:
            node_id: The node ID
            ref: Git ref (branch, tag, commit SHA) to blame at

        Returns:
            True if integration nodes were created successfully
        """
        try:
            # Initialize GitHubCreator if not already done
            if not self._github_creator:
                self._github_creator = GitHubCreator(
                    db_manager=self.db_manager,
                    graph_environment=self._graph_environment,
                    repo_owner=self.repo_owner,
                    repo_name=self.repo_name,
                    github_token=self.github_token,
                    ref=self.ref,
                )

            # Create integration nodes for this specific node
            result = self._github_creator.create_github_integration_from_nodes(
                node_ids=[node_id], save_to_database=True
            )

            return result.total_commits > 0

        except Exception as e:
            logger.error(f"Failed to create integration nodes: {e}")
            return False

    def _format_github_style_blame(self, node_info: Dict[str, Any], blame_data: List[Dict[str, Any]]) -> str:
        """Format blame data in GitHub-style output.

        Args:
            node_info: Node information dictionary
            blame_data: List of blame data dictionaries

        Returns:
            Formatted GitHub-style blame string
        """
        output = []

        # Header
        node_name = node_info.get("node_name", "Unknown")
        node_path = node_info.get("node_path", "Unknown")
        node_type = node_info.get("node_type", "Unknown")

        output.append(f"Git Blame for: {node_name} ({node_type})")
        output.append(f"File: {node_path}")
        output.append("=" * 80)
        output.append("")
        output.append("Tip: Use get_commit_by_id tool with any commit SHA shown below to see the full diff")
        output.append("")

        # Get code and parse into lines
        code = node_info.get("code", "")
        if not code:
            output.append("No code available for this node")
            return "\n".join(output)

        code_lines = code.split("\n")
        start_line = node_info.get("start_line", 1)

        # Build line-to-blame mapping
        line_blame_map = self._build_line_blame_map(blame_data, start_line, len(code_lines))

        # Format each line with blame info
        for i, code_line in enumerate(code_lines):
            line_num = start_line + i
            blame_info = line_blame_map.get(line_num, {})

            if blame_info:
                # Format blame info
                time_ago = self._format_time_ago(blame_info.get("timestamp", ""))
                author = (blame_info.get("author", "Unknown")[:10]).ljust(10)
                sha = blame_info.get("sha", "       ")[:7]
                msg = blame_info.get("message", "")  # Show full message

                blame_str = f"{time_ago.ljust(13)} {author} {sha}  {msg}"
            else:
                # No blame info for this line
                blame_str = " " * 65

            # Format line: "blame_info  line_num | code"
            output.append(f"{blame_str} {str(line_num).rjust(4)} | {code_line}")

        # Add summary section
        output.extend(["", "", "Summary:", "-" * 40])

        # Total commits with their SHAs
        unique_commits = set(b.get("commit_sha") for b in blame_data if b.get("commit_sha"))
        output.append(f"Total commits: {len(unique_commits)}")
        
        # List all unique commit SHAs for easy reference
        if unique_commits:
            output.append("")
            output.append("Commit SHAs (use with get_commit_by_id tool):")
            for sha in sorted([s for s in unique_commits if s]):  # Filter out None values
                commit_data = next((b for b in blame_data if b.get("commit_sha") == sha), {})
                commit_msg = commit_data.get("commit_message", "No message")
                output.append(f"  {sha[:7]} - {commit_msg}")

        # Calculate primary author (author with most lines)
        if blame_data:
            author_lines = self._calculate_author_lines(blame_data)
            if author_lines:
                primary_author = max(author_lines.items(), key=lambda x: x[1])
                output.append(f"Primary author: {primary_author[0]} ({primary_author[1]} lines)")

            # Last modified
            latest_commit = self._find_latest_commit(blame_data)
            if latest_commit:
                time_ago = self._format_time_ago(latest_commit.get("commit_timestamp", ""))
                author = latest_commit.get("commit_author", "Unknown")
                output.append(f"Last modified: {time_ago} by {author}")

            # Associated PRs
            prs = set((b.get("pr_number"), b.get("pr_title")) for b in blame_data if b.get("pr_number"))
            if prs:
                output.append("")
                output.append("Associated Pull Requests:")
                for pr_num, pr_title in sorted(prs):
                    if pr_title:
                        output.append(f"  PR #{pr_num}: {pr_title[:60]}")
        else:
            output.append("No blame information available")

        return "\n".join(output)

    def _build_line_blame_map(
        self, blame_data: List[Dict[str, Any]], start_line: int, num_lines: int
    ) -> Dict[int, Dict[str, Any]]:
        """Build a mapping of line numbers to blame information.

        Args:
            blame_data: List of blame data dictionaries
            start_line: Starting line number of the node
            num_lines: Number of lines in the node

        Returns:
            Dictionary mapping line numbers to blame info
        """
        line_blame_map: Dict[int, Dict[str, Any]] = {}

        for blame in blame_data:
            # Parse line ranges from blamed_lines JSON string
            line_ranges_str = blame.get("line_ranges", "[]")
            if isinstance(line_ranges_str, str):
                try:
                    line_ranges = json.loads(line_ranges_str)
                except json.JSONDecodeError:
                    line_ranges = []
            else:
                line_ranges = line_ranges_str or []

            # Map each line in the ranges to this commit
            for line_range in line_ranges:
                if isinstance(line_range, dict):
                    start = line_range.get("start", 0)
                    end = line_range.get("end", 0)

                    for line_num in range(start, end + 1):
                        # Only map lines within the node's range
                        if start_line <= line_num < start_line + num_lines:
                            line_blame_map[line_num] = {
                                "sha": blame.get("commit_sha", ""),
                                "message": blame.get("commit_message", ""),
                                "author": blame.get("commit_author", ""),
                                "timestamp": blame.get("commit_timestamp", ""),
                                "pr_number": blame.get("pr_number"),
                                "pr_title": blame.get("pr_title"),
                            }

        return line_blame_map

    def _format_time_ago(self, timestamp: str) -> str:
        """Convert ISO timestamp to human-readable 'X time ago' format.

        Args:
            timestamp: ISO format timestamp string

        Returns:
            Human-readable time string (e.g., "2 months ago")
        """
        if not timestamp:
            return "Unknown"

        try:
            # Parse ISO timestamp
            if timestamp.endswith("Z"):
                timestamp = timestamp[:-1] + "+00:00"

            commit_time = datetime.fromisoformat(timestamp)
            now = datetime.now(commit_time.tzinfo)

            # Calculate difference
            diff = now - commit_time

            # Format as human-readable
            if diff.days > 365:
                years = diff.days // 365
                return f"{years} year{'s' if years > 1 else ''} ago"
            elif diff.days > 30:
                months = diff.days // 30
                return f"{months} month{'s' if months > 1 else ''} ago"
            elif diff.days > 0:
                return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours} hour{'s' if hours > 1 else ''} ago"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
            else:
                return "Just now"

        except (ValueError, AttributeError) as e:
            logger.debug(f"Failed to parse timestamp {timestamp}: {e}")
            return "Unknown"

    def _calculate_author_lines(self, blame_data: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calculate number of lines attributed to each author.

        Args:
            blame_data: List of blame data dictionaries

        Returns:
            Dictionary mapping author names to line counts
        """
        author_lines: Dict[str, int] = {}

        for blame in blame_data:
            author = blame.get("commit_author", "Unknown")

            # Parse line ranges
            line_ranges_str = blame.get("line_ranges", "[]")
            if isinstance(line_ranges_str, str):
                try:
                    line_ranges = json.loads(line_ranges_str)
                except json.JSONDecodeError:
                    line_ranges = []
            else:
                line_ranges = line_ranges_str or []

            # Count lines for this author
            total_lines = 0
            for line_range in line_ranges:
                if isinstance(line_range, dict):
                    start = line_range.get("start", 0)
                    end = line_range.get("end", 0)
                    total_lines += max(0, end - start + 1)

            author_lines[author] = author_lines.get(author, 0) + total_lines

        return author_lines

    def _find_latest_commit(self, blame_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find the most recent commit from blame data.

        Args:
            blame_data: List of blame data dictionaries

        Returns:
            Dictionary of the latest commit or None
        """
        if not blame_data:
            return None

        # Filter out entries without timestamps
        valid_commits = [b for b in blame_data if b.get("commit_timestamp")]

        if not valid_commits:
            return None

        # Sort by timestamp and return the latest
        try:
            return max(valid_commits, key=lambda x: x["commit_timestamp"])
        except (KeyError, TypeError):
            return valid_commits[0] if valid_commits else None
