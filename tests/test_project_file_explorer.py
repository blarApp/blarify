"""
Tests for project file exploration functionality.
"""
import unittest
from unittest.mock import Mock, patch
import tempfile
import os
from pathlib import Path

from blarify.project_file_explorer.file import File
from blarify.project_file_explorer.folder import Folder
from blarify.project_file_explorer.project_files_iterator import ProjectFilesIterator
from blarify.project_file_explorer.project_files_stats import ProjectFileStats


class TestFile(unittest.TestCase):
    """Test File class functionality."""
    
    def test_file_creation(self) -> None:
        """Test creating a File instance."""
        file = File(
            name="main.py",
            root_path="/test",
            level=2
        )
        
        self.assertEqual(file.path, "/test/main.py")
        self.assertEqual(file.name, "main.py")
        self.assertEqual(file.extension, ".py")
        self.assertEqual(file.level, 2)
        
    def test_file_str_representation(self) -> None:
        """Test string representation of File."""
        file = File(
            name="utils.py",
            root_path="/test/src",
            level=3
        )
        
        str_repr = str(file)
        self.assertIn("utils.py", str_repr)
        self.assertIn("/test/src/utils.py", str_repr)
        
    def test_file_equality(self) -> None:
        """Test File equality comparison."""
        file1 = File("main.py", "/test", 2)
        file2 = File("main.py", "/test", 2)
        file3 = File("other.py", "/test", 2)
        
        self.assertEqual(file1, file2)
        self.assertNotEqual(file1, file3)


class TestFolder(unittest.TestCase):
    """Test Folder class functionality."""
    
    def test_folder_creation(self) -> None:
        """Test creating a Folder instance."""
        folder = Folder(
            name="src",
            path="/test/src",
            files=[],
            folders=[],
            level=1
        )
        
        self.assertEqual(folder.path, "/test/src")
        self.assertEqual(folder.name, "src")
        self.assertEqual(folder.level, 1)
        self.assertEqual(folder.files, [])
        self.assertEqual(folder.folders, [])
        
    def test_add_file_to_folder(self) -> None:
        """Test adding files to a folder."""
        folder = Folder("src", "/test/src", [], [], 1)
        file1 = File("main.py", "/test/src", 2)
        file2 = File("utils.py", "/test/src", 2)
        
        folder.files.append(file1)
        folder.files.append(file2)
        
        self.assertEqual(len(folder.files), 2)
        self.assertIn(file1, folder.files)
        self.assertIn(file2, folder.files)
        
    def test_add_subfolder(self) -> None:
        """Test adding subfolders to a folder."""
        parent = Folder("test", "/test", [], [], 0)
        child1 = Folder("src", "/test/src", [], [], 1)
        child2 = Folder("tests", "/test/tests", [], [], 1)
        
        parent.folders.append(child1)
        parent.folders.append(child2)
        
        self.assertEqual(len(parent.folders), 2)
        self.assertIn(child1, parent.folders)
        self.assertIn(child2, parent.folders)
        
    def test_folder_traversal(self) -> None:
        """Test traversing folder structure."""
        # Create structure
        root = Folder("test", "/test", [], [], 0)
        src = Folder("src", "/test/src", [], [], 1)
        utils = Folder("utils", "/test/src/utils", [], [], 2)
        
        root.folders.append(src)
        src.folders.append(utils)
        
        # Add files
        main_file = File("main.py", "/test", 1)
        util_file = File("helper.py", "/test/src/utils", 3)
        
        root.files.append(main_file)
        utils.files.append(util_file)
        
        # Test traversal
        self.assertEqual(len(root.files), 1)
        self.assertEqual(len(root.folders), 1)
        self.assertEqual(len(src.folders), 1)
        self.assertEqual(len(utils.files), 1)


