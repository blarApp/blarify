"""Unit tests for OpenAI provider with rotation support."""

from unittest.mock import Mock, patch
from datetime import datetime, timezone
from typing import Any

from blarify.agents.rotating_provider import RotatingKeyChatOpenAI, ErrorType, OpenAIRotationConfig
from blarify.agents.api_key_manager import APIKeyManager


class TestRotatingKeyChatOpenAI:
    """Test suite for RotatingKeyChatOpenAI."""

    def test_initialization(self) -> None:
        """Test wrapper initialization."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager, model="gpt-4", temperature=0.7)

        assert wrapper.get_provider_name() == "openai"
        assert wrapper.model_kwargs == {"model": "gpt-4", "temperature": 0.7}

    def test_initialization_with_custom_config(self) -> None:
        """Test initialization with custom rotation config."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        config = OpenAIRotationConfig(
            proactive_rotation_threshold_requests=5,
            proactive_rotation_threshold_tokens=500,
            default_cooldown_seconds=120,
        )

        wrapper = RotatingKeyChatOpenAI(key_manager=manager, rotation_config=config)

        assert wrapper.rotation_config.proactive_rotation_threshold_requests == 5
        assert wrapper.rotation_config.proactive_rotation_threshold_tokens == 500
        assert wrapper.rotation_config.default_cooldown_seconds == 120

    def test_api_key_not_in_kwargs(self) -> None:
        """Test that api_key is removed from kwargs."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager, api_key="should-be-removed", model="gpt-4")

        assert "api_key" not in wrapper.model_kwargs
        assert wrapper.model_kwargs["model"] == "gpt-4"

    def test_create_client(self) -> None:
        """Test client creation with API key."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager, model="gpt-4")

        with patch("blarify.agents.rotating_openai.ChatOpenAI") as mock_openai:
            wrapper._create_client("test_key_2")  # type: ignore[attr-defined]
            # Check that ChatOpenAI was called with SecretStr
            mock_openai.assert_called_once()
            call_args = mock_openai.call_args
            assert call_args[1]["model"] == "gpt-4"
            # api_key should be a SecretStr

    def test_analyze_rate_limit_error_with_retry_time(self) -> None:
        """Test rate limit error detection with specific retry time."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager)

        error = Exception("Rate limit reached for gpt-4 model (requests per min). Please try again in 20s.")
        error_type, retry = wrapper.analyze_error(error)

        assert error_type == ErrorType.RATE_LIMIT
        assert retry == 20

    def test_analyze_rate_limit_error_with_429_code(self) -> None:
        """Test rate limit error detection with 429 status code."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager)

        error = Exception("Error code: 429 - You exceeded your current quota")
        error_type, retry = wrapper.analyze_error(error)

        assert error_type == ErrorType.RATE_LIMIT
        assert retry == 60  # Default cooldown

    def test_analyze_auth_error_401(self) -> None:
        """Test authentication error detection with 401 status."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager)

        error = Exception("Error code: 401 - Invalid API key provided")
        error_type, retry = wrapper.analyze_error(error)

        assert error_type == ErrorType.AUTH_ERROR
        assert retry is None

    def test_analyze_auth_error_403(self) -> None:
        """Test authentication error detection with 403 status."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager)

        error = Exception("Error code: 403 - Access denied")
        error_type, retry = wrapper.analyze_error(error)

        assert error_type == ErrorType.AUTH_ERROR
        assert retry is None

    def test_analyze_quota_exceeded_error(self) -> None:
        """Test quota exceeded error detection."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager)

        error = Exception("Your quota has been exceeded for this month")
        error_type, retry = wrapper.analyze_error(error)

        assert error_type == ErrorType.QUOTA_EXCEEDED
        assert retry is None

    def test_analyze_retryable_error(self) -> None:
        """Test retryable error detection."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager)

        errors = [Exception("Connection timeout"), Exception("Network error occurred"), Exception("Request timeout")]

        for error in errors:
            error_type, retry = wrapper.analyze_error(error)
            assert error_type == ErrorType.RETRYABLE
            assert retry is None

    def test_analyze_non_retryable_error(self) -> None:
        """Test non-retryable error detection."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager)

        error = Exception("Invalid request format")
        error_type, retry = wrapper.analyze_error(error)

        assert error_type == ErrorType.NON_RETRYABLE
        assert retry is None

    def test_extract_retry_seconds_various_formats(self) -> None:
        """Test retry seconds extraction from various message formats."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager)

        test_cases = [
            ("Please try again in 30s", 30),
            ("Try again in 45 seconds", 45),
            ("Retry after 60", 60),
            ("Rate limit hit", 60),  # Default
        ]

        for message, expected in test_cases:
            result = wrapper._extract_retry_seconds(message.lower())  # type: ignore[attr-defined]
            assert result == expected

    def test_extract_headers_from_error_with_response(self) -> None:
        """Test header extraction from error with response object."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager)

        # Mock error with headers
        error = Mock()
        error.response = Mock()
        error.response.headers = {
            "x-ratelimit-remaining-requests": "5",
            "x-ratelimit-reset-requests": "2024-01-01T00:00:00Z",
            "x-ratelimit-remaining-tokens": "1000",
            "other-header": "should-not-be-extracted",
        }

        headers = wrapper.extract_headers_from_error(error)

        assert "x-ratelimit-remaining-requests" in headers
        assert headers["x-ratelimit-remaining-requests"] == "5"
        assert "x-ratelimit-reset-requests" in headers
        assert headers["x-ratelimit-reset-requests"] == "2024-01-01T00:00:00Z"
        assert "x-ratelimit-remaining-tokens" in headers
        assert headers["x-ratelimit-remaining-tokens"] == "1000"
        assert "other-header" not in headers

    def test_extract_headers_from_error_without_response(self) -> None:
        """Test header extraction from error without response object."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager)

        error = Exception("Simple error without response")
        headers = wrapper.extract_headers_from_error(error)

        assert headers == {}

    def test_should_preemptively_rotate_low_requests(self) -> None:
        """Test proactive rotation with low remaining requests."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager)

        headers = {"x-ratelimit-remaining-requests": "1"}
        assert wrapper._should_preemptively_rotate(headers) is True  # type: ignore[attr-defined]

        headers = {"x-ratelimit-remaining-requests": "0"}
        assert wrapper._should_preemptively_rotate(headers) is True  # type: ignore[attr-defined]

        headers = {"x-ratelimit-remaining-requests": "10"}
        assert wrapper._should_preemptively_rotate(headers) is False  # type: ignore[attr-defined]

    def test_should_preemptively_rotate_low_tokens(self) -> None:
        """Test proactive rotation with low remaining tokens."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager)

        headers = {"x-ratelimit-remaining-tokens": "50"}
        assert wrapper._should_preemptively_rotate(headers) is True  # type: ignore[attr-defined]

        headers = {"x-ratelimit-remaining-tokens": "100"}
        assert wrapper._should_preemptively_rotate(headers) is True  # type: ignore[attr-defined]

        headers = {"x-ratelimit-remaining-tokens": "500"}
        assert wrapper._should_preemptively_rotate(headers) is False  # type: ignore[attr-defined]

    def test_should_preemptively_rotate_custom_thresholds(self) -> None:
        """Test proactive rotation with custom thresholds."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        config = OpenAIRotationConfig(proactive_rotation_threshold_requests=5, proactive_rotation_threshold_tokens=500)

        wrapper = RotatingKeyChatOpenAI(key_manager=manager, rotation_config=config)

        headers = {"x-ratelimit-remaining-requests": "5"}
        assert wrapper._should_preemptively_rotate(headers) is True  # type: ignore[attr-defined]

        headers = {"x-ratelimit-remaining-requests": "6"}
        assert wrapper._should_preemptively_rotate(headers) is False  # type: ignore[attr-defined]

        headers = {"x-ratelimit-remaining-tokens": "500"}
        assert wrapper._should_preemptively_rotate(headers) is True  # type: ignore[attr-defined]

        headers = {"x-ratelimit-remaining-tokens": "501"}
        assert wrapper._should_preemptively_rotate(headers) is False  # type: ignore[attr-defined]

    def test_should_preemptively_rotate_empty_headers(self) -> None:
        """Test proactive rotation with empty headers."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager)

        assert wrapper._should_preemptively_rotate({}) is False  # type: ignore[attr-defined]
        assert wrapper._should_preemptively_rotate(None) is False  # type: ignore[attr-defined, arg-type]

    def test_calculate_cooldown_from_headers(self) -> None:
        """Test cooldown calculation from reset headers."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager)

        # Mock datetime.now to control time
        with patch("blarify.agents.rotating_openai.datetime") as mock_dt:
            # Set "now" to a specific time
            now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_dt.now.return_value = now
            mock_dt.fromisoformat = datetime.fromisoformat

            # Test with reset time 30 seconds in the future
            headers = {"x-ratelimit-reset-requests": "2024-01-01T12:00:30Z"}
            cooldown = wrapper._calculate_cooldown_from_headers(headers)  # type: ignore[attr-defined]
            assert cooldown == 30

            # Test with reset time using token header
            headers = {"x-ratelimit-reset-tokens": "2024-01-01T12:01:00Z"}
            cooldown = wrapper._calculate_cooldown_from_headers(headers)  # type: ignore[attr-defined]
            assert cooldown == 60

    def test_calculate_cooldown_invalid_format(self) -> None:
        """Test cooldown calculation with invalid date format."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager)

        headers = {"x-ratelimit-reset-requests": "invalid-date"}
        cooldown = wrapper._calculate_cooldown_from_headers(headers)  # type: ignore[attr-defined]
        assert cooldown is None

    def test_calculate_cooldown_no_reset_headers(self) -> None:
        """Test cooldown calculation without reset headers."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager)

        headers = {"other-header": "value"}
        cooldown = wrapper._calculate_cooldown_from_headers(headers)  # type: ignore[attr-defined]
        assert cooldown is None

    def test_integration_with_base_class(self) -> None:
        """Test that OpenAI wrapper integrates properly with base class."""
        manager = APIKeyManager("openai", auto_discover=False)
        manager.add_key("sk-test_key_1_with_valid_format_12345")
        manager.add_key("sk-test_key_2_with_valid_format_67890")

        wrapper = RotatingKeyChatOpenAI(key_manager=manager)

        # Test successful execution
        with patch.object(wrapper, "_create_client") as mock_create:
            mock_client = Mock()
            mock_client.invoke = Mock(return_value="success")
            mock_create.return_value = mock_client

            result = wrapper.invoke("test_input")
            assert result == "success"

        # Test rotation on rate limit
        call_count = 0

        def side_effect(*args: Any, **kwargs: Any) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Error code: 429 - Rate limit exceeded")
            return "success_after_rotation"

        with patch.object(wrapper, "_create_client") as mock_create:
            mock_client = Mock()
            mock_client.invoke = Mock(side_effect=side_effect)
            mock_create.return_value = mock_client

            result = wrapper.invoke("test_input")
            assert result == "success_after_rotation"
            assert call_count == 2
