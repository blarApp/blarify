"""Tests for rotating provider base class."""

import threading
import time
from typing import Any, Dict, Optional, Tuple
from unittest.mock import Mock

import pytest

from blarify.agents.api_key_manager import APIKeyManager
from blarify.agents.rotating_provider import ErrorType, RotatingProviderBase


def test_error_type_enum_values():
    """Test that ErrorType enum has expected values."""
    assert ErrorType.RATE_LIMIT.value == "rate_limit"
    assert ErrorType.AUTH_ERROR.value == "auth_error"
    assert ErrorType.QUOTA_EXCEEDED.value == "quota_exceeded"
    assert ErrorType.RETRYABLE.value == "retryable"
    assert ErrorType.NON_RETRYABLE.value == "non_retryable"


def test_cannot_instantiate_abstract_class():
    """Test that abstract base class cannot be instantiated directly."""
    manager = APIKeyManager("test", auto_discover=False)

    with pytest.raises(TypeError) as exc_info:
        RotatingProviderBase(manager)  # type: ignore[abstract]

    assert "Can't instantiate abstract class" in str(exc_info.value)


class MockProvider(RotatingProviderBase):
    """Mock provider implementation for testing."""

    def _create_client(self, api_key: str) -> Any:
        """Create mock client."""
        return f"client_with_{api_key}"

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "mock"

    def analyze_error(self, error: Exception) -> Tuple[ErrorType, Optional[int]]:
        """Analyze error for testing."""
        error_str = str(error).lower()
        if "rate_limit" in error_str:
            # Use a very short cooldown for testing (1 second)
            return (ErrorType.RATE_LIMIT, 1)
        return (ErrorType.RETRYABLE, None)

    def extract_headers_from_error(self, error: Exception) -> Dict[str, str]:
        """Extract headers for testing."""
        return {}


def test_mock_provider_creation():
    """Test that mock provider can be instantiated."""
    manager = APIKeyManager("test", auto_discover=False)
    provider = MockProvider(manager)

    assert provider.get_provider_name() == "mock"
    assert provider.key_manager == manager
    assert provider._current_key is None  # type: ignore[attr-defined]


def test_abstract_method_enforcement():
    """Test that all abstract methods must be implemented."""
    manager = APIKeyManager("test", auto_discover=False)

    # Missing analyze_error implementation
    class IncompleteProvider(RotatingProviderBase):
        def _create_client(self, api_key: str) -> Any:
            return "client"

        def get_provider_name(self) -> str:
            return "incomplete"

        def extract_headers_from_error(self, error: Exception) -> Dict[str, str]:
            return {}

    with pytest.raises(TypeError) as exc_info:
        IncompleteProvider(manager)  # type: ignore[abstract]

    assert "Can't instantiate abstract class" in str(exc_info.value)


def test_successful_execution():
    """Test successful execution without errors."""
    manager = APIKeyManager("test", auto_discover=False)
    manager.add_key("key1")

    provider = MockProvider(manager)

    api_call = Mock(return_value="success")

    result = provider.execute_with_rotation(api_call)
    assert result == "success"
    api_call.assert_called_once()
    # Verify the key was set before the call
    assert provider._current_key == "key1"  # type: ignore[attr-defined]


def test_rotation_on_rate_limit():
    """Test key rotation when rate limit is hit."""
    manager = APIKeyManager("test", auto_discover=False)
    manager.add_key("key1")
    manager.add_key("key2")

    provider = MockProvider(manager)

    call_count = 0

    def api_call() -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("rate_limit")
        return f"success_{call_count}"

    result = provider.execute_with_rotation(api_call)
    assert result == "success_2"
    assert call_count == 2

    # Check that first key was marked as rate limited
    states = manager.get_key_states()
    rate_limited_count = sum(1 for state in states.values() if state.state.value == "rate_limited")
    assert rate_limited_count == 1


