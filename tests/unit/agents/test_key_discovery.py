"""Unit tests for key discovery and validation utilities."""

import os
from unittest.mock import patch

from blarify.agents.utils import discover_keys_for_provider, validate_key


class TestKeyDiscovery:
    """Tests for discover_keys_for_provider function."""
    
    def test_discovery_with_no_keys(self) -> None:
        """Test discovery when no keys are present."""
        with patch.dict(os.environ, {}, clear=True):
            keys = discover_keys_for_provider("openai")
            assert keys == []
    
    def test_discovery_with_base_key_only(self) -> None:
        """Test discovery with only base key present."""
        env_vars = {"OPENAI_API_KEY": "sk-test-base"}
        with patch.dict(os.environ, env_vars, clear=True):
            keys = discover_keys_for_provider("openai")
            assert keys == ["sk-test-base"]
    
    def test_discovery_with_numbered_keys(self) -> None:
        """Test discovery with numbered keys."""
        env_vars = {
            "OPENAI_API_KEY": "sk-test-base",
            "OPENAI_API_KEY_1": "sk-test-1",
            "OPENAI_API_KEY_2": "sk-test-2",
            "OPENAI_API_KEY_3": "sk-test-3"
        }
        with patch.dict(os.environ, env_vars, clear=True):
            keys = discover_keys_for_provider("openai")
            assert keys == ["sk-test-base", "sk-test-1", "sk-test-2", "sk-test-3"]
    
    def test_discovery_with_only_numbered_keys(self) -> None:
        """Test discovery with only numbered keys (no base key)."""
        env_vars = {
            "OPENAI_API_KEY_1": "sk-test-1",
            "OPENAI_API_KEY_2": "sk-test-2"
        }
        with patch.dict(os.environ, env_vars, clear=True):
            keys = discover_keys_for_provider("openai")
            assert keys == ["sk-test-1", "sk-test-2"]
    
    def test_discovery_handles_gaps_in_numbering(self) -> None:
        """Test that discovery stops at the first gap in numbering."""
        env_vars = {
            "OPENAI_API_KEY": "sk-test-base",
            "OPENAI_API_KEY_1": "sk-test-1",
            "OPENAI_API_KEY_2": "sk-test-2",
            # Gap at 3
            "OPENAI_API_KEY_4": "sk-test-4",  # Should not be discovered
            "OPENAI_API_KEY_5": "sk-test-5"   # Should not be discovered
        }
        with patch.dict(os.environ, env_vars, clear=True):
            keys = discover_keys_for_provider("openai")
            assert keys == ["sk-test-base", "sk-test-1", "sk-test-2"]
    
    def test_discovery_with_anthropic_provider(self) -> None:
        """Test discovery with Anthropic provider."""
        env_vars = {
            "ANTHROPIC_API_KEY": "sk-ant-test-base",
            "ANTHROPIC_API_KEY_1": "sk-ant-test-1"
        }
        with patch.dict(os.environ, env_vars, clear=True):
            keys = discover_keys_for_provider("anthropic")
            assert keys == ["sk-ant-test-base", "sk-ant-test-1"]
    
    def test_discovery_with_google_provider(self) -> None:
        """Test discovery with Google provider."""
        env_vars = {
            "GOOGLE_API_KEY": "google-test-key",
            "GOOGLE_API_KEY_1": "google-test-key-1",
            "GOOGLE_API_KEY_2": "google-test-key-2"
        }
        with patch.dict(os.environ, env_vars, clear=True):
            keys = discover_keys_for_provider("google")
            assert keys == ["google-test-key", "google-test-key-1", "google-test-key-2"]
    
    def test_discovery_case_insensitive_provider(self) -> None:
        """Test that provider name is correctly uppercased."""
        env_vars = {"OPENAI_API_KEY": "sk-test"}
        with patch.dict(os.environ, env_vars, clear=True):
            # Test various casings
            assert discover_keys_for_provider("openai") == ["sk-test"]
            assert discover_keys_for_provider("OpenAI") == ["sk-test"]
            assert discover_keys_for_provider("OPENAI") == ["sk-test"]
    
    def test_discovery_does_not_pick_up_other_providers(self) -> None:
        """Test that discovery only picks up keys for the specified provider."""
        env_vars = {
            "OPENAI_API_KEY": "sk-openai",
            "ANTHROPIC_API_KEY": "sk-anthropic",
            "GOOGLE_API_KEY": "google-key"
        }
        with patch.dict(os.environ, env_vars, clear=True):
            openai_keys = discover_keys_for_provider("openai")
            assert openai_keys == ["sk-openai"]
            
            anthropic_keys = discover_keys_for_provider("anthropic")
            assert anthropic_keys == ["sk-anthropic"]
            
            google_keys = discover_keys_for_provider("google")
            assert google_keys == ["google-key"]
    
    def test_discovery_with_empty_string_values(self) -> None:
        """Test that empty string values are still discovered."""
        env_vars = {
            "OPENAI_API_KEY": "",  # Empty string
            "OPENAI_API_KEY_1": "sk-test-1"
        }
        with patch.dict(os.environ, env_vars, clear=True):
            keys = discover_keys_for_provider("openai")
            # Empty strings are still discovered (validation happens elsewhere)
            assert keys == ["", "sk-test-1"]
    
    def test_discovery_with_large_number_of_keys(self) -> None:
        """Test discovery with many numbered keys."""
        env_vars = {"OPENAI_API_KEY": "sk-base"}
        for i in range(1, 21):  # 20 numbered keys
            env_vars[f"OPENAI_API_KEY_{i}"] = f"sk-test-{i}"
        
        with patch.dict(os.environ, env_vars, clear=True):
            keys = discover_keys_for_provider("openai")
            assert len(keys) == 21  # Base + 20 numbered
            assert keys[0] == "sk-base"
            assert keys[1] == "sk-test-1"
            assert keys[20] == "sk-test-20"


