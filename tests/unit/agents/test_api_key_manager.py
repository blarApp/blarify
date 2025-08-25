"""Unit tests for API Key Manager."""

import os
import threading
import time
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import patch

from blarify.agents.api_key_manager import APIKeyManager, KeyState, KeyStatus


class TestKeyStatus:
    """Tests for KeyStatus enum."""
    
    def test_enum_values_are_unique(self) -> None:
        """Test that all enum values are unique."""
        values = [status.value for status in KeyStatus]
        assert len(values) == len(set(values))
    
    def test_string_representation(self) -> None:
        """Test string representation of enum values."""
        assert KeyStatus.AVAILABLE.value == "available"
        assert KeyStatus.RATE_LIMITED.value == "rate_limited"
        assert KeyStatus.QUOTA_EXCEEDED.value == "quota_exceeded"
        assert KeyStatus.INVALID.value == "invalid"


class TestKeyState:
    """Tests for KeyState dataclass."""
    
    def test_initialization_with_defaults(self) -> None:
        """Test KeyState initialization with default values."""
        key_state = KeyState(key="test-key", state=KeyStatus.AVAILABLE)
        
        assert key_state.key == "test-key"
        assert key_state.state == KeyStatus.AVAILABLE
        assert key_state.cooldown_until is None
        assert key_state.last_used is None
        assert key_state.error_count == 0
        assert key_state.metadata == {}
    
    def test_is_available_when_available(self) -> None:
        """Test is_available returns True when key is available."""
        key_state = KeyState(key="test-key", state=KeyStatus.AVAILABLE)
        assert key_state.is_available() is True
    
    def test_is_available_when_rate_limited(self) -> None:
        """Test is_available returns False when key is rate limited."""
        key_state = KeyState(key="test-key", state=KeyStatus.RATE_LIMITED)
        assert key_state.is_available() is False
    
    def test_is_available_when_invalid(self) -> None:
        """Test is_available returns False when key is invalid."""
        key_state = KeyState(key="test-key", state=KeyStatus.INVALID)
        assert key_state.is_available() is False
    
    def test_is_available_with_cooldown_not_expired(self) -> None:
        """Test is_available returns False when cooldown not expired."""
        future_time = datetime.now() + timedelta(seconds=60)
        key_state = KeyState(
            key="test-key", 
            state=KeyStatus.AVAILABLE,
            cooldown_until=future_time
        )
        assert key_state.is_available() is False
    
    def test_is_available_with_cooldown_expired(self) -> None:
        """Test is_available returns True when cooldown expired."""
        past_time = datetime.now() - timedelta(seconds=60)
        key_state = KeyState(
            key="test-key",
            state=KeyStatus.AVAILABLE,
            cooldown_until=past_time
        )
        assert key_state.is_available() is True


