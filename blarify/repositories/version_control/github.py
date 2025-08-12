"""GitHub implementation of the version control interface."""

import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from blarify.repositories.version_control.abstract_version_controller import AbstractVersionController

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