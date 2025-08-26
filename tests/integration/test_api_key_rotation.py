"""End-to-end integration tests for API key rotation feature."""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, List
from unittest.mock import Mock, patch

import pytest

from blarify.agents.api_key_manager import APIKeyManager
from blarify.agents.llm_provider import LLMProvider
from blarify.agents.rotating_provider import (
    RotatingKeyChatAnthropic,
    RotatingKeyChatGoogle,
    RotatingKeyChatOpenAI,
    ErrorType,
)
from blarify.agents.utils import discover_keys_for_provider

from .fixtures import multi_provider_env, single_provider_env  # noqa: F401  # type: ignore


class TestKeyDiscoveryAndInitialization:
    """Test key discovery and manager initialization."""

    def test_key_discovery_all_providers(self) -> None:  # noqa: F811
        """Test that all keys are discovered for each provider."""
        # OpenAI
        openai_keys = discover_keys_for_provider("openai")
        assert len(openai_keys) == 3
        assert all(k.startswith("sk-") for k in openai_keys)

        # Anthropic
        anthropic_keys = discover_keys_for_provider("anthropic")
        assert len(anthropic_keys) == 2
        assert all(k.startswith("sk-ant-") for k in anthropic_keys)

        # Google
        google_keys = discover_keys_for_provider("google")
        assert len(google_keys) == 2
        assert all("google" in k for k in google_keys)

    def test_api_key_manager_initialization(self) -> None:
        """Test APIKeyManager initializes with discovered keys."""
        # OpenAI manager
        openai_manager = APIKeyManager("openai", auto_discover=True)
        assert len(openai_manager.keys) == 3
        assert openai_manager.get_available_count() == 3

        # Anthropic manager
        anthropic_manager = APIKeyManager("anthropic", auto_discover=True)
        assert len(anthropic_manager.keys) == 2
        assert anthropic_manager.get_available_count() == 2

    def test_llm_provider_detects_rotation(self) -> None:
        """Test LLMProvider correctly detects when to use rotation."""
        # Create an LLMProvider instance
        provider = LLMProvider()

        # Test OpenAI models - should use rotation with multiple keys
        openai_keys = discover_keys_for_provider("openai")
        assert len(openai_keys) == 3  # Verify we have multiple keys

        # Get model and check if it has rotation
        model = provider._get_or_create_model("gpt-4.1")  # type: ignore[attr-defined]
        assert hasattr(model, "key_manager")  # Should have key_manager if using rotation

        # Test Anthropic models
        anthropic_keys = discover_keys_for_provider("anthropic")
        assert len(anthropic_keys) == 2  # Verify we have multiple keys

        model = provider._get_or_create_model("claude-3-5-haiku-latest")  # type: ignore[attr-defined]
        assert hasattr(model, "key_manager")  # Should have key_manager if using rotation

        # Test Google models
        google_keys = discover_keys_for_provider("google")
        assert len(google_keys) == 2  # Verify we have multiple keys

        model = provider._get_or_create_model("gemini-2.5-flash-preview-05-20")  # type: ignore[attr-defined]
        assert hasattr(model, "key_manager")  # Should have key_manager if using rotation


