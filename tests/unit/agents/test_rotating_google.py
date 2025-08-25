"""Unit tests for RotatingKeyChatGoogle."""

from unittest.mock import Mock

import pytest

from blarify.agents.api_key_manager import APIKeyManager
from blarify.agents.rotating_google import RotatingKeyChatGoogle
from blarify.agents.rotating_providers import ErrorType


def test_google_resource_exhausted_detection() -> None:
    """Test Google RESOURCE_EXHAUSTED error detection."""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")

    wrapper = RotatingKeyChatGoogle(manager)
    wrapper._current_key = "test-key-123"

    error = Exception("Error code: 429, Status: RESOURCE_EXHAUSTED")
    error_type, retry = wrapper.analyze_error(error)
    assert error_type == ErrorType.RATE_LIMIT
    assert retry == 1  # First backoff is 2^0 = 1


def test_google_exponential_backoff() -> None:
    """Test exponential backoff calculation."""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")

    wrapper = RotatingKeyChatGoogle(manager)
    wrapper._current_key = "test-key-123"

    # First backoff
    assert wrapper._calculate_backoff() == 1
    # Second backoff
    assert wrapper._calculate_backoff() == 2
    # Third backoff
    assert wrapper._calculate_backoff() == 4
    # Fourth backoff
    assert wrapper._calculate_backoff() == 8


def test_google_backoff_reset() -> None:
    """Test backoff reset after success."""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")

    wrapper = RotatingKeyChatGoogle(manager)
    wrapper._current_key = "test-key-123"

    # Set some backoff
    wrapper._backoff_multipliers["test-key-123"] = 3

    # Reset backoff
    wrapper._reset_backoff("test-key-123")

    # Next backoff should start from beginning
    assert wrapper._calculate_backoff() == 1


def test_google_quota_vs_rate_limit() -> None:
    """Test distinguishing quota exceeded from rate limit."""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")

    wrapper = RotatingKeyChatGoogle(manager)

    # Rate limit error
    error1 = Exception("429: RESOURCE_EXHAUSTED")
    error_type, _ = wrapper.analyze_error(error1)
    assert error_type == ErrorType.RATE_LIMIT

    # Quota error
    error2 = Exception("Quota exceeded for project. Please submit a quota increase request.")
    error_type, _ = wrapper.analyze_error(error2)
    assert error_type == ErrorType.QUOTA_EXCEEDED


def test_google_no_headers() -> None:
    """Test that Google doesn't return rate limit headers."""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")

    wrapper = RotatingKeyChatGoogle(manager)

    error = Mock()
    error.response = Mock()
    error.response.headers = {"date": "2024-01-01", "server": "Google"}

    headers = wrapper.extract_headers_from_error(error)
    # Should not have rate limit headers
    assert "x-ratelimit" not in str(headers).lower()
    assert "retry-after" not in headers


def test_google_auth_error_detection() -> None:
    """Test Google authentication error detection."""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")

    wrapper = RotatingKeyChatGoogle(manager)

    # 401 error
    error1 = Exception("401 Unauthenticated")
    error_type, retry_after = wrapper.analyze_error(error1)
    assert error_type == ErrorType.AUTH_ERROR
    assert retry_after is None

    # 403 error
    error2 = Exception("403 Forbidden")
    error_type, retry_after = wrapper.analyze_error(error2)
    assert error_type == ErrorType.AUTH_ERROR
    assert retry_after is None


def test_google_retryable_errors() -> None:
    """Test Google retryable error detection."""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")

    wrapper = RotatingKeyChatGoogle(manager)

    retryable_errors = [
        "Connection timeout",
        "Network unavailable",
        "Service unavailable",
        "Connection reset",
    ]

    for error_msg in retryable_errors:
        error = Exception(error_msg)
        error_type, retry_after = wrapper.analyze_error(error)
        assert error_type == ErrorType.RETRYABLE
        assert retry_after is None


def test_google_non_retryable_errors() -> None:
    """Test Google non-retryable error detection."""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")

    wrapper = RotatingKeyChatGoogle(manager)

    error = Exception("Invalid model configuration")
    error_type, retry_after = wrapper.analyze_error(error)
    assert error_type == ErrorType.NON_RETRYABLE
    assert retry_after is None


def test_google_max_backoff() -> None:
    """Test that exponential backoff has a maximum."""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")

    wrapper = RotatingKeyChatGoogle(manager)
    wrapper._current_key = "test-key-123"

    # Set a high multiplier to test max backoff
    wrapper._backoff_multipliers["test-key-123"] = 10

    # Should be capped at 300
    assert wrapper._calculate_backoff() == 300


def test_google_provider_name() -> None:
    """Test provider name is correct."""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")

    wrapper = RotatingKeyChatGoogle(manager)
    assert wrapper.get_provider_name() == "google"


def test_google_create_client() -> None:
    """Test client creation with API key."""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")

    wrapper = RotatingKeyChatGoogle(manager, model="gemini-pro", temperature=0.7)

    # Mock the ChatGoogleGenerativeAI to avoid actual instantiation
    with pytest.mock.patch("blarify.agents.rotating_google.ChatGoogleGenerativeAI") as mock_chat:
        wrapper._create_client("test-key-123")
        mock_chat.assert_called_once_with(
            google_api_key="test-key-123", model="gemini-pro", temperature=0.7
        )


def test_google_backoff_no_current_key() -> None:
    """Test backoff calculation when no current key."""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")

    wrapper = RotatingKeyChatGoogle(manager)
    wrapper._current_key = None

    # Should return default 60 seconds
    assert wrapper._calculate_backoff() == 60


def test_google_headers_no_response() -> None:
    """Test header extraction when error has no response."""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")

    wrapper = RotatingKeyChatGoogle(manager)

    error = Exception("Some error")
    headers = wrapper.extract_headers_from_error(error)
    assert headers == {}


def test_google_execute_with_rotation_success() -> None:
    """Test execute_with_rotation resets backoff on success."""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")

    wrapper = RotatingKeyChatGoogle(manager)
    wrapper._current_key = "test-key-123"
    wrapper._backoff_multipliers["test-key-123"] = 3

    # Mock successful execution
    def success_func() -> str:
        return "success"

    # Mock the parent class execute_with_rotation
    with pytest.mock.patch.object(
        RotatingKeyChatGoogle.__bases__[0], "execute_with_rotation", return_value="success"
    ):
        result = wrapper.execute_with_rotation(success_func)
        assert result == "success"
        # Backoff should be reset
        assert "test-key-123" not in wrapper._backoff_multipliers


def test_google_execute_with_rotation_failure() -> None:
    """Test execute_with_rotation re-raises exceptions."""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")

    wrapper = RotatingKeyChatGoogle(manager)

    def failing_func() -> None:
        raise ValueError("Test error")

    # Mock the parent class execute_with_rotation to raise
    with pytest.mock.patch.object(
        RotatingKeyChatGoogle.__bases__[0],
        "execute_with_rotation",
        side_effect=ValueError("Test error"),
    ):
        with pytest.raises(ValueError, match="Test error"):
            wrapper.execute_with_rotation(failing_func)