def test_non_retryable_error_propagation():
    """Test that non-retryable errors are not retried."""
    manager = APIKeyManager("test", auto_discover=False)
    manager.add_key("key1")

    provider = MockProvider(manager)

    # Override analyze_error for this test
    original_analyze = provider.analyze_error

    def analyze_non_retryable(error: Exception) -> Tuple[ErrorType, Optional[int]]:
        return (ErrorType.NON_RETRYABLE, None)

    provider.analyze_error = analyze_non_retryable

    call_count = 0

    def api_call() -> str:
        nonlocal call_count
        call_count += 1
        raise Exception("fatal error")

    with pytest.raises(Exception) as exc_info:
        provider.execute_with_rotation(api_call)

    assert str(exc_info.value) == "fatal error"
    assert call_count == 1  # Should not retry

    # Restore original method
    provider.analyze_error = original_analyze


def test_no_available_keys():
    """Test behavior when no keys are available."""
    manager = APIKeyManager("test", auto_discover=False)
    # No keys added

    provider = MockProvider(manager)

    def api_call() -> str:
        return "success"

    with pytest.raises(RuntimeError) as exc_info:
        provider.execute_with_rotation(api_call)

    assert "No available API keys" in str(exc_info.value)


def test_success_metadata_recording():
    """Test that successful requests update metadata."""
    manager = APIKeyManager("test", auto_discover=False)
    manager.add_key("key1")

    provider = MockProvider(manager)

    def api_call() -> str:
        return "success"

    # Make multiple successful calls
    for _ in range(3):
        provider.execute_with_rotation(api_call)

    # Check metadata
    states = manager.get_key_states()
    key_state = states["key1"]
    assert key_state.metadata["request_count"] == 3
    assert key_state.metadata["success_count"] == 3
    assert "last_success" in key_state.metadata


def test_failure_metadata_recording():
    """Test that failed requests update metadata."""
    manager = APIKeyManager("test", auto_discover=False)
    manager.add_key("key1")
    manager.add_key("key2")

    provider = MockProvider(manager)

    call_count = 0

    def api_call() -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("rate_limit")
        return f"success_{call_count}"

    result = provider.execute_with_rotation(api_call)
    assert result == "success_2"
    assert call_count == 2

    # Check metadata for both keys
    states = manager.get_key_states()

    # key1 was used first and failed with rate_limit
    key1_metadata = states["key1"].metadata
    assert key1_metadata["request_count"] == 1
    assert key1_metadata["failure_count"] == 1
    assert key1_metadata["rate_limit_count"] == 1
    assert "last_failure" in key1_metadata
    assert key1_metadata.get("success_count", 0) == 0

    # key2 was used second and succeeded
    key2_metadata = states["key2"].metadata
    assert key2_metadata["request_count"] == 1
    assert key2_metadata["success_count"] == 1
    assert key2_metadata.get("failure_count", 0) == 0
    assert "last_success" in key2_metadata


def test_provider_metrics_tracking():
    """Test that provider metrics are tracked correctly."""
    manager = APIKeyManager("test", auto_discover=False)
    manager.add_key("key1")
    manager.add_key("key2")

    provider = MockProvider(manager)

    # Successful call
    api_call_success = Mock(return_value="success")
    provider.execute_with_rotation(api_call_success)
    api_call_success.assert_called_once()

    # Check metrics after success
    metrics = provider.get_metrics_snapshot()
    assert metrics.total_requests == 1
    assert metrics.successful_requests == 1
    assert metrics.failed_requests == 0
    assert provider.get_success_rate() == 100.0

    # Failed call with rate limit (will exhaust retries)
    api_call_fail = Mock(side_effect=Exception("rate_limit"))
    try:
        provider.execute_with_rotation(api_call_fail, max_retries=1)
    except Exception:
        pass
    api_call_fail.assert_called_once()

    # Check metrics after failure
    metrics = provider.get_metrics_snapshot()
    assert metrics.total_requests == 2
    assert metrics.successful_requests == 1
    assert metrics.failed_requests == 1
    assert metrics.rate_limit_hits == 1
    assert metrics.error_breakdown.get("rate_limit") == 1
    assert provider.get_success_rate() == 50.0


def test_key_rotation_metrics():
    """Test that key rotation is tracked in metrics."""
    manager = APIKeyManager("test", auto_discover=False)
    manager.add_key("key1")
    manager.add_key("key2")

    provider = MockProvider(manager)

    # Mock that fails once then succeeds
    api_call = Mock(side_effect=[Exception("rate_limit"), "success"])

    result = provider.execute_with_rotation(api_call)
    assert result == "success"
    assert api_call.call_count == 2

    # Check rotation metrics
    metrics = provider.get_metrics_snapshot()
    assert metrics.key_rotations == 1
    assert metrics.last_rotation is not None