class TestRateLimitRotation:
    """Test rate limit rotation scenarios."""

    def test_openai_rate_limit_rotation(self) -> None:
        """Test OpenAI rotates keys on rate limit."""
        manager = APIKeyManager("openai", auto_discover=True)
        wrapper = RotatingKeyChatOpenAI(key_manager=manager, model="gpt-4")

        call_count = 0
        keys_used: List[str] = []

        def mock_api_call() -> str:
            nonlocal call_count
            call_count += 1

            # Track the current key being used
            current_key = getattr(wrapper, "_current_key", None)
            if current_key:
                keys_used.append(current_key)

            # First two calls hit rate limit with a simple Exception
            if call_count <= 2:
                # Create mock error that will be recognized as rate limit
                error = Exception("429: Rate limit reached for gpt-4 model. Please try again in 20s.")
                error.response = Mock(  # type: ignore[attr-defined]
                    headers={
                        "X-RateLimit-Remaining-Requests": "0",
                        "X-RateLimit-Reset-Requests": "20",
                    }
                )
                raise error

            return "Success"

        # Execute with rotation
        result = wrapper.execute_with_rotation(mock_api_call, max_retries=3)
        assert result == "Success"

        # Should have made 3 attempts (2 failures + 1 success)
        assert call_count == 3
        assert len(keys_used) == 3

        # With the new logic, the first key will be used for the first attempt,
        # then rotated after rate limit error. Same for the second key.
        # The third key should succeed.
        # We expect at least 2 different keys to be used
        unique_keys = set(keys_used)
        assert len(unique_keys) >= 2, f"Expected at least 2 unique keys, got {len(unique_keys)}: {unique_keys}"

        # At least 2 keys should be marked as rate limited
        key_states = manager.get_key_states()
        rate_limited_count = sum(1 for state in key_states.values() if state.state.value == "rate_limited")
        assert rate_limited_count >= 2

    def test_anthropic_spike_detection(self) -> None:
        """Test Anthropic detects and handles spike-triggered rate limits."""
        manager = APIKeyManager("anthropic", auto_discover=True)
        wrapper = RotatingKeyChatAnthropic(key_manager=manager, model_name="claude-3-opus-20240229")

        # Mock error with remaining quota (spike scenario)
        error = Exception("429: rate_limit_error")
        error.response = Mock()  # type: ignore[attr-defined]
        error.response.headers = {  # type: ignore[attr-defined]
            "anthropic-ratelimit-requests-remaining": "100",
            "retry-after": "5",
        }

        # Extract headers from error
        headers = wrapper.extract_headers_from_error(error)

        # Should detect as spike (has remaining requests but still rate limited)
        is_spike_triggered = wrapper._is_spike_triggered(headers)  # type: ignore
        assert is_spike_triggered is True

        # Should still mark as rate limited
        error_type, retry_after = wrapper.analyze_error(error)
        assert error_type == ErrorType.RATE_LIMIT
        assert retry_after == 5

    def test_google_exponential_backoff(self) -> None:
        """Test Google uses exponential backoff correctly."""
        manager = APIKeyManager("google", auto_discover=True)
        wrapper = RotatingKeyChatGoogle(key_manager=manager, model="gemini-1.5-flash")

        # Set a specific key as current
        first_key = list(manager.keys.keys())[0]
        wrapper._current_key = first_key  # type: ignore

        # First call - rate limit error
        error1 = Exception("429: RESOURCE_EXHAUSTED")
        error_type1, retry_after1 = wrapper.analyze_error(error1)

        assert error_type1 == ErrorType.RATE_LIMIT
        assert retry_after1 == 1  # 2^0 = 1 second

        # Check backoff was incremented
        assert wrapper._backoff_multipliers[first_key] == 1  # type: ignore

        # Second call - rate limit error again
        error2 = Exception("429: RESOURCE_EXHAUSTED")
        error_type2, retry_after2 = wrapper.analyze_error(error2)

        assert error_type2 == ErrorType.RATE_LIMIT
        assert retry_after2 == 2

        # Check backoff was incremented again
        assert wrapper._backoff_multipliers[first_key] == 2  # type: ignore

        # Third call - rate limit error again
        error3 = Exception("429: RESOURCE_EXHAUSTED")
        error_type3, retry_after3 = wrapper.analyze_error(error3)

        assert error_type3 == ErrorType.RATE_LIMIT
        assert retry_after3 == 4

        # Verify exponential backoff is working
        assert wrapper._backoff_multipliers[first_key] == 3  # type: ignore


class TestProviderFallback:
    """Test provider fallback with rotation."""

    def test_models_with_rotation(self) -> None:
        """Test models use rotation when multiple keys are available."""
        provider_instance = LLMProvider()
        models = ["gpt-4.1", "claude-3-5-haiku-latest"]

        # Both models should use rotation if multiple keys available
        for model in models:
            provider_name = provider_instance._get_provider_from_model(model)  # type: ignore[attr-defined]
            if provider_name:
                keys = discover_keys_for_provider(provider_name)
            else:
                keys = []

            if len(keys) > 1:
                # Should be using rotation
                model_instance = provider_instance._get_or_create_model(model)  # type: ignore[attr-defined]
                assert hasattr(model_instance, "key_manager")

    def test_all_keys_exhausted_fallback(self) -> None:
        """Test provider fallback when all keys for primary are exhausted."""
        manager_openai = APIKeyManager("openai", auto_discover=True)
        manager_anthropic = APIKeyManager("anthropic", auto_discover=True)

        # Mark all OpenAI keys as invalid (permanently unusable)
        for key in manager_openai.keys:
            manager_openai.mark_invalid(key)

        # Create wrapper that should fail
        wrapper_openai = RotatingKeyChatOpenAI(key_manager=manager_openai, model="gpt-4")

        # Should raise when all keys are invalid
        with pytest.raises(RuntimeError, match="No available API keys|No usable API keys"):
            wrapper_openai.execute_with_rotation(lambda: Mock())

        # Anthropic should still work
        wrapper_anthropic = RotatingKeyChatAnthropic(key_manager=manager_anthropic, model_name="claude-3-opus-20240229")
        result = wrapper_anthropic.execute_with_rotation(lambda: "success")
        assert result == "success"


