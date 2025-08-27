---
title: "Task 7: ChatFallback Integration"
parent_issue: 276
task_number: 7
description: "Integrate rotating providers with existing ChatFallback system"
---

# Task 7: ChatFallback Integration

## Context
Now that we have the rotating provider wrappers, we need to integrate them with the existing ChatFallback system to enable transparent key rotation before provider fallback.

## Objective
Modify the ChatFallback class to automatically use rotating providers when multiple API keys are available, while maintaining backwards compatibility with single-key configurations.

## Implementation Steps with Commits

### Step 1: Import Rotating Providers
**Files to modify:**
- `blarify/agents/chat_fallback.py`
- `tests/unit/agents/test_chat_fallback.py`

**Implementation:**
```python
# Add imports at the top of chat_fallback.py
from blarify.agents.api_key_manager import APIKeyManager
from blarify.agents.rotating_openai import RotatingKeyChatOpenAI
from blarify.agents.rotating_anthropic import RotatingKeyChatAnthropic
from blarify.agents.rotating_google import RotatingKeyChatGoogle
from blarify.agents.key_discovery import discover_keys_for_provider

import logging
logger = logging.getLogger(__name__)
```

**Commit 1:**
```
feat: add rotating provider imports to ChatFallback

Part of #276
```

### Step 2: Add Provider Detection from MODEL_PROVIDER_DICT
**Files to modify:**
- `blarify/agents/chat_fallback.py`
- `tests/unit/agents/test_chat_fallback.py`

**Implementation:**
```python
def _get_provider_from_model(self, model: str) -> Optional[str]:
    """Get provider name from MODEL_PROVIDER_DICT"""
    provider_class = self.MODEL_PROVIDER_DICT.get(model)
    if not provider_class:
        return None
    
    # Extract provider from class name
    class_name = provider_class.__name__
    if "OpenAI" in class_name:
        return "openai"
    elif "Anthropic" in class_name:
        return "anthropic"
    elif "Google" in class_name or "Gemini" in class_name:
        return "google"
    
    return None

def _should_use_rotation(self, model: str) -> bool:
    """Check if multiple keys exist for the model's provider"""
    provider = self._get_provider_from_model(model)
    if not provider:
        return False
    
    keys = discover_keys_for_provider(provider)
    has_multiple = len(keys) > 1
    
    if has_multiple:
        logger.debug(f"Found {len(keys)} keys for {provider}, enabling rotation")
    
    return has_multiple
```

**Commit 2:**
```
feat: add provider detection using MODEL_PROVIDER_DICT

Part of #276
```

### Step 3: Create Rotating Provider Mapping
**Files to modify:**
- `blarify/agents/chat_fallback.py`
- `tests/unit/agents/test_chat_fallback.py`

**Implementation:**
```python
# Add to class definition
ROTATING_PROVIDER_MAP = {
    "openai": RotatingKeyChatOpenAI,
    "anthropic": RotatingKeyChatAnthropic,
    "google": RotatingKeyChatGoogle,
}

def _get_rotating_provider_class(self, provider: str) -> Optional[type]:
    """Get the rotating provider class for a provider"""
    return self.ROTATING_PROVIDER_MAP.get(provider)
```

**Commit 3:**
```
feat: add rotating provider class mapping

Part of #276
```

### Step 4: Modify get_chat_model Method
**Files to modify:**
- `blarify/agents/chat_fallback.py`
- `tests/unit/agents/test_chat_fallback.py`

