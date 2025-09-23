"""Project configuration management for Blarify CLI and MCP server."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


class ProjectConfig:
    """Manages project configurations for Blarify."""

    @staticmethod
    def get_config_dir() -> Path:
        """Get the Blarify configuration directory."""
        return Path.home() / ".blarify"

    @staticmethod
    def get_credentials_file() -> Path:
        """Get the path to the Neo4j credentials file."""
        return ProjectConfig.get_config_dir() / "neo4j_credentials.json"

    @staticmethod
    def get_projects_file() -> Path:
        """Get the path to the projects configuration file."""
        return ProjectConfig.get_config_dir() / "projects.json"

    @staticmethod
    def load_neo4j_credentials() -> Dict[str, str]:
        """Load Neo4j credentials from storage.

        Returns:
            Dict with 'username' and 'password' keys

        Raises:
            FileNotFoundError: If credentials file doesn't exist
        """
        creds_file = ProjectConfig.get_credentials_file()
        if not creds_file.exists():
            raise FileNotFoundError(
                f"Neo4j credentials not found at {creds_file}. "
                "Please run 'blarify create' first to set up Neo4j."
            )

        with open(creds_file) as f:
            return json.load(f)

    @staticmethod
    def save_project_config(
        repo_id: str,
        entity_id: str,
        neo4j_uri: str
    ) -> None:
        """Save project configuration.

        Args:
            repo_id: Absolute path to the repository
            entity_id: Entity identifier for the project
            neo4j_uri: Neo4j connection URI
        """
        projects_file = ProjectConfig.get_projects_file()
        projects_file.parent.mkdir(exist_ok=True)

        # Load existing projects or create new dict
        if projects_file.exists():
            with open(projects_file) as f:
                projects = json.load(f)
        else:
            projects = {}

        # Normalize repo_id to absolute path
        repo_id = os.path.abspath(repo_id)

        # Update or create project entry
        now = datetime.now(timezone.utc).isoformat()
        if repo_id in projects:
            projects[repo_id]["updated_at"] = now
            projects[repo_id]["entity_id"] = entity_id
            projects[repo_id]["neo4j_uri"] = neo4j_uri
        else:
            projects[repo_id] = {
                "repo_id": repo_id,
                "entity_id": entity_id,
                "neo4j_uri": neo4j_uri,
                "created_at": now,
                "updated_at": now
            }

        # Save projects file
        with open(projects_file, "w") as f:
            json.dump(projects, f, indent=2)
        projects_file.chmod(0o600)

    @staticmethod
    def load_project_config(repo_id: Optional[str] = None) -> Dict[str, str]:
        """Load project configuration.

        Args:
            repo_id: Repository path/id. If None, tries to auto-detect from CWD.

        Returns:
            Project configuration dictionary

        Raises:
            FileNotFoundError: If projects file doesn't exist
            KeyError: If specified project not found
        """
        projects_file = ProjectConfig.get_projects_file()
        if not projects_file.exists():
            raise FileNotFoundError(
                "No projects found. Please run 'blarify create' first."
            )

        with open(projects_file) as f:
            projects = json.load(f)

        if not projects:
            raise FileNotFoundError("No projects configured.")

        # If no repo_id specified, try to auto-detect
        if repo_id is None:
            repo_id = ProjectConfig.find_project_by_path(os.getcwd())
            if repo_id is None:
                # If only one project exists, use it
                if len(projects) == 1:
                    repo_id = next(iter(projects.keys()))
                else:
                    raise KeyError(
                        "Multiple projects found. Please specify --project or run from a project directory."
                    )

        # Normalize repo_id
        repo_id = os.path.abspath(repo_id)

        if repo_id not in projects:
            raise KeyError(f"Project not found: {repo_id}")

        return projects[repo_id]

    @staticmethod
    def list_projects() -> List[Dict[str, str]]:
        """List all configured projects.

        Returns:
            List of project configurations
        """
        projects_file = ProjectConfig.get_projects_file()
        if not projects_file.exists():
            return []

        with open(projects_file) as f:
            projects = json.load(f)

        return list(projects.values())

    @staticmethod
    def find_project_by_path(current_path: str) -> Optional[str]:
        """Find a project that contains the given path.

        Args:
            current_path: Path to check

        Returns:
            repo_id of matching project, or None if not found
        """
        projects_file = ProjectConfig.get_projects_file()
        if not projects_file.exists():
            return None

        with open(projects_file) as f:
            projects = json.load(f)

        # Normalize current path
        current_path = os.path.abspath(current_path)

        # Check if current path is within any project
        for repo_id in projects.keys():
            repo_path = os.path.abspath(repo_id)
            # Check if current_path is repo_path or a subdirectory of it
            if current_path == repo_path or current_path.startswith(repo_path + os.sep):
                return repo_id

        return None

    @staticmethod
    def delete_project(repo_id: str) -> bool:
        """Delete a project configuration.

        Args:
            repo_id: Repository path/id to delete

        Returns:
            True if deleted, False if not found
        """
        projects_file = ProjectConfig.get_projects_file()
        if not projects_file.exists():
            return False

        with open(projects_file) as f:
            projects = json.load(f)

        # Normalize repo_id
        repo_id = os.path.abspath(repo_id)

        if repo_id in projects:
            del projects[repo_id]
            with open(projects_file, "w") as f:
                json.dump(projects, f, indent=2)
            return True

        return False