from typing import TYPE_CHECKING, Optional, Dict, List
import psutil
import concurrent.futures
import os
from blarify.vendor.multilspy import SyncLanguageServer
from blarify.utils.path_calculator import PathCalculator
from .types.Reference import Reference
from blarify.vendor.multilspy.multilspy_config import MultilspyConfig
from blarify.vendor.multilspy.multilspy_logger import MultilspyLogger
from blarify.vendor.multilspy.lsp_protocol_handler.server import Error
import time


if TYPE_CHECKING:
    from blarify.graph.node import DefinitionNode
    from blarify.code_hierarchy.languages import (
        LanguageDefinitions,
    )


import asyncio

import logging
import threading

logger = logging.getLogger(__name__)


class ProgressTracker:
    """Simple progress tracker for LSP reference queries"""

    def __init__(self, total_nodes: int):
        self.total_nodes = total_nodes
        self.completed_nodes = 0
        self.lock = threading.Lock()
        self.start_time = time.time()
        self.last_update_time = 0
        self.update_interval = 2.0  # Update every 2 seconds

    def update(self, nodes_completed: int):
        """Update progress and log if enough time has passed"""
        with self.lock:
            self.completed_nodes += nodes_completed
            current_time = time.time()

            # Only log progress every update_interval seconds to avoid spam
            if current_time - self.last_update_time >= self.update_interval:
                self._log_progress()
                self.last_update_time = current_time

    def _log_progress(self):
        """Log current progress"""
        if self.total_nodes == 0:
            return

        percentage = (self.completed_nodes / self.total_nodes) * 100
        elapsed_time = time.time() - self.start_time

        if self.completed_nodes > 0:
            estimated_total_time = elapsed_time * (self.total_nodes / self.completed_nodes)
            remaining_time = estimated_total_time - elapsed_time
            eta_str = f"ETA: {remaining_time:.0f}s"
        else:
            eta_str = "ETA: calculating..."

        # Create a simple progress bar
        bar_length = 30
        filled_length = int(bar_length * self.completed_nodes // self.total_nodes)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)

        logger.info(
            f"🔄 Progress: [{bar}] {self.completed_nodes}/{self.total_nodes} ({percentage:.1f}%) | {elapsed_time:.0f}s elapsed | {eta_str}"
        )

    def force_update(self):
        """Force a progress update regardless of time interval"""
        with self.lock:
            self._log_progress()
            self.last_update_time = time.time()

    def complete(self):
        """Mark as complete and log final status"""
        with self.lock:
            self.completed_nodes = self.total_nodes
            elapsed_time = time.time() - self.start_time

            bar = "█" * 30
            logger.info(
                f"✅ Complete: [{bar}] {self.total_nodes}/{self.total_nodes} (100.0%) | Total time: {elapsed_time:.1f}s"
            )


class FileExtensionNotSupported(Exception):
    pass


class LspResourceOptimizer:
    """Automatically determines optimal LSP server instance counts based on system resources"""

    @staticmethod
    def get_optimal_lsp_instances(language: str = None) -> int:
        """
        Calculate optimal number of LSP server instances based on:
        - CPU cores available
        - Available memory
        - Language-specific characteristics
        """
        # Get system resources
        cpu_cores = os.cpu_count() or 4
        memory_gb = psutil.virtual_memory().total / (1024**3)

        # Language-specific factors
        language_factors = {
            # Languages with heavier memory usage and slower startup
            "python": {
                "memory_per_instance_mb": 300,
                "cpu_efficiency": 0.8,
                "max_recommended": 8,
            },
            "typescript": {
                "memory_per_instance_mb": 400,
                "cpu_efficiency": 0.7,
                "max_recommended": 6,
            },
            "javascript": {
                "memory_per_instance_mb": 350,
                "cpu_efficiency": 0.8,
                "max_recommended": 8,
            },
            "java": {
                "memory_per_instance_mb": 500,
                "cpu_efficiency": 0.6,
                "max_recommended": 4,
            },
            "csharp": {
                "memory_per_instance_mb": 450,
                "cpu_efficiency": 0.6,
                "max_recommended": 4,
            },
            # Lighter languages
            "go": {
                "memory_per_instance_mb": 150,
                "cpu_efficiency": 0.9,
                "max_recommended": 12,
            },
            "rust": {
                "memory_per_instance_mb": 200,
                "cpu_efficiency": 0.9,
                "max_recommended": 10,
            },
            "ruby": {
                "memory_per_instance_mb": 250,
                "cpu_efficiency": 0.8,
                "max_recommended": 8,
            },
            "php": {
                "memory_per_instance_mb": 200,
                "cpu_efficiency": 0.8,
                "max_recommended": 8,
            },
        }

        # Default values for unknown languages
        default_factor = {
            "memory_per_instance_mb": 300,
            "cpu_efficiency": 0.8,
            "max_recommended": 6,
        }
        factor = language_factors.get(language, default_factor) if language else default_factor

        # Calculate based on CPU cores (with efficiency factor)
        cpu_based = max(1, int(cpu_cores * factor["cpu_efficiency"]))

        # Calculate based on available memory (reserve 2GB for system + other processes)
        available_memory_mb = max(0, (memory_gb - 2.0) * 1024)
        memory_based = max(1, int(available_memory_mb / factor["memory_per_instance_mb"]))

        # Take the minimum of CPU and memory constraints, but cap at language maximum
        optimal = min(cpu_based, memory_based, factor["max_recommended"])

        # Ensure at least 1, but no more than reasonable maximum
        optimal = max(1, min(optimal, 16))

        logger.info(
            f"🔧 LSP optimization for {language or 'unknown'}: {cpu_cores} cores, {memory_gb:.1f}GB RAM → {optimal} instances"
        )
        logger.debug(
            f"   CPU-based: {cpu_based}, Memory-based: {memory_based}, Language max: {factor['max_recommended']}"
        )

        return optimal

    @staticmethod
    def get_system_info() -> dict:
        """Get detailed system information for debugging"""
        return {
            "cpu_cores": os.cpu_count(),
            "memory_gb": psutil.virtual_memory().total / (1024**3),
            "available_memory_gb": psutil.virtual_memory().available / (1024**3),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
        }


class LspQueryHelper:
    root_uri: str
    language_to_lsp_servers: dict[str, list[SyncLanguageServer]]  # Changed to list of servers
    entered_lsp_servers: dict[str, list]  # Track contexts for each server instance
    LSP_USAGES = 0
    MAX_LSP_INSTANCES_PER_LANGUAGE = 10  # Configurable number of instances
    BASE_TIMEOUT = 30  # Base timeout in seconds
    PER_REQUEST_TIMEOUT = 2  # Additional timeout per request in seconds
    MAX_BATCH_SIZE = 50  # Maximum requests per batch before chunking

    def __init__(
        self,
        root_uri: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        max_lsp_instances: int = None,
        base_timeout: int = 30,
        per_request_timeout: int = 2,
        max_batch_size: int = 50,
        auto_optimize: bool = True,
    ):
        self.root_uri = root_uri
        self.entered_lsp_servers = {}
        self.language_to_lsp_servers = {}
        self.BASE_TIMEOUT = base_timeout
        self.PER_REQUEST_TIMEOUT = per_request_timeout
        self.MAX_BATCH_SIZE = max_batch_size
        self.auto_optimize = auto_optimize

        # Set default max instances (will be overridden per language if auto_optimize is True)
        self.MAX_LSP_INSTANCES_PER_LANGUAGE = max_lsp_instances or 4

        if auto_optimize:
            # Show system info for debugging
            system_info = LspResourceOptimizer.get_system_info()
            logger.info(
                f"💻 System resources: {system_info['cpu_cores']} cores, {system_info['memory_gb']:.1f}GB RAM ({system_info['available_memory_gb']:.1f}GB available)"
            )
        else:
            logger.info(f"🔧 Using fixed LSP instances: {self.MAX_LSP_INSTANCES_PER_LANGUAGE} per language")

    @staticmethod
    def get_language_definition_for_extension(extension: str) -> "LanguageDefinitions":
        from blarify.code_hierarchy.languages import (
            PythonDefinitions,
            JavascriptDefinitions,
            RubyDefinitions,
            TypescriptDefinitions,
            CsharpDefinitions,
            GoDefinitions,
            PhpDefinitions,
            JavaDefinitions,
        )

        if extension in PythonDefinitions.get_language_file_extensions():
            return PythonDefinitions
        elif extension in JavascriptDefinitions.get_language_file_extensions():
            return JavascriptDefinitions
        elif extension in TypescriptDefinitions.get_language_file_extensions():
            return TypescriptDefinitions
        elif extension in RubyDefinitions.get_language_file_extensions():
            return RubyDefinitions
        elif extension in CsharpDefinitions.get_language_file_extensions():
            return CsharpDefinitions
        elif extension in GoDefinitions.get_language_file_extensions():
            return GoDefinitions
        elif extension in PhpDefinitions.get_language_file_extensions():
            return PhpDefinitions
        elif extension in JavaDefinitions.get_language_file_extensions():
            return JavaDefinitions
        else:
            raise FileExtensionNotSupported(f'File extension "{extension}" is not supported)')

    def _create_lsp_server(self, language_definitions: "LanguageDefinitions", timeout=60) -> SyncLanguageServer:
        language = language_definitions.get_language_name()
        config = MultilspyConfig.from_dict({"code_language": language})
        logger = MultilspyLogger()
        lsp = SyncLanguageServer.create(config, logger, PathCalculator.uri_to_path(self.root_uri), timeout=timeout)
        return lsp

    def start(self) -> None:
        """
        DEPRECATED, LSP servers are started on demand
        """

    def _get_or_create_lsp_server(self, extension, timeout=60) -> SyncLanguageServer:
        """Get the first available LSP server for backwards compatibility"""
        servers = self._get_or_create_lsp_servers(extension, timeout, 1)
        return servers[0]

    def _get_or_create_lsp_servers(self, extension, timeout=60, count=None) -> List[SyncLanguageServer]:
        """Get or create multiple LSP server instances for a language"""
        language_definitions = self.get_language_definition_for_extension(extension)
        language = language_definitions.get_language_name()

        if count is None:
            count = self.MAX_LSP_INSTANCES_PER_LANGUAGE

        # Initialize the language entry if it doesn't exist
        if language not in self.language_to_lsp_servers:
            self.language_to_lsp_servers[language] = []
            self.entered_lsp_servers[language] = []

        existing_servers = self.language_to_lsp_servers[language]

        # Create additional servers if we need more
        while len(existing_servers) < count:
            new_lsp = self._create_lsp_server(language_definitions, timeout)
            existing_servers.append(new_lsp)
            context = self._initialize_lsp_server_instance(language, new_lsp)
            self.entered_lsp_servers[language].append(context)
            logger.info(f"Created LSP server instance {len(existing_servers)} for {language}")

        return existing_servers[:count]

    def _initialize_lsp_server_instance(self, language, lsp):
        """Initialize a single LSP server instance and return its context"""
        context = lsp.start_server()
        context.__enter__()
        return context

    def initialize_directory(self, file) -> None:
        """
        DEPRECATED, LSP servers are started on demand
        """

    def get_paths_where_node_is_referenced(self, node: "DefinitionNode") -> list[Reference]:
        server = self._get_or_create_lsp_server(node.extension)
        references = self._request_references_with_exponential_backoff(node, server)
        return [Reference(reference) for reference in references]

    def get_paths_where_nodes_are_referenced_batch(
        self, nodes: List["DefinitionNode"]
    ) -> Dict["DefinitionNode", List[Reference]]:
        """
        Batch process multiple nodes to get their references concurrently.
        Groups nodes by language and distributes them across multiple LSP server instances.

        Args:
            nodes: List of DefinitionNode objects to get references for

        Returns:
            Dictionary mapping each node to its list of references
        """
        if not nodes:
            return {}

        total_nodes = len(nodes)
        logger.info(f"🚀 Starting LSP reference queries for {total_nodes} nodes")

        # Create global progress tracker
        progress = ProgressTracker(total_nodes)

        # Group nodes by language/extension for efficient batching
        nodes_by_language: Dict[str, List["DefinitionNode"]] = {}
        for node in nodes:
            try:
                language_def = self.get_language_definition_for_extension(node.extension)
                language = language_def.get_language_name()
                if language not in nodes_by_language:
                    nodes_by_language[language] = []
                nodes_by_language[language].append(node)
            except FileExtensionNotSupported:
                logger.warning(f"Skipping node {node.name} with unsupported extension {node.extension}")
                continue

        # Show language distribution
        for language, language_nodes in nodes_by_language.items():
            percentage = (len(language_nodes) / total_nodes) * 100
            logger.info(f"📊 {language}: {len(language_nodes)} nodes ({percentage:.1f}%)")

        results: Dict["DefinitionNode", List[Reference]] = {}

        # Process each language group with multiple server instances
        for lang_index, (language, language_nodes) in enumerate(nodes_by_language.items(), 1):
            try:
                # Get multiple LSP server instances for this language
                first_node = language_nodes[0]
                lsp_servers = self._get_or_create_lsp_servers(first_node.extension)

                logger.info(
                    f"🔧 [{lang_index}/{len(nodes_by_language)}] Processing {len(language_nodes)} {language} nodes with {len(lsp_servers)} LSP server instances"
                )

                # Distribute nodes across multiple server instances
                language_results = self._batch_request_references_with_multiple_servers(
                    language_nodes, lsp_servers, progress
                )
                results.update(language_results)

            except Exception as e:
                logger.error(f"❌ Error processing nodes for language {language}: {e}")
                # Fallback to empty results for failed language
                for node in language_nodes:
                    results[node] = []
                # Still update progress for failed nodes
                progress.update(len(language_nodes))

        # Mark as complete
        progress.complete()
        return results

    def _batch_request_references_with_multiple_servers(
        self,
        nodes: List["DefinitionNode"],
        lsp_servers: List[SyncLanguageServer],
        progress: ProgressTracker,
    ) -> Dict["DefinitionNode", List[Reference]]:
        """
        Distribute nodes across multiple LSP server instances and process them concurrently.

        Args:
            nodes: List of nodes using the same language
            lsp_servers: List of LSP server instances for this language
            progress: Progress tracker to update as nodes are completed

        Returns:
            Dictionary mapping each node to its references
        """
        if not lsp_servers:
            logger.error("No LSP servers available")
            progress.update(len(nodes))  # Mark failed nodes as completed
            return {node: [] for node in nodes}

        # Distribute nodes across available servers using round-robin
        server_node_groups = [[] for _ in lsp_servers]
        for i, node in enumerate(nodes):
            server_index = i % len(lsp_servers)
            server_node_groups[server_index].append(node)

        # Create concurrent tasks for each server
        import concurrent.futures
        import threading

        results: Dict["DefinitionNode", List[Reference]] = {}
        results_lock = threading.Lock()

        def process_server_group(server_index: int):
            server = lsp_servers[server_index]
            server_nodes = server_node_groups[server_index]

            if not server_nodes:
                return

            # Process this group of nodes with one server instance
            group_results = self._batch_request_references_for_language(server_nodes, server, progress)

            # Thread-safe result collection
            with results_lock:
                results.update(group_results)

        # Execute all server groups concurrently using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(lsp_servers)) as executor:
            futures = []
            for server_index in range(len(lsp_servers)):
                if server_node_groups[server_index]:  # Only submit if there are nodes to process
                    future = executor.submit(process_server_group, server_index)
                    futures.append(future)

            # Wait for all server groups to complete
            concurrent.futures.wait(futures)

            # Check for any exceptions
            for future in futures:
                try:
                    future.result()  # This will raise any exception that occurred
                except Exception as e:
                    logger.error(f"❌ Error in server group processing: {e}")

        return results

    def _batch_request_references_for_language(
        self,
        nodes: List["DefinitionNode"],
        lsp_server: SyncLanguageServer,
        progress: ProgressTracker = None,
    ) -> Dict["DefinitionNode", List[Reference]]:
        """
        Send concurrent reference requests for multiple nodes to the same LSP server.
        Uses dynamic timeout calculation and chunking for large batches.

        Args:
            nodes: List of nodes using the same language
            lsp_server: The LSP server instance for this language
            progress: Optional progress tracker to update

        Returns:
            Dictionary mapping each node to its references
        """
        if not nodes:
            return {}

        # If batch is too large, split into smaller chunks
        if len(nodes) > self.MAX_BATCH_SIZE:
            return self._process_large_batch_in_chunks(nodes, lsp_server, progress)

        # Calculate dynamic timeout based on batch size
        dynamic_timeout = self._calculate_batch_timeout(len(nodes))

        results: Dict["DefinitionNode", List[Reference]] = {}

        # Create async tasks for all requests
        async def batch_requests():
            tasks = []
            for node in nodes:
                task = lsp_server.language_server.request_references(
                    relative_file_path=PathCalculator.get_relative_path_from_uri(root_uri=self.root_uri, uri=node.path),
                    line=node.definition_range.start_dict["line"],
                    column=node.definition_range.start_dict["character"],
                )
                tasks.append((node, task))

            # Wait for all requests to complete
            task_results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)

            # Process results
            for (node, _), result in zip(tasks, task_results):
                if isinstance(result, Exception):
                    logger.warning(f"Error getting references for {node.name}: {result}")
                    results[node] = []
                else:
                    results[node] = [Reference(ref) for ref in result] if result else []

            return results

        # Execute the batch request in the LSP server's event loop
        try:
            future = asyncio.run_coroutine_threadsafe(batch_requests(), lsp_server.loop)
            batch_results = future.result(timeout=dynamic_timeout)

            # Update progress tracker
            if progress:
                progress.update(len(nodes))

            return batch_results
        except concurrent.futures.TimeoutError:
            logger.error(
                f"⏰ Batch request timed out after {dynamic_timeout}s for {len(nodes)} nodes, falling back to smaller batches"
            )
            # Fallback: split into smaller chunks and retry
            return self._process_large_batch_in_chunks(
                nodes, lsp_server, progress, chunk_size=max(1, self.MAX_BATCH_SIZE // 2)
            )
        except Exception as e:
            logger.exception(f"Batch request failed: {e}")
            # Update progress even for failed nodes
            if progress:
                progress.update(len(nodes))
            # Fallback to empty results
            return {node: [] for node in nodes}

    def _calculate_batch_timeout(self, batch_size: int) -> int:
        """Calculate dynamic timeout based on batch size"""
        timeout = self.BASE_TIMEOUT + (batch_size * self.PER_REQUEST_TIMEOUT)
        # Cap at reasonable maximum (5 minutes)
        return min(timeout, 300)

    def _process_large_batch_in_chunks(
        self,
        nodes: List["DefinitionNode"],
        lsp_server: SyncLanguageServer,
        progress: ProgressTracker = None,
        chunk_size: int = None,
    ) -> Dict["DefinitionNode", List[Reference]]:
        """Process large batches by splitting into smaller chunks"""
        if chunk_size is None:
            chunk_size = self.MAX_BATCH_SIZE

        all_results = {}

        for i in range(0, len(nodes), chunk_size):
            chunk = nodes[i : i + chunk_size]

            try:
                chunk_results = self._batch_request_references_simple(chunk, lsp_server, progress)
                all_results.update(chunk_results)

            except Exception as e:
                logger.error(f"❌ Error processing chunk: {e}")
                # Add empty results for failed chunk and update progress
                for node in chunk:
                    all_results[node] = []
                if progress:
                    progress.update(len(chunk))

        return all_results

    def _batch_request_references_simple(
        self,
        nodes: List["DefinitionNode"],
        lsp_server: SyncLanguageServer,
        progress: ProgressTracker = None,
    ) -> Dict["DefinitionNode", List[Reference]]:
        """
        Simple batch processing without chunking (used by chunk processor to avoid recursion).

        Args:
            nodes: List of nodes using the same language
            lsp_server: The LSP server instance for this language
            progress: Optional progress tracker to update

        Returns:
            Dictionary mapping each node to its references
        """
        if not nodes:
            return {}

        # Calculate dynamic timeout based on batch size
        dynamic_timeout = self._calculate_batch_timeout(len(nodes))

        results: Dict["DefinitionNode", List[Reference]] = {}

        # Create async tasks for all requests
        async def batch_requests():
            tasks = []
            for node in nodes:
                task = lsp_server.language_server.request_references(
                    relative_file_path=PathCalculator.get_relative_path_from_uri(root_uri=self.root_uri, uri=node.path),
                    line=node.definition_range.start_dict["line"],
                    column=node.definition_range.start_dict["character"],
                )
                tasks.append((node, task))

            # Wait for all requests to complete
            task_results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)

            # Process results
            for (node, _), result in zip(tasks, task_results):
                if isinstance(result, Exception):
                    logger.warning(f"Error getting references for {node.name}: {result}")
                    results[node] = []
                else:
                    results[node] = [Reference(ref) for ref in result] if result else []

            return results

        # Execute the batch request in the LSP server's event loop
        try:
            future = asyncio.run_coroutine_threadsafe(batch_requests(), lsp_server.loop)
            batch_results = future.result(timeout=dynamic_timeout)

            # Update progress tracker
            if progress:
                progress.update(len(nodes))

            return batch_results
        except concurrent.futures.TimeoutError:
            logger.error(f"⏰ Simple batch timed out after {dynamic_timeout}s for {len(nodes)} nodes")
            # Update progress even for failed nodes
            if progress:
                progress.update(len(nodes))
            # For simple batch, just return empty results on timeout
            return {node: [] for node in nodes}
        except Exception as e:
            logger.exception(f"❌ Simple batch request failed: {e}")
            # Update progress even for failed nodes
            if progress:
                progress.update(len(nodes))
            # Fallback to empty results
            return {node: [] for node in nodes}

    def _request_references_with_exponential_backoff(self, node, lsp):
        timeout = 10
        for _ in range(1, 3):
            try:
                references = lsp.request_references(
                    file_path=PathCalculator.get_relative_path_from_uri(root_uri=self.root_uri, uri=node.path),
                    line=node.definition_range.start_dict["line"],
                    column=node.definition_range.start_dict["character"],
                )
                return references

            except (TimeoutError, ConnectionResetError, Error):
                timeout = timeout * 2
                logger.warning(
                    f"Error requesting references for {self.root_uri}, {node.definition_range}, attempting to restart LSP server with timeout {timeout}"
                )
                self._restart_lsp_for_extension(extension=node.extension)
                lsp = self._get_or_create_lsp_server(extension=node.extension, timeout=timeout)

        logger.exception("Failed to get references, returning empty list")
        return []

    def _restart_lsp_for_extension(self, extension):
        language_definitions = self.get_language_definition_for_extension(extension)
        language_name = language_definitions.get_language_name()
        self.exit_lsp_server(language_name)

        logger.warning(f"Restarting LSP servers for {language_name}")
        try:
            # Recreate one server instance for immediate use
            new_lsp = self._create_lsp_server(language_definitions)

            # Initialize the language entry
            if language_name not in self.language_to_lsp_servers:
                self.language_to_lsp_servers[language_name] = []
                self.entered_lsp_servers[language_name] = []

            # Add the new server instance
            self.language_to_lsp_servers[language_name].append(new_lsp)
            context = self._initialize_lsp_server_instance(language_name, new_lsp)
            self.entered_lsp_servers[language_name].append(context)

            logger.warning(f"LSP server restarted for {language_name}")
        except ConnectionResetError:
            logger.exception("Connection reset error")

    def exit_lsp_server(self, language) -> None:
        # Handle multiple server instances per language
        if language in self.entered_lsp_servers:
            contexts = self.entered_lsp_servers[language]
            for i, context in enumerate(contexts):
                try:
                    # Try to exit context manager with timeout, this is to ensure that we don't hang indefinitely
                    # It happens sometimes especially with c#
                    def exit_context():
                        context.__exit__(None, None, None)

                    thread = threading.Thread(target=exit_context)
                    thread.start()
                    thread.join(timeout=5)  # Wait up to 5 seconds

                    if thread.is_alive():
                        logger.warning(f"Context manager exit timed out for {language} instance {i}")
                        raise TimeoutError("Context manager exit timed out")
                    logger.info(f"Properly exited context manager for {language} instance {i}")
                except Exception as e:
                    logger.warning(f"Error exiting context manager for {language} instance {i}: {e}")
                    # If context exit fails, fall back to manual cleanup for this specific server
                    if language in self.language_to_lsp_servers and i < len(self.language_to_lsp_servers[language]):
                        self._manual_cleanup_lsp_server_instance(self.language_to_lsp_servers[language][i])

            del self.entered_lsp_servers[language]
        else:
            # No context managers, do manual cleanup for all instances
            if language in self.language_to_lsp_servers:
                for server in self.language_to_lsp_servers[language]:
                    self._manual_cleanup_lsp_server_instance(server)

        # Remove from the language server dict
        if language in self.language_to_lsp_servers:
            del self.language_to_lsp_servers[language]

    def _manual_cleanup_lsp_server_instance(self, lsp_server: SyncLanguageServer) -> None:
        """Manual cleanup for a single LSP server instance."""
        try:
            # Best line of code I've ever written (now with instance support):
            process = lsp_server.language_server.server.process

            # Kill running processes
            if psutil.pid_exists(process.pid):
                for child in psutil.Process(process.pid).children(recursive=True):
                    child.terminate()
                process.terminate()
        except Exception as e:
            logger.exception(f"Error killing process: {e}")

        # Cancel all tasks in the loop
        loop = lsp_server.loop
        try:
            tasks = asyncio.all_tasks(loop=loop)
            if tasks:
                for task in tasks:
                    task.cancel()

                # Schedule a coroutine to wait for cancelled tasks to complete
                async def wait_for_cancelled_tasks():
                    try:
                        await asyncio.gather(*tasks, return_exceptions=True)
                    except Exception:
                        pass  # Ignore exceptions from cancelled tasks

                # Run the cleanup coroutine in the loop
                future = asyncio.run_coroutine_threadsafe(wait_for_cancelled_tasks(), loop)
                try:
                    future.result(timeout=5)  # Wait up to 5 seconds for cleanup
                except Exception:
                    pass  # If cleanup times out, continue anyway

            logger.info("Tasks cancelled for server instance")
        except Exception as e:
            logger.exception(f"Error cancelling tasks: {e}")

        # Stop the loop
        if loop.is_running():
            loop.call_soon_threadsafe(loop.stop)

    def get_definition_path_for_reference(self, reference: Reference, extension: str) -> str:
        lsp_caller = self._get_or_create_lsp_server(extension)
        definitions = self._request_definition_with_exponential_backoff(reference, lsp_caller, extension)

        if not definitions:
            return ""

        return definitions[0]["uri"]

    def _request_definition_with_exponential_backoff(self, reference: Reference, lsp, extension):
        timeout = 10
        for _ in range(1, 3):
            try:
                definitions = lsp.request_definition(
                    file_path=PathCalculator.get_relative_path_from_uri(root_uri=self.root_uri, uri=reference.uri),
                    line=reference.range.start.line,
                    column=reference.range.start.character,
                )
                return definitions

            except (TimeoutError, ConnectionResetError, Error):
                timeout = timeout * 2
                logger.warning(
                    f"Error requesting definitions for {self.root_uri}, {reference.start_dict}, attempting to restart LSP server with timeout {timeout}"
                )
                self._restart_lsp_for_extension(extension)
                lsp = self._get_or_create_lsp_server(extension=extension, timeout=timeout)

        logger.exception("Failed to get references, returning empty list")
        return []

    def shutdown_exit_close(self) -> None:
        languages = list(self.language_to_lsp_servers.keys())

        for language in languages:
            try:
                self.exit_lsp_server(language)
            except Exception as e:
                logger.exception(f"Error shutting down LSP server for {language}: {e}")

        # Ensure all dictionaries are cleared
        self.entered_lsp_servers.clear()
        self.language_to_lsp_servers.clear()
        logger.info("LSP servers have been shut down")