class TestThreadSafety:
    """Test thread safety and concurrent operations."""

    def test_concurrent_rotation_thread_safety(self) -> None:
        """Test concurrent requests with rotation are thread-safe."""
        manager = APIKeyManager("openai", auto_discover=True)
        wrapper = RotatingKeyChatOpenAI(key_manager=manager, model="gpt-4")

        results: List[str] = []
        errors: List[str] = []
        keys_used: List[str] = []
        lock = threading.Lock()

        def make_request(request_id: int) -> None:
            try:
                # Track which key is used
                def mock_api_call() -> str:
                    with lock:
                        current_key = getattr(wrapper, "_current_key", None)
                        if current_key:
                            keys_used.append(current_key)
                    # Simulate some failures
                    if request_id % 5 == 0:
                        error = Mock()
                        error.__str__ = lambda: "429: Rate limit"
                        raise error
                    return f"response_{request_id}"

                result = wrapper.execute_with_rotation(mock_api_call, max_retries=2)
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        # Launch concurrent requests
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(50)]
            for future in as_completed(futures):
                future.result()  # Wait for completion

        # Verify results
        assert len(results) + len(errors) == 50
        assert len(keys_used) >= 50  # Some retries will use more

        # Check metrics are consistent
        metrics = wrapper.get_metrics_snapshot()
        assert metrics.total_requests >= 50

    def test_shared_key_manager_coordination(self) -> None:
        """Test multiple components sharing the same key manager."""
        shared_manager = APIKeyManager("openai", auto_discover=True)

        wrapper1 = RotatingKeyChatOpenAI(key_manager=shared_manager, model="gpt-4")
        wrapper2 = RotatingKeyChatOpenAI(key_manager=shared_manager, model="gpt-4")

        # Both should see same key states
        test_key = list(shared_manager.keys.keys())[0]

        # Mark key as rate limited in wrapper1
        shared_manager.mark_rate_limited(test_key, retry_after=10)

        # Wrapper2 should see the same state
        assert shared_manager.keys[test_key].state.value == "rate_limited"

        # Both should skip the rate-limited key
        available_key1 = wrapper1.key_manager.get_next_available_key()
        available_key2 = wrapper2.key_manager.get_next_available_key()

        assert available_key1 != test_key
        assert available_key2 != test_key


class TestEdgeCases:
    """Test edge cases and error recovery."""

    def test_invalid_keys_removal(self) -> None:
        """Test that invalid keys are properly marked and excluded."""
        manager = APIKeyManager("openai", auto_discover=True)

        # Mark first key as invalid (auth error)
        first_key = list(manager.keys.keys())[0]
        manager.mark_invalid(first_key)

        # Should not return invalid key
        for _ in range(10):
            key = manager.get_next_available_key()
            assert key != first_key

    def test_cooldown_expiration(self) -> None:
        """Test that rate-limited keys become available after cooldown."""
        manager = APIKeyManager("openai", auto_discover=True)

        # Mark key as rate limited with short cooldown
        test_key = list(manager.keys.keys())[0]
        manager.mark_rate_limited(test_key, retry_after=1)

        # Should not be available immediately
        assert manager.keys[test_key].state.value == "rate_limited"
        available_keys = []
        for _ in range(len(manager.keys) - 1):
            key = manager.get_next_available_key()
            if key:
                available_keys.append(key)
        assert test_key not in available_keys

        # Wait for cooldown
        time.sleep(1.5)

        # Should be available again
        manager.reset_expired_cooldowns()
        assert manager.keys[test_key].state.value == "available"

    def test_all_providers_no_keys(self) -> None:
        """Test graceful failure when no keys are available."""
        with patch.dict(os.environ, {}, clear=True):
            # Should not be able to create models without keys
            with pytest.raises(Exception):
                provider = LLMProvider()
                provider._get_or_create_model("gpt-4.1")  # type: ignore[attr-defined]

    def test_backwards_compatibility(self) -> None:
        """Test that single-key setup still works without rotation."""
        provider = LLMProvider()

        # With single key, should not use rotation
        openai_keys = discover_keys_for_provider("openai")
        assert len(openai_keys) == 1  # Verify single key

        # Should create standard model without key_manager
        model_instance = provider._get_or_create_model("gpt-4.1")  # type: ignore[attr-defined]
        assert not hasattr(model_instance, "key_manager")


