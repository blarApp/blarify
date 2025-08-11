"""Thread dependency tracking for deadlock detection in RecursiveDFSProcessor."""

import threading
import logging
from typing import Dict, Set, Optional

logger = logging.getLogger(__name__)


class ThreadDependencyTracker:
    """
    Tracks which threads are waiting for which nodes to detect potential deadlocks.
    
    This class monitors thread dependencies to prevent circular wait conditions
    that can occur when processing nodes with circular dependencies.
    """
    
    def __init__(self):
        """Initialize the dependency tracker."""
        self._waiting_threads: Dict[str, Set[str]] = {}  # thread_id -> set of node_ids
        self._processing_threads: Dict[str, str] = {}    # node_id -> thread_id
        self._lock = threading.Lock()
    
    def register_processor(self, node_id: str, thread_id: str) -> None:
        """
        Register a thread as the processor for a node.
        
        Args:
            node_id: ID of the node being processed
            thread_id: ID of the thread processing the node
        """
        with self._lock:
            self._processing_threads[node_id] = thread_id
            logger.debug(f"Thread {thread_id} registered as processor for node {node_id}")
    
    def register_waiter(self, node_id: str, thread_id: str) -> bool:
        """
        Register a thread as waiting for a node.
        Returns False if this would create a deadlock.
        
        Args:
            node_id: ID of the node the thread wants to wait for
            thread_id: ID of the thread that wants to wait
            
        Returns:
            True if safe to wait, False if would create deadlock
        """
        with self._lock:
            if thread_id not in self._waiting_threads:
                self._waiting_threads[thread_id] = set()
            
            # Check for potential deadlock before adding the wait dependency
            if self._would_create_deadlock(node_id, thread_id):
                logger.warning(
                    f"Deadlock prevention: Thread {thread_id} cannot wait for node {node_id} "
                    f"(would create circular dependency)"
                )
                return False
            
            self._waiting_threads[thread_id].add(node_id)
            logger.debug(f"Thread {thread_id} registered as waiter for node {node_id}")
            return True
    
    def unregister_waiter(self, node_id: str, thread_id: str) -> None:
        """
        Unregister a thread from waiting for a node.
        
        Args:
            node_id: ID of the node the thread was waiting for
            thread_id: ID of the thread that was waiting
        """
        with self._lock:
            if thread_id in self._waiting_threads:
                self._waiting_threads[thread_id].discard(node_id)
                if not self._waiting_threads[thread_id]:
                    del self._waiting_threads[thread_id]
                logger.debug(f"Thread {thread_id} unregistered from waiting for node {node_id}")
    
    def unregister_processor(self, node_id: str) -> None:
        """
        Unregister the processor for a node.
        
        Args:
            node_id: ID of the node that was being processed
        """
        with self._lock:
            if node_id in self._processing_threads:
                thread_id = self._processing_threads[node_id]
                del self._processing_threads[node_id]
                logger.debug(f"Thread {thread_id} unregistered as processor for node {node_id}")
    
    def _would_create_deadlock(self, target_node_id: str, requester_thread_id: str) -> bool:
        """
        Check if waiting for target_node_id would create a circular dependency.
        
        A deadlock occurs if:
        1. Thread A wants to wait for node X
        2. Thread B is processing node X  
        3. Thread B is already waiting (directly or transitively) for a node processed by Thread A
        
        Args:
            target_node_id: Node the thread wants to wait for
            requester_thread_id: Thread that wants to wait
            
        Returns:
            True if waiting would create a deadlock, False otherwise
        """
        processor_thread = self._processing_threads.get(target_node_id)
        if not processor_thread:
            return False  # No processor yet, safe to wait
        
        if processor_thread == requester_thread_id:
            logger.warning(f"Thread {requester_thread_id} trying to wait for itself (node {target_node_id})")
            return True  # Thread trying to wait for itself
        
        # Check for transitive dependencies
        if self._has_transitive_dependency(processor_thread, requester_thread_id):
            logger.warning(
                f"Transitive deadlock detected: Thread {requester_thread_id} -> node {target_node_id} "
                f"-> thread {processor_thread} -> ... -> thread {requester_thread_id}"
            )
            return True
        
        return False
    
    def _has_transitive_dependency(self, start_thread: str, target_thread: str) -> bool:
        """
        Check if start_thread transitively depends on target_thread.
        
        Args:
            start_thread: Thread to start checking from
            target_thread: Thread to check dependency on
            
        Returns:
            True if transitive dependency exists, False otherwise
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
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of thread dependencies for debugging.
        
        Returns:
            Dictionary with current state information
        """
        with self._lock:
            return {
                "waiting_threads": {k: list(v) for k, v in self._waiting_threads.items()},
                "processing_threads": dict(self._processing_threads),
                "total_waiting": len(self._waiting_threads),
                "total_processing": len(self._processing_threads)
            }