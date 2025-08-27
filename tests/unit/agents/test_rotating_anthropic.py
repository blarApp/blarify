"""Tests for Anthropic provider with rotating API keys."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from blarify.agents.api_key_manager import APIKeyManager
from blarify.agents.rotating_provider import RotatingKeyChatAnthropic, ErrorType


def test_anthropic_rate_limit_with_retry_after() -> None:
    """Test Anthropic rate limit with Retry-After header."""
    manager = APIKeyManager("anthropic", auto_discover=False)
    manager.add_key("sk-ant-test123")

    wrapper = RotatingKeyChatAnthropic(manager)

    # Mock error with Retry-After
    error = Mock()
    error.__str__ = lambda: "rate_limit_error: Your account has hit a rate limit"
    error.response = Mock()
    error.response.headers = {"retry-after": "15"}

    error_type, retry = wrapper.analyze_error(error)
    assert error_type == ErrorType.RATE_LIMIT
    assert retry == 15


def test_anthropic_spike_detection() -> None:
    """Test detection of spike-triggered rate limits."""
    manager = APIKeyManager("anthropic", auto_discover=False)
    manager.add_key("sk-ant-test123")

    wrapper = RotatingKeyChatAnthropic(manager)

    headers = {"anthropic-ratelimit-requests-remaining": "50", "retry-after": "5"}

    assert wrapper._is_spike_triggered(headers) is True  # type: ignore[attr-defined]


def test_rfc3339_timestamp_parsing() -> None:
    """Test parsing of RFC 3339 timestamps in headers."""
    manager = APIKeyManager("anthropic", auto_discover=False)
    manager.add_key("sk-ant-test123")

    wrapper = RotatingKeyChatAnthropic(manager)

    future_time = datetime.now(timezone.utc) + timedelta(seconds=30)
    headers = {"anthropic-ratelimit-requests-reset": future_time.isoformat()}

    cooldown = wrapper._calculate_cooldown_from_headers(headers)  # type: ignore[attr-defined]
    assert cooldown is not None
    assert 28 <= cooldown <= 32  # Allow some variance for test execution


def test_anthropic_auth_error() -> None:
    """Test Anthropic authentication error detection."""
    manager = APIKeyManager("anthropic", auto_discover=False)
    manager.add_key("sk-ant-test123")

    wrapper = RotatingKeyChatAnthropic(manager)

    error = Exception("Error: 401 - Authentication failed")
    error_type, retry = wrapper.analyze_error(error)
    assert error_type == ErrorType.AUTH_ERROR
    assert retry is None


def test_anthropic_quota_exceeded() -> None:
    """Test Anthropic quota exceeded error detection."""
    manager = APIKeyManager("anthropic", auto_discover=False)
    manager.add_key("sk-ant-test123")

    wrapper = RotatingKeyChatAnthropic(manager)

    error = Exception("Error: Your account has exceeded the monthly quota")
    error_type, retry = wrapper.analyze_error(error)
    assert error_type == ErrorType.QUOTA_EXCEEDED
    assert retry is None


def test_anthropic_retryable_error() -> None:
    """Test Anthropic retryable error detection."""
    manager = APIKeyManager("anthropic", auto_discover=False)
    manager.add_key("sk-ant-test123")

    wrapper = RotatingKeyChatAnthropic(manager)

    error = Exception("Connection timeout while calling Anthropic API")
    error_type, retry = wrapper.analyze_error(error)
    assert error_type == ErrorType.RETRYABLE
    assert retry is None


def test_anthropic_non_retryable_error() -> None:
    """Test Anthropic non-retryable error detection."""
    manager = APIKeyManager("anthropic", auto_discover=False)
    manager.add_key("sk-ant-test123")

    wrapper = RotatingKeyChatAnthropic(manager)

    error = Exception("Invalid request format")
    error_type, retry = wrapper.analyze_error(error)
    assert error_type == ErrorType.NON_RETRYABLE
    assert retry is None


def test_extract_all_anthropic_headers() -> None:
    """Test extraction of all Anthropic-specific headers."""
    manager = APIKeyManager("anthropic", auto_discover=False)
    manager.add_key("sk-ant-test123")

    wrapper = RotatingKeyChatAnthropic(manager)

    # Mock error with full set of headers
    error = Mock()
    error.response = Mock()
    error.response.headers = {
        "retry-after": "10",
        "anthropic-ratelimit-requests-limit": "1000",
        "anthropic-ratelimit-requests-remaining": "500",
        "anthropic-ratelimit-requests-reset": "2024-01-01T12:00:00Z",
        "anthropic-ratelimit-input-tokens-limit": "100000",
        "anthropic-ratelimit-input-tokens-remaining": "50000",
        "anthropic-ratelimit-input-tokens-reset": "2024-01-01T12:00:00Z",
        "anthropic-ratelimit-output-tokens-limit": "50000",
        "anthropic-ratelimit-output-tokens-remaining": "25000",
        "anthropic-ratelimit-output-tokens-reset": "2024-01-01T12:00:00Z",
        "other-header": "should-not-be-included",
    }

    headers = wrapper.extract_headers_from_error(error)

    assert headers["retry-after"] == "10"
    assert headers["anthropic-ratelimit-requests-limit"] == "1000"
    assert headers["anthropic-ratelimit-requests-remaining"] == "500"
    assert headers["anthropic-ratelimit-requests-reset"] == "2024-01-01T12:00:00Z"
    assert headers["anthropic-ratelimit-input-tokens-limit"] == "100000"
    assert headers["anthropic-ratelimit-input-tokens-remaining"] == "50000"
    assert headers["anthropic-ratelimit-input-tokens-reset"] == "2024-01-01T12:00:00Z"
    assert headers["anthropic-ratelimit-output-tokens-limit"] == "50000"
    assert headers["anthropic-ratelimit-output-tokens-remaining"] == "25000"
    assert headers["anthropic-ratelimit-output-tokens-reset"] == "2024-01-01T12:00:00Z"
    assert "other-header" not in headers


def test_calculate_cooldown_priority() -> None:
    """Test that Retry-After takes priority over reset timestamps."""
    manager = APIKeyManager("anthropic", auto_discover=False)
    manager.add_key("sk-ant-test123")

    wrapper = RotatingKeyChatAnthropic(manager)

    future_time = datetime.now(timezone.utc) + timedelta(seconds=60)
    headers = {
        "retry-after": "20",  # Should take priority
        "anthropic-ratelimit-requests-reset": future_time.isoformat(),
    }

    cooldown = wrapper._calculate_cooldown_from_headers(headers)  # type: ignore[attr-defined]
    assert cooldown == 20  # Should use Retry-After value


def test_spike_detection_with_no_remaining() -> None:
    """Test that spike detection doesn't trigger without remaining quota."""
    manager = APIKeyManager("anthropic", auto_discover=False)
    manager.add_key("sk-ant-test123")

    wrapper = RotatingKeyChatAnthropic(manager)

    headers = {"anthropic-ratelimit-requests-remaining": "0", "retry-after": "5"}

    assert wrapper._is_spike_triggered(headers) is False  # type: ignore[attr-defined]


def test_provider_name() -> None:
    """Test that provider name is correct."""
    manager = APIKeyManager("anthropic", auto_discover=False)
    manager.add_key("sk-ant-test123")

    wrapper = RotatingKeyChatAnthropic(manager)
    assert wrapper.get_provider_name() == "anthropic"


def test_model_kwargs_pass_through() -> None:
    """Test that model kwargs are passed through correctly."""
    manager = APIKeyManager("anthropic", auto_discover=False)
    manager.add_key("sk-ant-test123")

    wrapper = RotatingKeyChatAnthropic(manager, model="claude-3-opus-20240229", temperature=0.7, max_tokens=1000)

    assert wrapper.model_kwargs["model"] == "claude-3-opus-20240229"
    assert wrapper.model_kwargs["temperature"] == 0.7
    assert wrapper.model_kwargs["max_tokens"] == 1000
    assert "api_key" not in wrapper.model_kwargs