def test_invoke_with_rotation():
    """Test invoke method uses rotation logic."""
    manager = APIKeyManager("test", auto_discover=False)
    manager.add_key("key1")
    manager.add_key("key2")

    provider = MockProvider(manager)

    # Mock client with invoke method
    mock_client = Mock()
    mock_client.invoke = Mock(side_effect=[Exception("rate_limit"), "invoke_result"])

    # Override _create_client to return our mock
    provider._create_client = Mock(return_value=mock_client)  # type: ignore[assignment]

    result = provider.invoke("test_input")
    assert result == "invoke_result"

    # Should have created client twice (once for failure, once for success)
    assert provider._create_client.call_count == 2  # type: ignore[attr-defined]
    # First call with key1, second with key2
    provider._create_client.assert_any_call("key1")  # type: ignore[attr-defined]
    provider._create_client.assert_any_call("key2")  # type: ignore[attr-defined]


def test_stream_with_rotation():
    """Test stream method uses rotation logic."""
    manager = APIKeyManager("test", auto_discover=False)
    manager.add_key("key1")

    provider = MockProvider(manager)

    # Mock client with stream method
    mock_client = Mock()
    mock_client.stream = Mock(return_value="stream_result")

    provider._create_client = Mock(return_value=mock_client)  # type: ignore[assignment]

    result = provider.stream("test_input")
    assert result == "stream_result"

    provider._create_client.assert_called_once_with("key1")  # type: ignore[attr-defined]
    mock_client.stream.assert_called_once_with("test_input")


def test_batch_with_rotation():
    """Test batch method uses rotation logic."""
    manager = APIKeyManager("test", auto_discover=False)
    manager.add_key("key1")

    provider = MockProvider(manager)

    # Mock client with batch method
    mock_client = Mock()
    mock_client.batch = Mock(return_value=["result1", "result2"])

    provider._create_client = Mock(return_value=mock_client)  # type: ignore[assignment]

    result = provider.batch(["input1", "input2"])
    assert result == ["result1", "result2"]

    provider._create_client.assert_called_once_with("key1")  # type: ignore[attr-defined]
    mock_client.batch.assert_called_once_with(["input1", "input2"])


def test_concurrent_key_rotation():
    """Test thread safety with concurrent requests."""
    manager = APIKeyManager("test", auto_discover=False)
    manager.add_key("key1")
    manager.add_key("key2")
    manager.add_key("key3")

    provider = MockProvider(manager)

    results = []
    errors = []
    results_lock = threading.Lock()

    def make_request(request_id: int) -> None:
        """Make a request that may fail once."""
        # Use a mock that fails on first call for some threads
        if request_id % 3 == 0:
            api_call = Mock(side_effect=[Exception("rate_limit"), f"success_{request_id}"])
        else:
            api_call = Mock(return_value=f"success_{request_id}")

        try:
            result = provider.execute_with_rotation(api_call)
            with results_lock:
                results.append(result)
        except Exception as e:
            with results_lock:
                errors.append(str(e))

    # Launch multiple threads
    threads = []
    for i in range(30):  # Reduced to avoid exhausting all keys
        t = threading.Thread(target=make_request, args=(i,))
        threads.append(t)
        t.start()
        # Small stagger to avoid all threads hitting at once
        if i < 10:
            time.sleep(0.05)

    # Wait for all threads
    for t in threads:
        t.join()

    # All requests should eventually succeed (10 will retry once)
    assert len(results) == 30
    assert len(errors) == 0

    # Verify metrics consistency
    metrics = provider.get_metrics_snapshot()
    # 30 successful requests + 10 failed attempts that were retried
    assert metrics.total_requests == 40
    assert metrics.successful_requests == 30
    assert metrics.failed_requests == 10
    assert metrics.rate_limit_hits == 10


