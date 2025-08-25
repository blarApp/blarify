"""Tests for rotating provider base class."""

import pytest

from blarify.agents.api_key_manager import APIKeyManager
from blarify.agents.rotating_providers import ErrorType, RotatingProviderBase


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
        RotatingProviderBase(manager)
    
    assert "Can't instantiate abstract class" in str(exc_info.value)