"""Unit tests for Neo4j credential management."""
# pyright: reportMissingParameterType=false

import json
from pathlib import Path

from blarify.cli.commands import create


class TestNeo4jCredentials:
    """Test credential management for Neo4j containers."""

    def test_generates_secure_random_password(self):
        """Test password generation meets security requirements."""
        password = create.generate_neo4j_password()

        # Check length
        assert len(password) == 16

        # Check it's alphanumeric
        assert password.isalnum()

        # Test randomness (different calls produce different passwords)
        password2 = create.generate_neo4j_password()
        assert password != password2

        # Check minimum Neo4j requirement (8 chars)
        assert len(password) >= 8

    def test_password_contains_mix_of_characters(self):
        """Test that generated passwords have good character distribution."""
        # Generate multiple passwords to check randomness
        passwords = [create.generate_neo4j_password() for _ in range(10)]

        # All should be unique
        assert len(set(passwords)) == 10

        # Check that we get both letters and numbers (statistically)
        has_letter = False
        has_digit = False
        for password in passwords:
            if any(c.isalpha() for c in password):
                has_letter = True
            if any(c.isdigit() for c in password):
                has_digit = True

        assert has_letter
        assert has_digit

    def test_stores_credentials_securely(self, tmp_path: Path, monkeypatch):
        """Test credentials are stored with correct permissions."""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        creds = {"username": "neo4j", "password": "test12345678"}
        create.store_neo4j_credentials(creds)

        creds_file = tmp_path / ".blarify" / "neo4j_credentials.json"

        # Check file exists
        assert creds_file.exists()

        # Check permissions (0o600 = read/write for owner only)
        stat_info = creds_file.stat()
        assert oct(stat_info.st_mode)[-3:] == "600"

        # Check content
        with open(creds_file) as f:
            stored = json.load(f)
        assert stored == creds

    def test_loads_existing_credentials(self, tmp_path: Path, monkeypatch):
        """Test loading existing credentials from file."""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Create credentials file
        creds_file = tmp_path / ".blarify" / "neo4j_credentials.json"
        creds_file.parent.mkdir(parents=True)
        creds = {"username": "neo4j", "password": "existing123"}
        creds_file.write_text(json.dumps(creds))

        # Load credentials
        loaded = create.get_or_create_neo4j_credentials()
        assert loaded == creds

    def test_creates_new_credentials_when_none_exist(self, tmp_path: Path, monkeypatch):
        """Test new credentials are created when file doesn't exist."""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        creds = create.get_or_create_neo4j_credentials()

        # Check structure
        assert "username" in creds
        assert "password" in creds

        # Check values
        assert creds["username"] == "neo4j"
        assert len(creds["password"]) == 16
        assert creds["password"].isalnum()

        # Check file was created
        creds_file = tmp_path / ".blarify" / "neo4j_credentials.json"
        assert creds_file.exists()

    def test_creates_blarify_directory_if_not_exists(self, tmp_path: Path, monkeypatch):
        """Test that .blarify directory is created if it doesn't exist."""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Ensure directory doesn't exist
        blarify_dir = tmp_path / ".blarify"
        assert not blarify_dir.exists()

        # Create credentials
        create.get_or_create_neo4j_credentials()

        # Check directory was created
        assert blarify_dir.exists()
        assert blarify_dir.is_dir()

    def test_credentials_file_is_json_formatted(self, tmp_path: Path, monkeypatch):
        """Test that credentials file is valid JSON."""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        creds = {"username": "test_user", "password": "test_pass_123"}
        create.store_neo4j_credentials(creds)

        creds_file = tmp_path / ".blarify" / "neo4j_credentials.json"

        # Read and parse as JSON
        with open(creds_file) as f:
            loaded = json.load(f)  # This will raise if not valid JSON

        assert loaded == creds

    def test_overwrites_existing_credentials(self, tmp_path: Path, monkeypatch):
        """Test that storing credentials overwrites existing file."""
        # Mock home directory
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        # Store initial credentials
        initial_creds = {"username": "neo4j", "password": "initial123"}
        create.store_neo4j_credentials(initial_creds)

        # Store new credentials
        new_creds = {"username": "neo4j", "password": "newpass456"}
        create.store_neo4j_credentials(new_creds)

        # Check that new credentials are stored
        creds_file = tmp_path / ".blarify" / "neo4j_credentials.json"
        with open(creds_file) as f:
            loaded = json.load(f)

        assert loaded == new_creds
        assert loaded != initial_creds