**Implementation:**
```python
def get_chat_model(self, model: str, timeout: Optional[int] = None) -> Runnable:
    """Get a chat model instance, using rotation if multiple keys available"""
    # First check if model is in MODEL_PROVIDER_DICT
    if model not in self.MODEL_PROVIDER_DICT:
        raise ValueError(f"Unknown model: {model}")
    
    # Check if we should use rotation for this model
    if self._should_use_rotation(model):
        provider = self._get_provider_from_model(model)
        rotating_class = self._get_rotating_provider_class(provider)
        
        if rotating_class:
            logger.info(f"Using rotating provider for {model} ({provider})")
            return self._create_rotating_model(model, provider, rotating_class, timeout)
    
    # Fall back to standard model creation
    return self._create_standard_model(model, timeout)

def _create_rotating_model(
    self, 
    model: str, 
    provider: str, 
    rotating_class: type,
    timeout: Optional[int] = None
) -> Runnable:
    """Create a rotating model instance"""
    # Create APIKeyManager for the provider
    key_manager = APIKeyManager(provider, auto_discover=True)
    
    # Get model kwargs
    model_kwargs = {
        "model": model,
        "timeout": timeout or self.timeout,
        "temperature": self.temperature,
        "max_retries": self.max_retries,
    }
    
    # Create rotating provider instance
    return rotating_class(key_manager, **model_kwargs)

def _create_standard_model(self, model: str, timeout: Optional[int] = None) -> Runnable:
    """Create a standard (non-rotating) model instance"""
    provider_class = self.MODEL_PROVIDER_DICT[model]
    
    return provider_class(
        model=model,
        timeout=timeout or self.timeout,
        temperature=self.temperature,
        max_retries=self.max_retries,
    )
```

**Commit 4:**
```
feat: integrate rotation logic in get_chat_model

Part of #276
```

### Step 5: Update create_with_fallbacks Method
**Files to modify:**
- `blarify/agents/chat_fallback.py`
- `tests/unit/agents/test_chat_fallback.py`

**Implementation:**
```python
@classmethod
def create_with_fallbacks(
    cls,
    models: List[str],
    temperature: float = 0.7,
    timeout: int = 60,
    max_retries: int = 3,
) -> RunnableWithFallbacks:
    """Create a chat model with fallbacks, using rotation where available"""
    if not models:
        raise ValueError("At least one model must be provided")
    
    # Validate all models exist in MODEL_PROVIDER_DICT
    for model in models:
        if model not in cls.MODEL_PROVIDER_DICT:
            raise ValueError(f"Unknown model: {model}")
    
    instance = cls(
        temperature=temperature,
        timeout=timeout,
        max_retries=max_retries,
    )
    
    # Create primary model (with rotation if available)
    primary_model = instance.get_chat_model(models[0])
    
    # Create fallback models (with rotation if available)
    fallback_models = []
    for model in models[1:]:
        try:
            fallback_model = instance.get_chat_model(model)
            fallback_models.append(fallback_model)
            
            # Log rotation status
            if instance._should_use_rotation(model):
                provider = instance._get_provider_from_model(model)
                keys_count = len(discover_keys_for_provider(provider))
                logger.info(f"Fallback model {model} using {keys_count} rotating keys")
        except Exception as e:
            logger.warning(f"Failed to create fallback model {model}: {e}")
    
    # Create RunnableWithFallbacks
    if fallback_models:
        return primary_model.with_fallbacks(fallback_models)
    return primary_model
```

**Commit 5:**
```
feat: update create_with_fallbacks for rotation support

Part of #276
```

### Step 6: Add Backwards Compatibility Tests
**Files to modify:**
- `tests/unit/agents/test_chat_fallback.py`