class TestProjectFilesIterator(unittest.TestCase):
    """Test project files iteration."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir: str = tempfile.mkdtemp()  # type: ignore[misc]
        
    def tearDown(self) -> None:
        """Clean up test directory."""
        import shutil
        shutil.rmtree(self.temp_dir)
        
    def create_test_structure(self):
        """Create test file structure."""
        # Create directories
        (Path(self.temp_dir) / "src").mkdir()
        (Path(self.temp_dir) / "tests").mkdir()
        (Path(self.temp_dir) / "__pycache__").mkdir()
        
        # Create files
        files = {
            "README.md": "# Test Project",
            "setup.py": "setup()",
            "src/main.py": "def main(): pass",
            "src/utils.py": "def util(): pass",
            "tests/test_main.py": "def test(): pass",
            "__pycache__/cache.pyc": "compiled",
            ".gitignore": "*.pyc"
        }
        
        for path, content in files.items():
            file_path = Path(self.temp_dir) / path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            
    def test_iterate_all_files(self) -> None:
        """Test iterating through all project files."""
        self.create_test_structure()
        
        iterator = ProjectFilesIterator(
            root_path=self.temp_dir,
            extensions_to_skip=[],
            names_to_skip=[]
        )
        
        folders = list(iterator)
        all_files = []  # type: ignore[var-annotated]
        for folder in folders:
            all_files.extend(folder.files)  # type: ignore[union-attr]
        file_names = [f.name for f in all_files]  # type: ignore[union-attr]
        
        # Should include all files
        self.assertIn("README.md", file_names)  # type: ignore[arg-type]
        self.assertIn("setup.py", file_names)  # type: ignore[arg-type]
        self.assertIn("main.py", file_names)  # type: ignore[arg-type]
        self.assertIn("utils.py", file_names)  # type: ignore[arg-type]
        self.assertIn("test_main.py", file_names)  # type: ignore[arg-type]
        
    def test_skip_extensions(self) -> None:
        """Test skipping files by extension."""
        self.create_test_structure()
        
        iterator = ProjectFilesIterator(
            root_path=self.temp_dir,
            extensions_to_skip=[".pyc", ".pyo"],
            names_to_skip=[]
        )
        
        folders = list(iterator)
        all_files = []  # type: ignore[var-annotated]
        for folder in folders:
            all_files.extend(folder.files)  # type: ignore[union-attr]
        file_names = [f.name for f in all_files]  # type: ignore[union-attr]
        
        # Should not include .pyc files
        self.assertNotIn("cache.pyc", file_names)  # type: ignore[arg-type]
        # Should include other files
        self.assertIn("main.py", file_names)  # type: ignore[arg-type]
        
    def test_skip_folders(self) -> None:
        """Test skipping folders by name."""
        self.create_test_structure()
        
        iterator = ProjectFilesIterator(
            root_path=self.temp_dir,
            extensions_to_skip=[],
            names_to_skip=["__pycache__", "tests"]
        )
        
        folders = list(iterator)
        folder_paths = [f.path for f in folders]  # type: ignore[union-attr]
        all_files = []  # type: ignore[var-annotated]
        for folder in folders:
            all_files.extend(folder.files)  # type: ignore[union-attr]
        file_paths = [f.path for f in all_files]  # type: ignore[union-attr]
        
        # Should not include files from skipped folders
        pycache_folders = [p for p in folder_paths if "__pycache__" in p]  # type: ignore[operator]
        test_folders = [p for p in folder_paths if "tests" in p]  # type: ignore[operator]
        
        self.assertEqual(len(pycache_folders), 0)
        self.assertEqual(len(test_folders), 0)
        
        # Should include files from other folders
        self.assertTrue(any("main.py" in str(p) for p in file_paths))  # type: ignore[union-attr]
        
    def test_file_levels(self) -> None:
        """Test that file levels are calculated correctly."""
        self.create_test_structure()
        
        iterator = ProjectFilesIterator(
            root_path=self.temp_dir,
            extensions_to_skip=[],
            names_to_skip=[]
        )
        
        folders = list(iterator)
        
        # Find files at different levels
        readme = None
        main = None
        for folder in folders:
            for file in folder.files:
                if file.name == "README.md":
                    readme = file
                elif file.name == "main.py":
                    main = file
        
        self.assertIsNotNone(readme)
        self.assertIsNotNone(main)
        
        # README is at root level (0 or 1 depending on implementation)
        # main.py is one level deeper
        self.assertLess(readme.level, main.level)  # type: ignore[union-attr]
        
    def test_empty_directory(self) -> None:
        """Test iterating empty directory."""
        iterator = ProjectFilesIterator(
            root_path=self.temp_dir,
            extensions_to_skip=[],
            names_to_skip=[]
        )
        
        folders = list(iterator)
        
        # Should have at least one folder (the root)
        self.assertGreaterEqual(len(folders), 1)
        
    def test_single_file(self) -> None:
        """Test directory with single file."""
        single_file = Path(self.temp_dir) / "only.txt"
        single_file.write_text("only file")
        
        iterator = ProjectFilesIterator(
            root_path=self.temp_dir,
            extensions_to_skip=[],
            names_to_skip=[]
        )
        
        folders = list(iterator)
        all_files = []  # type: ignore[misc]
        for folder in folders:
            all_files.extend(folder.files)  # type: ignore[misc,arg-type]
        
        self.assertEqual(len(all_files), 1)  # type: ignore[misc,arg-type]
        self.assertEqual(all_files[0].name, "only.txt")  # type: ignore[misc,attr-defined]


class TestProjectFileStats(unittest.TestCase):
    """Test project files statistics."""
    
    def test_stats_initialization(self) -> None:
        """Test creating ProjectFileStats instance."""
        # Create a mock iterator
        mock_iterator = Mock()
        mock_iterator.__iter__ = Mock(return_value=iter([]))
        
        stats = ProjectFileStats(project_files_iterator=mock_iterator)
        
        self.assertEqual(len(stats.file_stats), 0)
        
    def test_file_stats_collection(self) -> None:
        """Test collecting file statistics."""
        # Create a mock iterator with test data
        mock_file1 = Mock()
        mock_file1.path = "/test/file1.py"
        mock_file1.name = "file1.py"
        
        mock_file2 = Mock()
        mock_file2.path = "/test/file2.py"
        mock_file2.name = "file2.py"
        
        mock_folder = Mock()
        mock_folder.files = [mock_file1, mock_file2]
        
        mock_iterator = Mock()
        mock_iterator.__iter__ = Mock(return_value=iter([mock_folder]))
        
        # Mock file reading
        with patch.object(ProjectFileStats, '_read_file') as mock_read:
            mock_read.side_effect = [
                ["line1", "line2", "line3"],  # file1.py
                ["line1", "line2"]  # file2.py
            ]
            
            with patch('os.path.getsize') as mock_getsize:
                mock_getsize.side_effect = [100, 200]
                
                stats = ProjectFileStats(project_files_iterator=mock_iterator)
        
        self.assertEqual(len(stats.file_stats), 2)
        self.assertEqual(stats.file_stats[0]['size'], 200)  # Sorted by size descending
        self.assertEqual(stats.file_stats[1]['size'], 100)
        
    def test_get_file_stats(self) -> None:
        """Test getting individual file statistics."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("line1\nline2\nline3\n")
            temp_file = f.name
        
        try:
            # Create mock iterator
            mock_iterator = Mock()
            mock_iterator.__iter__ = Mock(return_value=iter([]))
            
            stats = ProjectFileStats(project_files_iterator=mock_iterator)
            file_stat = stats.get_file_stats(temp_file)
            
            self.assertIsNotNone(file_stat)
            if file_stat is not None:
                self.assertEqual(file_stat['lines_count'], 3)  # type: ignore[misc]
                self.assertEqual(file_stat['name'], os.path.basename(temp_file))  # type: ignore[misc]
                self.assertGreater(file_stat['size'], 0)  # type: ignore[misc]
        finally:
            os.unlink(temp_file)
        
    def test_print_stats(self) -> None:
        """Test printing file statistics."""
        # Create mock files
        mock_file = Mock()
        mock_file.path = "/test/large_file.py"
        mock_file.name = "large_file.py"
        
        mock_folder = Mock()
        mock_folder.files = [mock_file]
        
        mock_iterator = Mock()
        mock_iterator.__iter__ = Mock(return_value=iter([mock_folder]))
        
        # Mock file reading and size
        with patch.object(ProjectFileStats, '_read_file') as mock_read:
            mock_read.return_value = ["line1", "line2", "line3"]
            
            with patch('os.path.getsize') as mock_getsize:
                mock_getsize.return_value = 1000
                
                with patch('blarify.logger.Logger.log') as mock_log:
                    stats = ProjectFileStats(project_files_iterator=mock_iterator)
                    stats.print(limit=1)
                    
                    # Verify logging was called
                    self.assertTrue(mock_log.called)


if __name__ == '__main__':
    unittest.main()