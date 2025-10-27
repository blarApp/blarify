"""SCIP-based reference resolver for faster code intelligence.

Prerequisites:
- Install scip-python via npm: `npm install -g @sourcegraph/scip-python`
- Protobuf is required for reading SCIP index files (automatically installed via requirements)

This resolver provides up to 330x faster reference resolution compared to LSP
while maintaining identical accuracy.
"""

import os
import logging
from typing import Dict, List, Optional, TYPE_CHECKING, Any
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from blarify.graph.node import DefinitionNode
from .types.Reference import Reference
from .lsp_helper import ProgressTracker

logger = logging.getLogger(__name__)

# Import SCIP protobuf bindings with multiple fallback paths
scip_available = False
scip = None

if TYPE_CHECKING:
    from blarify import scip_pb2 as scip_module
    scip_available = True

    from typing import TypeAlias
    ScipIndex: TypeAlias = scip_module.Index  # type: ignore[attr-defined]
    ScipDocument: TypeAlias = scip_module.Document  # type: ignore[attr-defined]
    ScipOccurrence: TypeAlias = scip_module.Occurrence  # type: ignore[attr-defined]
else:
    from typing import TypeAlias
    ScipIndex: TypeAlias = Any
    ScipDocument: TypeAlias = Any
    ScipOccurrence: TypeAlias = Any

    # Try multiple import paths for maximum compatibility
    import_attempts = [
        # Try package-relative import first
        ("from blarify import scip_pb2 as scip", lambda: __import__("blarify.scip_pb2", fromlist=[""])),
        # Try direct import from package directory
        ("import scip_pb2 as scip", lambda: __import__("scip_pb2")),
        # Try importing from current directory
        ("from . import scip_pb2 as scip", lambda: __import__("scip_pb2", globals(), locals(), [], 1)),
    ]

    for description, import_func in import_attempts:
        try:
            scip = import_func()
            scip_available = True
            logger.debug(f"Successfully imported SCIP using: {description}")
            break
        except (ImportError, ModuleNotFoundError, ValueError) as e:
            logger.debug(f"Import attempt failed ({description}): {e}")
            continue

if not scip_available:
    # Create a mock scip module for type hints and graceful degradation
    class MockScip:
        class Index:
            def __init__(self):
                pass

            def ParseFromString(self, data: bytes) -> None:
                pass

            @property
            def documents(self):
                return []

        class Document:
            def __init__(self):
                pass

            @property
            def relative_path(self):
                return ""

            @property
            def occurrences(self):
                return []

        class Occurrence:
            def __init__(self):
                pass

            @property
            def symbol(self):
                return ""

            @property
            def symbol_roles(self):
                return 0

            @property
            def range(self):
                return []

        class SymbolRole:
            Definition = 1
            ReadAccess = 8
            WriteAccess = 4
            Import = 2

    scip = MockScip()
    logger.warning(
        "SCIP protobuf bindings not found. SCIP functionality will be disabled. "
        "To enable SCIP:\n"
        "  1. Run 'python scripts/initialize_scip.py' to generate bindings\n"
        "  2. Or ensure scip_pb2.py is available in your Python path\n"
        "  3. Or install protobuf: pip install protobuf>=6.30.0"
    )


