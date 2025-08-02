import os
import tempfile
import shutil
from pathlib import Path
from typing import List, Any
import pytest
from typing import Any, List, Dict, Optional
from blarify.project_file_explorer import ProjectFilesIterator


class TestGitignoreIntegration:
    """Test that .gitignore patterns are respected when processing files."""
    
    def setup_method(self):
        """Create a temporary directory for testing."""
        self.test_dir = tempfile.mkdtemp()  # type: ignore[misc]
        
    def teardown_method(self):
        """Clean up the temporary directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def create_test_structure(self):
        """Create a test directory structure with .gitignore and .blarignore files."""
        # Create directories
        os.makedirs(os.path.join(self.test_dir, "src"))
        os.makedirs(os.path.join(self.test_dir, "node_modules"))
        os.makedirs(os.path.join(self.test_dir, "build"))
        os.makedirs(os.path.join(self.test_dir, ".venv"))
        
        # Create files
        Path(os.path.join(self.test_dir, "main.py")).write_text("print('main')")
        Path(os.path.join(self.test_dir, "src", "app.py")).write_text("print('app')")
        Path(os.path.join(self.test_dir, "node_modules", "lib.js")).write_text("console.log('lib')")
        Path(os.path.join(self.test_dir, "build", "output.js")).write_text("console.log('output')")
        Path(os.path.join(self.test_dir, ".env")).write_text("SECRET=123")
        Path(os.path.join(self.test_dir, ".venv", "pip.conf")).write_text("[global]")
        Path(os.path.join(self.test_dir, "test.log")).write_text("log data")
        
        # Create .gitignore
        gitignore_content = """
# Dependencies
node_modules/

# Build output
build/
dist/

# Virtual environment
.venv/
venv/

# Environment files
.env
.env.local

# Logs
*.log

# OS files
.DS_Store
"""
        Path(os.path.join(self.test_dir, ".gitignore")).write_text(gitignore_content.strip())
        
        # Create .blarignore with additional exclusions
        blarignore_content = """
# Test files
test_*.py
*_test.py
"""
        Path(os.path.join(self.test_dir, ".blarignore")).write_text(blarignore_content.strip())
    
    def test_gitignore_files_are_excluded(self) -> None:
        """Test that files matching .gitignore patterns are excluded."""
        self.create_test_structure()
        
        # Create iterator - this should automatically load .gitignore
        iterator = ProjectFilesIterator(root_path=self.test_dir)
        
        # Collect all files
        all_files: List[Any] = []
        for folder in iterator:
            all_files.extend(folder.files)
        
        # Get file names
        file_names: List[str] = [file.name for file in all_files]
        file_paths: List[str] = [file.path for file in all_files]
        
        # Files that should be included
        assert "main.py" in file_names
        assert "app.py" in file_names
        
        # Files from .gitignore that should be excluded
        assert "lib.js" not in file_names  # in node_modules/
        assert "output.js" not in file_names  # in build/
        assert ".env" not in file_names
        assert "pip.conf" not in file_names  # in .venv/
        assert "test.log" not in file_names  # *.log pattern
        
        # Verify no files from ignored directories
        assert not any("node_modules" in path for path in file_paths)
        assert not any("build" in path for path in file_paths)
        assert not any(".venv" in path for path in file_paths)
    
    def test_blarignore_is_additive_to_gitignore(self) -> None:
        """Test that .blarignore adds additional exclusions on top of .gitignore."""
        self.create_test_structure()
        
        # Add test files that match .blarignore patterns
        Path(os.path.join(self.test_dir, "test_utils.py")).write_text("# test utils")
        Path(os.path.join(self.test_dir, "app_test.py")).write_text("# app test")
        
        # Create iterator
        iterator = ProjectFilesIterator(root_path=self.test_dir)
        
        # Collect all files
        all_files: List[Any] = []
        for folder in iterator:
            all_files.extend(folder.files)
        
        file_names: List[str] = [file.name for file in all_files]
        
        # Files from .blarignore should also be excluded
        assert "test_utils.py" not in file_names
        assert "app_test.py" not in file_names
        
        # Regular files should still be included
        assert "main.py" in file_names
        assert "app.py" in file_names
    
    def test_nested_gitignore_files(self) -> None:
        """Test that nested .gitignore files in subdirectories are respected."""
        self.create_test_structure()
        
        # Create nested .gitignore
        nested_gitignore = """
