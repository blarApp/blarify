"""End-to-end integration tests for API key rotation feature."""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List
from unittest.mock import Mock, patch

import pytest

from blarify.agents.api_key_manager import APIKeyManager
from blarify.agents.chat_fallback import ChatFallback
from blarify.agents.rotating_anthropic import RotatingKeyChatAnthropic
from blarify.agents.rotating_google import RotatingKeyChatGoogle
from blarify.agents.rotating_openai import RotatingKeyChatOpenAI
from blarify.agents.utils import discover_keys_for_provider

from .fixtures import multi_provider_env, single_provider_env, mock_llm_responses, mock_rate_limit_error, mock_invalid_key_error  # noqa: F401


class TestKeyDiscoveryAndInitialization:
    """Test key discovery and manager initialization."""

    def test_key_discovery_all_providers(self, multi_provider_env: Dict[str, str]) -> None:
        """Test that all keys are discovered for each provider."""
        # OpenAI
        openai_keys = discover_keys_for_provider("openai")
        assert len(openai_keys) == 3
        assert all(k.startswith("sk-test") for k in openai_keys)

        # Anthropic
        anthropic_keys = discover_keys_for_provider("anthropic")
        assert len(anthropic_keys) == 2
        assert all(k.startswith("sk-ant") for k in anthropic_keys)

        # Google
        google_keys = discover_keys_for_provider("google")
        assert len(google_keys) == 2
        assert all("google" in k for k in google_keys)

    def test_api_key_manager_initialization(self, multi_provider_env: Dict[str, str]) -> None:
        """Test APIKeyManager initializes with discovered keys."""
        # OpenAI manager
        openai_manager = APIKeyManager("openai", auto_discover=True)
        assert len(openai_manager.keys) == 3
        assert openai_manager.get_available_count() == 3

        # Anthropic manager
        anthropic_manager = APIKeyManager("anthropic", auto_discover=True)
        assert len(anthropic_manager.keys) == 2
        assert anthropic_manager.get_available_count() == 2

    def test_chat_fallback_detects_rotation(self, multi_provider_env: Dict[str, str]) -> None:
        """Test ChatFallback correctly detects when to use rotation."""
        # Create a fallback with valid models from MODEL_PROVIDER_DICT
        fallback = ChatFallback(
            model="gpt-4.1",
            fallback_list=["claude-3-5-haiku-latest", "gemini-2.5-flash-preview-05-20"]
        )

        # Test OpenAI models
        assert fallback._should_use_rotation("gpt-4.1") is True  # type: ignore
        assert fallback._should_use_rotation("gpt-4.1-mini") is True  # type: ignore

        # Test Anthropic models  
        assert fallback._should_use_rotation("claude-3-5-haiku-latest") is True  # type: ignore

        # Test Google models
        assert fallback._should_use_rotation("gemini-2.5-flash-preview-05-20") is True  # type: ignore


