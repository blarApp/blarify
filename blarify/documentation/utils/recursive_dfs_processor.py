"""
Recursive DFS processor for analyzing code hierarchies one branch at a time.

This module implements a depth-first search traversal of the code graph, processing
leaf nodes first and then building up understanding through parent nodes with
skeleton comment replacement.
"""

import re
import logging
import concurrent.futures
import contextvars
import functools
import threading
import time
from typing import Dict, List, Optional, Any, Set
from concurrent.futures import Future
from pydantic import BaseModel, Field, ConfigDict

from ...agents.llm_provider import LLMProvider
from ...agents.prompt_templates import (
    LEAF_NODE_ANALYSIS_TEMPLATE,
    PARENT_NODE_ANALYSIS_TEMPLATE,
    FUNCTION_WITH_CALLS_ANALYSIS_TEMPLATE,
    FUNCTION_WITH_CYCLE_ANALYSIS_TEMPLATE,
)
from ...db_managers.db_manager import AbstractDbManager
from ...db_managers.dtos.node_with_content_dto import NodeWithContentDto
from ...db_managers.queries import (
    get_node_by_path,
    get_direct_children,
    get_call_stack_children,
    detect_function_cycles,
    get_existing_documentation_for_node,
)
from ...graph.node.documentation_node import DocumentationNode

# Note: We don't import concrete Node classes as we work with DTOs in documentation layer
from ...graph.graph_environment import GraphEnvironment

logger = logging.getLogger(__name__)


class ThreadDependencyTracker:
    """
    Tracks which threads are waiting for which nodes to detect potential deadlocks.
    
    This class maintains the dependency graph between threads and nodes to detect
    circular wait conditions that would lead to deadlocks in multi-threaded processing.
    """
    
    def __init__(self):
        """Initialize the thread dependency tracker."""
        self._waiting_threads: Dict[str, Set[str]] = {}  # thread_id -> set of node_ids
        self._processing_threads: Dict[str, str] = {}    # node_id -> thread_id
        self._lock = threading.Lock()
    
    def register_processor(self, node_id: str, thread_id: str) -> None:
        """
        Register a thread as the processor for a node.
        
        Args:
            node_id: The ID of the node being processed
            thread_id: The ID of the thread processing the node
        """
        with self._lock:
            self._processing_threads[node_id] = thread_id
    
    def register_waiter(self, node_id: str, thread_id: str) -> bool:
        """
        Register a thread as waiting for a node.
        
        Args:
            node_id: The ID of the node the thread wants to wait for
            thread_id: The ID of the thread that wants to wait
            
        Returns:
            False if this would create a deadlock, True otherwise
        """
        with self._lock:
            if thread_id not in self._waiting_threads:
                self._waiting_threads[thread_id] = set()
            
            # Check for potential deadlock before adding the wait dependency
            if self._would_create_deadlock(node_id, thread_id):
                return False
            
            self._waiting_threads[thread_id].add(node_id)
            return True
    
    def unregister_waiter(self, node_id: str, thread_id: str) -> None:
        """
        Unregister a thread from waiting for a node.
        
        Args:
            node_id: The ID of the node the thread was waiting for
            thread_id: The ID of the thread that was waiting
        """
        with self._lock:
            if thread_id in self._waiting_threads:
                self._waiting_threads[thread_id].discard(node_id)
                if not self._waiting_threads[thread_id]:
                    del self._waiting_threads[thread_id]
    
    def unregister_processor(self, node_id: str) -> None:
        """
        Unregister the processor for a node.
        
        Args:
            node_id: The ID of the node to unregister
        """
        with self._lock:
            self._processing_threads.pop(node_id, None)
    
    def _would_create_deadlock(self, target_node_id: str, requester_thread_id: str) -> bool:
        """
        Check if waiting for target_node_id would create a circular dependency.
        
        A deadlock occurs if:
        1. Thread A wants to wait for node X
        2. Thread B is processing node X  
        3. Thread B is already waiting (directly or transitively) for a node processed by Thread A
        
        Args:
            target_node_id: The node the requester wants to wait for
            requester_thread_id: The thread that wants to wait
            
        Returns:
            True if this would create a deadlock, False otherwise
        """
        processor_thread = self._processing_threads.get(target_node_id)
        if not processor_thread:
            return False  # No processor yet, safe to wait
        
        if processor_thread == requester_thread_id:
            return True  # Thread trying to wait for itself
        
        # Check for transitive dependencies
        return self._has_transitive_dependency(processor_thread, requester_thread_id)
    
    def _has_transitive_dependency(self, start_thread: str, target_thread: str) -> bool:
        """
        Check if start_thread transitively depends on target_thread.
        
        This performs a depth-first search through the dependency graph to detect
        if there's a path from start_thread to target_thread through wait dependencies.
        
        Args:
            start_thread: The thread to start the search from
            target_thread: The thread we're looking for in the dependency chain
            
        Returns:
            True if start_thread transitively depends on target_thread
        """
        visited = set()
        stack = [start_thread]
        
        while stack:
            current_thread = stack.pop()
            if current_thread in visited:
                continue
            visited.add(current_thread)
            
            if current_thread == target_thread:
                return True
            
            # Find nodes this thread is waiting for
            waiting_for_nodes = self._waiting_threads.get(current_thread, set())
            for node_id in waiting_for_nodes:
                processor = self._processing_threads.get(node_id)
                if processor and processor not in visited:
                    stack.append(processor)
        
        return False