class TestInvokeWrapping:
    """Test that invoke methods are properly wrapped for rotation."""

    def test_openai_invoke_wrapped(self) -> None:
        """Test that ChatOpenAI.invoke is wrapped when using rotation."""
        provider = LLMProvider()

        # Get model with rotation (multiple keys available)
        model = provider._get_or_create_model("gpt-4.1")  # type: ignore[attr-defined]

        # Should be a RotatingKeyChatOpenAI instance
        from blarify.agents.rotating_provider import RotatingKeyChatOpenAI

        assert isinstance(model, RotatingKeyChatOpenAI)

        # Should have key_manager
        assert hasattr(model, "key_manager")
        assert model.key_manager is not None

        # Test that invoke is wrapped - verify it goes through rotation logic
        # Mock the execute_with_rotation method which is called by invoke
        with patch.object(model, "execute_with_rotation") as mock_execute:
            mock_execute.return_value = Mock(content="test response")

            # Call through LLMProvider's _invoke_agent
            result = provider._invoke_agent(  # type: ignore[attr-defined]
                system_prompt="Test system", input_prompt="Test prompt", input_dict={}, ai_model="gpt-4.1"
            )

            # Verify the rotation logic was called
            assert mock_execute.called
            assert result is not None

    def test_anthropic_invoke_wrapped(self) -> None:
        """Test that ChatAnthropic.invoke is wrapped when using rotation."""
        provider = LLMProvider()

        # Get model with rotation (multiple keys available)
        model = provider._get_or_create_model("claude-3-5-haiku-latest")  # type: ignore[attr-defined]

        # Should be a RotatingKeyChatAnthropic instance
        from blarify.agents.rotating_provider import RotatingKeyChatAnthropic

        assert isinstance(model, RotatingKeyChatAnthropic)

        # Should have key_manager
        assert hasattr(model, "key_manager")
        assert model.key_manager is not None

        # Test that invoke is wrapped
        with patch.object(model, "execute_with_rotation") as mock_execute:
            mock_execute.return_value = Mock(content="test response")

            # Call through LLMProvider's _invoke_agent
            result = provider._invoke_agent(  # type: ignore[attr-defined]
                system_prompt="Test system",
                input_prompt="Test prompt",
                input_dict={},
                ai_model="claude-3-5-haiku-latest",
            )

            # Verify the rotation logic was called
            assert mock_execute.called
            assert result is not None

    def test_google_invoke_wrapped(self) -> None:
        """Test that ChatGoogleGenerativeAI.invoke is wrapped when using rotation."""
        provider = LLMProvider()

        # Get model with rotation (multiple keys available)
        model = provider._get_or_create_model("gemini-2.5-flash-preview-05-20")  # type: ignore[attr-defined]

        # Should be a RotatingKeyChatGoogle instance
        from blarify.agents.rotating_provider import RotatingKeyChatGoogle

        assert isinstance(model, RotatingKeyChatGoogle)

        # Should have key_manager
        assert hasattr(model, "key_manager")
        assert model.key_manager is not None

        # Test that invoke is wrapped
        with patch.object(model, "execute_with_rotation") as mock_execute:
            mock_execute.return_value = Mock(content="test response")

            # Call through LLMProvider's _invoke_agent
            result = provider._invoke_agent(  # type: ignore[attr-defined]
                system_prompt="Test system",
                input_prompt="Test prompt",
                input_dict={},
                ai_model="gemini-2.5-flash-preview-05-20",
            )

            # Verify the rotation logic was called
            assert mock_execute.called
            assert result is not None

    def test_metrics_persist_across_invokes(self) -> None:
        """Test that metrics persist across multiple invokes through LLMProvider."""
        provider = LLMProvider()

        # Get the same model twice
        model1 = provider._get_or_create_model("gpt-4.1")  # type: ignore[attr-defined]
        model2 = provider._get_or_create_model("gpt-4.1")  # type: ignore[attr-defined]

        # Should be the exact same instance (cached)
        assert model1 is model2

        # If using rotation, verify metrics persist
        if hasattr(model1, "metrics"):
            initial_metrics = model1.get_metrics_snapshot()  # type: ignore[attr-defined]
            initial_requests = initial_metrics.total_requests

            # Test that the metrics are updated when we actually call through rotation
            # We'll mock the underlying _create_client to avoid actual API calls
            def mock_call(*args: Any, **kwargs: Any) -> str:
                return "success"

            # Call execute_with_rotation directly to update metrics
            model1.execute_with_rotation(mock_call)  # type: ignore[attr-defined]
            model1.execute_with_rotation(mock_call)  # type: ignore[attr-defined]

            # Get metrics after calls
            final_metrics = model1.get_metrics_snapshot()  # type: ignore[attr-defined]

            # Metrics should have incremented
            assert final_metrics.total_requests == initial_requests + 2
            assert final_metrics.successful_requests == initial_metrics.successful_requests + 2

    def test_single_key_uses_standard_provider(self) -> None:
        """Test that single key configuration uses standard provider without wrapping."""
        provider = LLMProvider()

        # Get model with single key (no rotation)
        model = provider._get_or_create_model("gpt-4.1")  # type: ignore[attr-defined]

        # Should NOT be a rotating provider
        from blarify.agents.rotating_provider import RotatingKeyChatOpenAI

        assert not isinstance(model, RotatingKeyChatOpenAI)

        # Should not have key_manager
        assert not hasattr(model, "key_manager")

        # Should be a standard ChatOpenAI
        from langchain_openai import ChatOpenAI

        assert isinstance(model, ChatOpenAI)