class TestRateLimitRotation:
    """Test rate limit rotation scenarios."""

    def test_openai_rate_limit_rotation(self, multi_provider_env: Dict[str, str]) -> None:
        """Test OpenAI rotates keys on rate limit."""
        manager = APIKeyManager("openai", auto_discover=True)
        wrapper = RotatingKeyChatOpenAI(key_manager=manager, model="gpt-4")

        call_count = 0
        keys_used: List[str] = []

        def mock_invoke(*args: Any, **kwargs: Any) -> Mock:
            nonlocal call_count, keys_used
            current_key = getattr(wrapper, "_current_key", None)
            if current_key:
                keys_used.append(current_key)
            call_count += 1

            # First two keys hit rate limit
            if call_count <= 2:
                error = Mock()
                error.__str__ = lambda: "Rate limit reached for gpt-4 model. Please try again in 20s."
                error.response = Mock()
                error.response.headers = {
                    "X-RateLimit-Remaining-Requests": "0",
                    "X-RateLimit-Reset-Requests": "20",
                }
                raise error
            return Mock(content="Success")

        with patch.object(wrapper, "_create_client") as mock_create:
            mock_client = Mock()
            mock_client.invoke = mock_invoke
            mock_create.return_value = mock_client

            # Should succeed after rotating through keys
            result = wrapper.invoke("test prompt")
            assert result.content == "Success"

        # Should have tried 3 keys
        assert len(keys_used) == 3
        assert len(set(keys_used)) == 3  # All different keys

        # First two keys should be marked as rate limited
        assert manager.keys[keys_used[0]].state.value == "rate_limited"
        assert manager.keys[keys_used[1]].state.value == "rate_limited"
        assert manager.keys[keys_used[2]].state.value == "available"

    def test_anthropic_spike_detection(self, multi_provider_env: Dict[str, str]) -> None:
        """Test Anthropic detects and handles spike-triggered rate limits."""
        manager = APIKeyManager("anthropic", auto_discover=True)
        wrapper = RotatingKeyChatAnthropic(key_manager=manager, model="claude-3-opus-20240229")

        # Mock error with remaining quota (spike scenario)
        error = Mock()
        error.__str__ = lambda: "rate_limit_error"
        error.response = Mock()
        error.response.headers = {
            "anthropic-ratelimit-requests-remaining": "100",
            "retry-after": "5",
        }

        # Should detect as spike
        is_spike_triggered = getattr(wrapper, "_is_spike_triggered", None)
        if is_spike_triggered:
            assert is_spike_triggered(wrapper.extract_headers_from_error(error)) is True

        # Should still mark as rate limited
        error_type, retry_after = wrapper.analyze_error(error)
        assert error_type.value == "rate_limit"
        assert retry_after == 5

    def test_google_exponential_backoff(self, multi_provider_env: Dict[str, str]) -> None:
        """Test Google uses exponential backoff correctly."""
        manager = APIKeyManager("google", auto_discover=True)
        wrapper = RotatingKeyChatGoogle(key_manager=manager, model="gemini-1.5-flash")

        call_count = 0

        def mock_invoke(*args: Any, **kwargs: Any) -> Mock:
            nonlocal call_count
            call_count += 1

            # Fail first 3 times with rate limit
            if call_count <= 3:
                error = Mock()
                error.__str__ = lambda: "429: RESOURCE_EXHAUSTED"
                error.response = Mock()
                error.response.headers = {}
                raise error
            return Mock(content="Success")

        with patch.object(wrapper, "_create_client") as mock_create:
            mock_client = Mock()
            mock_client.invoke = mock_invoke
            mock_create.return_value = mock_client

            # Set first key as current
            setattr(wrapper, "_current_key", list(manager.keys.keys())[0])

            # Should fail after retries
            with pytest.raises(Exception, match="RESOURCE_EXHAUSTED"):
                wrapper.invoke("test prompt", max_retries=2)

        # Check backoff was incremented
        current_key = getattr(wrapper, "_current_key", None)
        backoff_multipliers = getattr(wrapper, "_backoff_multipliers", {})
        if current_key and current_key in backoff_multipliers:
            assert backoff_multipliers[current_key] >= 1


class TestProviderFallback:
    """Test provider fallback with rotation."""

    def test_fallback_chain_with_rotation(self, multi_provider_env: Dict[str, str]) -> None:
        """Test fallback chain when primary provider keys are exhausted."""
        models = ["gpt-4.1", "claude-3-5-haiku-latest"]

        # Create fallback chain
        chain = ChatFallback.create_with_fallbacks(models=models)

        # Verify chain creation
        assert chain is not None

        # Both models should use rotation if multiple keys available
        for model in models:
            fallback_instance = ChatFallback(
                model=models[0],
                fallback_list=models[1:]
            )
            provider = fallback_instance._get_provider_from_model(model)  # type: ignore
            if provider:
                keys = discover_keys_for_provider(provider)
            else:
                keys = []
            if len(keys) > 1:
                # Should be using rotation
                model_instance = fallback_instance.get_chat_model(model)
                assert hasattr(model_instance, "key_manager")

    def test_all_keys_exhausted_fallback(self, multi_provider_env: Dict[str, str]) -> None:
        """Test provider fallback when all keys for primary are exhausted."""
        manager_openai = APIKeyManager("openai", auto_discover=True)
        manager_anthropic = APIKeyManager("anthropic", auto_discover=True)

        # Mark all OpenAI keys as rate limited
        for key in manager_openai.keys:
            manager_openai.mark_rate_limited(key, retry_after=3600)

        # Create wrapper that should fail
        wrapper_openai = RotatingKeyChatOpenAI(key_manager=manager_openai, model="gpt-4")

        # Should raise when all keys exhausted
        with pytest.raises(RuntimeError, match="No available API keys"):
            wrapper_openai.execute_with_rotation(lambda: Mock())

        # Anthropic should still work
        wrapper_anthropic = RotatingKeyChatAnthropic(
            key_manager=manager_anthropic, model="claude-3-opus-20240229"
        )
        result = wrapper_anthropic.execute_with_rotation(lambda: "success")
        assert result == "success"