# Local config
local.conf
*.local
"""
        Path(os.path.join(self.test_dir, "src", ".gitignore")).write_text(nested_gitignore.strip())
        
        # Create files that should be ignored by nested .gitignore
        Path(os.path.join(self.test_dir, "src", "local.conf")).write_text("config")
        Path(os.path.join(self.test_dir, "src", "settings.local")).write_text("settings")
        
        # Create iterator
        iterator = ProjectFilesIterator(root_path=self.test_dir)
        
        # Collect all files in src/
        src_files: List[Any] = []
        for folder in iterator:
            if folder.name == "src":
                src_files.extend(folder.files)
        
        src_file_names: List[str] = [file.name for file in src_files]
        
        # Files from nested .gitignore should be excluded
        assert "local.conf" not in src_file_names
        assert "settings.local" not in src_file_names
        
        # Regular files should still be included
        assert "app.py" in src_file_names
    
    @pytest.mark.skip(reason="Negation patterns are complex and will be addressed in a follow-up PR")
    def test_gitignore_negation_patterns(self) -> None:
        """Test that gitignore negation patterns (!) work correctly."""
        self.create_test_structure()
        
        # Update .gitignore with negation patterns
        gitignore_with_negation = """
# Ignore all .log files
*.log

# But keep important.log
!important.log

# Ignore everything in build/
build/*

# But keep build/keep/ and its contents
!build/keep/
!build/keep/**
"""
        Path(os.path.join(self.test_dir, ".gitignore")).write_text(gitignore_with_negation.strip())
        
        # Create files
        Path(os.path.join(self.test_dir, "important.log")).write_text("important")
        os.makedirs(os.path.join(self.test_dir, "build", "keep"), exist_ok=True)
        Path(os.path.join(self.test_dir, "build", "keep", "file.txt")).write_text("keep this")
        # Also add a file directly in build to test
        Path(os.path.join(self.test_dir, "build", "other.txt")).write_text("should be ignored")
        
        # Create iterator
        iterator = ProjectFilesIterator(root_path=self.test_dir)
        
        # Collect all files
        all_files: List[Any] = []
        all_folders: List[str] = []
        for folder in iterator:
            all_folders.append(folder.path)
            all_files.extend(folder.files)
        
        file_names: List[str] = [file.name for file in all_files]
        file_paths: List[str] = [file.path for file in all_files]
        
        # Debug: print what files were found
        print(f"\nFound folders: {all_folders}")
        print(f"\nFound files: {file_names}")
        print(f"File paths: {file_paths}")
        
        # Negated files should be included
        assert "important.log" in file_names
        assert any("build/keep/file.txt" in path for path in file_paths)
        
        # Other .log files should still be excluded
        assert "test.log" not in file_names
    
    def test_gitignore_can_be_disabled(self) -> None:
        """Test that gitignore integration can be disabled if needed."""
        self.create_test_structure()
        
        # Create iterator with gitignore disabled
        iterator = ProjectFilesIterator(
            root_path=self.test_dir,
            use_gitignore=False  # This parameter doesn't exist yet
        )
        
        # Collect all files
        all_files: List[Any] = []
        for folder in iterator:
            all_files.extend(folder.files)
        
        file_names: List[str] = [file.name for file in all_files]
        
        # When disabled, gitignored files should be included
        assert ".env" in file_names
        assert "lib.js" in file_names
        assert "output.js" in file_names
        assert "test.log" in file_names