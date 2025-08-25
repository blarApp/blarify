"""Tests for ChatFallback integration with rotating providers."""

import os
from unittest.mock import patch

import pytest

from blarify.agents.chat_fallback import ChatFallback, MODEL_PROVIDER_DICT


class TestChatFallbackIntegration:
    """Test ChatFallback integration with rotating providers."""

    def test_single_key_backwards_compatibility(self) -> None:
        """Test that single key configurations work without changes."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'sk-test123456789012345678901234567890'}, clear=True):
            # Test with a known OpenAI model
            openai_models = [m for m in MODEL_PROVIDER_DICT.keys() if "gpt" in m or "o4" in m or "o3" in m]
            if openai_models:
                model_name = openai_models[0]
                fallback = ChatFallback(
                    model=model_name,
                    fallback_list=[],
                    output_schema=None,
                    timeout=60
                )
                chat_model = fallback.get_chat_model(model_name)
                
                # Should get standard ChatOpenAI, not rotating
                assert not hasattr(chat_model, 'key_manager')

    def test_multiple_keys_triggers_rotation(self) -> None:
        """Test that multiple keys trigger rotation."""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'sk-test1234567890123456789012345678901',
            'OPENAI_API_KEY_1': 'sk-test1234567890123456789012345678902',
            'OPENAI_API_KEY_2': 'sk-test1234567890123456789012345678903'
        }, clear=True):
            # Test with a known OpenAI model
            openai_models = [m for m in MODEL_PROVIDER_DICT.keys() if "gpt" in m or "o4" in m or "o3" in m]
            if openai_models:
                model_name = openai_models[0]
                fallback = ChatFallback(
                    model=model_name,
                    fallback_list=[],
                    output_schema=None,
                    timeout=60
                )
                chat_model = fallback.get_chat_model(model_name)
                
                # Should get RotatingKeyChatOpenAI
                assert hasattr(chat_model, 'key_manager')
                if hasattr(chat_model, 'key_manager'):
                    assert chat_model.key_manager.get_available_count() == 3  # type: ignore

    def test_unknown_model_raises_error(self) -> None:
        """Test that unknown models raise ValueError."""
        fallback = ChatFallback(
            model="gpt-4.1",  # Using a valid model for initialization
            fallback_list=[],
            output_schema=None,
            timeout=60
        )
        
        with pytest.raises(ValueError, match="Model unknown-model not found"):
            fallback.get_chat_model("unknown-model")

    def test_model_provider_dict_coverage(self) -> None:
        """Test all models in MODEL_PROVIDER_DICT can be created."""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'sk-test1234567890123456789012345678901',
            'ANTHROPIC_API_KEY': 'sk-ant-test1234567890123456789012345',
            'GOOGLE_API_KEY': 'google-test1234567890123456789012345'
        }):
            for model in MODEL_PROVIDER_DICT.keys():
                fallback = ChatFallback(
                    model=model,
                    fallback_list=[],
                    output_schema=None,
                    timeout=60
                )
                
                try:
                    chat_model = fallback.get_chat_model(model)
                    assert chat_model is not None
                except Exception as e:
                    # Model creation might fail due to missing deps, but should not raise Unknown model
                    assert "not found in MODEL_PROVIDER_DICT" not in str(e)

    def test_fallback_chain_with_rotation(self) -> None:
        """Test fallback chain works with rotating providers."""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'sk-test1234567890123456789012345678901',
            'OPENAI_API_KEY_1': 'sk-test1234567890123456789012345678902',
            'ANTHROPIC_API_KEY': 'sk-ant-test1234567890123456789012345'
        }, clear=True):
            # Get first OpenAI and first Anthropic model
            openai_models = [m for m in MODEL_PROVIDER_DICT.keys() if "gpt" in m or "o4" in m or "o3" in m]
            anthropic_models = [m for m in MODEL_PROVIDER_DICT.keys() if "claude" in m]
            
            if openai_models and anthropic_models:
                models = [openai_models[0], anthropic_models[0]]
                
                fallback = ChatFallback(
                    model=models[0],
                    fallback_list=[models[1]],
                    output_schema=None,
                    timeout=60
                )
                
                chain = fallback.get_fallback_chat_model()
                
                # Should create a RunnableWithFallbacks
                assert chain is not None
                assert hasattr(chain, 'fallbacks')

    def test_create_with_fallbacks_class_method(self) -> None:
        """Test the create_with_fallbacks class method."""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'sk-test1234567890123456789012345678901',
            'ANTHROPIC_API_KEY': 'sk-ant-test1234567890123456789012345'
        }, clear=True):
            # Get first OpenAI and first Anthropic model
            openai_models = [m for m in MODEL_PROVIDER_DICT.keys() if "gpt" in m or "o4" in m or "o3" in m]
            anthropic_models = [m for m in MODEL_PROVIDER_DICT.keys() if "claude" in m]
            
            if openai_models and anthropic_models:
                models = [openai_models[0], anthropic_models[0]]
                
                chain = ChatFallback.create_with_fallbacks(
                    models=models,
                    timeout=60
                )
                
                # Should create a RunnableWithFallbacks
                assert chain is not None

    def test_create_with_fallbacks_validates_models(self) -> None:
        """Test that create_with_fallbacks validates model names."""
        with pytest.raises(ValueError, match="At least one model must be provided"):
            ChatFallback.create_with_fallbacks(models=[])
        
        with pytest.raises(ValueError, match="Unknown model: invalid-model"):
            ChatFallback.create_with_fallbacks(models=["invalid-model"])

    def test_rotation_status_tracking(self) -> None:
        """Test rotation status tracking."""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'sk-test1234567890123456789012345678901',
            'OPENAI_API_KEY_1': 'sk-test1234567890123456789012345678902',
            'ANTHROPIC_API_KEY': 'sk-ant-test1234567890123456789012345'
        }, clear=True):
            fallback = ChatFallback(
                model="gpt-4.1",
                fallback_list=[],
                output_schema=None,
                timeout=60
            )
            
            status = fallback.get_rotation_status()
            
            # Check OpenAI models show rotation enabled
            for _model, info in status.items():
                if info['provider'] == 'openai':
                    assert info['rotation_enabled'] is True
                    assert info['keys_count'] == 2
                elif info['provider'] == 'anthropic':
                    assert info['rotation_enabled'] is False
                    assert info['keys_count'] == 1

    def test_provider_detection(self) -> None:
        """Test provider detection from model names."""
        fallback = ChatFallback(
            model="gpt-4.1",
            fallback_list=[],
            output_schema=None,
            timeout=60
        )
        
        # Test OpenAI models
        assert fallback._get_provider_from_model("gpt-4.1") == "openai"  # type: ignore
        assert fallback._get_provider_from_model("o4-mini") == "openai"  # type: ignore
        
        # Test Anthropic models
        assert fallback._get_provider_from_model("claude-3-5-haiku-latest") == "anthropic"  # type: ignore
        
        # Test Google models  
        assert fallback._get_provider_from_model("gemini-2.5-flash-preview-05-20") == "google"  # type: ignore
        
        # Test unknown model
        assert fallback._get_provider_from_model("unknown-model") is None  # type: ignore

    def test_rotation_enabled_tracking(self) -> None:
        """Test that rotation enabled state is tracked."""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'sk-test1234567890123456789012345678901',
            'OPENAI_API_KEY_1': 'sk-test1234567890123456789012345678902',
        }, clear=True):
            fallback = ChatFallback(
                model="gpt-4.1",
                fallback_list=[],
                output_schema=None,
                timeout=60
            )
            
            # Initially empty
            assert fallback._rotation_enabled == {}  # type: ignore
            
            # After getting a rotating model
            _ = fallback.get_chat_model("gpt-4.1")
            assert fallback._rotation_enabled.get("gpt-4.1") is True  # type: ignore

    def test_single_model_without_fallbacks(self) -> None:
        """Test using a single model without any fallbacks."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'sk-test1234567890123456789012345678901'}, clear=True):
            openai_models = [m for m in MODEL_PROVIDER_DICT.keys() if "gpt" in m]
            if openai_models:
                chain = ChatFallback.create_with_fallbacks(
                    models=[openai_models[0]],
                    timeout=60
                )
                
                # Should still work with just one model
                assert chain is not None