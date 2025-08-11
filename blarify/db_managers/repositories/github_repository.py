"""GitHub API repository for fetching PR and commit data."""

import os
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class GitHubRepository:
    """
    Repository class for GitHub API interactions.
    
    Handles fetching PRs, commits, and file changes from GitHub with
    proper authentication, rate limiting, and error handling.
    """
    
    def __init__(
        self,
        token: Optional[str] = None,
        repo_owner: str = None,
        repo_name: str = None,
        api_version: str = "v3"
    ):
        """
        Initialize GitHub repository client.
        
        Args:
            token: GitHub personal access token (optional, uses env var if not provided)
            repo_owner: Repository owner/organization
            repo_name: Repository name
            api_version: GitHub API version (v3 or v4)
        """
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.repo_owner = repo_owner or os.getenv("GITHUB_REPO_OWNER")
        self.repo_name = repo_name or os.getenv("GITHUB_REPO_NAME")
        self.api_version = api_version
        self.base_url = "https://api.github.com"
        
        if not self.repo_owner or not self.repo_name:
            raise ValueError("Repository owner and name must be provided or set in environment variables")
        
        # Set up session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set up headers
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Blarify-GitHub-Integration/1.0"
        })
        
        if self.token:
            self.session.headers.update({
                "Authorization": f"token {self.token}"
            })
        
    def _handle_rate_limit(self, response: requests.Response) -> None:
        """
        Handle GitHub API rate limiting.
        
        Args:
            response: Response object from GitHub API
        """
        if response.status_code == 403:
            # Check if it's rate limiting
            remaining = response.headers.get('X-RateLimit-Remaining', '0')
            if int(remaining) == 0:
                reset_time = int(response.headers.get('X-RateLimit-Reset', '0'))
                if reset_time:
                    wait_time = reset_time - int(time.time())
                    if wait_time > 0:
                        logger.warning(f"Rate limit exceeded. Waiting {wait_time} seconds...")
                        time.sleep(wait_time + 1)
                    
    def fetch_prs(
        self,
        limit: int = 50,
        since_date: Optional[str] = None,
        state: str = "all"
    ) -> List[Dict[str, Any]]:
        """
        Fetch pull requests from GitHub.
        
        Args:
            limit: Maximum number of PRs to fetch
            since_date: ISO format date to fetch PRs since (optional)
            state: PR state filter ("open", "closed", "all")
            
        Returns:
            List of PR data dictionaries
        """
        prs = []
        page = 1
        per_page = min(limit, 100)  # GitHub max is 100 per page
        
        while len(prs) < limit:
            params = {
                "state": state,
                "sort": "updated",
                "direction": "desc",
                "per_page": per_page,
                "page": page
            }
            
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls"
            
            try:
                response = self.session.get(url, params=params)
                self._handle_rate_limit(response)
                response.raise_for_status()
                
                page_prs = response.json()
                
                if not page_prs:
                    break
                
                # Filter by date if specified
                if since_date:
                    since_dt = datetime.fromisoformat(since_date.replace('Z', '+00:00'))
                    page_prs = [
                        pr for pr in page_prs
                        if datetime.fromisoformat(pr['updated_at'].replace('Z', '+00:00')) >= since_dt
                    ]
                
                prs.extend(page_prs)
                
                if len(page_prs) < per_page:
                    break  # No more pages
                    
                page += 1
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching PRs: {e}")
                break
        
        return prs[:limit]
    
    def fetch_commits_for_pr(self, pr_number: int) -> List[Dict[str, Any]]:
        """
        Fetch commits associated with a pull request.
        
        Args:
            pr_number: Pull request number
            
        Returns:
            List of commit data dictionaries
        """
        commits = []
        page = 1
        per_page = 100
        
        while True:
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}/commits"
            params = {"per_page": per_page, "page": page}
            
            try:
                response = self.session.get(url, params=params)
                self._handle_rate_limit(response)
                response.raise_for_status()
                
                page_commits = response.json()
                
                if not page_commits:
                    break
                
                commits.extend(page_commits)
                
                if len(page_commits) < per_page:
                    break
                    
                page += 1
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching commits for PR {pr_number}: {e}")
                break
        
        return commits
    
    def fetch_commit_changes(self, commit_sha: str) -> Dict[str, Any]:
        """
        Fetch detailed file changes for a specific commit.
        
        Args:
            commit_sha: Commit SHA
            
        Returns:
            Dictionary with commit details including file changes
        """
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/commits/{commit_sha}"
        
        try:
            response = self.session.get(url)
            self._handle_rate_limit(response)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching commit {commit_sha}: {e}")
            return {}
    
    def fetch_pr_details(self, pr_number: int) -> Dict[str, Any]:
        """
        Fetch detailed information about a specific PR.
        
        Args:
            pr_number: Pull request number
            
        Returns:
            Dictionary with PR details
        """
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}"
        
        try:
            response = self.session.get(url)
            self._handle_rate_limit(response)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching PR {pr_number}: {e}")
            return {}
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Get current rate limit status.
        
        Returns:
            Dictionary with rate limit information
        """
        url = f"{self.base_url}/rate_limit"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching rate limit status: {e}")
            return {}
    
    def test_connection(self) -> bool:
        """
        Test connection to GitHub API.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to fetch repository information
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}"
            response = self.session.get(url)
            response.raise_for_status()
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub connection test failed: {e}")
            return False