class TestAPIKeyManager:
    """Tests for APIKeyManager class."""
    
    def test_initialization(self) -> None:
        """Test APIKeyManager initialization."""
        manager = APIKeyManager("openai", auto_discover=False)
        
        assert manager.provider == "openai"
        assert manager.keys == {}
        assert manager._key_order == []  # type: ignore[attr-defined]
        assert manager._current_index == 0  # type: ignore[attr-defined]
    
    def test_auto_discovery_on_initialization(self) -> None:
        """Test auto-discovery of keys on initialization."""
        env_vars = {
            "OPENAI_API_KEY": "sk-proj-123456789012345678901234567890",
            "OPENAI_API_KEY_1": "sk-proj-abcdef123456789012345678901234",
            "OPENAI_API_KEY_2": "sk-123456789012345678901234567890"
        }
        with patch.dict(os.environ, env_vars, clear=True):
            manager = APIKeyManager("openai")  # auto_discover=True by default
            
            assert len(manager.keys) == 3
            assert "sk-proj-123456789012345678901234567890" in manager.keys
            assert "sk-proj-abcdef123456789012345678901234" in manager.keys
            assert "sk-123456789012345678901234567890" in manager.keys
    
    def test_disabling_auto_discovery(self) -> None:
        """Test disabling auto-discovery."""
        env_vars = {
            "OPENAI_API_KEY": "sk-proj-123456789012345678901234567890",
            "OPENAI_API_KEY_1": "sk-proj-abcdef123456789012345678901234"
        }
        with patch.dict(os.environ, env_vars, clear=True):
            manager = APIKeyManager("openai", auto_discover=False)
            
            assert len(manager.keys) == 0  # No keys discovered
    
    def test_auto_discovery_with_no_env_keys(self) -> None:
        """Test auto-discovery when no environment keys exist."""
        with patch.dict(os.environ, {}, clear=True):
            manager = APIKeyManager("openai")  # auto_discover=True by default
            
            assert len(manager.keys) == 0
    
    def test_add_key(self) -> None:
        """Test adding a new key to the manager."""
        manager = APIKeyManager("openai", auto_discover=False)
        result = manager.add_key("sk-test-key-123456789012345678901234", validate=False)
        
        assert result is True
        assert "sk-test-key-123456789012345678901234" in manager.keys
        assert manager.keys["sk-test-key-123456789012345678901234"].state == KeyStatus.AVAILABLE
        assert "sk-test-key-123456789012345678901234" in manager._key_order  # type: ignore[attr-defined]
    
    def test_add_key_with_validation_valid(self) -> None:
        """Test adding a valid key with validation enabled."""
        manager = APIKeyManager("openai", auto_discover=False)
        result = manager.add_key("sk-proj-abcdef123456789012345678901234567890")  # validation=True by default
        
        assert result is True
        assert "sk-proj-abcdef123456789012345678901234567890" in manager.keys
    
    def test_add_key_with_validation_invalid(self) -> None:
        """Test adding an invalid key with validation enabled."""
        manager = APIKeyManager("openai", auto_discover=False)
        result = manager.add_key("invalid-key")  # validation=True by default
        
        assert result is False
        assert "invalid-key" not in manager.keys
        assert len(manager.keys) == 0
    
    def test_add_duplicate_key(self) -> None:
        """Test that duplicate keys are not added."""
        manager = APIKeyManager("openai", auto_discover=False)
        result1 = manager.add_key("sk-test-key-123456789012345678901234", validate=False)
        result2 = manager.add_key("sk-test-key-123456789012345678901234", validate=False)  # Try to add duplicate
        
        assert result1 is True
        assert result2 is False
        assert len(manager.keys) == 1
        assert len(manager._key_order) == 1  # type: ignore[attr-defined]
    
    def test_get_next_available_key_round_robin(self) -> None:
        """Test round-robin key selection."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("key-1", validate=False)
        manager.add_key("key-2", validate=False)
        manager.add_key("key-3", validate=False)
        
        # Should return keys in round-robin order
        assert manager.get_next_available_key() == "key-1"
        assert manager.get_next_available_key() == "key-2"
        assert manager.get_next_available_key() == "key-3"
        assert manager.get_next_available_key() == "key-1"  # Back to first
    
    def test_get_next_available_key_skips_unavailable(self) -> None:
        """Test that selection skips unavailable keys."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("key-1", validate=False)
        manager.add_key("key-2", validate=False)
        manager.add_key("key-3", validate=False)
        
        # Mark key-2 as rate limited
        manager.keys["key-2"].state = KeyStatus.RATE_LIMITED
        
        # Should skip key-2
        assert manager.get_next_available_key() == "key-1"
        assert manager.get_next_available_key() == "key-3"  # Skips key-2
        assert manager.get_next_available_key() == "key-1"  # Back to key-1
    
    def test_get_next_available_key_returns_none_when_all_exhausted(self) -> None:
        """Test returns None when all keys are exhausted."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("key-1", validate=False)
        manager.add_key("key-2", validate=False)
        
        # Mark all keys as invalid
        manager.keys["key-1"].state = KeyStatus.INVALID
        manager.keys["key-2"].state = KeyStatus.INVALID
        
        assert manager.get_next_available_key() is None
    
    def test_get_next_available_key_with_no_keys(self) -> None:
        """Test returns None when no keys are configured."""
        manager = APIKeyManager("openai", auto_discover=False)
        assert manager.get_next_available_key() is None
    
    def test_mark_rate_limited_without_retry_after(self) -> None:
        """Test marking a key as rate limited without cooldown."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("key-1", validate=False)
        
        manager.mark_rate_limited("key-1")
        
        assert manager.keys["key-1"].state == KeyStatus.RATE_LIMITED
        assert manager.keys["key-1"].cooldown_until is None
    
    def test_mark_rate_limited_with_retry_after(self) -> None:
        """Test marking a key as rate limited with cooldown."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("key-1", validate=False)
        
        manager.mark_rate_limited("key-1", retry_after=30)
        
        assert manager.keys["key-1"].state == KeyStatus.RATE_LIMITED
        assert manager.keys["key-1"].cooldown_until is not None
        # Check cooldown is approximately 30 seconds in the future
        time_diff = (manager.keys["key-1"].cooldown_until - datetime.now()).total_seconds()
        assert 29 <= time_diff <= 31
    
    def test_mark_invalid(self) -> None:
        """Test marking a key as invalid."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("key-1", validate=False)
        
        initial_error_count = manager.keys["key-1"].error_count
        manager.mark_invalid("key-1")
        
        assert manager.keys["key-1"].state == KeyStatus.INVALID
        assert manager.keys["key-1"].error_count == initial_error_count + 1
    
    def test_mark_quota_exceeded(self) -> None:
        """Test marking a key as quota exceeded."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("key-1", validate=False)
        
        manager.mark_quota_exceeded("key-1")
        
        assert manager.keys["key-1"].state == KeyStatus.QUOTA_EXCEEDED
    
    def test_state_transitions_on_non_existent_key(self) -> None:
        """Test state transitions on non-existent keys do nothing."""
        manager = APIKeyManager("openai", auto_discover=False)
        
        # These should not raise exceptions
        manager.mark_rate_limited("non-existent")
        manager.mark_invalid("non-existent")
        manager.mark_quota_exceeded("non-existent")
        
        assert len(manager.keys) == 0
    
    def test_automatic_cooldown_expiration(self) -> None:
        """Test automatic cooldown expiration."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("key-1", validate=False)
        manager.add_key("key-2", validate=False)
        
        # Mark key-1 with expired cooldown
        past_time = datetime.now() - timedelta(seconds=10)
        manager.keys["key-1"].state = KeyStatus.RATE_LIMITED
        manager.keys["key-1"].cooldown_until = past_time
        
        # Mark key-2 with future cooldown
        future_time = datetime.now() + timedelta(seconds=60)
        manager.keys["key-2"].state = KeyStatus.RATE_LIMITED
        manager.keys["key-2"].cooldown_until = future_time
        
        # Call get_next_available_key which internally calls reset_expired_cooldowns
        result = manager.get_next_available_key()
        
        # key-1 should be available again
        assert manager.keys["key-1"].state == KeyStatus.AVAILABLE
        assert manager.keys["key-1"].cooldown_until is None
        assert result == "key-1"
        
        # key-2 should still be rate limited
        assert manager.keys["key-2"].state == KeyStatus.RATE_LIMITED
        assert manager.keys["key-2"].cooldown_until == future_time
    
    def test_multiple_keys_with_different_cooldowns(self) -> None:
        """Test multiple keys with different cooldown periods."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("key-1", validate=False)
        manager.add_key("key-2", validate=False)
        manager.add_key("key-3", validate=False)
        
        # All keys start available
        assert manager.get_next_available_key() == "key-1"
        
        # Mark all as rate limited with different cooldowns
        manager.mark_rate_limited("key-1", retry_after=1)
        manager.mark_rate_limited("key-2", retry_after=2)
        manager.mark_rate_limited("key-3", retry_after=3)
        
        # No keys available immediately
        assert manager.get_next_available_key() is None
        
        # Wait for key-1 to become available
        time.sleep(1.1)
        assert manager.get_next_available_key() == "key-1"
        
        # key-2 and key-3 should still be rate limited
        assert manager.keys["key-2"].state == KeyStatus.RATE_LIMITED
        assert manager.keys["key-3"].state == KeyStatus.RATE_LIMITED
    
    def test_no_change_when_cooldown_not_expired(self) -> None:
        """Test no state change when cooldown not expired."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("key-1", validate=False)
        
        # Mark with future cooldown
        manager.mark_rate_limited("key-1", retry_after=60)
        
        # Try to get key (calls reset_expired_cooldowns)
        result = manager.get_next_available_key()
        
        # Should still be rate limited
        assert manager.keys["key-1"].state == KeyStatus.RATE_LIMITED
        assert manager.keys["key-1"].cooldown_until is not None
        assert result is None
    
    def test_get_key_states(self) -> None:
        """Test getting current state of all keys."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("key-1", validate=False)
        manager.add_key("key-2", validate=False)
        
        manager.mark_invalid("key-1")
        manager.mark_rate_limited("key-2")
        
        states = manager.get_key_states()
        
        assert len(states) == 2
        assert states["key-1"].state == KeyStatus.INVALID
        assert states["key-2"].state == KeyStatus.RATE_LIMITED
    
    def test_get_available_count(self) -> None:
        """Test getting count of available keys."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("key-1", validate=False)
        manager.add_key("key-2", validate=False)
        manager.add_key("key-3", validate=False)
        
        # All keys initially available
        assert manager.get_available_count() == 3
        
        # Mark one as invalid
        manager.mark_invalid("key-1")
        assert manager.get_available_count() == 2
        
        # Mark another as rate limited
        manager.mark_rate_limited("key-2")
        assert manager.get_available_count() == 1
        
        # Mark last one as quota exceeded
        manager.mark_quota_exceeded("key-3")
        assert manager.get_available_count() == 0
    
    def test_get_available_count_with_expired_cooldowns(self) -> None:
        """Test available count with expired cooldowns."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("key-1", validate=False)
        manager.add_key("key-2", validate=False)
        
        # Mark key-1 with expired cooldown
        past_time = datetime.now() - timedelta(seconds=10)
        manager.keys["key-1"].state = KeyStatus.RATE_LIMITED
        manager.keys["key-1"].cooldown_until = past_time
        
        # Mark key-2 with future cooldown
        manager.mark_rate_limited("key-2", retry_after=60)
        
        # get_available_count should reset expired cooldowns
        count = manager.get_available_count()
        
        assert count == 1  # Only key-1 should be available
        assert manager.keys["key-1"].state == KeyStatus.AVAILABLE


class TestAPIKeyManagerThreadSafety:
    """Test thread safety of APIKeyManager."""
    
    def test_concurrent_key_selection(self) -> None:
        """Test thread safety with concurrent key selection."""
        manager = APIKeyManager("test", auto_discover=False)
        for i in range(5):
            manager.add_key(f"key-{i}", validate=False)
        
        results: list[str] = []
        lock = threading.Lock()
        
        def get_key() -> None:
            for _ in range(100):
                key = manager.get_next_available_key()
                if key:
                    with lock:
                        results.append(key)
        
        threads = [threading.Thread(target=get_key) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify no corruption and fair distribution
        assert len(results) == 1000
        assert all(key in [f"key-{i}" for i in range(5)] for key in results)
        
        # Check reasonable distribution (each key should get some selections)
        key_counts = {f"key-{i}": 0 for i in range(5)}
        for key in results:
            key_counts[key] += 1
        
        # Each key should have been selected at least once
        assert all(count > 0 for count in key_counts.values())
    
    def test_concurrent_state_modifications(self) -> None:
        """Test concurrent state modifications."""
        manager = APIKeyManager("test", auto_discover=False)
        for i in range(10):
            manager.add_key(f"key-{i}", validate=False)
        
        def modify_states() -> None:
            for i in range(50):
                key = f"key-{i % 10}"
                if i % 3 == 0:
                    manager.mark_rate_limited(key, retry_after=1)
                elif i % 3 == 1:
                    manager.mark_invalid(key)
                else:
                    manager.mark_quota_exceeded(key)
        
        threads = [threading.Thread(target=modify_states) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify all keys still exist and have valid states
        assert len(manager.keys) == 10
        for key_state in manager.keys.values():
            assert key_state.state in [
                KeyStatus.AVAILABLE,
                KeyStatus.RATE_LIMITED,
                KeyStatus.INVALID,
                KeyStatus.QUOTA_EXCEEDED
            ]
    
    def test_concurrent_add_and_select(self) -> None:
        """Test concurrent key addition and selection."""
        manager = APIKeyManager("test", auto_discover=False)
        
        def add_keys() -> None:
            for i in range(50):
                manager.add_key(f"key-{threading.current_thread().name}-{i}")
                time.sleep(0.001)  # Small delay to simulate real-world timing
        
        def select_keys() -> None:
            for _ in range(100):
                manager.get_next_available_key()
                time.sleep(0.001)
        
        add_threads = [threading.Thread(target=add_keys, name=f"adder-{i}") for i in range(3)]
        select_threads = [threading.Thread(target=select_keys) for _ in range(3)]
        
        all_threads = add_threads + select_threads
        for t in all_threads:
            t.start()
        for t in all_threads:
            t.join()
        
        # Verify all keys were added correctly
        assert len(manager.keys) == 150  # 3 threads * 50 keys each
    
    def test_concurrent_cooldown_expiration(self) -> None:
        """Test concurrent cooldown expiration and key selection."""
        manager = APIKeyManager("test", auto_discover=False)
        for i in range(5):
            manager.add_key(f"key-{i}", validate=False)
        
        # Mark all keys with short cooldowns
        for i in range(5):
            manager.mark_rate_limited(f"key-{i}", retry_after=1)
        
        results_before: list[Optional[str]] = []
        results_after: list[str] = []
        lock = threading.Lock()
        
        def try_get_keys() -> None:
            # Try before cooldown expires
            key = manager.get_next_available_key()
            with lock:
                results_before.append(key)
            
            # Wait for cooldowns to expire
            time.sleep(1.1)
            
            # Try after cooldown expires
            key = manager.get_next_available_key()
            if key:
                with lock:
                    results_after.append(key)
        
        threads = [threading.Thread(target=try_get_keys) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Before cooldown expiration, no keys should be available
        assert all(key is None for key in results_before)
        
        # After cooldown expiration, keys should be available
        assert len(results_after) == 10
        assert all(key in [f"key-{i}" for i in range(5)] for key in results_after)


class TestAPIKeyManagerPerformance:
    """Performance tests for APIKeyManager."""
    
    def test_key_selection_performance(self) -> None:
        """Ensure key selection is fast enough."""
        manager = APIKeyManager("test", auto_discover=False)
        for i in range(100):
            manager.add_key(f"key-{i}", validate=False)
        
        start = time.time()
        for _ in range(10000):
            manager.get_next_available_key()
        duration = time.time() - start
        
        # Should complete 10k selections in under 100ms
        assert duration < 0.1, f"Key selection took {duration:.3f}s, expected < 0.1s"
    
    def test_state_transition_performance(self) -> None:
        """Test performance of state transitions."""
        manager = APIKeyManager("test", auto_discover=False)
        for i in range(100):
            manager.add_key(f"key-{i}", validate=False)
        
        start = time.time()
        for i in range(1000):
            key = f"key-{i % 100}"
            manager.mark_rate_limited(key, retry_after=1)
            manager.mark_invalid(key)
            manager.mark_quota_exceeded(key)
        duration = time.time() - start
        
        # Should complete 3k state transitions in under 100ms
        assert duration < 0.1, f"State transitions took {duration:.3f}s, expected < 0.1s"
    
    def test_concurrent_performance(self) -> None:
        """Test performance under concurrent load."""
        manager = APIKeyManager("test", auto_discover=False)
        for i in range(50):
            manager.add_key(f"key-{i}", validate=False)
        
        operations_count = 0
        lock = threading.Lock()
        
        def perform_operations() -> None:
            nonlocal operations_count
            for _ in range(1000):
                manager.get_next_available_key()
                with lock:
                    operations_count += 1
        
        start = time.time()
        threads = [threading.Thread(target=perform_operations) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        duration = time.time() - start
        
        # Should complete 10k operations across 10 threads in under 1 second
        assert duration < 1.0, f"Concurrent operations took {duration:.3f}s, expected < 1.0s"
        assert operations_count == 10000