def test_metrics_thread_safety():
    """Test that metrics updates are thread-safe."""
    manager = APIKeyManager("test", auto_discover=False)
    manager.add_key("key1")

    provider = MockProvider(manager)

    def update_metrics() -> None:
        """Update metrics many times."""
        for _ in range(100):
            provider._update_metrics()  # type: ignore[attr-defined]
            provider._update_metrics(ErrorType.RATE_LIMIT)  # type: ignore[attr-defined]

    threads = [threading.Thread(target=update_metrics) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    metrics = provider.get_metrics_snapshot()
    # 10 threads * 200 updates each = 2000 total
    assert metrics.total_requests == 2000
    assert metrics.successful_requests == 1000
    assert metrics.rate_limit_hits == 1000


def test_concurrent_metadata_updates():
    """Test thread-safe metadata updates with concurrent access."""
    manager = APIKeyManager("test", auto_discover=False)
    manager.add_key("key1")
    manager.add_key("key2")

    provider = MockProvider(manager)

    def update_metadata(key: str, success: bool) -> None:
        """Update metadata for a key."""
        for _ in range(50):
            if success:
                provider._record_success(key)  # type: ignore[attr-defined]
            else:
                provider._record_failure(key, ErrorType.RATE_LIMIT)  # type: ignore[attr-defined]
            time.sleep(0.001)  # Small delay to increase chance of race conditions

    threads = []
    # Create threads for concurrent updates
    for key in ["key1", "key2"]:
        for success in [True, False]:
            t = threading.Thread(target=update_metadata, args=(key, success))
            threads.append(t)
            t.start()

    # Wait for all threads
    for t in threads:
        t.join()

    # Check metadata consistency
    states = manager.get_key_states()

    # Each key should have 100 total requests (50 success + 50 failure)
    for key in ["key1", "key2"]:
        metadata = states[key].metadata
        assert metadata["request_count"] == 100
        assert metadata["success_count"] == 50
        assert metadata["failure_count"] == 50
        assert metadata["rate_limit_count"] == 50


def test_concurrent_key_selection():
    """Test that key selection is thread-safe under concurrent access."""
    manager = APIKeyManager("test", auto_discover=False)
    for i in range(10):
        manager.add_key(f"key{i}")

    provider = MockProvider(manager)

    selected_keys = []
    lock = threading.Lock()

    def select_and_use_key() -> None:
        """Select a key and use it."""
        for _ in range(10):
            api_call = Mock(return_value="success")
            provider.execute_with_rotation(api_call)

            with lock:
                selected_keys.append(provider._current_key)  # type: ignore[attr-defined]

    threads = [threading.Thread(target=select_and_use_key) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Should have made 100 total selections
    assert len(selected_keys) == 100

    # All selected keys should be valid
    for key in selected_keys:
        assert key in [f"key{i}" for i in range(10)]

    # Metrics should be consistent
    metrics = provider.get_metrics_snapshot()
    assert metrics.total_requests == 100
    assert metrics.successful_requests == 100


def test_race_condition_on_rotation():
    """Test that key rotation doesn't cause race conditions."""
    manager = APIKeyManager("test", auto_discover=False)
    # Add more keys to avoid exhaustion
    for i in range(5):
        manager.add_key(f"key{i}")

    provider = MockProvider(manager)

    successful_results = []
    lock = threading.Lock()

    def trigger_rotation(thread_id: int) -> None:
        """Trigger key rotation through failures."""
        # Each thread gets a unique mock that fails once then succeeds
        api_call = Mock(side_effect=[Exception("rate_limit"), f"success_{thread_id}"])

        try:
            result = provider.execute_with_rotation(api_call)
            with lock:
                successful_results.append(result)
        except Exception:
            pass  # Should not happen with 5 keys and only 10 threads

    threads = []
    for i in range(10):  # Reduced number of threads
        t = threading.Thread(target=trigger_rotation, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # All 10 threads should succeed
    assert len(successful_results) == 10

    # Check that rotations occurred
    metrics = provider.get_metrics_snapshot()
    # At least 5 unique keys should have been used (rotations)
    # May be more due to concurrent access and rate-limited key reselection
    assert metrics.key_rotations >= 5
    assert metrics.key_rotations <= 20  # Should not exceed total requests
    assert metrics.total_requests == 20  # 10 failures + 10 successes
    assert metrics.successful_requests == 10
    assert metrics.failed_requests == 10
