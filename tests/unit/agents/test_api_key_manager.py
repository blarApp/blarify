"""Unit tests for API Key Manager."""

import threading
import time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from blarify.agents.api_key_manager import APIKeyManager, KeyState, KeyStatus


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


class TestAPIKeyManager:
    """Tests for APIKeyManager class."""
    
    def test_initialization(self) -> None:
        """Test APIKeyManager initialization."""
        manager = APIKeyManager("openai")
        
        assert manager.provider == "openai"
        assert manager.keys == {}
        assert manager._key_order == []
        assert manager._current_index == 0
    
    def test_add_key(self) -> None:
        """Test adding a new key to the manager."""
        manager = APIKeyManager("openai")
        manager.add_key("test-key-1")
        
        assert "test-key-1" in manager.keys
        assert manager.keys["test-key-1"].state == KeyStatus.AVAILABLE
        assert "test-key-1" in manager._key_order
    
    def test_add_duplicate_key(self) -> None:
        """Test that duplicate keys are not added."""
        manager = APIKeyManager("openai")
        manager.add_key("test-key-1")
        manager.add_key("test-key-1")  # Try to add duplicate
        
        assert len(manager.keys) == 1
        assert len(manager._key_order) == 1
    
    def test_get_next_available_key_round_robin(self) -> None:
        """Test round-robin key selection."""
        manager = APIKeyManager("openai")
        manager.add_key("key-1")
        manager.add_key("key-2")
        manager.add_key("key-3")
        
        # Should return keys in round-robin order
        assert manager.get_next_available_key() == "key-1"
        assert manager.get_next_available_key() == "key-2"
        assert manager.get_next_available_key() == "key-3"
        assert manager.get_next_available_key() == "key-1"  # Back to first
    
    def test_get_next_available_key_skips_unavailable(self) -> None:
        """Test that selection skips unavailable keys."""
        manager = APIKeyManager("openai")
        manager.add_key("key-1")
        manager.add_key("key-2")
        manager.add_key("key-3")
        
        # Mark key-2 as rate limited
        manager.keys["key-2"].state = KeyStatus.RATE_LIMITED
        
        # Should skip key-2
        assert manager.get_next_available_key() == "key-1"
        assert manager.get_next_available_key() == "key-3"  # Skips key-2
        assert manager.get_next_available_key() == "key-1"  # Back to key-1
    
    def test_get_next_available_key_returns_none_when_all_exhausted(self) -> None:
        """Test returns None when all keys are exhausted."""
        manager = APIKeyManager("openai")
        manager.add_key("key-1")
        manager.add_key("key-2")
        
        # Mark all keys as invalid
        manager.keys["key-1"].state = KeyStatus.INVALID
        manager.keys["key-2"].state = KeyStatus.INVALID
        
        assert manager.get_next_available_key() is None
    
    def test_get_next_available_key_with_no_keys(self) -> None:
        """Test returns None when no keys are configured."""
        manager = APIKeyManager("openai")
        assert manager.get_next_available_key() is None