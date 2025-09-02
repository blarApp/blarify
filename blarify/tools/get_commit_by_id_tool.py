"""Tool for getting detailed commit information including diffs."""

import json
import logging
from typing import Any, Dict, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.repositories.graph_db_manager import AbstractDbManager

logger = logging.getLogger(__name__)


class CommitIdInput(BaseModel):
    """Input schema for GetCommitByIdTool."""

    commit_sha: str = Field(
        description="The commit SHA (full or short) to get detailed information for. This can be obtained from the blame tool output."
    )


class GetCommitByIdTool(BaseTool):
    """Tool for retrieving detailed commit information including the full diff/patch.

    This tool displays comprehensive commit information including:
    - Commit metadata (author, date, message)
    - Associated pull request information
    - Full patch/diff showing all changes made in the commit
    - Affected files and line changes
    """

    name: str = "get_commit_by_id"
    description: str = (
        "Get detailed commit information including the full diff/patch, showing all changes made in a specific commit"
    )
    args_schema: type[BaseModel] = CommitIdInput

    db_manager: AbstractDbManager = Field(description="Database manager for graph operations")

    def __init__(
        self,
        db_manager: Any,
        handle_validation_error: bool = False,
    ):
        """Initialize GetCommitByIdTool.

        Args:
            db_manager: Database manager for graph operations
            handle_validation_error: Whether to handle validation errors
        """
        super().__init__(
            db_manager=db_manager,
            handle_validation_error=handle_validation_error,
        )

    def _run(
        self,
        commit_sha: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Execute the tool to get commit information.

        Args:
            commit_sha: The commit SHA to get information for
            run_manager: Optional callback manager

        Returns:
            Formatted commit information including diff as a string
        """
        try:
            # Query for commit node and related information
            commit_info = self._get_commit_info(commit_sha)
            if not commit_info:
                return f"Error: Commit with SHA {commit_sha} not found in the graph database"

            # Format and return the commit information
            return self._format_commit_output(commit_info)

        except Exception as e:
            logger.error(f"Error getting commit {commit_sha}: {e}")
            return f"Error: Failed to get commit information - {str(e)}"

    def _get_commit_info(self, commit_sha: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive commit information from the database.

        Args:
            commit_sha: The commit SHA (can be short or full)

        Returns:
            Dictionary with commit information or None if not found
        """
        # Query supports both full and short SHAs
        query = """
        MATCH (c:NODE)
        WHERE c.source_type = 'commit' 
          AND c.layer = 'integrations'
          AND (c.external_id = $commit_sha OR c.external_id STARTS WITH $commit_sha)
        OPTIONAL MATCH (pr:NODE)-[:INTEGRATION_SEQUENCE]->(c)
        WHERE pr.source_type = 'pull_request' AND pr.layer = 'integrations'
        OPTIONAL MATCH (c)-[mod:MODIFIED_BY]->(code:NODE)
        WHERE code.layer = 'code'
        RETURN c.external_id as commit_sha,
               c.title as commit_title,
               c.content as diff_text,
               c.timestamp as commit_timestamp,
               c.author as commit_author,
               c.url as commit_url,
               c.metadata as commit_metadata,
               pr.external_id as pr_number,
               pr.title as pr_title,
               pr.url as pr_url,
               pr.author as pr_author,
               collect(DISTINCT {
                   node_id: code.node_id,
                   node_name: code.name,
                   node_type: code.label,
                   node_path: code.path,
                   blamed_lines: mod.blamed_lines,
                   attribution_method: mod.attribution_method
               }) as affected_nodes
        LIMIT 1
        """

        results = self.db_manager.query(query, {"commit_sha": commit_sha})
        if results and len(results) > 0:
            return results[0]
        return None

    def _format_commit_output(self, commit_info: Dict[str, Any]) -> str:
        """Format commit information for display.

        Args:
            commit_info: Dictionary containing commit information

        Returns:
            Formatted commit information as a string
        """
        output = []

        # Header
        commit_sha = commit_info.get("commit_sha", "Unknown")
        output.append(f"Commit: {commit_sha}")
        output.append("=" * 80)
        output.append("")

        # Basic commit information
        output.append("Commit Information:")
        output.append("-" * 40)
        output.append(f"SHA: {commit_sha}")
        output.append(f"Author: {commit_info.get('commit_author', 'Unknown')}")
        output.append(f"Date: {commit_info.get('commit_timestamp', 'Unknown')}")
        output.append(f"Message: {commit_info.get('commit_title', 'No message')}")

        # URL if available
        if commit_info.get("commit_url"):
            output.append(f"URL: {commit_info.get('commit_url')}")

        # Pull Request information if available
        if commit_info.get("pr_number"):
            output.append("")
            output.append("Associated Pull Request:")
            output.append("-" * 40)
            output.append(f"PR #{commit_info.get('pr_number')}: {commit_info.get('pr_title', 'No title')}")
            output.append(f"Author: {commit_info.get('pr_author', 'Unknown')}")
            if commit_info.get("pr_url"):
                output.append(f"URL: {commit_info.get('pr_url')}")

        # Affected code nodes
        affected_nodes = commit_info.get("affected_nodes", [])
        if affected_nodes and any(node.get("node_id") for node in affected_nodes):
            output.append("")
            output.append("Affected Code Nodes:")
            output.append("-" * 40)

            # Group by file
            files = {}
            for node in affected_nodes:
                if not node.get("node_id"):
                    continue

                path = node.get("node_path", "Unknown")
                if path not in files:
                    files[path] = []

                node_info = f"  - {node.get('node_type', 'UNKNOWN')}: {node.get('node_name', 'Unknown')}"
                if node.get("node_id"):
                    node_info += f" (ID: {node.get('node_id')})"
                if node.get("blamed_lines"):
                    node_info += f" [Lines: {node.get('blamed_lines')}]"
                files[path].append(node_info)

            for path, nodes in sorted(files.items()):
                output.append(f"\n{path}:")
                output.extend(nodes)

        # Commit metadata if available
        metadata: Dict[str, str | int] = json.loads(commit_info.get("commit_metadata", "{}"))
        if metadata:
            additions = metadata.get("additions")
            deletions = metadata.get("deletions")
            if additions is not None or deletions is not None:
                output.append("")
                output.append("Statistics:")
                output.append("-" * 40)
                if additions is not None:
                    output.append(f"Lines added: +{additions}")
                if deletions is not None:
                    output.append(f"Lines deleted: -{deletions}")

        # Full diff/patch
        diff_text = commit_info.get("diff_text", "")
        if diff_text:
            output.append("")
            output.append("Full Diff/Patch:")
            output.append("=" * 80)
            output.append(diff_text)
        else:
            output.append("")
            output.append("No diff/patch available for this commit")

        return "\n".join(output)
