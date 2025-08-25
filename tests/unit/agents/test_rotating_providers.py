"""Tests for rotating provider base class."""

from typing import Any, Dict, Optional, Tuple

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
            return (ErrorType.RATE_LIMIT, 60)
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
    assert provider._current_key is None


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
        IncompleteProvider(manager)
    
    assert "Can't instantiate abstract class" in str(exc_info.value)