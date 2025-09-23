"""Hybrid reference resolver that uses SCIP when available, falls back to LSP.

SCIP resolver is used for Python and TypeScript projects since scip-python and
scip-typescript are available for these languages. For other programming languages
(Java, C#, Go, etc.), the resolver automatically uses LSP instead of SCIP.
"""

import logging
from typing import Any, Dict, List, Optional
from enum import Enum

from blarify.graph.node import DefinitionNode
from .types.Reference import Reference
from .lsp_helper import LspQueryHelper
from .scip_helper import ScipReferenceResolver

logger = logging.getLogger(__name__)


class ResolverMode(Enum):
    """Available resolver modes."""

    SCIP_ONLY = "scip_only"
    LSP_ONLY = "lsp_only"
    SCIP_WITH_LSP_FALLBACK = "scip_with_lsp_fallback"
    AUTO = "auto"


class HybridReferenceResolver:
    """Hybrid resolver that uses SCIP for speed and LSP as fallback.

    SCIP is used for Python and TypeScript projects since dedicated indexers
    (scip-python and scip-typescript) are available for these languages. For other
    programming languages, LSP resolver is used instead.
    """

    def __init__(
        self,
        root_uri: str,
        mode: ResolverMode = ResolverMode.AUTO,
        scip_index_path: Optional[str] = None,
        **lsp_kwargs: Any,
    ):
        """
        Initialize hybrid resolver.

        Args:
            root_uri: Root URI of the project
            mode: Resolver mode to use
            scip_index_path: Path to SCIP index file
            **lsp_kwargs: Arguments to pass to LspQueryHelper
        """
        self.root_uri = root_uri
        self.mode = mode

        # Initialize SCIP resolver
        from blarify.utils.path_calculator import PathCalculator

        root_path = PathCalculator.uri_to_path(root_uri)
        self.scip_resolver = ScipReferenceResolver(root_path, scip_index_path)

        # Initialize LSP resolver (lazy initialization)
        self._lsp_resolver: Optional[LspQueryHelper] = None
        self._lsp_kwargs = lsp_kwargs

        # Determine which resolvers to use
        self._use_scip = False
        self._use_lsp = False
        self._setup_resolvers()

    def _setup_resolvers(self):
        """Determine which resolvers to use based on mode and availability."""
        # Check project language to determine if SCIP is applicable
        from blarify.utils.project_detector import ProjectDetector
        from blarify.utils.path_calculator import PathCalculator

        root_path = PathCalculator.uri_to_path(self.root_uri)
        detected_language = ProjectDetector.get_primary_language(root_path)

        # SCIP is only supported for Python and TypeScript projects
        scip_supported_languages = {"python", "typescript"}
        is_scip_supported = detected_language in scip_supported_languages

        if not is_scip_supported:
            logger.info(
                f"🚫 {detected_language or 'Unknown'} project detected - SCIP resolver disabled (only Python and TypeScript are supported)"
            )
            self._use_scip = False
            self._use_lsp = True
            return

        # Set the language for the SCIP resolver
        self.scip_resolver.language = detected_language
        logger.info(f"🔧 Detected {detected_language} project - SCIP resolver enabled")

        if self.mode == ResolverMode.SCIP_ONLY:
            self._use_scip = self._try_setup_scip()
            self._use_lsp = False
            if not self._use_scip:
                logger.error("SCIP_ONLY mode requested but SCIP index unavailable")

        elif self.mode == ResolverMode.LSP_ONLY:
            self._use_scip = False
            self._use_lsp = True

        elif self.mode == ResolverMode.SCIP_WITH_LSP_FALLBACK:
            self._use_scip = self._try_setup_scip()
            self._use_lsp = True  # Always available as fallback

        elif self.mode == ResolverMode.AUTO:
            self._use_scip = self._try_setup_scip()
            self._use_lsp = not self._use_scip  # Use LSP only if SCIP fails

        logger.info(
            f"🔧 Hybrid resolver mode: {self.mode.value} | Language: {detected_language} | SCIP: {self._use_scip} | LSP: {self._use_lsp}"
        )

    def _try_setup_scip(self) -> bool:
        """Try to set up SCIP resolver."""
        try:
            # Try to generate index if needed
            if not self.scip_resolver.generate_index_if_needed("blarify"):
                return False

            # Try to load the index
            if not self.scip_resolver.ensure_loaded():
                return False

            stats = self.scip_resolver.get_statistics()
            logger.info(f"📚 SCIP index loaded: {stats}")
            return True

        except Exception as e:
            logger.warning(f"Failed to setup SCIP resolver: {e}")
            return False

    @property
    def lsp_resolver(self) -> LspQueryHelper:
        """Lazy initialization of LSP resolver."""
        if self._lsp_resolver is None:
            self._lsp_resolver = LspQueryHelper(self.root_uri, **self._lsp_kwargs)
            self._lsp_resolver.start()
        return self._lsp_resolver

    def get_paths_where_nodes_are_referenced_batch(
        self, nodes: List[DefinitionNode]
    ) -> Dict[DefinitionNode, List[Reference]]:
        """
        Get references for multiple nodes using the best available method.

        Args:
            nodes: List of nodes to get references for

        Returns:
            Dictionary mapping each node to its references
        """
        if not nodes:
            return {}

        total_nodes = len(nodes)
        logger.info(f"🚀 Starting hybrid reference resolution for {total_nodes} nodes")

        # Try SCIP first if enabled
        if self._use_scip:
            try:
                results = self.scip_resolver.get_references_batch_with_progress(nodes)

                # Check if SCIP gave us good results
                total_refs = sum(len(refs) for refs in results.values())

                logger.info(f"📚 SCIP results: {total_refs} references")

                return results

            except Exception as e:
                logger.error(f"SCIP resolution failed: {e}")

        # Fall back to LSP if SCIP failed or is disabled
        if self._use_lsp:
            logger.info("🔧 Using LSP resolver")
            return self.lsp_resolver.get_paths_where_nodes_are_referenced_batch(nodes)

        # No resolvers available
        logger.error("No reference resolvers available")
        return {node: [] for node in nodes}

    def get_paths_where_node_is_referenced(self, node: DefinitionNode) -> List[Reference]:
        """Get references for a single node."""
        results = self.get_paths_where_nodes_are_referenced_batch([node])
        return results.get(node, [])

    def get_resolver_info(self) -> Dict[str, Any]:
        """Get information about the current resolver configuration."""
        from blarify.utils.project_detector import ProjectDetector
        from blarify.utils.path_calculator import PathCalculator

        root_path = PathCalculator.uri_to_path(self.root_uri)
        detected_language = ProjectDetector.get_primary_language(root_path)

        info = {
            "mode": self.mode.value,
            "detected_language": detected_language,
            "scip_enabled": self._use_scip,
            "lsp_enabled": self._use_lsp,
        }

        if self._use_scip:
            info["scip_stats"] = self.scip_resolver.get_statistics()
            info["scip_language"] = getattr(self.scip_resolver, "language", "unknown")

        return info

    def initialize_directory(self, file) -> None:  # type: ignore
        """
        Initialize directory for the given file.
        Delegates to LSP resolver if available.
        """
        if self._use_lsp:
            self.lsp_resolver.initialize_directory(file)

    def shutdown(self):
        """Shutdown all resolvers."""
        if self._lsp_resolver:
            self._lsp_resolver.shutdown_exit_close()