class TestPerformanceAndMetrics:
    """Test performance characteristics and metrics collection."""

    def test_rotation_performance(self) -> None:
        """Test that rotation adds minimal overhead."""
        manager = APIKeyManager("openai", auto_discover=True)

        # Measure time for key selection
        start = time.time()
        for _ in range(1000):
            _ = manager.get_next_available_key()
        duration = time.time() - start

        # Should be very fast (< 10ms for 1000 selections)
        assert duration < 0.01

        # Per-selection should be < 0.01ms
        per_selection = duration / 1000
        assert per_selection < 0.00001

    def test_metrics_accuracy(self) -> None:
        """Test that metrics are accurately tracked."""
        manager = APIKeyManager("openai", auto_discover=True)
        wrapper = RotatingKeyChatOpenAI(key_manager=manager, model="gpt-4")

        success_count = 0
        failure_count = 0
        rate_limit_count = 0

        for i in range(20):
            try:

                def mock_call() -> str:
                    if i % 3 == 0:
                        # Create an error that will be recognized as rate limit
                        error = Exception("429: Rate limit reached")
                        # Add response attribute so it can be analyzed
                        error.response = Mock(headers={})  # type: ignore[attr-defined]
                        raise error
                    return "success"

                result = wrapper.execute_with_rotation(mock_call, max_retries=1)
                if result == "success":
                    success_count += 1
            except Exception as e:
                failure_count += 1
                # Count rate limit errors
                if "429" in str(e) or "rate limit" in str(e).lower():
                    rate_limit_count += 1

        # Check metrics
        metrics = wrapper.get_metrics_snapshot()

        # Metrics should track attempts
        assert metrics.total_requests >= success_count + failure_count
        assert metrics.successful_requests == success_count
        # Rate limit hits should be tracked
        assert metrics.rate_limit_hits >= rate_limit_count

    def test_rotation_with_metrics(self) -> None:
        """Test that rotation maintains metrics across calls."""
        provider = LLMProvider()

        # Get the same model multiple times - should return cached instance
        model1 = provider._get_or_create_model("gpt-4.1")  # type: ignore[attr-defined]
        model2 = provider._get_or_create_model("gpt-4.1")  # type: ignore[attr-defined]

        # Should be the same instance (cached)
        assert model1 is model2

        # If using rotation, check metrics are maintained
        if hasattr(model1, "key_manager"):
            # Make a mock call to increment metrics
            def mock_call() -> str:
                return "success"

            # First call
            model1.execute_with_rotation(mock_call)  # type: ignore
            metrics1 = model1.get_metrics_snapshot()  # type: ignore

            # Second call on "different" model (actually same cached instance)
            model2.execute_with_rotation(mock_call)  # type: ignore
            metrics2 = model2.get_metrics_snapshot()  # type: ignore

            # Metrics should accumulate
            assert metrics2.total_requests == metrics1.total_requests + 1