class ProcessingResult(BaseModel):
    """Result of processing a node (folder or file) with recursive DFS."""

    model_config = ConfigDict(arbitrary_types_allowed=True)  # Allow Node objects

    node_path: str
    node_relationships: List[Dict[str, Any]] = Field(default_factory=list)
    hierarchical_analysis: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    node_source_mapping: Dict[str, str] = Field(default_factory=dict)  # Maps info_node_id -> source_node_id
    save_status: Optional[Dict[str, Any]] = None  # Optional save status information
    information_nodes: List[Dict[str, Any]] = Field(default_factory=list)  # DocumentationNode objects (as dicts)

    # New fields for proper Node object handling
    documentation_nodes: List[DocumentationNode] = Field(default_factory=list)  # Actual DocumentationNode objects
    source_nodes: List[NodeWithContentDto] = Field(default_factory=list)  # Source code DTOs


class RecursiveDFSProcessor:
    """
    Processes code hierarchies using recursive depth-first search.

    This processor analyzes leaf nodes first, then builds up understanding
    through parent nodes, replacing skeleton comments with LLM-generated
    descriptions as it traverses up the hierarchy.
    """

    def __init__(
        self,
        db_manager: AbstractDbManager,
        agent_caller: LLMProvider,
        company_id: str,
        repo_id: str,
        graph_environment: GraphEnvironment,
        max_workers: int = 5,
        root_node: Optional[NodeWithContentDto] = None,
    ):
        """
        Initialize the recursive DFS processor.

        Args:
            db_manager: Database manager for querying nodes
            agent_caller: LLM provider for generating descriptions
            company_id: Company/entity ID for database queries
            repo_id: Repository ID for database queries
            graph_environment: Graph environment for node ID generation
            max_workers: Maximum number of threads for parallel child processing
        """
        self.db_manager = db_manager
        self.agent_caller = agent_caller
        self.company_id = company_id
        self.repo_id = repo_id
        self.graph_environment = graph_environment
        self.max_workers = max_workers
        self.node_descriptions: Dict[str, DocumentationNode] = {}  # Cache processed nodes
        self.node_source_mapping: Dict[str, str] = {}  # Maps info_node_id -> source_node_id
        self.source_nodes_cache: Dict[str, NodeWithContentDto] = {}  # Cache source DTOs by node_id
        self.source_to_description: Dict[str, str] = {}  # Maps source_node_id -> description content
        self.processing_futures: Dict[
            str, Future[DocumentationNode]
        ] = {}  # Per-node futures for coordination (broadcast)
        self.futures_lock = threading.Lock()  # Protects the processing_futures dictionary
        self.root_node = root_node  # Optional root node to start processing from
        self.processing_stack: Set[str] = set()  # Detect cycles during processing
        self.cycle_participants: Dict[str, Set[str]] = {}  # Track cycle relationships
        self._global_executor: Optional[concurrent.futures.ThreadPoolExecutor] = None  # Shared thread pool
        self._thread_local = threading.local()  # Thread-local storage for processing paths
        
        # Deadlock prevention and fallback mechanisms
        self.dependency_tracker = ThreadDependencyTracker()
        self.deadlock_fallback_cache: Dict[str, DocumentationNode] = {}
        self.processing_timeouts: Dict[str, float] = {}  # node_id -> timeout timestamp
        self.fallback_timeout_seconds: float = 30.0  # Maximum wait time before fallback

    def process_node(self, node_path: str) -> ProcessingResult:
        """
        Entry point - processes a node (folder or file) recursively.

        For folders, this performs recursive DFS processing of all children.
        For files, this processes the file as a leaf node.

        Args:
            node_path: Path to the node (folder or file) to process

        Returns:
            ProcessingResult with all information nodes and relationships
        """
        try:
            logger.info(f"Starting recursive DFS processing for node: {node_path}")

            # Get the root node (folder or file)
            root_node: Optional[NodeWithContentDto] = self.root_node
            if not root_node:
                root_node = get_node_by_path(self.db_manager, self.company_id, self.repo_id, node_path)
                if not root_node:
                    logger.exception(f"Node not found for path: {node_path}")
                    return ProcessingResult(node_path=node_path, error=f"Node not found: {node_path}")

            # Initialize global thread pool with limited threads to prevent exhaustion
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                self._global_executor = executor

                # Process the node recursively
                root_description = self._process_node_recursive(root_node)

            # Clear executor reference
            self._global_executor = None

            # Collect all processed descriptions and convert to dicts
            all_descriptions_as_dicts = [node.as_object() for node in self.node_descriptions.values()]
            all_documentation_nodes = list(self.node_descriptions.values())
            all_source_nodes = list(self.source_nodes_cache.values())

            logger.info(f"Completed recursive DFS processing. Generated {len(all_descriptions_as_dicts)} descriptions")

            return ProcessingResult(
                node_path=node_path,
                hierarchical_analysis={"complete": True, "root_description": root_description.as_object()},
                node_source_mapping=self.node_source_mapping,
                information_nodes=all_descriptions_as_dicts,
                documentation_nodes=all_documentation_nodes,
                source_nodes=all_source_nodes,
            )

        except Exception as e:
            logger.exception(f"Error in recursive DFS processing: {e}")
            return ProcessingResult(node_path=node_path, error=str(e))

    def _get_processing_path(self) -> Set[str]:
        """Get the current thread's processing path, creating it if necessary."""
        if not hasattr(self._thread_local, "processing_path"):
            self._thread_local.processing_path = set()
        return self._thread_local.processing_path

    def _process_node_recursive(self, node: NodeWithContentDto) -> DocumentationNode:
        """
        Core recursive method - processes a node and all its children using queue-based coordination.

        Args:
            node: The node to process

        Returns:
            DocumentationNodeDescription for this node
        """
        node_id = node.id

        # Check if already completed (no lock needed for read-only check)
        if node_id in self.node_descriptions:
            logger.info(f"DEBUG: Cache hit for node: {node.name} ({node_id})")
            return self.node_descriptions[node_id]

        # Check database for existing documentation
        existing_doc = self._check_database_for_existing_documentation(node)
        if existing_doc:
            # Cache it and return immediately
            self.node_descriptions[node_id] = existing_doc
            self.node_source_mapping[existing_doc.hashed_id] = node_id
            self.source_nodes_cache[node_id] = node
            self.source_to_description[node_id] = existing_doc.content
            logger.info(f"DEBUG: Database cache hit for node: {node.name} ({node_id})")
            return existing_doc

        # Get current thread ID for tracking
        thread_id = str(threading.get_ident())
        
        # Try to become the processor for this node using Future for broadcast
        with self.futures_lock:
            fut = self.processing_futures.get(node_id)
            if fut is None:
                # We're the first thread for this node - we'll process it
                fut = Future()
                self.processing_futures[node_id] = fut
                self.dependency_tracker.register_processor(node_id, thread_id)
                should_process = True
            else:
                # Another thread is already processing this node - check if we can safely wait
                can_wait = self.dependency_tracker.register_waiter(node_id, thread_id)
                should_process = False
                
                if not can_wait:
                    # Would create deadlock - use fallback strategy
                    logger.warning(
                        f"Potential deadlock detected for node {node.name} ({node_id}), "
                        f"using fallback strategy"
                    )
                    return self._handle_deadlock_fallback(node)

        if should_process:
            # We're the processor thread - do the actual work
            logger.info(f"DEBUG: Processing node: {node.name} ({node_id})")

            # Get and update the processing path to detect cycles
            processing_path = self._get_processing_path()
            processing_path.add(node_id)

            try:
                # Get immediate children based on navigation strategy (hierarchy or call stack)
                children = self._get_navigation_children(node)

                if not children:  # LEAF NODE
                    logger.info(f"DEBUG: Processing leaf node: {node.name}")
                    description = self._process_leaf_node(node)
                else:  # PARENT NODE
                    if node.name == "blarify":
                        logger.info(f"DEBUG: root node: {node.name} ({node_id})")
                    logger.info(f"DEBUG: Processing parent node: {node.name} with {len(children)} children")

                    # Process ALL children using navigation-based strategy
                    child_descriptions = self._process_children_parallel(children, node)

                    # Process parent with complete child context
                    description = self._process_parent_node(node, child_descriptions)

                # Cache the result in existing node_descriptions
                self.node_descriptions[node_id] = description
                logger.info(f"DEBUG: Cached result for node: {node.name} ({node_id})")

                # Broadcast result to all waiting threads via Future
                fut.set_result(description)

                return description

            except Exception as e:
                # Propagate error to all waiting threads via Future
                logger.exception(f"Error processing node {node.name} ({node_id}): {e}")
                fut.set_exception(e)
                raise
            finally:
                # Always remove from processing path and clean up futures mapping
                processing_path.discard(node_id)
                # Clean up the future from processing_futures to avoid memory leak
                with self.futures_lock:
                    self.processing_futures.pop(node_id, None)
                # Clean up dependency tracker
                self.dependency_tracker.unregister_processor(node_id)
                self.processing_timeouts.pop(node_id, None)
        else:
            # We're a waiter thread - wait for the processor to complete with timeout
            logger.info(f"DEBUG: Waiting for another thread to complete {node.name} ({node_id})")
            
            try:
                # Wait with timeout to avoid infinite blocking
                result = fut.result(timeout=self.fallback_timeout_seconds)
                logger.info(f"DEBUG: Received result from processor thread for {node.name} ({node_id})")
                return result
            except concurrent.futures.TimeoutError:
                logger.warning(
                    f"Timeout waiting for node {node.name} ({node_id}) after {self.fallback_timeout_seconds}s, "
                    f"using fallback strategy"
                )
                return self._handle_timeout_fallback(node)
            finally:
                # Always unregister as waiter
                self.dependency_tracker.unregister_waiter(node_id, thread_id)

    def _get_available_threads(self) -> int:
        """Get number of available threads in the thread pool."""
        if self._global_executor is None:
            return 0

        try:
            # Conservative approach: always assume limited availability to prevent deadlocks
            # The _threads attribute doesn't accurately reflect available threads
            # since it includes all threads ever created, not just active ones
            max_workers = self._global_executor._max_workers

            # Dynamic calculation based on active futures (nodes being processed)
            # This gives a more accurate picture of thread availability
            active_nodes = len(self.processing_futures)
            conservative_available = max(1, max_workers - active_nodes)

            logger.debug(f"Thread pool: max_workers={max_workers}, conservative_available={conservative_available}")
            return conservative_available
        except Exception as e:
            logger.warning(f"Could not check thread pool capacity: {e}")
            return 0

    def _process_children_parallel(
        self, children: List[NodeWithContentDto], parent_node: NodeWithContentDto
    ) -> List[DocumentationNode]:
        """
        Process child nodes using navigation-based strategy to prevent recursion deadlocks.

        Args:
            children: List of child nodes to process
            parent_node: Parent node to determine navigation strategy

        Returns:
            List of processed child descriptions
        """
        if not children:
            return []

        child_descriptions: List[DocumentationNode] = []

        # Determine if parent uses call stack navigation (function calling other functions)
        uses_call_stack = self._should_use_call_stack(parent_node)

        if uses_call_stack:
            # Call stack navigation - always process sequentially to avoid recursion deadlocks
            logger.info(
                f"Call stack navigation detected for {parent_node.name}, processing {len(children)} children sequentially to avoid recursion deadlocks"
            )
            for child in children:
                child_desc = self._process_node_recursive(child)
                child_descriptions.append(child_desc)
        else:
            # Hierarchy navigation - safe to parallelize with capacity checking
            available_threads = self._get_available_threads()
            needs_parallel = len(children) > 1 and self.max_workers > 1 and self._global_executor is not None
            # Since _get_available_threads() already returns a conservative estimate (max_workers // 3),
            # we just need to check if we have enough threads for the children
            has_capacity = available_threads >= len(children)

            if not needs_parallel or not has_capacity:
                # Process sequentially if:
                # - Single child or single worker mode
                # - No thread pool available
                # - Not enough thread capacity
                if not has_capacity and needs_parallel:
                    logger.info(
                        f"Thread pool near capacity ({available_threads} available), processing {len(children)} children sequentially"
                    )

                for child in children:
                    child_desc = self._process_node_recursive(child)
                    child_descriptions.append(child_desc)
            else:
                # Process in parallel - we have enough thread capacity and it's safe (hierarchy navigation)
                logger.debug(
                    f"Hierarchy navigation: processing {len(children)} children in parallel ({available_threads} threads available)"
                )
                futures = []
                for child in children:
                    ctx = contextvars.copy_context()
                    try:
                        if self._global_executor is None:
                            child_desc = self._process_node_recursive(child)
                            child_descriptions.append(child_desc)
                            continue

                        future = self._global_executor.submit(
                            ctx.run, functools.partial(self._process_node_recursive, child)
                        )
                        futures.append((future, child))
                    except RuntimeError as e:
                        if "can't start new thread" in str(e):
                            logger.warning(
                                f"Thread pool exhausted during submission, processing {child.name} ({child.id}) sequentially"
                            )
                            # Fall back to sequential processing for this child
                            child_desc = self._process_node_recursive(child)
                            child_descriptions.append(child_desc)
                        else:
                            raise

                # Collect results from submitted futures
                for future, child in futures:
                    try:
                        child_desc = future.result()
                        child_descriptions.append(child_desc)
                    except Exception as e:
                        logger.exception(f"Error processing child node {child.name} ({child.id}): {e}")
                        # Create fallback description for failed child
                        fallback_desc = self._create_fallback_description(child, str(e))
                        child_descriptions.append(fallback_desc)

        return child_descriptions

    def _create_fallback_description(self, node: NodeWithContentDto, error_msg: str) -> DocumentationNode:
        """
        Create a fallback description for nodes that failed to process.

        Args:
            node: The node that failed to process
            error_msg: Error message describing the failure

        Returns:
            Fallback DocumentationNode
        """
        info_node = DocumentationNode(
            title=f"Description of {node.name}",
            content=f"Error processing this {' | '.join(node.labels) if node.labels else 'code element'}: {error_msg}",
            info_type="error_fallback",
            source_path=node.path,
            source_name=node.name,
            source_labels=node.labels,
            source_id=node.id,
            source_type="parallel_processing_error",
            graph_environment=self.graph_environment,
        )

        # Update mappings (protected by the calling method's per-node lock)
        self.node_source_mapping[info_node.hashed_id] = node.id
        self.source_to_description[node.id] = info_node.content

        return info_node

    def _process_leaf_node(self, node: NodeWithContentDto) -> DocumentationNode:
        """
        Process a leaf node using the dumb agent.

        Args:
            node: The leaf node to process

        Returns:
            DocumentationNodeDescription for the leaf node
        """
        try:
            # Get raw templates and let LLM provider handle formatting
            system_prompt, input_prompt = LEAF_NODE_ANALYSIS_TEMPLATE.get_prompts()

            # Use call_dumb_agent for simple, fast processing with 5s timeout
            runnable_config = {"run_name": node.name}
            response = self.agent_caller.call_dumb_agent(
                system_prompt=system_prompt,
                input_dict={
                    "node_name": node.name,
                    "node_labels": " | ".join(node.labels) if node.labels else "UNKNOWN",
                    "node_path": node.path,
                    "node_content": node.content,
                },
                output_schema=None,
                input_prompt=input_prompt,
                config=runnable_config,
                timeout=5,
            )

            # Extract response content
            response_content = response.content if hasattr(response, "content") else str(response)

            # Create DocumentationNode
            info_node = DocumentationNode(
                title=f"Description of {node.name}",
                content=response_content,
                info_type="leaf_description",
                source_path=node.path,
                source_name=node.name,
                source_labels=node.labels,
                source_id=node.id,
                source_type="recursive_leaf_analysis",
                graph_environment=self.graph_environment,
            )

            # Track mapping using the node's hashed_id (protected by per-node lock)
            self.node_source_mapping[info_node.hashed_id] = node.id
            # Cache the actual source Node object
            self.source_nodes_cache[node.id] = node
            # Also track for efficient child lookup during skeleton replacement
            self.source_to_description[node.id] = response_content

            return info_node

        except Exception as e:
            logger.exception(f"Error analyzing leaf node {node.name} ({node.id}): {e}")
            # Return fallback description
            info_node = DocumentationNode(
                title=f"Description of {node.name}",
                content=f"Error analyzing this {' | '.join(node.labels) if node.labels else 'code element'}: {str(e)}",
                info_type="leaf_description",
                source_path=node.path,
                source_name=node.name,
                source_labels=node.labels,
                source_id=node.id,
                source_type="error_fallback",
                graph_environment=self.graph_environment,
            )

            # Track mapping using the node's hashed_id (protected by per-node lock)
            self.node_source_mapping[info_node.hashed_id] = node.id
            # Cache the actual source Node object
            self.source_nodes_cache[node.id] = node
            # Also track for efficient child lookup during skeleton replacement
            self.source_to_description[node.id] = (
                f"Error analyzing this {' | '.join(node.labels) if node.labels else 'code element'}: {str(e)}"
            )

            return info_node

    def _process_parent_node(
        self, node: NodeWithContentDto, child_descriptions: List[DocumentationNode]
    ) -> DocumentationNode:
        """
        Process a parent node with context from all its children.

        Args:
            node: The parent node to process
            child_descriptions: List of child descriptions

        Returns:
            DocumentationNodeDescription for the parent node
        """
        try:
            # Determine processing strategy and get analysis input
            system_prompt, input_prompt, input_dict, enhanced_content = self._prepare_parent_analysis(
                node, child_descriptions
            )

            # Generate LLM response
            response_content = self._generate_parent_response(node, system_prompt, input_prompt, input_dict)

            # Create and cache documentation node
            return self._create_parent_documentation_node(node, response_content, enhanced_content, child_descriptions)

        except Exception as e:
            logger.exception(f"Error analyzing parent node {node.name} ({node.id}): {e}")
            return self._create_fallback_parent_node(node, child_descriptions, str(e))

    def _prepare_parent_analysis(
        self, node: NodeWithContentDto, child_descriptions: List[DocumentationNode]
    ) -> tuple[str, str, Dict[str, Any], str]:
        """
        Prepare analysis input for parent node based on type and cycle detection.

        Args:
            node: The parent node to process
            child_descriptions: List of child descriptions

        Returns:
            Tuple of (system_prompt, input_prompt, input_dict, enhanced_content)
        """
        is_function_with_calls = self._should_use_call_stack(node) and child_descriptions

        if is_function_with_calls:
            # Check for cycles in function calls with error handling
            try:
                cycles = detect_function_cycles(self.db_manager, self.company_id, self.repo_id, node.id)
                has_cycles = len(cycles) > 0

                if has_cycles:
                    logger.info(f"DEBUG: Detected {len(cycles)} cycles for function {node.name}")
                    return self._prepare_function_with_cycle_analysis(node, child_descriptions, cycles)
                else:
                    return self._prepare_function_with_calls_analysis(node, child_descriptions)
            except Exception as e:
                logger.warning(f"Cycle detection failed for function {node.name} ({node.id}): {e}")
                # Fall back to regular function with calls analysis
                return self._prepare_function_with_calls_analysis(node, child_descriptions)
        else:
            return self._prepare_regular_parent_analysis(node, child_descriptions)

    def _prepare_function_with_calls_analysis(
        self, node: NodeWithContentDto, child_descriptions: List[DocumentationNode]
    ) -> tuple[str, str, Dict[str, Any], str]:
        """Prepare analysis for functions with calls but no cycles."""
        system_prompt, input_prompt = FUNCTION_WITH_CALLS_ANALYSIS_TEMPLATE.get_prompts()
        child_calls_context = self._create_function_calls_context(child_descriptions)

        # Check if this function makes recursive calls
        recursive_calls = getattr(self._thread_local, "recursive_calls", {}).get(node.id, [])
        if recursive_calls:
            # Add recursive call information to the context
            recursive_info = "\n\n**Recursive Calls Detected:**\n"
            for recursive_call in recursive_calls:
                recursive_info += f"- This function recursively calls **{recursive_call.name}** (which is currently being processed)\n"
            child_calls_context += recursive_info

        input_dict = {
            "node_name": node.name,
            "node_labels": " | ".join(node.labels) if node.labels else "UNKNOWN",
            "node_path": node.path,
            "start_line": str(node.start_line) if node.start_line else "Unknown",
            "end_line": str(node.end_line) if node.end_line else "Unknown",
            "node_content": node.content,
            "child_calls_context": child_calls_context,
        }

        return system_prompt, input_prompt, input_dict, child_calls_context

    def _prepare_function_with_cycle_analysis(
        self, node: NodeWithContentDto, child_descriptions: List[DocumentationNode], cycles: List[List[str]]
    ) -> tuple[str, str, Dict[str, Any], str]:
        """Prepare analysis for functions that participate in cycles."""
        system_prompt, input_prompt = FUNCTION_WITH_CYCLE_ANALYSIS_TEMPLATE.get_prompts()
        child_calls_context = self._create_function_calls_context(child_descriptions)
        cycle_participants = self._format_cycle_participants(cycles)

        # Check if this function makes recursive calls
        recursive_calls = getattr(self._thread_local, "recursive_calls", {}).get(node.id, [])
        if recursive_calls:
            # Add recursive call information to the context
            recursive_info = "\n\n**Direct Recursive Calls Detected:**\n"
            for recursive_call in recursive_calls:
                recursive_info += f"- This function directly calls **{recursive_call.name}** recursively\n"
            child_calls_context += recursive_info

        input_dict = {
            "node_name": node.name,
            "node_labels": " | ".join(node.labels) if node.labels else "UNKNOWN",
            "node_path": node.path,
            "start_line": str(node.start_line) if node.start_line else "Unknown",
            "end_line": str(node.end_line) if node.end_line else "Unknown",
            "node_content": node.content,
            "cycle_participants": cycle_participants,
            "child_calls_context": child_calls_context,
        }

        return system_prompt, input_prompt, input_dict, child_calls_context

    def _prepare_regular_parent_analysis(
        self, node: NodeWithContentDto, child_descriptions: List[DocumentationNode]
    ) -> tuple[str, str, Dict[str, Any], str]:
        """Prepare analysis for non-function parent nodes."""
        system_prompt, input_prompt = PARENT_NODE_ANALYSIS_TEMPLATE.get_prompts()

        # Create enhanced content based on node type
        if "FOLDER" in node.labels:
            enhanced_content = self._create_child_descriptions_summary(child_descriptions)
        else:
            # For files and code nodes with actual content, replace skeleton comments
            enhanced_content = self._replace_skeleton_comments_with_descriptions(node.content, child_descriptions)

        input_dict = {
            "node_name": node.name,
            "node_labels": " | ".join(node.labels) if node.labels else "UNKNOWN",
            "node_path": node.path,
            "node_content": enhanced_content,
        }

        return system_prompt, input_prompt, input_dict, enhanced_content

    def _generate_parent_response(
        self, node: NodeWithContentDto, system_prompt: str, input_prompt: str, input_dict: Dict[str, Any]
    ) -> str:
        """Generate LLM response for parent node analysis."""
        runnable_config = {"run_name": node.name}
        response = self.agent_caller.call_dumb_agent(
            system_prompt=system_prompt,
            input_dict=input_dict,
            output_schema=None,
            input_prompt=input_prompt,
            config=runnable_config,
            timeout=5,
        )

        return response.content if hasattr(response, "content") else str(response)

    def _create_parent_documentation_node(
        self,
        node: NodeWithContentDto,
        response_content: str,
        enhanced_content: str,
        child_descriptions: List[DocumentationNode],
    ) -> DocumentationNode:
        """Create and cache the documentation node for a parent."""
        info_node = DocumentationNode(
            title=f"Description of {node.name}",
            content=response_content,
            info_type="parent_description",
            source_path=node.path,
            source_name=node.name,
            source_labels=node.labels,
            source_id=node.id,
            source_type="recursive_parent_analysis",
            enhanced_content=enhanced_content,
            children_count=len(child_descriptions),
            graph_environment=self.graph_environment,
        )

        # Track mapping using the node's hashed_id (protected by per-node lock)
        self.node_source_mapping[info_node.hashed_id] = node.id
        # Cache the actual source Node object
        self.source_nodes_cache[node.id] = node
        self.source_to_description[node.id] = response_content

        return info_node

    def _create_fallback_parent_node(
        self, node: NodeWithContentDto, child_descriptions: List[DocumentationNode], error_msg: str
    ) -> DocumentationNode:
        """Create fallback documentation node for failed parent processing."""
        info_node = DocumentationNode(
            title=f"Description of {node.name}",
            content=f"Error analyzing this {' | '.join(node.labels) if node.labels else 'code element'}: {error_msg}",
            info_type="parent_description",
            source_path=node.path,
            source_name=node.name,
            source_labels=node.labels,
            source_id=node.id,
            source_type="error_fallback",
            children_count=len(child_descriptions),
            graph_environment=self.graph_environment,
        )

        # Track mapping using the node's hashed_id (protected by per-node lock)
        self.node_source_mapping[info_node.hashed_id] = node.id
        # Cache the actual source Node object
        self.source_nodes_cache[node.id] = node
        self.source_to_description[node.id] = (
            f"Error analyzing this {' | '.join(node.labels) if node.labels else 'code element'}: {error_msg}"
        )

        return info_node

    def _format_cycle_participants(self, cycles: List[List[str]]) -> str:
        """Format cycle information for LLM analysis."""
        if not cycles:
            return "No cycles detected"

        cycle_info = []
        for i, cycle in enumerate(cycles):
            cycle_str = " -> ".join(cycle)
            cycle_info.append(f"Cycle {i + 1}: {cycle_str}")

        return "; ".join(cycle_info)

    def _replace_skeleton_comments_with_descriptions(
        self, parent_content: str, child_descriptions: List[DocumentationNode]
    ) -> str:
        """
        Replace skeleton comments with LLM-generated descriptions.

        Args:
            parent_content: The parent node's content with skeleton comments
            child_descriptions: List of child descriptions to insert

        Returns:
            Enhanced content with descriptions replacing skeleton comments
        """
        if not parent_content:
            return ""

        enhanced_content = parent_content

        # Use the pre-built source_to_description mapping for efficient lookup
        # (safe since this runs within the per-node lock context)
        child_lookup = self.source_to_description.copy()

        # Pattern to match skeleton comments
        # Example: # Code replaced for brevity, see node: 6fd101f9571073a44fed7c085c94eec2
        skeleton_pattern = r"# Code replaced for brevity, see node: ([a-f0-9]+)"

        def replace_comment(match: re.Match[str]) -> str:
            node_id = match.group(1)
            if node_id in child_lookup:
                description = child_lookup[node_id]
                # Format as a proper docstring
                # Indent the description to match the original comment's indentation
                indent_match = re.search(r"^(\s*)", match.group(0))
                indent = indent_match.group(1) if indent_match else ""
                formatted_desc = f'{indent}"""\n'
                for line in description.split("\n"):
                    formatted_desc += f"{indent}{line}\n"
                formatted_desc += f'{indent}"""'
                return formatted_desc
            else:
                # Keep original if no description found
                return match.group(0)

        enhanced_content = re.sub(skeleton_pattern, replace_comment, enhanced_content, flags=re.MULTILINE)

        return enhanced_content

    def _create_child_descriptions_summary(self, child_descriptions: List[DocumentationNode]) -> str:
        """
        Create enhanced content for folder nodes by summarizing child descriptions.

        Args:
            child_descriptions: List of child descriptions

        Returns:
            Structured summary of all child elements
        """
        if not child_descriptions:
            return "Empty folder with no child elements."

        content_parts = ["Folder containing the following elements:\n"]

        for desc in child_descriptions:
            # Extract node type from source labels
            node_type = " | ".join(desc.source_labels) if desc.source_labels else "UNKNOWN"

            # Get just the filename/component name from path
            component_name = desc.source_path.split("/")[-1] if desc.source_path else "unknown"

            content_parts.append(f"- **{component_name}** ({node_type}): {desc.content}")

        return "\n".join(content_parts)

    # Call Stack Navigation Methods

    def _get_navigation_children(self, node: NodeWithContentDto) -> List[NodeWithContentDto]:
        """
        Decides between hierarchy or call stack children based on node type.

        Args:
            node: The node to get children for

        Returns:
            List of child nodes using appropriate navigation strategy
        """
        if self._should_use_call_stack(node):
            return self._get_call_stack_children(node)
        else:
            return self._get_hierarchy_children(node)

    def _should_use_call_stack(self, node: NodeWithContentDto) -> bool:
        """
        Determines if node should use call stack navigation.

        Args:
            node: The node to check

        Returns:
            True if should use call stack navigation, False for hierarchy
        """
        # Use call stack navigation for functions that are not files or folders
        return "FUNCTION" in node.labels and not ("FILE" in node.labels or "FOLDER" in node.labels)

    def _get_hierarchy_children(self, node: NodeWithContentDto) -> List[NodeWithContentDto]:
        """
        Get children using hierarchy relationships (CONTAINS, FUNCTION_DEFINITION, CLASS_DEFINITION).

        Args:
            node: The parent node

        Returns:
            List of child nodes through hierarchical relationships
        """
        return get_direct_children(self.db_manager, self.company_id, self.repo_id, node.id)

    def _get_call_stack_children(self, node: NodeWithContentDto) -> List[NodeWithContentDto]:
        """
        Get children using call stack relationships (CALLS, USES).
        Filters out children that would create cycles to prevent infinite recursion.

        Args:
            node: The parent function node

        Returns:
            List of called/used nodes through CALLS and USES relationships, excluding cycles
        """
        all_children = get_call_stack_children(self.db_manager, self.company_id, self.repo_id, node.id)

        # Get current processing path to detect potential cycles
        processing_path = self._get_processing_path()

        # Filter out children that are already in the processing path
        filtered_children = []
        recursive_calls = []

        for child in all_children:
            if child.id in processing_path:
                logger.info(
                    f"Detected recursive call: {node.name} calls {child.name} which is already in processing path"
                )
                recursive_calls.append(child)
            else:
                filtered_children.append(child)

        # Store recursive call information for later use in description
        if recursive_calls:
            if not hasattr(self._thread_local, "recursive_calls"):
                self._thread_local.recursive_calls = {}
            self._thread_local.recursive_calls[node.id] = recursive_calls

        return filtered_children

    def _create_function_calls_context(self, child_descriptions: List[DocumentationNode]) -> str:
        """
        Create formatted context from child function descriptions for call stack analysis.

        Deduplicates functions that are called multiple times to avoid repetition.

        Args:
            child_descriptions: List of descriptions for called/used functions

        Returns:
            Formatted string describing called functions and their purposes
        """
        if not child_descriptions:
            return "This function does not call any other functions or use dependencies."

        # Deduplicate by function name and source path to avoid repeating same function multiple times
        unique_functions = {}

        for desc in child_descriptions:
            # Get function name from source name or path
            function_name = desc.source_name or "Unknown function"
            source_path = desc.source_path or ""

            # Create unique key combining name and path to handle functions with same name in different files
            unique_key = f"{function_name}|{source_path}"

            # Store first occurrence (they should all have same description)
            if unique_key not in unique_functions:
                unique_functions[unique_key] = desc

        context_parts = []
        for desc in unique_functions.values():
            # Get function name from source name or path
            function_name = desc.source_name or "Unknown function"

            # Extract node type info
            node_type = " | ".join(desc.source_labels) if desc.source_labels else "FUNCTION"

            # Format the description entry
            context_parts.append(f"- **{function_name}** ({node_type}): {desc.content}")

        return "\n".join(context_parts)

    def _check_database_for_existing_documentation(self, node: NodeWithContentDto) -> Optional[DocumentationNode]:
        """
        Check if documentation already exists for this node in the database.

        Args:
            node: The node to check for existing documentation

        Returns:
            DocumentationNode if documentation exists, None otherwise
        """
        try:
            # Query database for existing documentation
            doc_data = get_existing_documentation_for_node(self.db_manager, self.company_id, self.repo_id, node.id)

            if not doc_data:
                return None

            # Create DocumentationNode from database data
            info_node = DocumentationNode(
                title=doc_data.get("title", f"Description of {node.name}"),
                content=doc_data.get("content", ""),
                info_type=doc_data.get("info_type", "database_cached"),
                source_path=doc_data.get("source_path", node.path),
                source_name=node.name,  # Use node.name since source_name is not stored in database
                source_labels=doc_data.get("source_labels", node.labels),
                source_id=node.id,
                source_type=doc_data.get("source_type", "database_cached"),
                enhanced_content=doc_data.get("enhanced_content"),
                children_count=doc_data.get("children_count"),
                graph_environment=self.graph_environment,
            )

            return info_node

        except Exception as e:
            logger.exception(
                f"Error checking database for existing documentation for node {node.name} ({node.id}): {e}"
            )
            return None
    
    def _handle_deadlock_fallback(self, node: NodeWithContentDto) -> DocumentationNode:
        """
        Handle deadlock scenario by using available context or processing as leaf.
        
        Args:
            node: The node to process with fallback strategy
            
        Returns:
            DocumentationNode with fallback processing
        """
        node_id = node.id
        
        # Check if we already have a fallback result for this node
        if node_id in self.deadlock_fallback_cache:
            return self.deadlock_fallback_cache[node_id]
        
        logger.info(f"Processing node {node.name} ({node_id}) with deadlock fallback strategy")
        
        # Strategy 1: Try to get partial context from already-processed children
        children = self._get_navigation_children(node)
        available_children: List[DocumentationNode] = []
        
        for child in children:
            if child.id in self.node_descriptions:
                # Child is already processed - we can use it
                available_children.append(self.node_descriptions[child.id])
        
        if available_children:
            # We have some child context - process as parent with partial information
            description = self._process_parent_node_with_partial_context(
                node, available_children, is_fallback=True
            )
        else:
            # No child context available - process as enhanced leaf
            description = self._process_node_as_enhanced_leaf(node, is_fallback=True)
        
        # Cache the fallback result
        self.deadlock_fallback_cache[node_id] = description
        self.node_descriptions[node_id] = description
        
        return description
    
    def _handle_timeout_fallback(self, node: NodeWithContentDto) -> DocumentationNode:
        """Handle timeout by using available context or creating fallback description."""
        return self._handle_deadlock_fallback(node)  # Same strategy for now
    
    def _process_parent_node_with_partial_context(
        self, 
        node: NodeWithContentDto, 
        available_children: List[DocumentationNode],
        is_fallback: bool = False
    ) -> DocumentationNode:
        """
        Process parent node with only partially available child context.
        
        Args:
            node: The parent node to process
            available_children: List of available child DocumentationNodes
            is_fallback: Whether this is fallback processing
            
        Returns:
            DocumentationNode with partial context processing
        """
        try:
            # Prepare child descriptions
            child_descriptions = "\n\n".join([
                f"- **{child.source_name}**: {child.content}"
                for child in available_children
            ])
            
            # Prepare fallback note
            fallback_note = ""
            if is_fallback:
                fallback_note = (
                    "**Note**: This analysis uses partial information due to circular "
                    "dependencies in the codebase. Some child function details may be incomplete."
                )
            
            # Use the existing parent node template with partial context
            system_prompt, input_prompt = PARENT_NODE_ANALYSIS_TEMPLATE.get_prompts()
            
            # Prepare input dictionary
            input_dict = {
                "node_name": node.name,
                "node_labels": " | ".join(node.labels) if node.labels else "UNKNOWN",
                "node_path": node.path,
                "node_content": node.content,
                "child_descriptions": child_descriptions,
                "fallback_note": fallback_note
            }
            
            # Generate response
            runnable_config = {"run_name": f"{node.name}_partial_parent"}
            response = self.agent_caller.call_dumb_agent(
                system_prompt=system_prompt,
                input_dict=input_dict,
                output_schema=None,
                input_prompt=input_prompt,
                config=runnable_config,
                timeout=10,
            )
            
            response_content = response.content if hasattr(response, "content") else str(response)
            
            # Create documentation node with fallback metadata
            info_node = DocumentationNode(
                title=f"Description of {node.name}",
                content=response_content,
                info_type="parent_description_fallback" if is_fallback else "parent_description",
                source_path=node.path,
                source_name=node.name,
                source_labels=node.labels,
                source_id=node.id,
                source_type="recursive_parent_analysis_fallback" if is_fallback else "recursive_parent_analysis",
                enhanced_content=node.content,
                children_count=len(available_children),
                graph_environment=self.graph_environment,
                metadata={
                    "is_fallback": is_fallback,
                    "partial_children_count": len(available_children),
                    "fallback_reason": "circular_dependency_deadlock" if is_fallback else None
                }
            )
            
            # Update mappings
            self.node_source_mapping[info_node.hashed_id] = node.id
            self.source_nodes_cache[node.id] = node
            self.source_to_description[node.id] = response_content
            
            return info_node
            
        except Exception as e:
            logger.exception(f"Error in fallback parent processing for {node.name}: {e}")
            return self._create_fallback_description(node, f"Fallback processing error: {e}")
    
    def _process_node_as_enhanced_leaf(
        self, 
        node: NodeWithContentDto,
        is_fallback: bool = False
    ) -> DocumentationNode:
        """
        Process node as an enhanced leaf when child context is not available.
        
        Args:
            node: The node to process as enhanced leaf
            is_fallback: Whether this is fallback processing
            
        Returns:
            DocumentationNode with enhanced leaf processing
        """
        try:
            # Prepare fallback note
            fallback_note = ""
            if is_fallback:
                fallback_note = (
                    "**Note**: This analysis is limited due to circular dependencies "
                    "in the codebase that prevented full context analysis."
                )
            
            # Use the existing leaf node template
            system_prompt, input_prompt = LEAF_NODE_ANALYSIS_TEMPLATE.get_prompts()
            
            # Prepare input dictionary
            input_dict = {
                "node_name": node.name,
                "node_labels": " | ".join(node.labels) if node.labels else "UNKNOWN",
                "node_path": node.path,
                "node_content": node.content,
                "fallback_note": fallback_note
            }
            
            # Generate description
            runnable_config = {"run_name": f"{node.name}_enhanced_leaf"}
            response = self.agent_caller.call_dumb_agent(
                system_prompt=system_prompt,
                input_dict=input_dict,
                output_schema=None,
                input_prompt=input_prompt,
                config=runnable_config,
                timeout=5,
            )
            
            response_content = response.content if hasattr(response, "content") else str(response)
            
            # Create documentation node
            info_node = DocumentationNode(
                title=f"Description of {node.name}",
                content=response_content,
                info_type="enhanced_leaf_fallback" if is_fallback else "enhanced_leaf_description",
                source_path=node.path,
                source_name=node.name,
                source_labels=node.labels,
                source_id=node.id,
                source_type="enhanced_leaf_analysis_fallback" if is_fallback else "enhanced_leaf_analysis",
                graph_environment=self.graph_environment,
                metadata={
                    "is_fallback": is_fallback,
                    "fallback_reason": "circular_dependency_deadlock" if is_fallback else None
                }
            )
            
            # Update mappings
            self.node_source_mapping[info_node.hashed_id] = node.id
            self.source_nodes_cache[node.id] = node
            self.source_to_description[node.id] = response_content
            
            return info_node
            
        except Exception as e:
            logger.exception(f"Error in enhanced leaf processing for {node.name}: {e}")
            return self._create_fallback_description(node, f"Enhanced leaf processing error: {e}")
    
    def _create_fallback_description(self, node: NodeWithContentDto, error_msg: str) -> DocumentationNode:
        """Create a basic fallback description when all else fails."""
        fallback_content = f"Fallback description for {node.name}: {error_msg}"
        
        info_node = DocumentationNode(
            title=f"Fallback for {node.name}",
            content=fallback_content,
            info_type="error_fallback",
            source_path=node.path,
            source_name=node.name,
            source_labels=node.labels,
            source_id=node.id,
            source_type="error_fallback",
            graph_environment=self.graph_environment,
            metadata={
                "is_fallback": True,
                "fallback_reason": "processing_error",
                "error": error_msg
            }
        )
        
        return info_node
