"""GitHub implementation of the version control interface."""

import os
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from blarify.repositories.version_control.abstract_version_controller import AbstractVersionController
from blarify.repositories.graph_db_manager.dtos.code_node_dto import CodeNodeDto
from blarify.repositories.graph_db_manager.dtos.blame_commit_dto import BlameCommitDto
from blarify.repositories.graph_db_manager.dtos.blame_line_range_dto import BlameLineRangeDto
from blarify.repositories.graph_db_manager.dtos.pull_request_info_dto import PullRequestInfoDto

logger = logging.getLogger(__name__)


class GitHub(AbstractVersionController):
    """GitHub implementation of the version control interface.
    
    This class provides GitHub-specific implementation for fetching PRs,
    commits, and file changes using the GitHub API v3.
    """
    
    def __init__(
        self,
        token: Optional[str] = None,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        base_url: str = "https://api.github.com"
    ):
        """Initialize GitHub client.
        
        Args:
            token: GitHub personal access token (optional, uses env var if not provided)
            repo_owner: Repository owner/organization
            repo_name: Repository name
            base_url: GitHub API base URL (for GitHub Enterprise)
        """
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.base_url = base_url.rstrip('/')
        
        # Initialize blame cache
        self._blame_cache: Dict[str, List[Dict[str, Any]]] = {}
        
        # Setup session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set headers
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Blarify-GitHub-Integration"
        })
        
        if self.token:
            self.session.headers["Authorization"] = f"token {self.token}"
    
    def _get_repo_url(self) -> str:
        """Get the repository API URL."""
        return f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}"
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Make an API request with error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            params: Query parameters
            json_data: JSON payload for POST/PUT requests
            
        Returns:
            Response JSON or raises exception
        """
        url = f"{self._get_repo_url()}/{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                timeout=30
            )
            
            # Check rate limiting
            if response.status_code == 429:
                reset_time = response.headers.get('X-RateLimit-Reset', 'unknown')
                raise Exception(f"GitHub rate limit exceeded. Resets at {reset_time}")
            
            response.raise_for_status()
            return response.json() if response.text else None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub API request failed: {e}")
            raise
    
    def fetch_pull_requests(
        self,
        limit: int = 50,
        since_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Fetch merged pull requests from GitHub.
        
        Only fetches PRs that have been merged into the codebase.
        
        Args:
            limit: Maximum number of merged PRs to fetch
            since_date: Fetch PRs created after this date
            
        Returns:
            List of standardized PR dictionaries (only merged PRs)
        """
        prs = []
        page = 1
        per_page = min(limit, 100)  # GitHub max is 100 per page
        
        while len(prs) < limit:
            params = {
                "state": "closed",  # Must be closed to be merged
                "sort": "created",
                "direction": "desc",
                "page": page,
                "per_page": per_page
            }
            
            if since_date:
                params["since"] = since_date.isoformat()
            
            try:
                response = self._make_request("GET", "pulls", params=params)
                
                if not response:
                    break
                
                for pr in response:
                    # Skip PRs that weren't merged
                    if not pr.get("merged_at"):
                        continue
                    
                    # Skip if before since_date
                    if since_date:
                        created = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
                        if created < since_date:
                            continue
                    
                    # Standardize PR data
                    standardized_pr = {
                        "number": pr["number"],
                        "title": pr["title"],
                        "description": pr.get("body", ""),
                        "author": pr["user"]["login"],
                        "created_at": pr["created_at"],
                        "updated_at": pr["updated_at"],
                        "merged_at": pr.get("merged_at"),
                        "state": pr["state"],
                        "url": pr["html_url"],
                        "metadata": {
                            "head_sha": pr["head"]["sha"],
                            "base_sha": pr["base"]["sha"],
                            "mergeable": pr.get("mergeable"),
                            "labels": [label["name"] for label in pr.get("labels", [])]
                        }
                    }
                    prs.append(standardized_pr)
                    
                    if len(prs) >= limit:
                        break
                
                # Check if there are more pages
                if len(response) < per_page:
                    break
                    
                page += 1
                
            except Exception as e:
                logger.error(f"Error fetching pull requests: {e}")
                break
        
        logger.info(f"Fetched {len(prs)} pull requests from GitHub")
        return prs[:limit]
    
    def fetch_commits(
        self,
        pr_number: Optional[int] = None,
        branch: Optional[str] = None,
        since_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch commits from GitHub.
        
        Args:
            pr_number: Fetch commits for a specific PR
            branch: Fetch commits for a specific branch
            since_date: Fetch commits after this date
            limit: Maximum number of commits to fetch
            
        Returns:
            List of standardized commit dictionaries
        """
        commits = []
        
        if pr_number:
            # Fetch commits for a specific PR
            endpoint = f"pulls/{pr_number}/commits"
            params = {"per_page": min(limit, 100)}
            
            try:
                response = self._make_request("GET", endpoint, params=params)
                
                for commit in response[:limit]:
                    standardized_commit = {
                        "sha": commit["sha"],
                        "message": commit["commit"]["message"],
                        "author": commit["commit"]["author"]["name"],
                        "author_email": commit["commit"]["author"]["email"],
                        "timestamp": commit["commit"]["author"]["date"],
                        "url": commit["html_url"],
                        "pr_number": pr_number,
                        "metadata": {
                            "tree_sha": commit["commit"]["tree"]["sha"],
                            "parent_shas": [p["sha"] for p in commit.get("parents", [])]
                        }
                    }
                    commits.append(standardized_commit)
                    
            except Exception as e:
                logger.error(f"Error fetching commits for PR {pr_number}: {e}")
        
        else:
            # Fetch commits from branch or default branch
            endpoint = "commits"
            page = 1
            per_page = min(limit, 100)
            
            while len(commits) < limit:
                params: Dict[str, Any] = {
                    "page": page,
                    "per_page": per_page
                }
                
                if branch:
                    params["sha"] = branch
                    
                if since_date:
                    params["since"] = since_date.isoformat()
                
                try:
                    response = self._make_request("GET", endpoint, params=params)
                    
                    if not response:
                        break
                    
                    for commit in response:
                        standardized_commit = {
                            "sha": commit["sha"],
                            "message": commit["commit"]["message"],
                            "author": commit["commit"]["author"]["name"],
                            "author_email": commit["commit"]["author"]["email"],
                            "timestamp": commit["commit"]["author"]["date"],
                            "url": commit["html_url"],
                            "pr_number": None,
                            "metadata": {
                                "tree_sha": commit["commit"]["tree"]["sha"],
                                "parent_shas": [p["sha"] for p in commit.get("parents", [])]
                            }
                        }
                        commits.append(standardized_commit)
                        
                        if len(commits) >= limit:
                            break
                    
                    if len(response) < per_page:
                        break
                        
                    page += 1
                    
                except Exception as e:
                    logger.error(f"Error fetching commits: {e}")
                    break
        
        logger.info(f"Fetched {len(commits)} commits from GitHub")
        return commits[:limit]
    
    def fetch_commit_changes(self, commit_sha: str) -> List[Dict[str, Any]]:
        """Fetch file changes for a specific commit.
        
        Args:
            commit_sha: The commit SHA to get changes for
            
        Returns:
            List of file change dictionaries
        """
        endpoint = f"commits/{commit_sha}"
        
        try:
            response = self._make_request("GET", endpoint)
            
            changes = []
            for file in response.get("files", []):
                change = {
                    "filename": file["filename"],
                    "status": file["status"],
                    "additions": file["additions"],
                    "deletions": file["deletions"],
                    "patch": file.get("patch", ""),
                    "previous_filename": file.get("previous_filename")
                }
                changes.append(change)
            
            logger.info(f"Fetched {len(changes)} file changes for commit {commit_sha}")
            return changes
            
        except Exception as e:
            logger.error(f"Error fetching commit changes for {commit_sha}: {e}")
            return []
    
    def fetch_file_at_commit(
        self,
        file_path: str,
        commit_sha: str
    ) -> Optional[str]:
        """Fetch the contents of a file at a specific commit.
        
        Args:
            file_path: Path to the file in the repository
            commit_sha: The commit SHA
            
        Returns:
            File contents as string, or None if file doesn't exist
        """
        endpoint = f"contents/{file_path}"
        params = {"ref": commit_sha}
        
        try:
            response = self._make_request("GET", endpoint, params=params)
            
            if response and "content" in response:
                import base64
                content = base64.b64decode(response["content"]).decode('utf-8')
                return content
                
        except Exception as e:
            logger.error(f"Error fetching file {file_path} at commit {commit_sha}: {e}")
        
        return None
    
    def get_repository_info(self) -> Dict[str, Any]:
        """Get information about the repository.
        
        Returns:
            Repository information dictionary
        """
        try:
            # Make request to base repo URL (without trailing endpoint)
            url = self._get_repo_url()
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            repo = response.json()
            
            return {
                "name": repo["name"],
                "owner": repo["owner"]["login"],
                "url": repo["html_url"],
                "default_branch": repo["default_branch"],
                "created_at": repo["created_at"],
                "updated_at": repo["updated_at"],
                "metadata": {
                    "description": repo.get("description"),
                    "language": repo.get("language"),
                    "size": repo.get("size"),
                    "stargazers_count": repo.get("stargazers_count"),
                    "forks_count": repo.get("forks_count"),
                    "private": repo.get("private", False)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting repository info: {e}")
            return {}
    
    def test_connection(self) -> bool:
        """Test the connection to GitHub.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try to get repository info as a connection test
            info = self.get_repository_info()
            return bool(info)
            
        except Exception as e:
            logger.error(f"GitHub connection test failed: {e}")
            return False
    
    # GraphQL API Methods
    
    def _execute_graphql_query(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a GraphQL query against GitHub API.
        
        Args:
            query: GraphQL query string
            variables: Query variables
            
        Returns:
            Response JSON from GraphQL API
            
        Raises:
            Exception: If GraphQL query fails
        """
        url = "https://api.github.com/graphql"
        
        try:
            response = self.session.post(
                url,
                json={"query": query, "variables": variables},
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Check for GraphQL errors
            if "errors" in result:
                error_messages = [e.get("message", "Unknown error") for e in result["errors"]]
                raise Exception(f"GraphQL error: {'; '.join(error_messages)}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GraphQL query failed: {e}")
            raise
    
    def _build_blame_query(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        ref: str = "HEAD"
    ) -> Tuple[str, Dict[str, Any]]:
        """Build GraphQL query for blame information.
        
        Args:
            file_path: Path to file in repository
            start_line: Starting line number (1-indexed)
            end_line: Ending line number (inclusive)
            ref: Git ref (branch, tag, commit SHA) to blame at
            
        Returns:
            Tuple of (query string, variables dict)
        """
        # GitHub GraphQL API uses blame on Commit type, not Blob
        query = """
        query ($owner:String!, $name:String!, $ref:String!, $path:String!) {
            repository(owner:$owner, name:$name) {
                ref(qualifiedName: $ref) {
                    target {
                        ... on Commit {
                            blame(path: $path) {
                                ranges {
                                    startingLine
                                    endingLine
                                    age
                                    commit {
                                        oid
                                        committedDate
                                        message
                                        additions
                                        deletions
                                        author {
                                            name
                                            email
                                            user { login }
                                        }
                                        committer {
                                            name
                                            email
                                            user { login }
                                        }
                                        url
                                        associatedPullRequests(first: 1) {
                                            nodes {
                                                number
                                                title
                                                url
                                                author { login }
                                                mergedAt
                                                state
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        # Clean up file path - remove leading slash if present
        clean_path = file_path.lstrip('/')
        
        # Handle ref - if it's a commit SHA, we need to use object instead of ref
        # For now, let's use the branch name
        ref_name = ref if ref != "HEAD" else "main"
        
        variables = {
            "owner": self.repo_owner,
            "name": self.repo_name,
            "ref": ref_name,
            "path": clean_path
        }
        
        return query, variables
    
    def _parse_blame_response(self, response: Dict[str, Any]) -> List[BlameCommitDto]:
        """Parse GraphQL blame response into commit list.
        
        Args:
            response: GraphQL response JSON
            
        Returns:
            List of BlameCommitDto objects with line attribution
            
        Raises:
            Exception: If response has errors or unexpected format
        """
        if "errors" in response:
            error_messages = [e.get("message", "Unknown error") for e in response["errors"]]
            raise Exception(f"GraphQL error: {'; '.join(error_messages)}")
        
        commits: List[BlameCommitDto] = []
        seen_shas: Dict[str, int] = {}  # Map SHA to commit index for consolidation
        
        try:
            # Navigate through the new response structure
            blame_data = response["data"]["repository"]["ref"]["target"]["blame"]
            
            for blame_range in blame_data["ranges"]:
                commit_data = blame_range["commit"]
                sha = commit_data["oid"]
                
                # Extract line range for this blame range
                line_range = BlameLineRangeDto(
                    start=blame_range["startingLine"],
                    end=blame_range["endingLine"]
                )
                
                if sha in seen_shas:
                    # Add line range to existing commit - need to create new DTO since frozen
                    existing_commit = commits[seen_shas[sha]]
                    new_line_ranges = list(existing_commit.line_ranges)
                    new_line_ranges.append(line_range)
                    commits[seen_shas[sha]] = BlameCommitDto(
                        sha=existing_commit.sha,
                        message=existing_commit.message,
                        author=existing_commit.author,
                        author_email=existing_commit.author_email,
                        author_login=existing_commit.author_login,
                        timestamp=existing_commit.timestamp,
                        url=existing_commit.url,
                        additions=existing_commit.additions,
                        deletions=existing_commit.deletions,
                        line_ranges=new_line_ranges,
                        pr_info=existing_commit.pr_info
                    )
                else:
                    # Create new commit entry
                    seen_shas[sha] = len(commits)
                    
                    # Extract PR information if available
                    pr_info = None
                    if commit_data.get("associatedPullRequests", {}).get("nodes"):
                        pr = commit_data["associatedPullRequests"]["nodes"][0]
                        pr_info = PullRequestInfoDto(
                            number=pr["number"],
                            title=pr["title"],
                            url=pr["url"],
                            author=pr.get("author", {}).get("login"),
                            merged_at=pr.get("mergedAt"),
                            state=pr.get("state", "MERGED")
                        )
                    
                    # Extract author information safely
                    author_data = commit_data.get("author", {})
                    author_user = author_data.get("user") if author_data else None
                    
                    commit = BlameCommitDto(
                        sha=sha,
                        message=commit_data["message"],
                        author=author_data.get("name", "Unknown") if author_data else "Unknown",
                        author_email=author_data.get("email") if author_data else None,
                        author_login=author_user.get("login") if author_user else None,
                        timestamp=commit_data["committedDate"],
                        url=commit_data["url"],
                        additions=commit_data.get("additions"),
                        deletions=commit_data.get("deletions"),
                        line_ranges=[line_range],
                        pr_info=pr_info
                    )
                    commits.append(commit)
            
        except KeyError as e:
            logger.error(f"Unexpected GraphQL response structure: {e}")
            raise Exception(f"Failed to parse blame response: {e}")
        
        return commits
    
    def blame_commits_for_range(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        ref: str = "HEAD"
    ) -> List[BlameCommitDto]:
        """Get all commits that modified specific line range using blame.
        
        Args:
            file_path: Path to file in repository
            start_line: Starting line number (1-indexed)
            end_line: Ending line number (inclusive)
            ref: Git ref (branch, tag, commit SHA) to blame at
            
        Returns:
            List of BlameCommitDto objects with line attribution
        """
        # Check cache first
        cache_key = f"{file_path}:{start_line}-{end_line}@{ref}"
        if cache_key in self._blame_cache:
            logger.debug(f"Using cached blame for {cache_key}")
            return self._blame_cache[cache_key]
        
        logger.info(f"Fetching blame for {file_path} lines {start_line}-{end_line} at {ref}")
        
        # Build and execute GraphQL query
        query, variables = self._build_blame_query(file_path, start_line, end_line, ref)
        response = self._execute_graphql_query(query, variables)
        
        # Parse response
        commits = self._parse_blame_response(response)
        
        # Cache results
        self._blame_cache[cache_key] = commits
        
        logger.info(f"Found {len(commits)} commits for {file_path} lines {start_line}-{end_line}")
        return commits
    
    def blame_commits_for_nodes(
        self,
        nodes: List[CodeNodeDto]
    ) -> Dict[str, List[BlameCommitDto]]:
        """Get commits for multiple code nodes efficiently.
        
        Args:
            nodes: List of CodeNodeDto objects
            
        Returns:
            Dictionary mapping node IDs to their BlameCommitDto lists
        """
        results: Dict[str, List[BlameCommitDto]] = {}
        
        # Group nodes by file to optimize queries
        nodes_by_file: Dict[str, List[CodeNodeDto]] = {}
        for node in nodes:
            file_path = node.path
            # Clean file path - remove file:// prefix and make relative
            if file_path.startswith("file://"):
                file_path = file_path[7:]  # Remove file://
            # Make path relative to repository root
            import os
            if os.path.isabs(file_path):
                # Assuming the repo root is the current directory
                file_path = os.path.relpath(file_path, os.getcwd())
            
            if file_path not in nodes_by_file:
                nodes_by_file[file_path] = []
            nodes_by_file[file_path].append(node)
        
        # Process each file
        for file_path, file_nodes in nodes_by_file.items():
            # Merge overlapping ranges to minimize queries
            merged_ranges = self._merge_line_ranges(file_nodes)
            
            for range_info in merged_ranges:
                commits = self.blame_commits_for_range(
                    file_path=file_path,
                    start_line=range_info["start"],
                    end_line=range_info["end"]
                )
                
                # Assign commits to original nodes
                for node in range_info["nodes"]:
                    node_commits: List[BlameCommitDto] = []
                    for commit in commits:
                        # Check if commit actually touches this node's lines
                        if self._ranges_overlap(
                            [{"start": lr.start, "end": lr.end} for lr in commit.line_ranges],
                            node.start_line,
                            node.end_line
                        ):
                            node_commits.append(commit)
                    
                    results[node.id] = node_commits
        
        logger.info(f"Processed blame for {len(nodes)} nodes across {len(nodes_by_file)} files")
        return results
    
    def _merge_line_ranges(self, nodes: List[CodeNodeDto]) -> List[Dict[str, Any]]:
        """Merge overlapping or adjacent line ranges to minimize API calls.
        
        Args:
            nodes: List of nodes with start_line and end_line
            
        Returns:
            List of merged ranges with associated nodes
        """
        if not nodes:
            return []
        
        # Sort nodes by start line
        sorted_nodes = sorted(nodes, key=lambda n: n.start_line)
        
        merged = []
        current_range = {
            "start": sorted_nodes[0].start_line,
            "end": sorted_nodes[0].end_line,
            "nodes": [sorted_nodes[0]]
        }
        
        for node in sorted_nodes[1:]:
            # Check if overlapping or adjacent (within 5 lines)
            if node.start_line <= current_range["end"] + 5:
                # Merge ranges
                current_range["end"] = max(current_range["end"], node.end_line)
                current_range["nodes"].append(node)
            else:
                # Start new range
                merged.append(current_range)
                current_range = {
                    "start": node.start_line,
                    "end": node.end_line,
                    "nodes": [node]
                }
        
        # Add last range
        merged.append(current_range)
        
        logger.debug(f"Merged {len(nodes)} nodes into {len(merged)} ranges")
        return merged
    
    def _ranges_overlap(
        self,
        line_ranges: List[Dict[str, int]],
        start_line: int,
        end_line: int
    ) -> bool:
        """Check if any of the line ranges overlap with given range.
        
        Args:
            line_ranges: List of line range dictionaries with start/end
            start_line: Start of range to check
            end_line: End of range to check
            
        Returns:
            True if any range overlaps, False otherwise
        """
        for range_dict in line_ranges:
            range_start = range_dict["start"]
            range_end = range_dict["end"]
            
            # Check for overlap
            if not (range_end < start_line or range_start > end_line):
                return True
        
        return False