class TestKeyReuse:
    """Test cases for key reuse behavior."""

    def test_key_reused_on_success(self) -> None:
        """Test that the same key is reused for successful requests."""
        manager = APIKeyManager("openai", auto_discover=True)
        wrapper = RotatingKeyChatOpenAI(key_manager=manager, model="gpt-4")

        keys_used: List[str] = []

        def mock_api_call() -> str:
            # Track the current key being used
            current_key = getattr(wrapper, "_current_key", None)
            if current_key:
                keys_used.append(current_key)
            return "Success"

        # Make multiple successful calls
        for _ in range(3):
            result = wrapper.execute_with_rotation(mock_api_call)
            assert result == "Success"

        # All calls should use the same key
        assert len(keys_used) == 3
        assert len(set(keys_used)) == 1, f"Expected same key for all calls, got: {keys_used}"

    def test_key_rotated_on_rate_limit(self) -> None:
        """Test that key is rotated on rate limit errors."""
        manager = APIKeyManager("openai", auto_discover=True)
        wrapper = RotatingKeyChatOpenAI(key_manager=manager, model="gpt-4")

        keys_used: List[str] = []
        call_count = 0

        def mock_api_call() -> str:
            nonlocal call_count
            call_count += 1

            # Track the current key being used
            current_key = getattr(wrapper, "_current_key", None)
            if current_key:
                keys_used.append(current_key)

            # First call succeeds, second hits rate limit, third succeeds with new key
            if call_count == 2:
                error = Exception("429: Rate limit")
                error.response = Mock(headers={})  # type: ignore[attr-defined]
                raise error

            return "Success"

        # First successful call
        result1 = wrapper.execute_with_rotation(mock_api_call)
        assert result1 == "Success"

        # Second call hits rate limit and rotates
        result2 = wrapper.execute_with_rotation(mock_api_call, max_retries=2)
        assert result2 == "Success"

        # Should have used 3 keys total (1 for first success, 1 that hit rate limit, 1 for final success)
        assert len(keys_used) == 3
        # First key should be reused for second attempt, then rotate after rate limit
        assert keys_used[0] == keys_used[1], "Same key should be used for first two attempts"
        assert keys_used[1] != keys_used[2], "Different key should be used after rate limit"

    def test_key_rotated_on_auth_error(self) -> None:
        """Test that key is rotated on authentication errors."""
        manager = APIKeyManager("anthropic", auto_discover=True)
        wrapper = RotatingKeyChatAnthropic(key_manager=manager, model_name="claude-3-opus-20240229")

        keys_used: List[str] = []
        call_count = 0

        def mock_api_call() -> str:
            nonlocal call_count
            call_count += 1

            # Track the current key being used
            current_key = getattr(wrapper, "_current_key", None)
            if current_key:
                keys_used.append(current_key)

            # First call hits auth error
            if call_count == 1:
                raise Exception("401: Authentication required")

            return "Success"

        # Execute with rotation - should recover from auth error
        result = wrapper.execute_with_rotation(mock_api_call, max_retries=2)
        assert result == "Success"

        # Should have used 2 different keys (one failed auth, one succeeded)
        assert len(keys_used) == 2
        assert keys_used[0] != keys_used[1], "Different key should be used after auth error"

    def test_key_reused_on_retryable_error(self) -> None:
        """Test that the same key is reused for retryable errors."""
        manager = APIKeyManager("google", auto_discover=True)
        wrapper = RotatingKeyChatGoogle(key_manager=manager, model="gemini-1.5-pro")

        keys_used: List[str] = []
        call_count = 0

        def mock_api_call() -> str:
            nonlocal call_count
            call_count += 1

            # Track the current key being used
            current_key = getattr(wrapper, "_current_key", None)
            if current_key:
                keys_used.append(current_key)

            # First two calls hit retryable errors (e.g., network issues)
            if call_count <= 2:
                raise Exception("Network error: Connection reset")

            return "Success"

        # Execute with rotation
        result = wrapper.execute_with_rotation(mock_api_call, max_retries=3)
        assert result == "Success"

        # All calls should use the same key (retryable errors don't rotate)
        assert len(keys_used) == 3
        assert len(set(keys_used)) == 1, f"Expected same key for retryable errors, got: {keys_used}"
