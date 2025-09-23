"""SCIP-based reference resolver for faster code intelligence.

Prerequisites:
- Install scip-python via npm: `npm install -g @sourcegraph/scip-python`
- Protobuf is required for reading SCIP index files (automatically installed via requirements)

This resolver provides up to 330x faster reference resolution compared to LSP
while maintaining identical accuracy.
"""

import os
import logging
from typing import Dict, List, Optional, TYPE_CHECKING
from pathlib import Path
import time

from blarify.graph.node import DefinitionNode
from .types.Reference import Reference
from .lsp_helper import ProgressTracker

logger = logging.getLogger(__name__)

# Import SCIP protobuf bindings with multiple fallback paths
scip_available = False
scip = None

if TYPE_CHECKING:
    from blarify import scip_pb2 as scip
    scip_available = True
else:
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
        self._index: Optional["scip.Index"] = None
        self._symbol_to_occurrences: Dict[str, List["scip.Occurrence"]] = {}
        self._document_by_path: Dict[str, "scip.Document"] = {}
        self._occurrence_to_document: Dict[int, "scip.Document"] = {}  # Use id() as key
        self._loaded = False

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

    def ensure_loaded(self) -> bool:
        """Load the SCIP index if not already loaded."""
        if not scip_available:
            logger.error("SCIP protobuf bindings are not available. Cannot load SCIP index.")
            return False

        if self._loaded:
            return True

        if not os.path.exists(self.scip_index_path):
            logger.warning(f"SCIP index not found at {self.scip_index_path}")
            return False

        try:
            start_time = time.time()
            self._load_index()
            load_time = time.time() - start_time
            logger.info(
                f"📚 Loaded SCIP index in {load_time:.2f}s: {len(self._document_by_path)} documents, {len(self._symbol_to_occurrences)} symbols"
            )
            self._loaded = True
            return True
        except Exception as e:
            logger.error(f"Failed to load SCIP index: {e}")
            return False

    def _load_index(self):
        """Load and parse the SCIP index file."""
        with open(self.scip_index_path, "rb") as f:
            data = f.read()

        self._index = scip.Index()
        self._index.ParseFromString(data)

        # Build lookup tables for fast querying
        self._build_lookup_tables()

    def _build_lookup_tables(self):
        """Build efficient lookup tables from the SCIP index."""
        if not self._index:
            return

        # Index documents by relative path
        for document in self._index.documents:
            self._document_by_path[document.relative_path] = document

            # Index occurrences by symbol and build occurrence-to-document mapping
            for occurrence in document.occurrences:
                if occurrence.symbol not in self._symbol_to_occurrences:
                    self._symbol_to_occurrences[occurrence.symbol] = []
                self._symbol_to_occurrences[occurrence.symbol].append(occurrence)
                # Use id() of the occurrence object as key since protobuf objects aren't hashable
                self._occurrence_to_document[id(occurrence)] = document

    def generate_index_if_needed(self, project_name: str = "blarify") -> bool:
        """Generate SCIP index if it doesn't exist or is outdated."""
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

    def _generate_index(self, project_name: str) -> bool:
        """Generate SCIP index using the appropriate language indexer."""
        import subprocess

        # Create empty-env.json for Python projects (required by scip-python)
        if self.language == "python":
            env_file = os.path.join(self.root_path, "empty-env.json")
            if not os.path.exists(env_file):
                with open(env_file, "w") as f:
                    import json

                    json.dump([], f)

        try:
            # Choose the appropriate indexer command based on language
            if self.language == "python":
                cmd = [
                    "scip-python",
                    "index",
                    "--project-name",
                    project_name,
                    "--output",
                    self.scip_index_path,
                    "--environment",
                    os.path.join(self.root_path, "empty-env.json"),
                    "--quiet",
                ]
            elif self.language in ["typescript", "javascript"]:
                # scip-typescript has a simpler command structure without --project-name or --environment
                # It outputs to index.scip by default, so we need to handle output differently
                cmd = [
                    "scip-typescript",
                    "index",
                    "--output",
                    os.path.basename(self.scip_index_path),  # Only filename, not full path
                ]
            else:
                logger.error(f"Unsupported language for SCIP indexing: {self.language}")
                return False

            result = subprocess.run(cmd, cwd=self.root_path, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                # For TypeScript, we may need to move the file if it was created with a different name
                if self.language in ["typescript", "javascript"]:
                    actual_output = os.path.join(self.root_path, os.path.basename(self.scip_index_path))
                    if actual_output != self.scip_index_path and os.path.exists(actual_output):
                        import shutil

                        shutil.move(actual_output, self.scip_index_path)

                logger.info(f"✅ Generated {self.language} SCIP index at {self.scip_index_path}")
                return True
            else:
                logger.error(f"Failed to generate SCIP index: {result.stderr.strip()}")
                return False

        except Exception as e:
            logger.error(f"Error generating SCIP index: {e}")
            return False

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
                    results[node] = self._get_references_for_symbol(symbol)
                else:
                    results[node] = []  # No symbol found for this node
                progress.update(1)

            # Force progress update every batch
            progress.force_update()

        progress.complete()
        return results

    def _find_symbol_for_node(self, node: DefinitionNode) -> Optional[str]:
        """Find the SCIP symbol identifier for a given node."""
        # Convert file URI to relative path
        from blarify.utils.path_calculator import PathCalculator

        relative_path = PathCalculator.get_relative_path_from_uri(root_uri=f"file://{self.root_path}", uri=node.path)

        # Find document
        document = self._document_by_path.get(relative_path)
        if not document:
            return None

        # Look for a definition occurrence at the node's position
        for occurrence in document.occurrences:
            if not (occurrence.symbol_roles & scip.SymbolRole.Definition):
                continue

            # Check if position matches exactly (line and character)
            if (
                occurrence.range
                and len(occurrence.range) >= 2
                and occurrence.range[0] == node.definition_range.start_dict["line"]
                and occurrence.range[1] == node.definition_range.start_dict["character"]
            ):
                return occurrence.symbol

        return None

    def _batch_find_symbols_for_nodes(self, nodes: List[DefinitionNode]) -> Dict[DefinitionNode, Optional[str]]:
        """Efficiently find symbols for multiple nodes by grouping by document."""
        from blarify.utils.path_calculator import PathCalculator

        # Group nodes by their relative path
        nodes_by_path = {}
        for node in nodes:
            relative_path = PathCalculator.get_relative_path_from_uri(
                root_uri=f"file://{self.root_path}", uri=node.path
            )
            if relative_path not in nodes_by_path:
                nodes_by_path[relative_path] = []
            nodes_by_path[relative_path].append(node)

        node_to_symbol = {}

        # Process each document once
        for relative_path, path_nodes in nodes_by_path.items():
            document = self._document_by_path.get(relative_path)
            if not document:
                for node in path_nodes:
                    node_to_symbol[node] = None
                continue

            # Build a position index for this document's definition occurrences
            position_to_symbol = {}
            for occurrence in document.occurrences:
                if not (occurrence.symbol_roles & scip.SymbolRole.Definition):
                    continue
                if occurrence.range and len(occurrence.range) >= 2:
                    pos_key = (occurrence.range[0], occurrence.range[1])
                    position_to_symbol[pos_key] = occurrence.symbol

            # Match nodes to symbols using the position index
            for node in path_nodes:
                pos_key = (node.definition_range.start_dict["line"], node.definition_range.start_dict["character"])
                node_to_symbol[node] = position_to_symbol.get(pos_key)

        return node_to_symbol

    def _is_reference_occurrence(self, occurrence: "scip.Occurrence") -> bool:
        """Check if an occurrence is a reference (not a definition).

        TypeScript and JavaScript SCIP indexers use symbol_roles=0 for references,
        while Python uses proper ReadAccess/WriteAccess flags.

        Args:
            occurrence: The SCIP occurrence to check

        Returns:
            True if this is a reference occurrence, False otherwise
        """
        # Always skip definitions
        if occurrence.symbol_roles & scip.SymbolRole.Definition:
            return False

        # Language-specific behavior
        if self.language in ["typescript", "javascript"]:
            # TypeScript/JavaScript: symbol_roles=0 indicates a reference
            # Also accept explicit access flags if present
            return (
                occurrence.symbol_roles == 0
                or (occurrence.symbol_roles & (
                    scip.SymbolRole.ReadAccess |
                    scip.SymbolRole.WriteAccess |
                    scip.SymbolRole.Import
                )) != 0
            )
        else:
            # Python and other languages: require explicit access flags
            return (
                occurrence.symbol_roles & (
                    scip.SymbolRole.ReadAccess |
                    scip.SymbolRole.WriteAccess |
                    scip.SymbolRole.Import
                )
            ) != 0

    def _get_references_for_symbol(self, symbol: str) -> List[Reference]:
        """Get references for a specific symbol (optimized version)."""
        occurrences = self._symbol_to_occurrences.get(symbol, [])
        references = []

        for occurrence in occurrences:
            # Use the new helper function to check if this is a reference
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

    def _find_document_for_occurrence(self, occurrence: "scip.Occurrence") -> Optional["scip.Document"]:
        """Find the document containing an occurrence."""
        return self._occurrence_to_document.get(id(occurrence))

    def _occurrence_to_reference(self, occurrence: "scip.Occurrence", document: "scip.Document") -> Optional[Reference]:
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

            # Create a Reference object compatible with the existing system
            reference_data = {
                "uri": f"file://{os.path.join(self.root_path, document.relative_path)}",
                "range": {
                    "start": {"line": start_line, "character": start_char},
                    "end": {"line": end_line, "character": end_char},
                },
                "relativePath": document.relative_path,
                "absolutePath": os.path.join(self.root_path, document.relative_path),
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