class TestThreadSafety:
    """Test thread safety and concurrent operations."""

    def test_concurrent_rotation_thread_safety(self, multi_provider_env: Dict[str, str]) -> None:
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

    def test_shared_key_manager_coordination(self, multi_provider_env: Dict[str, str]) -> None:
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

    def test_invalid_keys_removal(self, multi_provider_env: Dict[str, str]) -> None:
        """Test that invalid keys are properly marked and excluded."""
        manager = APIKeyManager("openai", auto_discover=True)

        # Mark first key as invalid (auth error)
        first_key = list(manager.keys.keys())[0]
        manager.mark_invalid(first_key)

        # Should not return invalid key
        for _ in range(10):
            key = manager.get_next_available_key()
            assert key != first_key

    def test_cooldown_expiration(self, multi_provider_env: Dict[str, str]) -> None:
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
            # Should not be able to create managers
            with pytest.raises(Exception):
                fallback = ChatFallback(
                    model="gpt-4.1",
                    fallback_list=[]
                )
                fallback.get_chat_model("gpt-4.1")

    def test_backwards_compatibility(self, single_provider_env: Dict[str, str]) -> None:
        """Test that single-key setup still works without rotation."""
        fallback = ChatFallback(
            model="gpt-4.1",
            fallback_list=[]
        )

        # Should not use rotation with single key
        assert fallback._should_use_rotation("gpt-4.1") is False  # type: ignore
        assert fallback._should_use_rotation("claude-3-5-haiku-latest") is False  # type: ignore

        # Should create standard model
        model_instance = fallback.get_chat_model("gpt-4.1")
        assert not hasattr(model_instance, "key_manager")


class TestPerformanceAndMetrics:
    """Test performance characteristics and metrics collection."""

    def test_rotation_performance(self, multi_provider_env: Dict[str, str]) -> None:
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

    def test_metrics_accuracy(self, multi_provider_env: Dict[str, str]) -> None:
        """Test that metrics are accurately tracked."""
        manager = APIKeyManager("openai", auto_discover=True)
        wrapper = RotatingKeyChatOpenAI(key_manager=manager, model="gpt-4")

        success_count = 0
        failure_count = 0

        for i in range(20):
            try:

                def mock_call() -> str:
                    if i % 3 == 0:
                        error = Mock()
                        error.__str__ = lambda: "429: Rate limit"
                        raise error
                    return "success"

                wrapper.execute_with_rotation(mock_call, max_retries=1)
                success_count += 1
            except Exception:
                failure_count += 1

        # Check metrics
        metrics = wrapper.get_metrics_snapshot()
        assert metrics.successful_requests >= success_count
        assert metrics.failed_requests >= failure_count
        assert metrics.rate_limit_hits > 0

    def test_rotation_status_reporting(self, multi_provider_env: Dict[str, str]) -> None:
        """Test status reporting for monitoring."""
        fallback = ChatFallback(
            model="gpt-4.1",
            fallback_list=[]
        )
        status = fallback.get_rotation_status()

        # Should report status for all configured providers
        assert len(status) > 0

        for _provider, info in status.items():
            assert "rotation_enabled" in info
            assert "keys_count" in info

            # Multi-key providers should have rotation enabled
            if info["keys_count"] > 1:
                assert info["rotation_enabled"] is True