class TestKeyValidation:
    """Tests for validate_key function."""
    
    def test_validate_openai_key_valid(self) -> None:
        """Test valid OpenAI key format."""
        assert validate_key("sk-proj-abcdef123456789012345678901234567890", "openai") is True
        assert validate_key("sk-123456789012345678901234567890", "openai") is True
    
    def test_validate_openai_key_invalid(self) -> None:
        """Test invalid OpenAI key formats."""
        assert validate_key("", "openai") is False
        assert validate_key("invalid-key", "openai") is False
        assert validate_key("sk-", "openai") is False  # Too short
        assert validate_key("sk-12345", "openai") is False  # Too short
        assert validate_key("openai-key-without-prefix", "openai") is False
    
    def test_validate_anthropic_key_valid(self) -> None:
        """Test valid Anthropic key format."""
        assert validate_key("sk-ant-api03-1234567890123456789012345678901234567890", "anthropic") is True
        assert validate_key("sk-ant-123456789012345678901234567890", "anthropic") is True
    
    def test_validate_anthropic_key_invalid(self) -> None:
        """Test invalid Anthropic key formats."""
        assert validate_key("", "anthropic") is False
        assert validate_key("invalid-key", "anthropic") is False
        assert validate_key("sk-ant-", "anthropic") is False  # Too short
        assert validate_key("sk-ant-12345", "anthropic") is False  # Too short
        assert validate_key("sk-123456789012345678901234567890", "anthropic") is False  # Wrong prefix
    
    def test_validate_google_key_valid(self) -> None:
        """Test valid Google key format."""
        assert validate_key("AIzaSyDfCd7bS8p1234567890123456789012345", "google") is True
        assert validate_key("google-api-key-1234567890123456789012345", "google") is True
        assert validate_key("any-string-longer-than-20-characters", "google") is True
    
    def test_validate_google_key_invalid(self) -> None:
        """Test invalid Google key formats."""
        assert validate_key("", "google") is False
        assert validate_key("short-key", "google") is False  # Too short
        assert validate_key("12345678901234567890", "google") is False  # Exactly 20 chars (need > 20)
    
    def test_validate_unknown_provider(self) -> None:
        """Test validation for unknown provider (should accept any non-empty string)."""
        assert validate_key("any-non-empty-key", "unknown") is True
        assert validate_key("x", "unknown") is True
        assert validate_key("", "unknown") is False
    
    def test_validate_case_insensitive_provider(self) -> None:
        """Test that provider name is case-insensitive."""
        key = "sk-proj-abcdef123456789012345678901234567890"
        assert validate_key(key, "OpenAI") is True
        assert validate_key(key, "OPENAI") is True
        assert validate_key(key, "openai") is True