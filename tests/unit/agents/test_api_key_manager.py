"""Unit tests for API Key Manager."""

import threading
import time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from blarify.agents.api_key_manager import KeyStatus


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