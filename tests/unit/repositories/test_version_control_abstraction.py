"""Test abstract version controller interface."""

import pytest
from datetime import datetime
from typing import Dict, List, Any, Optional

from blarify.repositories.version_control.abstract_version_controller import AbstractVersionController


def test_abstract_version_controller_interface():
    """Test AbstractVersionController defines required methods."""
    assert hasattr(AbstractVersionController, 'fetch_pull_requests')
    assert hasattr(AbstractVersionController, 'fetch_commits')
    assert hasattr(AbstractVersionController, 'fetch_commit_changes')
    assert hasattr(AbstractVersionController, 'fetch_file_at_commit')
    assert hasattr(AbstractVersionController, 'get_repository_info')
    assert hasattr(AbstractVersionController, 'test_connection')


def test_cannot_instantiate_abstract():
    """Test AbstractVersionController cannot be instantiated."""
    with pytest.raises(TypeError):
        AbstractVersionController()


def test_parse_patch_header():
    """Test patch header parsing utility method."""
    # Create a concrete implementation for testing
    class TestController(AbstractVersionController):
        def fetch_pull_requests(self, *args, **kwargs):
            pass
        def fetch_commits(self, *args, **kwargs):
            pass
        def fetch_commit_changes(self, *args, **kwargs):
            pass
        def fetch_file_at_commit(self, *args, **kwargs):
            pass
        def get_repository_info(self):
            pass
        def test_connection(self):
            pass
    
    controller = TestController()
    
    # Test standard patch header
    result = controller.parse_patch_header("@@ -45,7 +45,15 @@")
    assert result["deleted"]["start_line"] == 45
    assert result["deleted"]["line_count"] == 7
    assert result["added"]["start_line"] == 45
    assert result["added"]["line_count"] == 15
    
    # Test single line change
    result = controller.parse_patch_header("@@ -10 +10 @@")
    assert result["deleted"]["start_line"] == 10
    assert result["deleted"]["line_count"] == 1
    assert result["added"]["start_line"] == 10
    assert result["added"]["line_count"] == 1
    
    # Test invalid header
    result = controller.parse_patch_header("invalid")
    assert result["deleted"] == {}
    assert result["added"] == {}


def test_extract_change_ranges():
    """Test extraction of change ranges from patch."""
    class TestController(AbstractVersionController):
        def fetch_pull_requests(self, *args, **kwargs):
            pass
        def fetch_commits(self, *args, **kwargs):
            pass
        def fetch_commit_changes(self, *args, **kwargs):
            pass
        def fetch_file_at_commit(self, *args, **kwargs):
            pass
        def get_repository_info(self):
            pass
        def test_connection(self):
            pass
    
    controller = TestController()
    
    patch = """@@ -45,7 +45,15 @@ class LoginHandler:
-    def authenticate(self, user):
-        # Old implementation
-        return False
+    def authenticate(self, user, password):
+        # New implementation
+        if not user or not password:
+            return False
+        
+        hashed = self.hash_password(password)
+        stored = self.get_stored_password(user)
+        return hashed == stored"""
    
    changes = controller.extract_change_ranges(patch)
    
    # Check we have both deletions and additions
    deletions = [c for c in changes if c["type"] == "deletion"]
    additions = [c for c in changes if c["type"] == "addition"]
    
    assert len(deletions) == 3
    assert len(additions) == 8
    
    # Check first deletion
    assert deletions[0]["line_start"] == 45
    assert "def authenticate(self, user):" in deletions[0]["content"]
    
    # Check first addition
    assert additions[0]["line_start"] == 45
    assert "def authenticate(self, user, password):" in additions[0]["content"]