**Implementation:**
```python
import os
from unittest.mock import patch, Mock
from blarify.agents.chat_fallback import ChatFallback

def test_single_key_backwards_compatibility():
    """Test that single key configurations work without changes"""
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'sk-test123'}, clear=True):
        # Assume gpt-4 is in MODEL_PROVIDER_DICT
        fallback = ChatFallback()
        model = fallback.get_chat_model("gpt-4")
        
        # Should get standard ChatOpenAI, not rotating
        assert not hasattr(model, 'key_manager')

def test_multiple_keys_triggers_rotation():
    """Test that multiple keys trigger rotation"""
    with patch.dict(os.environ, {
        'OPENAI_API_KEY': 'sk-test1',
        'OPENAI_API_KEY_1': 'sk-test2',
        'OPENAI_API_KEY_2': 'sk-test3'
    }, clear=True):
        fallback = ChatFallback()
        model = fallback.get_chat_model("gpt-4")
        
        # Should get RotatingKeyChatOpenAI
        assert hasattr(model, 'key_manager')
        assert model.key_manager.get_available_count() == 3

def test_unknown_model_raises_error():
    """Test that unknown models raise ValueError"""
    fallback = ChatFallback()
    
    with pytest.raises(ValueError, match="Unknown model"):
        fallback.get_chat_model("unknown-model")

def test_model_provider_dict_coverage():
    """Test all models in MODEL_PROVIDER_DICT can be created"""
    with patch.dict(os.environ, {
        'OPENAI_API_KEY': 'sk-test',
        'ANTHROPIC_API_KEY': 'sk-ant-test',
        'GOOGLE_API_KEY': 'google-test'
    }):
        fallback = ChatFallback()
        
        for model in ChatFallback.MODEL_PROVIDER_DICT.keys():
            try:
                chat_model = fallback.get_chat_model(model)
                assert chat_model is not None
            except Exception as e:
                # Model creation might fail due to missing deps, but should not raise Unknown model
                assert "Unknown model" not in str(e)

def test_fallback_chain_with_rotation():
    """Test fallback chain works with rotating providers"""
    with patch.dict(os.environ, {
        'OPENAI_API_KEY': 'sk-test1',
        'OPENAI_API_KEY_1': 'sk-test2',
        'ANTHROPIC_API_KEY': 'sk-ant-test'
    }, clear=True):
        # Use actual model names from MODEL_PROVIDER_DICT
        models = list(ChatFallback.MODEL_PROVIDER_DICT.keys())[:2]
        
        chain = ChatFallback.create_with_fallbacks(
            models=models,
            temperature=0.5
        )
        
        # Should create a RunnableWithFallbacks or single model
        assert chain is not None
```

**Commit 6:**
```
test: add comprehensive tests for ChatFallback integration

Part of #276
```

### Step 7: Add Metrics Tracking
**Files to modify:**
- `blarify/agents/chat_fallback.py`

**Implementation:**
```python
def __init__(self, temperature: float = 0.7, timeout: int = 60, max_retries: int = 3):
    """Initialize ChatFallback with rotation tracking"""
    self.temperature = temperature
    self.timeout = timeout
    self.max_retries = max_retries
    self._rotation_enabled = {}  # Track which models use rotation

def get_rotation_status(self) -> Dict[str, Dict[str, Any]]:
    """Get rotation status for all configured models"""
    status = {}
    
    for model in self.MODEL_PROVIDER_DICT.keys():
        provider = self._get_provider_from_model(model)
        if provider:
            keys = discover_keys_for_provider(provider)
            status[model] = {
                'provider': provider,
                'rotation_enabled': len(keys) > 1,
                'keys_count': len(keys)
            }
    
    return status

def _create_rotating_model(
    self, 
    model: str, 
    provider: str, 
    rotating_class: type,
    timeout: Optional[int] = None
) -> Runnable:
    """Create a rotating model instance with tracking"""
    # Track that rotation is enabled for this model
    self._rotation_enabled[model] = True
    
    # ... rest of implementation
```

**Commit 7:**
```
feat: add rotation status tracking to ChatFallback

Part of #276
```

## Validation Criteria

- [ ] Multiple keys trigger rotation automatically
- [ ] Single key configurations work unchanged
- [ ] Only models in MODEL_PROVIDER_DICT are accepted
- [ ] Unknown models raise clear errors
- [ ] Fallback chain works with rotating providers
- [ ] Rotation status available for monitoring
- [ ] No breaking changes to existing API
- [ ] No pyright type errors
- [ ] Ruff linting passes
- [ ] All commits made incrementally

## Next Steps
After completing this task, proceed to Task 8: Update EmbeddingService integration.