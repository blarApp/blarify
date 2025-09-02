"""Abstract base class for version control system integrations."""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime


class AbstractVersionController(ABC):
    """Abstract base class defining interface for version control systems.

    This class provides the contract for implementing integrations with various
    version control systems like GitHub, GitLab, Bitbucket, etc.
    """

    @abstractmethod
    def fetch_pull_requests(self, limit: int = 50, since_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch merged pull requests from the version control system.

        Only returns PRs that have been merged into the codebase.

        Args:
            limit: Maximum number of merged PRs to fetch
            since_date: Fetch PRs created after this date

        Returns:
            List of PR dictionaries with standardized fields (only merged PRs):
                - number: PR number/ID
                - title: PR title
                - description: PR description/body
                - author: Author username
                - created_at: Creation timestamp
                - updated_at: Last update timestamp
                - merged_at: Merge timestamp (always present)
                - state: Current state (always 'closed' for merged PRs)
                - url: Web URL to the PR
                - metadata: Additional system-specific data
        """
        pass

    @abstractmethod
    def fetch_commits(
        self,
        pr_number: Optional[int] = None,
        branch: Optional[str] = None,
        since_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch commits from the version control system.

        Args:
            pr_number: Fetch commits for a specific PR
            branch: Fetch commits for a specific branch
            since_date: Fetch commits after this date
            limit: Maximum number of commits to fetch

        Returns:
            List of commit dictionaries with standardized fields:
                - sha: Commit SHA/hash
                - message: Commit message
                - author: Author name
                - author_email: Author email
                - timestamp: Commit timestamp
                - url: Web URL to the commit
                - pr_number: Associated PR number (if applicable)
                - metadata: Additional system-specific data
        """
        pass

    @abstractmethod
    def fetch_commit_changes(self, commit_sha: str) -> List[Dict[str, Any]]:
        """Fetch file changes for a specific commit.

        Args:
            commit_sha: The commit SHA/hash to get changes for

        Returns:
            List of file change dictionaries:
                - filename: Path to the file
                - status: Change status (added, modified, removed)
                - additions: Number of lines added
                - deletions: Number of lines deleted
                - patch: Diff patch showing the changes
                - previous_filename: Previous name if renamed
        """
        pass

    @abstractmethod
    def fetch_file_at_commit(self, file_path: str, commit_sha: str) -> Optional[str]:
        """Fetch the contents of a file at a specific commit.

        Args:
            file_path: Path to the file in the repository
            commit_sha: The commit SHA/hash

        Returns:
            File contents as string, or None if file doesn't exist
        """
        pass

    @abstractmethod
    def get_repository_info(self) -> Dict[str, Any]:
        """Get information about the repository.

        Returns:
            Repository information dictionary:
                - name: Repository name
                - owner: Repository owner/organization
                - url: Repository URL
                - default_branch: Default branch name
                - created_at: Creation timestamp
                - updated_at: Last update timestamp
                - metadata: Additional system-specific data
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test the connection to the version control system.

        Returns:
            True if connection is successful, False otherwise
        """
        pass

    @abstractmethod
    def blame_commits_for_range(self, file_path: str, start_line: int, end_line: int) -> List[Any]:
        """Get all commits that modified specific line range using blame.

        Args:
            file_path: Path to file in repository
            start_line: Starting line number (1-indexed)
            end_line: Ending line number (inclusive)
            ref: Git ref (branch, tag, commit SHA) to blame at

        Returns:
            List of blame commit objects with line attribution
        """
        pass

    @abstractmethod
    def blame_commits_for_nodes(self, nodes: List[Any]) -> Dict[str, List[Any]]:
        """Get commits for multiple code nodes efficiently.

        Args:
            nodes: List of code node objects
            ref: Git ref (branch, tag, commit SHA) to blame at

        Returns:
            Dictionary mapping node IDs to their blame commit lists
        """
        pass

    def parse_patch_header(self, patch_header: str) -> Dict[str, Any]:
        """Parse a patch header to extract line range information.

        Args:
            patch_header: Patch header string like "@@ -45,7 +45,15 @@"

        Returns:
            Dictionary with parsed information:
                - deleted: {start_line, line_count}
                - added: {start_line, line_count}
        """
        import re

        # Pattern: @@ -start,count +start,count @@
        pattern = r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@"
        match = re.match(pattern, patch_header)

        if not match:
            return {"deleted": {}, "added": {}}

        deleted_start = int(match.group(1))
        deleted_count = int(match.group(2)) if match.group(2) else 1
        added_start = int(match.group(3))
        added_count = int(match.group(4)) if match.group(4) else 1

        return {
            "deleted": {"start_line": deleted_start, "line_count": deleted_count},
            "added": {"start_line": added_start, "line_count": added_count},
        }

    def extract_change_ranges(self, patch: str) -> List[Dict[str, Any]]:
        """Extract specific line and character ranges for each change.

        Groups consecutive lines of the same type into single ranges.

        Args:
            patch: Git patch/diff string

        Returns:
            List of change dictionaries with line/character ranges
        """
        changes = []
        lines = patch.split("\n")

        current_old_line = 0
        current_new_line = 0
        current_change = None

        for line in lines:
            if line.startswith("@@"):
                # Save any pending change
                if current_change:
                    changes.append(current_change)
                    current_change = None

                # Parse the header to get starting line numbers
                header_info = self.parse_patch_header(line)
                current_old_line = header_info["deleted"].get("start_line", 0)
                current_new_line = header_info["added"].get("start_line", 0)

            elif line.startswith("-") and not line.startswith("---"):
                # Deletion
                if (
                    current_change
                    and current_change["type"] == "deletion"
                    and current_change["line_end"] == current_old_line - 1
                ):
                    # Extend existing deletion range
                    current_change["line_end"] = current_old_line
                    current_change["content"] += "\n" + line[1:]
                else:
                    # Save previous change and start new deletion
                    if current_change:
                        changes.append(current_change)
                    current_change = {
                        "type": "deletion",
                        "line_start": current_old_line,
                        "line_end": current_old_line,
                        "content": line[1:],
                    }
                current_old_line += 1

            elif line.startswith("+") and not line.startswith("+++"):
                # Addition
                if (
                    current_change
                    and current_change["type"] == "addition"
                    and current_change["line_end"] == current_new_line - 1
                ):
                    # Extend existing addition range
                    current_change["line_end"] = current_new_line
                    current_change["content"] += "\n" + line[1:]
                else:
                    # Save previous change and start new addition
                    if current_change:
                        changes.append(current_change)
                    current_change = {
                        "type": "addition",
                        "line_start": current_new_line,
                        "line_end": current_new_line,
                        "content": line[1:],
                    }
                current_new_line += 1

            elif line and not line.startswith("\\"):
                # Context line (unchanged) - save any pending change
                if current_change:
                    changes.append(current_change)
                    current_change = None
                current_old_line += 1
                current_new_line += 1

        # Save any final pending change
        if current_change:
            changes.append(current_change)

        return changes