class ScipReferenceResolver:
    """Fast reference resolution using SCIP (Source Code Intelligence Protocol) index."""

    def __init__(self, root_path: str, scip_index_path: Optional[str] = None, language: Optional[str] = None):
        self.root_path = root_path
        self.scip_index_path = scip_index_path or os.path.join(root_path, "index.scip")
        self.language = language or self._detect_project_language()
        self._index: Optional[ScipIndex] = None
        self._symbol_to_occurrences: Dict[str, List[ScipOccurrence]] = {}
        self._document_by_path: Dict[str, ScipDocument] = {}
        self._occurrence_to_document: Dict[int, ScipDocument] = {}  # Use id() as key
        self._loaded = False

        self._monorepo_mode = False
        self._package_indexes: Dict[str, tuple[ScipIndex, Dict[str, List[ScipOccurrence]], Dict[str, ScipDocument], Dict[int, ScipDocument], Dict[int, str]]] = {}
        self._path_to_package: Dict[str, str] = {}
        self._occurrence_to_repo_path: Dict[int, str] = {}

    def _detect_project_language(self) -> str:
        """Auto-detect the project language."""
        try:
            # Try to import ProjectDetector to detect language
            import sys
            import os

            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(self.root_path))))
            from blarify.utils.project_detector import ProjectDetector

            if ProjectDetector.is_python_project(self.root_path):
                return "python"
            elif ProjectDetector.is_typescript_project(self.root_path):
                return "typescript"
            else:
                logger.warning("Could not detect project language, defaulting to Python")
                return "python"
        except ImportError:
            logger.warning("Could not import ProjectDetector, defaulting to Python")
            return "python"

    def _find_all_tsconfigs(self) -> List[tuple[str, str]]:
        """Find all tsconfig.json files in the project for monorepo support.

        Returns:
            List of (package_root, tsconfig_path) tuples
        """
        from blarify.project_file_explorer.project_files_iterator import ProjectFilesIterator

        tsconfig_files: List[tuple[str, str]] = []
        blarignore_path = os.path.join(self.root_path, ".blarignore")

        iterator = ProjectFilesIterator(
            root_path=self.root_path,
            blarignore_path=blarignore_path if os.path.exists(blarignore_path) else None,
        )

        for folder in iterator:
            tsconfig_path = os.path.join(folder.path, "tsconfig.json")
            if os.path.exists(tsconfig_path):
                tsconfig_files.append((folder.path, tsconfig_path))

        if tsconfig_files:
            logger.info(f"Found {len(tsconfig_files)} tsconfig.json files in monorepo")

        return tsconfig_files

    def _find_workspace_package(self, package_name: str) -> Optional[str]:
        """Find a workspace package by name in the monorepo.

        Args:
            package_name: Package name like "@vambe/tsconfig" or "tsconfig"

        Returns:
            Path to the package directory, or None if not found
        """
        from blarify.project_file_explorer.project_files_iterator import ProjectFilesIterator

        blarignore_path = os.path.join(self.root_path, ".blarignore")
        iterator = ProjectFilesIterator(
            root_path=self.root_path,
            blarignore_path=blarignore_path if os.path.exists(blarignore_path) else None,
        )

        for folder in iterator:
            package_json_path = os.path.join(folder.path, "package.json")
            if os.path.exists(package_json_path):
                try:
                    import json
                    with open(package_json_path, "r") as f:
                        package_data = json.load(f)
                        if package_data.get("name") == package_name:
                            return folder.path
                except Exception as e:
                    logger.debug(f"Error reading {package_json_path}: {e}")
                    continue

        return None

    def _resolve_workspace_extends(self, tsconfig_path: str, package_root: str) -> Optional[str]:
        """Resolve workspace package extends in tsconfig to actual file path.

        Args:
            tsconfig_path: Path to the tsconfig.json file
            package_root: Root directory of the package

        Returns:
            Path to backup of original tsconfig if modification was needed, None otherwise
        """
        try:
            import json
            import shutil
            from json_repair import repair_json

            with open(tsconfig_path, "r") as f:
                content = f.read()

            repaired = repair_json(content)
            tsconfig = json.loads(repaired)

            extends_value = tsconfig.get("extends")
            if not extends_value:
                return None

            if not isinstance(extends_value, str) or not extends_value.startswith("@"):
                return None

            parts = extends_value.split("/")
            if len(parts) < 2:
                return None

            package_name = f"{parts[0]}/{parts[1]}"
            relative_path = "/".join(parts[2:]) if len(parts) > 2 else ""

            workspace_package_dir = self._find_workspace_package(package_name)
            if not workspace_package_dir:
                logger.warning(f"Workspace package {package_name} not found in monorepo")
                return None

            resolved_path = os.path.join(workspace_package_dir, relative_path) if relative_path else workspace_package_dir
            if not resolved_path.endswith(".json"):
                resolved_path = os.path.join(resolved_path, "tsconfig.json")

            if not os.path.exists(resolved_path):
                logger.warning(f"Resolved tsconfig not found at {resolved_path}")
                return None

            relative_to_package = os.path.relpath(resolved_path, package_root)

            backup_path = f"{tsconfig_path}.blarify_backup"
            shutil.copy2(tsconfig_path, backup_path)

            modified_config = tsconfig.copy()
            modified_config["extends"] = relative_to_package

            with open(tsconfig_path, "w") as f:
                json.dump(modified_config, f, indent=2)

            logger.info(f"Resolved workspace extends to: {relative_to_package}")
            return backup_path

        except Exception as e:
            logger.warning(f"Error resolving workspace extends in {tsconfig_path}: {e}")
            return None

    def _generate_indexes_parallel(self, tsconfig_files: List[tuple[str, str]], max_workers: int = 4) -> Dict[str, str]:
        """Generate SCIP indexes for multiple packages in parallel.

        Args:
            tsconfig_files: List of (package_root, tsconfig_path) tuples
            max_workers: Maximum number of parallel workers

        Returns:
            Dictionary mapping package_root to index_path for successful generations
        """
        index_mapping: Dict[str, str] = {}

        def generate_package_index(package_data: tuple[str, str]) -> tuple[str, Optional[str]]:
            package_root, tsconfig_path = package_data
            package_name = os.path.basename(package_root)
            index_path = os.path.join(package_root, "index.scip")

            logger.info(f"Generating SCIP index for package: {package_name}")
            success = self._generate_index(
                project_name=package_name,
                tsconfig_path=tsconfig_path,
                package_root=package_root,
                output_path=index_path
            )

            if success:
                return (package_root, index_path)
            else:
                logger.warning(f"Failed to generate index for package: {package_name}")
                return (package_root, None)

        logger.info(f"Starting parallel index generation for {len(tsconfig_files)} packages with {max_workers} workers")
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_package = {executor.submit(generate_package_index, pkg): pkg for pkg in tsconfig_files}

            for future in as_completed(future_to_package):
                package_root, index_path = future.result()
                if index_path:
                    index_mapping[package_root] = index_path

        elapsed_time = time.time() - start_time
        logger.info(f"Generated {len(index_mapping)}/{len(tsconfig_files)} indexes in {elapsed_time:.2f}s")

        return index_mapping

    def ensure_loaded(self) -> bool:
        """Load the SCIP index if not already loaded."""
        if not scip_available:
            logger.error("SCIP protobuf bindings are not available. Cannot load SCIP index.")
            return False

        if self._loaded:
            return True

        try:
            start_time = time.time()
            self._load_index()
            load_time = time.time() - start_time

            # Check if any indexes were loaded (either single or monorepo)
            total_docs = len(self._document_by_path) if not self._monorepo_mode else sum(
                len(data[2]) for data in self._package_indexes.values()
            )

            if total_docs == 0:
                logger.warning("No SCIP indexes found or loaded")
                return False

            logger.info(
                f"📚 Loaded SCIP index in {load_time:.2f}s: {total_docs} documents"
            )
            self._loaded = True
            return True
        except Exception as e:
            logger.error(f"Failed to load SCIP index: {e}")
            return False

    def _load_index(self):
        """Load and parse the SCIP index file(s). Detects and handles monorepos."""
        if self.language in ["typescript", "javascript"]:
            tsconfig_files = self._find_all_tsconfigs()

            if len(tsconfig_files) > 1:
                self._monorepo_mode = True
                logger.info(f"Detected TypeScript monorepo with {len(tsconfig_files)} packages")
                self._load_multiple_indexes(tsconfig_files)
                return

        if os.path.exists(self.scip_index_path):
            with open(self.scip_index_path, "rb") as f:
                data = f.read()

            self._index = scip.Index()  # type: ignore[union-attr]
            self._index.ParseFromString(data)  # type: ignore[union-attr]

            self._symbol_to_occurrences, self._document_by_path, self._occurrence_to_document, self._occurrence_to_repo_path = self._build_lookup_tables(self._index)
        else:
            logger.warning(f"SCIP index not found at {self.scip_index_path}")

    def _load_multiple_indexes(self, tsconfig_files: List[tuple[str, str]]) -> None:
        """Load multiple SCIP indexes for monorepo support."""
        for package_root, _ in tsconfig_files:
            index_path = os.path.join(package_root, "index.scip")

            if not os.path.exists(index_path):
                logger.warning(f"Index not found for package at {package_root}, skipping")
                continue

            try:
                with open(index_path, "rb") as f:
                    data = f.read()

                index = scip.Index()  # type: ignore[union-attr]
                index.ParseFromString(data)

                symbol_to_occurrences, document_by_path, occurrence_to_document, occurrence_to_repo_path = self._build_lookup_tables(index, package_root)

                self._package_indexes[package_root] = (index, symbol_to_occurrences, document_by_path, occurrence_to_document, occurrence_to_repo_path)

                for doc_path in document_by_path.keys():
                    full_path = os.path.join(self.root_path, doc_path)
                    self._path_to_package[full_path] = package_root

                logger.info(f"Loaded index for package at {package_root}: {len(document_by_path)} documents")

            except Exception as e:
                logger.error(f"Failed to load index for package at {package_root}: {e}")

    def _get_index_for_path(self, file_path: str) -> Optional[tuple[Dict[str, List[ScipOccurrence]], Dict[str, ScipDocument], Dict[int, ScipDocument], Dict[int, str]]]:
        """Get the correct index data for a given file path in monorepo mode.

        Args:
            file_path: Absolute file path

        Returns:
            Tuple of (symbol_to_occurrences, document_by_path, occurrence_to_document, occurrence_to_repo_path) or None if not found
        """
        if not self._monorepo_mode:
            return (self._symbol_to_occurrences, self._document_by_path, self._occurrence_to_document, self._occurrence_to_repo_path)

        package_roots = sorted(self._package_indexes.keys(), key=len, reverse=True)
        for package_root in package_roots:
            if file_path.startswith(package_root):
                _, symbol_map, doc_map, occ_map, repo_path_map = self._package_indexes[package_root]
                return (symbol_map, doc_map, occ_map, repo_path_map)

        logger.warning(f"No index found for file path: {file_path}")
        return None

    def _build_lookup_tables(self, index: ScipIndex, package_root: Optional[str] = None) -> tuple[Dict[str, List[ScipOccurrence]], Dict[str, ScipDocument], Dict[int, ScipDocument], Dict[int, str]]:
        """Build efficient lookup tables from a SCIP index.

        Args:
            index: The SCIP index to build lookup tables from
            package_root: Package root for monorepo normalization (paths will be made relative to self.root_path)

        Returns:
            Tuple of (symbol_to_occurrences, document_by_path, occurrence_to_document, occurrence_to_repo_path)
        """
        symbol_to_occurrences: Dict[str, List[ScipOccurrence]] = {}
        document_by_path: Dict[str, ScipDocument] = {}
        occurrence_to_document: Dict[int, ScipDocument] = {}
        occurrence_to_repo_path: Dict[int, str] = {}

        for document in index.documents:
            if package_root:
                package_relative_to_repo = os.path.relpath(package_root, self.root_path)
                normalized_path = os.path.join(package_relative_to_repo, document.relative_path)
            else:
                normalized_path = document.relative_path

            document_by_path[normalized_path] = document

            for occurrence in document.occurrences:
                if occurrence.symbol not in symbol_to_occurrences:
                    symbol_to_occurrences[occurrence.symbol] = []
                symbol_to_occurrences[occurrence.symbol].append(occurrence)
                occurrence_to_document[id(occurrence)] = document
                occurrence_to_repo_path[id(occurrence)] = normalized_path

        return symbol_to_occurrences, document_by_path, occurrence_to_document, occurrence_to_repo_path

    def generate_index_if_needed(self, project_name: str = "blarify") -> bool:
        """Generate SCIP index if it doesn't exist or is outdated."""
        # Check for monorepo
        if self.language in ["typescript", "javascript"]:
            tsconfig_files = self._find_all_tsconfigs()

            if len(tsconfig_files) > 1:
                logger.info(f"Detected TypeScript monorepo with {len(tsconfig_files)} packages")
                return self._generate_indexes_if_needed_monorepo(tsconfig_files)

        # Single index project
        if os.path.exists(self.scip_index_path):
            # Check if index is newer than source files (simple heuristic)
            index_mtime = os.path.getmtime(self.scip_index_path)

            # Get appropriate file extensions based on language
            if self.language == "python":
                source_files = list(Path(self.root_path).rglob("*.py"))
            elif self.language in ["typescript", "javascript"]:
                source_files = []
                for ext in ["*.ts", "*.tsx", "*.js", "*.jsx"]:
                    source_files.extend(list(Path(self.root_path).rglob(ext)))
            else:
                source_files = list(Path(self.root_path).rglob("*.py"))  # Default to Python

            if source_files:
                newest_source = max(os.path.getmtime(f) for f in source_files)
                if index_mtime > newest_source:
                    logger.info(f"📚 SCIP index for {self.language} is up to date")
                    return True

        logger.info(f"🔄 Generating SCIP index for {self.language}...")
        return self._generate_index(project_name)

    def _generate_indexes_if_needed_monorepo(self, tsconfig_files: List[tuple[str, str]]) -> bool:
        """Generate SCIP indexes for monorepo packages only if needed.

        Args:
            tsconfig_files: List of (package_root, tsconfig_path) tuples

        Returns:
            True if all indexes exist and are up to date or were successfully generated
        """
        packages_needing_update: List[tuple[str, str]] = []

        for package_root, tsconfig_path in tsconfig_files:
            index_path = os.path.join(package_root, "index.scip")

            if os.path.exists(index_path):
                # Check if index is newer than source files in this package
                index_mtime = os.path.getmtime(index_path)
                source_files = []
                for ext in ["*.ts", "*.tsx", "*.js", "*.jsx"]:
                    source_files.extend(list(Path(package_root).rglob(ext)))

                if source_files:
                    newest_source = max(os.path.getmtime(f) for f in source_files)
                    if index_mtime > newest_source:
                        logger.info(f"📚 SCIP index for {os.path.basename(package_root)} is up to date")
                        continue

            packages_needing_update.append((package_root, tsconfig_path))

        if not packages_needing_update:
            logger.info("✅ All SCIP indexes are up to date")
            return True

        logger.info(f"🔄 Generating SCIP indexes for {len(packages_needing_update)} packages...")
        index_mapping = self._generate_indexes_parallel(packages_needing_update, max_workers=4)

        return len(index_mapping) == len(packages_needing_update)

    def _generate_index(self, project_name: str, tsconfig_path: Optional[str] = None, package_root: Optional[str] = None, output_path: Optional[str] = None) -> bool:
        """Generate SCIP index using the appropriate language indexer.

        Args:
            project_name: Name of the project
            tsconfig_path: Path to tsconfig.json for TypeScript projects (for monorepo support)
            package_root: Root directory of the package (for monorepo support)
            output_path: Custom output path for the index file

        Returns:
            True if index generation was successful, False otherwise
        """
        import subprocess

        working_dir = package_root or self.root_path
        index_output = output_path or self.scip_index_path

        # Create empty-env.json for Python projects (required by scip-python)
        if self.language == "python":
            env_file = os.path.join(working_dir, "empty-env.json")
            if not os.path.exists(env_file):
                with open(env_file, "w") as f:
                    import json

                    json.dump([], f)

        backup_tsconfig: Optional[str] = None
        try:
            # Choose the appropriate indexer command based on language
            if self.language == "python":
                cmd = [
                    "scip-python",
                    "index",
                    "--project-name",
                    project_name,
                    "--output",
                    index_output,
                    "--environment",
                    os.path.join(working_dir, "empty-env.json"),
                    "--quiet",
                ]
            elif self.language in ["typescript", "javascript"]:
                tsconfig_file = tsconfig_path or os.path.join(working_dir, "tsconfig.json")
                backup_tsconfig = self._resolve_workspace_extends(tsconfig_file, working_dir)

                cmd = [
                    "scip-typescript",
                    "index",
                    "--output",
                    os.path.basename(index_output),
                ]
            else:
                logger.error(f"Unsupported language for SCIP indexing: {self.language}")
                return False

            result = subprocess.run(cmd, cwd=working_dir, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                # For TypeScript, we may need to move the file if it was created with a different name
                if self.language in ["typescript", "javascript"]:
                    actual_output = os.path.join(working_dir, os.path.basename(index_output))
                    if actual_output != index_output and os.path.exists(actual_output):
                        import shutil

                        shutil.move(actual_output, index_output)

                logger.info(f"✅ Generated {self.language} SCIP index at {index_output}")
                return True
            else:
                logger.error(
                    f"Failed to generate SCIP index for {project_name}\n"
                    f"Command: {' '.join(cmd)}\n"
                    f"Working dir: {working_dir}\n"
                    f"Return code: {result.returncode}\n"
                    f"STDERR: {result.stderr.strip()}\n"
                    f"STDOUT: {result.stdout.strip()}"
                )
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"SCIP index generation timed out after 300s for {project_name}")
            return False
        except Exception as e:
            logger.error(f"Error generating SCIP index for {project_name}: {e}")
            return False
        finally:
            if backup_tsconfig and os.path.exists(backup_tsconfig):
                try:
                    import shutil
                    tsconfig_file = tsconfig_path or os.path.join(working_dir, "tsconfig.json")
                    shutil.move(backup_tsconfig, tsconfig_file)
                    logger.debug("Restored original tsconfig from backup")
                except Exception as e:
                    logger.warning(f"Failed to restore original tsconfig from {backup_tsconfig}: {e}")

    def get_references_for_node(self, node: DefinitionNode) -> List[Reference]:
        """Get all references for a single node using SCIP index."""
        if not self.ensure_loaded():
            return []

        # Find the symbol for this node
        symbol = self._find_symbol_for_node(node)
        if not symbol:
            return []

        # Get all occurrences of this symbol
        occurrences = self._symbol_to_occurrences.get(symbol, [])
        references = []

        for occurrence in occurrences:
            # Use the helper function to check if this is a reference
            if not self._is_reference_occurrence(occurrence):
                continue

            # Find the document for this occurrence
            doc = self._find_document_for_occurrence(occurrence)
            if not doc:
                continue

            # Convert SCIP occurrence to Reference
            ref = self._occurrence_to_reference(occurrence, doc)
            if ref:
                references.append(ref)
        return references

    def get_references_batch(self, nodes: List[DefinitionNode]) -> Dict[DefinitionNode, List[Reference]]:
        """Get references for multiple nodes efficiently using SCIP index."""
        if not self.ensure_loaded():
            return {node: [] for node in nodes}

        results = {}

        for node in nodes:
            results[node] = self.get_references_for_node(node)

        return results

    def get_references_batch_with_progress(self, nodes: List[DefinitionNode]) -> Dict[DefinitionNode, List[Reference]]:
        """Get references for multiple nodes with progress tracking."""
        if not self.ensure_loaded():
            return {node: [] for node in nodes}

        total_nodes = len(nodes)
        logger.info(f"🚀 Starting SCIP reference queries for {total_nodes} nodes")

        # Pre-compute symbols for all nodes to avoid repeated path calculations
        logger.info("📝 Pre-computing symbol mappings...")
        node_to_symbol = self._batch_find_symbols_for_nodes(nodes)
        nodes_with_symbols = [node for node, symbol in node_to_symbol.items() if symbol is not None]

        logger.info(
            f"📊 Found symbols for {len(nodes_with_symbols)}/{total_nodes} nodes ({len(nodes_with_symbols) / total_nodes * 100:.1f}%)"
        )

        progress = ProgressTracker(len(nodes_with_symbols))
        results = {node: [] for node in nodes}  # Initialize all nodes with empty lists

        # Process only nodes that have symbols
        batch_size = 500  # Larger batches for better performance
        for i in range(0, len(nodes_with_symbols), batch_size):
            batch = nodes_with_symbols[i : i + batch_size]

            for node in batch:
                symbol = node_to_symbol[node]
                if symbol is not None:
                    file_path = node.path.replace("file://", "")
                    results[node] = self._get_references_for_symbol(symbol, file_path)
                else:
                    results[node] = []  # No symbol found for this node
                progress.update(1)

            # Force progress update every batch
            progress.force_update()

        progress.complete()
        return results

    def _find_symbol_for_node(self, node: DefinitionNode) -> Optional[str]:
        """Find the SCIP symbol identifier for a given node."""
        from blarify.utils.path_calculator import PathCalculator

        file_path = node.path.replace("file://", "")
        index_data = self._get_index_for_path(file_path)

        if not index_data:
            return None

        _, document_by_path, _, _ = index_data

        relative_path = PathCalculator.get_relative_path_from_uri(root_uri=f"file://{self.root_path}", uri=node.path)
        document = document_by_path.get(relative_path)

        if not document:
            return None

        for occurrence in document.occurrences:
            if not (occurrence.symbol_roles & scip.SymbolRole.Definition):  # type: ignore[union-attr]
                continue

            if (
                occurrence.range
                and len(occurrence.range) >= 2
                and occurrence.range[0] == node.definition_range.start_dict["line"]
                and occurrence.range[1] == node.definition_range.start_dict["character"]
            ):
                return occurrence.symbol

        return None

    def _build_position_to_symbol_map(self, document: ScipDocument) -> Dict[tuple[int, int], str]:
        """Build a position-to-symbol mapping for a document.

        Args:
            document: The SCIP document to process

        Returns:
            Dictionary mapping (line, character) to symbol
        """
        position_to_symbol: Dict[tuple[int, int], str] = {}

        for occurrence in document.occurrences:
            if not (occurrence.symbol_roles & scip.SymbolRole.Definition):  # type: ignore[union-attr]
                continue
            if occurrence.range and len(occurrence.range) >= 2:
                pos_key = (occurrence.range[0], occurrence.range[1])
                position_to_symbol[pos_key] = occurrence.symbol

        return position_to_symbol

    def _match_nodes_to_symbols(self, nodes: List[DefinitionNode], document_by_path: Dict[str, ScipDocument]) -> Dict[DefinitionNode, Optional[str]]:
        """Match nodes to their symbols using document position index.

        Args:
            nodes: List of nodes to match
            document_by_path: Document lookup by relative path

        Returns:
            Dictionary mapping nodes to their symbols
        """
        from blarify.utils.path_calculator import PathCalculator

        nodes_by_path: Dict[str, List[DefinitionNode]] = {}
        for node in nodes:
            relative_path = PathCalculator.get_relative_path_from_uri(
                root_uri=f"file://{self.root_path}", uri=node.path
            )
            if relative_path not in nodes_by_path:
                nodes_by_path[relative_path] = []
            nodes_by_path[relative_path].append(node)

        node_to_symbol: Dict[DefinitionNode, Optional[str]] = {}

        for relative_path, path_nodes in nodes_by_path.items():
            document = document_by_path.get(relative_path)
            if not document:
                for node in path_nodes:
                    node_to_symbol[node] = None
                continue

            position_to_symbol = self._build_position_to_symbol_map(document)

            for node in path_nodes:
                pos_key = (node.definition_range.start_dict["line"], node.definition_range.start_dict["character"])
                node_to_symbol[node] = position_to_symbol.get(pos_key)

        return node_to_symbol

    def _batch_find_symbols_for_nodes(self, nodes: List[DefinitionNode]) -> Dict[DefinitionNode, Optional[str]]:
        """Efficiently find symbols for multiple nodes by grouping by document."""
        node_to_symbol: Dict[DefinitionNode, Optional[str]] = {}

        if self._monorepo_mode:
            nodes_by_package: Dict[str, List[DefinitionNode]] = {}

            for node in nodes:
                file_path = node.path.replace("file://", "")
                package_root = None

                for pkg_root in sorted(self._package_indexes.keys(), key=len, reverse=True):
                    if file_path.startswith(pkg_root):
                        package_root = pkg_root
                        break

                if package_root:
                    if package_root not in nodes_by_package:
                        nodes_by_package[package_root] = []
                    nodes_by_package[package_root].append(node)
                else:
                    node_to_symbol[node] = None

            for package_root, package_nodes in nodes_by_package.items():
                _, _, document_by_path, _, _ = self._package_indexes[package_root]
                node_to_symbol.update(self._match_nodes_to_symbols(package_nodes, document_by_path))
        else:
            node_to_symbol = self._match_nodes_to_symbols(nodes, self._document_by_path)

        return node_to_symbol

    def _is_reference_occurrence(self, occurrence: ScipOccurrence) -> bool:
        """Check if an occurrence is a reference (not a definition).

        TypeScript and JavaScript SCIP indexers use symbol_roles=0 for references,
        while Python uses proper ReadAccess/WriteAccess flags.

        Args:
            occurrence: The SCIP occurrence to check

        Returns:
            True if this is a reference occurrence, False otherwise
        """
        # Always skip definitions
        if occurrence.symbol_roles & scip.SymbolRole.Definition:  # type: ignore[union-attr]
            return False

        # Language-specific behavior
        if self.language in ["typescript", "javascript"]:
            # TypeScript/JavaScript: symbol_roles=0 indicates a reference
            # Also accept explicit access flags if present
            return (
                occurrence.symbol_roles == 0
                or (occurrence.symbol_roles & (
                    scip.SymbolRole.ReadAccess |  # type: ignore[union-attr]
                    scip.SymbolRole.WriteAccess |  # type: ignore[union-attr]
                    scip.SymbolRole.Import  # type: ignore[union-attr]
                )) != 0
            )
        else:
            # Python and other languages: require explicit access flags
            return (
                occurrence.symbol_roles & (
                    scip.SymbolRole.ReadAccess |  # type: ignore[union-attr]
                    scip.SymbolRole.WriteAccess |  # type: ignore[union-attr]
                    scip.SymbolRole.Import  # type: ignore[union-attr]
                )
            ) != 0

    def _get_references_for_symbol(self, symbol: str, file_path: Optional[str] = None) -> List[Reference]:
        """Get references for a specific symbol (optimized version).

        Args:
            symbol: The symbol to find references for
            file_path: File path to route to correct index in monorepo mode (required if monorepo_mode is True)

        Returns:
            List of references to the symbol
        """
        references: List[Reference] = []

        if self._monorepo_mode and file_path:
            index_data = self._get_index_for_path(file_path)
            if not index_data:
                return references

            symbol_to_occurrences, _, occurrence_to_document, occurrence_to_repo_path = index_data
            occurrences = symbol_to_occurrences.get(symbol, [])

            for occurrence in occurrences:
                if not self._is_reference_occurrence(occurrence):
                    continue

                doc = occurrence_to_document.get(id(occurrence))
                if not doc:
                    continue

                repo_path = occurrence_to_repo_path.get(id(occurrence))
                ref = self._occurrence_to_reference(occurrence, doc, repo_path)
                if ref:
                    references.append(ref)
        else:
            occurrences = self._symbol_to_occurrences.get(symbol, [])

            for occurrence in occurrences:
                if not self._is_reference_occurrence(occurrence):
                    continue

                doc = self._occurrence_to_document.get(id(occurrence))
                if not doc:
                    continue

                repo_path = self._occurrence_to_repo_path.get(id(occurrence))
                ref = self._occurrence_to_reference(occurrence, doc, repo_path)
                if ref:
                    references.append(ref)

        return references

    def _find_document_for_occurrence(self, occurrence: ScipOccurrence) -> Optional[ScipDocument]:
        """Find the document containing an occurrence."""
        return self._occurrence_to_document.get(id(occurrence))

    def _occurrence_to_reference(self, occurrence: ScipOccurrence, document: ScipDocument, repo_relative_path: Optional[str] = None) -> Optional[Reference]:
        """Convert a SCIP occurrence to a Reference object."""
        if not occurrence.range or len(occurrence.range) < 3:
            return None

        try:
            # SCIP range format: [start_line, start_character, end_character]
            # or [start_line, start_character, end_line, end_character]
            start_line = occurrence.range[0]
            start_char = occurrence.range[1]
            end_char = occurrence.range[2] if len(occurrence.range) == 3 else occurrence.range[3]
            end_line = start_line if len(occurrence.range) == 3 else occurrence.range[2]

            relative_path = repo_relative_path if repo_relative_path else document.relative_path

            # Create a Reference object compatible with the existing system
            reference_data = {
                "uri": f"file://{os.path.join(self.root_path, relative_path)}",
                "range": {
                    "start": {"line": start_line, "character": start_char},
                    "end": {"line": end_line, "character": end_char},
                },
                "relativePath": relative_path,
                "absolutePath": os.path.join(self.root_path, relative_path),
            }

            return Reference(reference_data)

        except Exception as e:
            logger.warning(f"Error converting occurrence to reference: {e}")
            return None

    def get_statistics(self) -> Dict[str, int]:
        """Get statistics about the loaded SCIP index."""
        if not self.ensure_loaded():
            return {}

        return {
            "documents": len(self._document_by_path),
            "symbols": len(self._symbol_to_occurrences),
            "total_occurrences": sum(len(occs) for occs in self._symbol_to_occurrences.values()),
        }
