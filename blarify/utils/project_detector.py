"""Utility to detect project types and characteristics."""

import os
import json
from pathlib import Path
from typing import Optional


class ProjectDetector:
    """Utility class to detect project characteristics."""

    # Python project indicators
    PYTHON_CONFIG_FILES = {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "Pipfile",
        "poetry.lock",
        "uv.lock",
    }

    PYTHON_DIRECTORIES = {"__pycache__", ".venv", "venv", "env", ".pytest_cache"}

    PYTHON_FILE_EXTENSIONS = {".py", ".pyx", ".pyi"}

    # TypeScript/JavaScript project indicators
    TYPESCRIPT_CONFIG_FILES = {"tsconfig.json", "package.json", "yarn.lock", "package-lock.json", "pnpm-lock.yaml"}

    TYPESCRIPT_DIRECTORIES = {"node_modules", ".next", "dist", "build", ".nuxt"}

    TYPESCRIPT_FILE_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}

    @staticmethod
    def is_python_project(root_path: str) -> bool:
        """
        Determine if a project is primarily a Python project.

        Args:
            root_path: Root path of the project

        Returns:
            True if the project appears to be a Python project
        """
        root = Path(root_path)

        # Check for Python configuration files in root
        for config_file in ProjectDetector.PYTHON_CONFIG_FILES:
            if (root / config_file).exists():
                return True

        # Check for Python-specific directories
        for python_dir in ProjectDetector.PYTHON_DIRECTORIES:
            if (root / python_dir).exists():
                return True

        # Count Python files vs other files to determine if it's predominantly Python
        python_files = 0
        total_code_files = 0

        # Sample first few levels to avoid deep traversal
        for root_dir, dirs, files in os.walk(root_path):
            # Limit depth to avoid expensive traversal
            level = root_dir[len(root_path) :].count(os.sep)
            if level >= 3:
                dirs.clear()  # Don't go deeper
                continue

            # Skip common non-source directories
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in {"node_modules", "__pycache__", "target", "build", "dist", "vendor", "deps", "packages"}
            ]

            for file in files:
                file_path = Path(file)
                suffix = file_path.suffix.lower()

                # Count Python files
                if suffix in ProjectDetector.PYTHON_FILE_EXTENSIONS:
                    python_files += 1
                    total_code_files += 1
                # Count other common code file types
                elif suffix in {
                    ".js",
                    ".ts",
                    ".jsx",
                    ".tsx",
                    ".java",
                    ".c",
                    ".cpp",
                    ".cs",
                    ".rb",
                    ".go",
                    ".rs",
                    ".php",
                    ".kt",
                    ".swift",
                }:
                    total_code_files += 1

        # If we have significant Python files, consider it a Python project
        if total_code_files == 0:
            return False

        python_ratio = python_files / total_code_files
        return python_ratio > 0.5  # More than 50% Python files

    @staticmethod
    def is_typescript_project(root_path: str) -> bool:
        """
        Determine if a project is primarily a TypeScript/JavaScript project.

        Args:
            root_path: Root path of the project

        Returns:
            True if the project appears to be a TypeScript/JavaScript project
        """
        root = Path(root_path)

        # Check for TypeScript/JavaScript configuration files in root
        for config_file in ProjectDetector.TYPESCRIPT_CONFIG_FILES:
            if (root / config_file).exists():
                # If package.json exists, check if it has TypeScript dependencies
                if config_file == "package.json":
                    try:
                        with open(root / config_file, "r") as f:
                            package_data = json.load(f)

                        # Check for TypeScript in dependencies or devDependencies
                        all_deps = {}
                        all_deps.update(package_data.get("dependencies", {}))
                        all_deps.update(package_data.get("devDependencies", {}))

                        ts_indicators = {
                            "typescript",
                            "@types/node",
                            "ts-node",
                            "tsc",
                            "next",
                            "react",
                            "vue",
                            "angular",
                        }
                        if any(dep in all_deps for dep in ts_indicators):
                            return True
                    except (json.JSONDecodeError, FileNotFoundError):
                        pass
                else:
                    return True

        # Check for TypeScript-specific directories
        for ts_dir in ProjectDetector.TYPESCRIPT_DIRECTORIES:
            if (root / ts_dir).exists():
                return True

        # Count TypeScript files vs other files to determine if it's predominantly TypeScript
        ts_files = 0
        total_code_files = 0

        # Sample first few levels to avoid deep traversal
        for root_dir, dirs, files in os.walk(root_path):
            # Limit depth to avoid expensive traversal
            level = root_dir[len(root_path) :].count(os.sep)
            if level >= 3:
                dirs.clear()  # Don't go deeper
                continue

            # Skip common non-source directories
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in {"node_modules", "__pycache__", "target", "build", "dist", "vendor", "deps", "packages"}
            ]

            for file in files:
                file_path = Path(file)
                suffix = file_path.suffix.lower()

                # Count TypeScript files
                if suffix in ProjectDetector.TYPESCRIPT_FILE_EXTENSIONS:
                    ts_files += 1
                    total_code_files += 1
                # Count other common code file types
                elif suffix in {".py", ".java", ".c", ".cpp", ".cs", ".rb", ".go", ".rs", ".php", ".kt", ".swift"}:
                    total_code_files += 1

        # If we have significant TypeScript files, consider it a TypeScript project
        if total_code_files == 0:
            return False

        ts_ratio = ts_files / total_code_files
        return ts_ratio > 0.5  # More than 50% TypeScript/JavaScript files

    @staticmethod
    def get_primary_language(root_path: str) -> Optional[str]:
        """
        Detect the primary programming language of a project.

        Args:
            root_path: Root path of the project

        Returns:
            Primary language name or None if undetermined
        """
        if ProjectDetector.is_python_project(root_path):
            return "python"
        elif ProjectDetector.is_typescript_project(root_path):
            return "typescript"

        # Could extend this for other languages in the future
        return None
