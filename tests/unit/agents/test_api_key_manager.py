"""Unit tests for API Key Manager."""

import threading
import time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from blarify.agents.api_key_manager import KeyState, KeyStatus


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