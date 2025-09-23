"""Unit tests for project configuration management."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import pytest

from blarify.cli.project_config import ProjectConfig


class TestProjectConfig:
    """Test project configuration management."""

    def test_saves_and_loads_project_config(self, tmp_path: Path, monkeypatch):
        """Test saving and loading project configuration."""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Save a project
        repo_id = "/test/project/path"
        entity_id = "test_entity"
        neo4j_uri = "bolt://localhost:7687"

        ProjectConfig.save_project_config(repo_id, entity_id, neo4j_uri)

        # Load the project
        config = ProjectConfig.load_project_config(repo_id)

        assert config["repo_id"] == repo_id
        assert config["entity_id"] == entity_id
        assert config["neo4j_uri"] == neo4j_uri
        assert "created_at" in config
        assert "updated_at" in config

    def test_updates_existing_project(self, tmp_path: Path, monkeypatch):
        """Test updating an existing project configuration."""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        repo_id = "/test/project/path"

        # Save initial config
        ProjectConfig.save_project_config(repo_id, "entity1", "bolt://localhost:7687")
        config1 = ProjectConfig.load_project_config(repo_id)
        created_at = config1["created_at"]

        # Update config
        ProjectConfig.save_project_config(repo_id, "entity2", "bolt://localhost:7688")
        config2 = ProjectConfig.load_project_config(repo_id)

        # Created time should be preserved, updated time should change
        assert config2["created_at"] == created_at
        assert config2["updated_at"] != created_at
        assert config2["entity_id"] == "entity2"
        assert config2["neo4j_uri"] == "bolt://localhost:7688"

    def test_lists_multiple_projects(self, tmp_path: Path, monkeypatch):
        """Test listing multiple projects."""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Save multiple projects
        ProjectConfig.save_project_config("/project1", "entity1", "bolt://localhost:7687")
        ProjectConfig.save_project_config("/project2", "entity2", "bolt://localhost:7688")
        ProjectConfig.save_project_config("/project3", "entity3", "bolt://localhost:7689")

        # List projects
        projects = ProjectConfig.list_projects()

        assert len(projects) == 3
        repo_ids = [p["repo_id"] for p in projects]
        assert "/project1" in repo_ids
        assert "/project2" in repo_ids
        assert "/project3" in repo_ids

    def test_finds_project_by_path(self, tmp_path: Path, monkeypatch):
        """Test finding a project by current path."""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Save a project
        ProjectConfig.save_project_config("/test/project", "entity1", "bolt://localhost:7687")

        # Test exact match
        found = ProjectConfig.find_project_by_path("/test/project")
        assert found == "/test/project"

        # Test subdirectory
        found = ProjectConfig.find_project_by_path("/test/project/src/subdir")
        assert found == "/test/project"

        # Test non-matching path
        found = ProjectConfig.find_project_by_path("/other/path")
        assert found is None

    def test_auto_uses_single_project(self, tmp_path: Path, monkeypatch):
        """Test auto-selection when only one project exists."""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Save single project
        ProjectConfig.save_project_config("/single/project", "entity1", "bolt://localhost:7687")

        # Load without specifying repo_id (should auto-select)
        config = ProjectConfig.load_project_config()

        assert config["repo_id"] == "/single/project"
        assert config["entity_id"] == "entity1"

    def test_raises_error_for_multiple_projects_without_selection(self, tmp_path: Path, monkeypatch):
        """Test error when multiple projects exist without selection."""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Save multiple projects
        ProjectConfig.save_project_config("/project1", "entity1", "bolt://localhost:7687")
        ProjectConfig.save_project_config("/project2", "entity2", "bolt://localhost:7688")

        # Mock current directory to not match any project
        monkeypatch.chdir(str(tmp_path))

        # Should raise error when no project specified
        with pytest.raises(KeyError) as excinfo:
            ProjectConfig.load_project_config()

        assert "Multiple projects found" in str(excinfo.value)

    def test_deletes_project(self, tmp_path: Path, monkeypatch):
        """Test deleting a project configuration."""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Save and then delete
        ProjectConfig.save_project_config("/test/project", "entity1", "bolt://localhost:7687")
        assert len(ProjectConfig.list_projects()) == 1

        # Delete the project
        result = ProjectConfig.delete_project("/test/project")
        assert result is True
        assert len(ProjectConfig.list_projects()) == 0

        # Try deleting non-existent project
        result = ProjectConfig.delete_project("/non/existent")
        assert result is False

    def test_handles_missing_config_files(self, tmp_path: Path, monkeypatch):
        """Test proper error handling when config files don't exist."""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Test loading credentials when file doesn't exist
        with pytest.raises(FileNotFoundError) as excinfo:
            ProjectConfig.load_neo4j_credentials()
        assert "Neo4j credentials not found" in str(excinfo.value)

        # Test loading projects when file doesn't exist
        with pytest.raises(FileNotFoundError) as excinfo:
            ProjectConfig.load_project_config("/some/path")
        assert "No projects found" in str(excinfo.value)

        # Test listing projects when file doesn't exist
        projects = ProjectConfig.list_projects()
        assert projects == []

    def test_normalizes_paths(self, tmp_path: Path, monkeypatch):
        """Test that paths are properly normalized to absolute paths."""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Save with relative path
        import os
        original_cwd = os.getcwd()
        os.chdir(str(tmp_path))

        ProjectConfig.save_project_config("./relative/path", "entity1", "bolt://localhost:7687")

        # Should be saved as absolute path
        projects = ProjectConfig.list_projects()
        assert len(projects) == 1
        assert projects[0]["repo_id"] == os.path.abspath("./relative/path")

        os.chdir(original_cwd)