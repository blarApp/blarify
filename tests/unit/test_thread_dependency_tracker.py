"""
Unit tests for ThreadDependencyTracker following TDD approach.

These tests are written first (TDD) to define the behavior we expect
from the ThreadDependencyTracker before implementation.
"""

import pytest


class TestThreadDependencyTracker:
    """Unit tests for ThreadDependencyTracker following TDD approach."""
    
    @pytest.fixture
    def tracker(self):
        """Create a ThreadDependencyTracker instance for testing."""
        # Import will fail initially (TDD) - we're defining expected behavior
        from blarify.documentation.utils.recursive_dfs_processor import ThreadDependencyTracker
        return ThreadDependencyTracker()
    
    def test_register_processor(self, tracker: ThreadDependencyTracker) -> None:
        """Test that a thread can be registered as processor for a node."""
        # Given
        node_id = "node_a"
        thread_id = "thread_1"
        
        # When
        tracker.register_processor(node_id, thread_id)
        
        # Then - verify internal state (we'll need to add a getter or test method)
        # For now, we just verify no exception is raised
        assert True  # Will enhance once implementation provides inspection methods
        
    def test_register_waiter_no_deadlock(self, tracker: ThreadDependencyTracker) -> None:
        """Test registering a waiter when no deadlock would occur."""
        # Given - Thread 1 is processing node A
        tracker.register_processor("node_a", "thread_1")
        
        # When - Thread 2 wants to wait for node A (safe)
        can_wait = tracker.register_waiter("node_a", "thread_2")
        
        # Then
        assert can_wait is True, "Should be able to wait when no circular dependency exists"
        
    def test_detect_direct_deadlock(self, tracker):
        """Test detection of direct circular dependency (A waits for B, B waits for A)."""
        # Given
        # Thread 1 processes node A
        tracker.register_processor("node_a", "thread_1")
        # Thread 2 processes node B
        tracker.register_processor("node_b", "thread_2")
        # Thread 1 waits for node B
        can_wait = tracker.register_waiter("node_b", "thread_1")
        assert can_wait is True, "First wait should succeed"
        
        # When - Thread 2 tries to wait for node A (would create deadlock)
        can_wait = tracker.register_waiter("node_a", "thread_2")
        
        # Then
        assert can_wait is False, "Should detect direct circular dependency deadlock"
        
    def test_detect_transitive_deadlock(self, tracker):
        """Test detection of transitive circular dependency (A->B->C->A)."""
        # Given - Set up a chain: Thread1->NodeB (Thread2)->NodeC (Thread3)
        tracker.register_processor("node_a", "thread_1")
        tracker.register_processor("node_b", "thread_2")
        tracker.register_processor("node_c", "thread_3")
        
        # Thread 1 waits for node B
        can_wait = tracker.register_waiter("node_b", "thread_1")
        assert can_wait is True
        
        # Thread 2 waits for node C  
        can_wait = tracker.register_waiter("node_c", "thread_2")
        assert can_wait is True
        
        # When - Thread 3 tries to wait for node A (would create A->B->C->A cycle)
        can_wait = tracker.register_waiter("node_a", "thread_3")
        
        # Then
        assert can_wait is False, "Should detect transitive circular dependency"
        
    def test_unregister_waiter(self, tracker):
        """Test that waiters can be unregistered properly."""
        # Given - Thread waiting for a node
        tracker.register_processor("node_a", "thread_1")
        tracker.register_waiter("node_a", "thread_2")
        
        # When - Unregister the waiter
        tracker.unregister_waiter("node_a", "thread_2")
        
        # Then - Thread 2 should no longer be waiting
        # We verify this by checking that the same thread can wait again
        can_wait = tracker.register_waiter("node_a", "thread_2")
        assert can_wait is True, "Should be able to wait again after unregistering"
        
    def test_thread_waiting_for_itself(self, tracker):
        """Test that a thread cannot wait for a node it's processing."""
        # Given - Thread 1 is processing node A
        tracker.register_processor("node_a", "thread_1")
        
        # When - Thread 1 tries to wait for node A (waiting for itself)
        can_wait = tracker.register_waiter("node_a", "thread_1")
        
        # Then
        assert can_wait is False, "Thread should not be able to wait for node it's processing"
        
    def test_unregister_processor(self, tracker):
        """Test that processors can be unregistered properly."""
        # Given - Thread processing a node
        tracker.register_processor("node_a", "thread_1")
        
        # When - Unregister the processor
        tracker.unregister_processor("node_a")
        
        # Then - Another thread should be able to become processor
        tracker.register_processor("node_a", "thread_2")
        # No exception means it worked
        assert True
        
    def test_multiple_waiters_same_node(self, tracker):
        """Test that multiple threads can wait for the same node."""
        # Given - Thread 1 processing node A
        tracker.register_processor("node_a", "thread_1")
        
        # When - Multiple threads wait for node A
        can_wait_2 = tracker.register_waiter("node_a", "thread_2")
        can_wait_3 = tracker.register_waiter("node_a", "thread_3")
        can_wait_4 = tracker.register_waiter("node_a", "thread_4")
        
        # Then - All should be able to wait (no circular dependencies)
        assert can_wait_2 is True
        assert can_wait_3 is True
        assert can_wait_4 is True
        
    def test_complex_dependency_chain(self, tracker):
        """Test detection in a complex dependency scenario."""
        # Given - Complex setup:
        # Thread1 processes NodeA, waits for NodeB
        # Thread2 processes NodeB, waits for NodeC and NodeD
        # Thread3 processes NodeC
        # Thread4 processes NodeD, wants to wait for NodeA
        
        tracker.register_processor("node_a", "thread_1")
        tracker.register_processor("node_b", "thread_2")
        tracker.register_processor("node_c", "thread_3")
        tracker.register_processor("node_d", "thread_4")
        
        # Set up wait dependencies
        assert tracker.register_waiter("node_b", "thread_1") is True
        assert tracker.register_waiter("node_c", "thread_2") is True
        assert tracker.register_waiter("node_d", "thread_2") is True
        
        # When - Thread4 tries to wait for NodeA
        # This would create: Thread4->NodeA(Thread1)->NodeB(Thread2)->NodeD(Thread4)
        can_wait = tracker.register_waiter("node_a", "thread_4")
        
        # Then
        assert can_wait is False, "Should detect complex circular dependency"
        
    def test_safe_parallel_processing(self, tracker):
        """Test that independent branches can be processed in parallel safely."""
        # Given - Two independent processing branches
        # Branch 1: Thread1->NodeA, Thread2->NodeB  
        # Branch 2: Thread3->NodeC, Thread4->NodeD
        
        tracker.register_processor("node_a", "thread_1")
        tracker.register_processor("node_b", "thread_2")
        tracker.register_processor("node_c", "thread_3")
        tracker.register_processor("node_d", "thread_4")
        
        # When - Set up non-circular dependencies
        can_wait_1 = tracker.register_waiter("node_b", "thread_1")  # Thread1 waits for NodeB
        can_wait_2 = tracker.register_waiter("node_d", "thread_3")  # Thread3 waits for NodeD
        
        # Then - Both should succeed (no circular dependencies)
        assert can_wait_1 is True
        assert can_wait_2 is True