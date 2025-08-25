"""Integration test fixtures for API key rotation testing."""

import os
from typing import Any, Callable, Dict
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def multi_provider_env() -> Any:
    """Environment with multiple keys for each provider."""
    env_vars: Dict[str, str] = {
        "OPENAI_API_KEY": "sk-test1",
        "OPENAI_API_KEY_1": "sk-test2",
        "OPENAI_API_KEY_2": "sk-test3",
        "ANTHROPIC_API_KEY": "sk-ant-test1",
        "ANTHROPIC_API_KEY_1": "sk-ant-test2",
        "GOOGLE_API_KEY": "google-test1",
        "GOOGLE_API_KEY_1": "google-test2",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        yield env_vars


@pytest.fixture
def single_provider_env() -> Any:
    """Environment with single key for each provider."""
    env_vars: Dict[str, str] = {
        "OPENAI_API_KEY": "sk-test-single",
        "ANTHROPIC_API_KEY": "sk-ant-single",
        "GOOGLE_API_KEY": "google-single",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        yield env_vars


@pytest.fixture
def mock_llm_responses() -> Callable[[str], Mock]:
    """Mock LLM responses for testing."""

    def _mock_response(content: str = "Test response") -> Mock:
        response = Mock()
        response.content = content
        return response

    return _mock_response


@pytest.fixture
def mock_rate_limit_error() -> Callable[[str, int], Mock]:
    """Create mock rate limit errors with headers."""

    def _create_error(provider: str = "openai", retry_after: int = 20) -> Mock:
        error = Mock()
        error.response = Mock()

        if provider == "openai":
            error.__str__ = lambda: f"Rate limit reached for gpt-4 model. Please try again in {retry_after}s."
            error.response.headers = {
                "X-RateLimit-Limit-Requests": "10000",
                "X-RateLimit-Remaining-Requests": "0",
                "X-RateLimit-Reset-Requests": str(retry_after),
                "X-RateLimit-Limit-Tokens": "100000",
                "X-RateLimit-Remaining-Tokens": "0",
                "X-RateLimit-Reset-Tokens": str(retry_after),
            }
        elif provider == "anthropic":
            error.__str__ = lambda: "rate_limit_error"
            error.response.headers = {
                "retry-after": str(retry_after),
                "anthropic-ratelimit-requests-limit": "1000",
                "anthropic-ratelimit-requests-remaining": "0",
                "anthropic-ratelimit-requests-reset": "2025-01-01T00:00:00Z",
            }
        elif provider == "google":
            error.__str__ = lambda: "429: RESOURCE_EXHAUSTED"
            error.response.headers = {}  # Google doesn't provide headers

        error.response.status_code = 429
        return error

    return _create_error


@pytest.fixture
def mock_invalid_key_error() -> Callable[[], Mock]:
    """Create mock authentication errors."""

    def _create_error() -> Mock:
        error = Mock()
        error.response = Mock()
        error.response.status_code = 401
        error.__str__ = lambda: "Invalid API key"
        return error

    return _create_error