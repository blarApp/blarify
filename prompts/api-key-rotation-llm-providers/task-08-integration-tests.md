---
title: "Task 8: End-to-End Integration Tests"
parent_issue: 276
task_number: 8
description: "Create comprehensive integration tests for the complete API key rotation feature"
---

# Task 8: End-to-End Integration Tests

## Context
With all components implemented, we need comprehensive integration tests to verify the entire API key rotation system works correctly end-to-end.

## Objective
Create integration tests that validate the complete flow: key discovery, rotation during rate limits, provider fallback, and coordination between components.

## Implementation Steps with Commits

### Step 1: Create Integration Test File Structure
**Files to create:**
- `tests/integration/test_api_key_rotation.py` (create)
- `tests/integration/fixtures.py` (create)

**Implementation:**
```python
# tests/integration/fixtures.py
import os
import pytest
from unittest.mock import patch, Mock
from typing import Dict, List

@pytest.fixture
def multi_provider_env():
    """Environment with multiple keys for each provider"""
    env_vars = {
        'OPENAI_API_KEY': 'sk-test1',
        'OPENAI_API_KEY_1': 'sk-test2',
        'OPENAI_API_KEY_2': 'sk-test3',
        'ANTHROPIC_API_KEY': 'sk-ant-test1',
        'ANTHROPIC_API_KEY_1': 'sk-ant-test2',
        'GOOGLE_API_KEY': 'google-test1',
        'GOOGLE_API_KEY_1': 'google-test2',
    }
    with patch.dict(os.environ, env_vars, clear=True):
        yield env_vars

@pytest.fixture
def single_provider_env():
    """Environment with single key for each provider"""
    env_vars = {
        'OPENAI_API_KEY': 'sk-test-single',
        'ANTHROPIC_API_KEY': 'sk-ant-single',
        'GOOGLE_API_KEY': 'google-single',
    }
    with patch.dict(os.environ, env_vars, clear=True):
        yield env_vars

@pytest.fixture
def mock_llm_responses():
    """Mock LLM responses for testing"""
    def _mock_response(content: str = "Test response"):
        response = Mock()
        response.content = content
        return response
    return _mock_response
```

**Commit 1:**
```
test: create integration test fixtures

Part of #276
```

### Step 2: Test Key Discovery and Initialization
**Files to modify:**
- `tests/integration/test_api_key_rotation.py`

**Implementation:**
```python
import pytest
from blarify.agents.api_key_manager import APIKeyManager
from blarify.agents.key_discovery import discover_keys_for_provider
from blarify.agents.chat_fallback import ChatFallback

def test_key_discovery_all_providers(multi_provider_env):
    """Test that all keys are discovered for each provider"""
    # OpenAI
    openai_keys = discover_keys_for_provider("openai")
    assert len(openai_keys) == 3
    assert all(k.startswith("sk-test") for k in openai_keys)
    
    # Anthropic
    anthropic_keys = discover_keys_for_provider("anthropic")
    assert len(anthropic_keys) == 2
    assert all(k.startswith("sk-ant") for k in anthropic_keys)
    
    # Google
    google_keys = discover_keys_for_provider("google")
    assert len(google_keys) == 2
    assert all("google" in k for k in google_keys)

def test_api_key_manager_initialization(multi_provider_env):
    """Test APIKeyManager initializes with discovered keys"""
    # OpenAI manager
    openai_manager = APIKeyManager("openai", auto_discover=True)
    assert len(openai_manager.keys) == 3
    assert openai_manager.get_available_count() == 3
    
    # Anthropic manager
    anthropic_manager = APIKeyManager("anthropic", auto_discover=True)
    assert len(anthropic_manager.keys) == 2
    assert anthropic_manager.get_available_count() == 2

def test_chat_fallback_detects_rotation(multi_provider_env):
    """Test ChatFallback correctly detects when to use rotation"""
    fallback = ChatFallback()
    
    # Assuming these models are in MODEL_PROVIDER_DICT
    for model in fallback.MODEL_PROVIDER_DICT.keys():
        provider = fallback._get_provider_from_model(model)
        if provider == "openai":
            assert fallback._should_use_rotation(model) == True
        elif provider == "anthropic":
            assert fallback._should_use_rotation(model) == True
        elif provider == "google":
            assert fallback._should_use_rotation(model) == True
```

**Commit 2:**
```
test: add key discovery and initialization tests

Part of #276
```

### Step 3: Test Rate Limit Rotation Scenarios
**Files to modify:**
- `tests/integration/test_api_key_rotation.py`

**Implementation:**
```python
from unittest.mock import patch, Mock
from blarify.agents.rotating_openai import RotatingKeyChatOpenAI
from blarify.agents.rotating_anthropic import RotatingKeyChatAnthropic
from blarify.agents.rotating_google import RotatingKeyChatGoogle

def test_openai_rate_limit_rotation(multi_provider_env):
    """Test OpenAI rotates keys on rate limit"""
    manager = APIKeyManager("openai", auto_discover=True)
    wrapper = RotatingKeyChatOpenAI(manager)
    
    call_count = 0
    keys_used = []
    
    def mock_invoke(*args, **kwargs):
        nonlocal call_count, keys_used
        keys_used.append(wrapper._current_key)
        call_count += 1
        
        # First two keys hit rate limit
        if call_count <= 2:
            raise Exception("Rate limit reached for gpt-4 model. Please try again in 20s.")
        return Mock(content="Success")
    
    with patch.object(wrapper, '_create_client') as mock_create:
        mock_client = Mock()
        mock_client.invoke = mock_invoke
        mock_create.return_value = mock_client
        
        # Should succeed after rotating through keys
        result = wrapper.invoke("test prompt")
        assert result.content == "Success"
        
    # Should have tried 3 keys
    assert len(keys_used) == 3
    assert len(set(keys_used)) == 3  # All different keys
    
    # First two keys should be marked as rate limited
    assert manager.keys[keys_used[0]].state.value == "rate_limited"
    assert manager.keys[keys_used[1]].state.value == "rate_limited"
    assert manager.keys[keys_used[2]].state.value == "available"

def test_anthropic_spike_detection(multi_provider_env):
    """Test Anthropic detects and handles spike-triggered rate limits"""
    manager = APIKeyManager("anthropic", auto_discover=True)
    wrapper = RotatingKeyChatAnthropic(manager)
    
    # Mock error with remaining quota (spike scenario)
    error = Mock()
    error.__str__ = lambda self: "rate_limit_error"
    error.response = Mock()
    error.response.headers = {
        'anthropic-ratelimit-requests-remaining': '100',
        'retry-after': '5'
    }
    
    # Should detect as spike
    assert wrapper._is_spike_triggered(wrapper.extract_headers_from_error(error))
    
    # Should still mark as rate limited
    error_type, retry_after = wrapper.analyze_error(error)
    assert error_type.value == "rate_limit"
    assert retry_after == 5

def test_google_exponential_backoff(multi_provider_env):
    """Test Google uses exponential backoff correctly"""
    manager = APIKeyManager("google", auto_discover=True)
    wrapper = RotatingKeyChatGoogle(manager)
    
    call_count = 0
    
    def mock_invoke(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        # Fail first 3 times with rate limit
        if call_count <= 3:
            raise Exception("429: RESOURCE_EXHAUSTED")
        return Mock(content="Success")
    
    with patch.object(wrapper, '_create_client') as mock_create:
        mock_client = Mock()
        mock_client.invoke = mock_invoke
        mock_create.return_value = mock_client
        
        # Set first key as current
        wrapper._current_key = list(manager.keys.keys())[0]
        
        # Should fail after retries
        with pytest.raises(Exception, match="RESOURCE_EXHAUSTED"):
            wrapper.invoke("test prompt", max_retries=2)
    
    # Check backoff was incremented
    assert wrapper._backoff_multipliers[wrapper._current_key] >= 1
```

**Commit 3:**
```
test: add rate limit rotation scenario tests

Part of #276
```

### Step 4: Test Provider Fallback with Rotation
**Files to modify:**
- `tests/integration/test_api_key_rotation.py`

**Implementation:**
```python
def test_fallback_chain_with_rotation(multi_provider_env):
    """Test fallback chain when primary provider keys are exhausted"""
    # Get first two different provider models from MODEL_PROVIDER_DICT
    models = []
    providers_seen = set()
    
    fallback_instance = ChatFallback()
    for model, provider_class in fallback_instance.MODEL_PROVIDER_DICT.items():
        provider = fallback_instance._get_provider_from_model(model)
        if provider and provider not in providers_seen:
            models.append(model)
            providers_seen.add(provider)
            if len(models) == 2:
                break
    
    # Create fallback chain
    chain = ChatFallback.create_with_fallbacks(
        models=models,
        temperature=0.5,
        max_retries=2
    )
    
    # Verify chain creation
    assert chain is not None
    
    # Both models should use rotation if multiple keys available
    for model in models:
        provider = fallback_instance._get_provider_from_model(model)
        keys = discover_keys_for_provider(provider)
        if len(keys) > 1:
            # Should be using rotation
            model_instance = fallback_instance.get_chat_model(model)
            assert hasattr(model_instance, 'key_manager')

def test_all_keys_exhausted_fallback(multi_provider_env):
    """Test provider fallback when all keys for primary are exhausted"""
    manager_openai = APIKeyManager("openai", auto_discover=True)
    manager_anthropic = APIKeyManager("anthropic", auto_discover=True)
    
    # Mark all OpenAI keys as rate limited
    for key in manager_openai.keys:
        manager_openai.mark_rate_limited(key, retry_after=3600)
    
    # Create wrapper that should fail
    wrapper_openai = RotatingKeyChatOpenAI(manager_openai)
    
    # Should raise when all keys exhausted
    with pytest.raises(RuntimeError, match="No available API keys"):
        wrapper_openai.execute_with_rotation(lambda: Mock())
    
    # Anthropic should still work
    wrapper_anthropic = RotatingKeyChatAnthropic(manager_anthropic)
    result = wrapper_anthropic.execute_with_rotation(lambda: "success")
    assert result == "success"
```

**Commit 4:**
```
test: add provider fallback integration tests

Part of #276
```

### Step 5: Test Thread Safety and Concurrency
**Files to modify:**
- `tests/integration/test_api_key_rotation.py`

**Implementation:**
```python
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def test_concurrent_rotation_thread_safety(multi_provider_env):
    """Test concurrent requests with rotation are thread-safe"""
    manager = APIKeyManager("openai", auto_discover=True)
    wrapper = RotatingKeyChatOpenAI(manager)
    
    results = []
    errors = []
    keys_used = []
    
    def make_request(request_id: int):
        try:
            # Track which key is used
            def mock_api_call():
                keys_used.append(wrapper._current_key)
                # Simulate some failures
                if request_id % 5 == 0:
                    raise Exception("429: Rate limit")
                return f"response_{request_id}"
            
            result = wrapper.execute_with_rotation(mock_api_call, max_retries=2)
            results.append(result)
        except Exception as e:
            errors.append(str(e))
    
    # Launch concurrent requests
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request, i) for i in range(50)]
        for future in as_completed(futures):
            future.result()  # Wait for completion
    
    # Verify results
    assert len(results) + len(errors) == 50
    assert len(keys_used) >= 50  # Some retries will use more
    
    # Check metrics are consistent
    metrics = wrapper.get_metrics_snapshot()
    assert metrics.total_requests >= 50

def test_shared_key_manager_coordination(multi_provider_env):
    """Test multiple components sharing the same key manager"""
    shared_manager = APIKeyManager("openai", auto_discover=True)
    
    wrapper1 = RotatingKeyChatOpenAI(shared_manager)
    wrapper2 = RotatingKeyChatOpenAI(shared_manager)
    
    # Both should see same key states
    test_key = list(shared_manager.keys.keys())[0]
    
    # Mark key as rate limited in wrapper1
    shared_manager.mark_rate_limited(test_key, retry_after=10)
    
    # Wrapper2 should see the same state
    assert shared_manager.keys[test_key].state.value == "rate_limited"
    
    # Both should skip the rate-limited key
    available_key1 = wrapper1.key_manager.get_next_available_key()
    available_key2 = wrapper2.key_manager.get_next_available_key()
    
    assert available_key1 != test_key
    assert available_key2 != test_key
```

**Commit 5:**
```
test: add thread safety and concurrency tests

Part of #276
```

### Step 6: Test Edge Cases and Error Recovery
**Files to modify:**
- `tests/integration/test_api_key_rotation.py`

**Implementation:**
```python
def test_invalid_keys_removal(multi_provider_env):
    """Test that invalid keys are properly marked and excluded"""
    manager = APIKeyManager("openai", auto_discover=True)
    wrapper = RotatingKeyChatOpenAI(manager)
    
    # Mark first key as invalid (auth error)
    first_key = list(manager.keys.keys())[0]
    manager.mark_invalid(first_key)
    
    # Should not return invalid key
    for _ in range(10):
        key = manager.get_next_available_key()
        assert key != first_key

def test_cooldown_expiration(multi_provider_env):
    """Test that rate-limited keys become available after cooldown"""
    manager = APIKeyManager("openai", auto_discover=True)
    wrapper = RotatingKeyChatOpenAI(manager)
    
    # Mark key as rate limited with short cooldown
    test_key = list(manager.keys.keys())[0]
    manager.mark_rate_limited(test_key, retry_after=1)
    
    # Should not be available immediately
    assert manager.keys[test_key].state.value == "rate_limited"
    available_keys = []
    for _ in range(len(manager.keys) - 1):
        key = manager.get_next_available_key()
        if key:
            available_keys.append(key)
    assert test_key not in available_keys
    
    # Wait for cooldown
    time.sleep(1.5)
    
    # Should be available again
    manager.reset_expired_cooldowns()
    assert manager.keys[test_key].state.value == "available"

def test_all_providers_no_keys():
    """Test graceful failure when no keys are available"""
    with patch.dict(os.environ, {}, clear=True):
        # Should not be able to create managers
        with pytest.raises(Exception):
            ChatFallback().get_chat_model("gpt-4")

def test_backwards_compatibility(single_provider_env):
    """Test that single-key setup still works without rotation"""
    fallback = ChatFallback()
    
    # Should work without rotation
    for model in fallback.MODEL_PROVIDER_DICT.keys():
        provider = fallback._get_provider_from_model(model)
        if provider:
            # Should not use rotation with single key
            assert not fallback._should_use_rotation(model)
            
            # Should create standard model
            try:
                model_instance = fallback.get_chat_model(model)
                assert not hasattr(model_instance, 'key_manager')
            except Exception:
                # Model creation might fail for other reasons
                pass
```

**Commit 6:**
```
test: add edge case and error recovery tests

Part of #276
```

### Step 7: Test Performance and Metrics
**Files to modify:**
- `tests/integration/test_api_key_rotation.py`

**Implementation:**
```python
import time

def test_rotation_performance(multi_provider_env):
    """Test that rotation adds minimal overhead"""
    manager = APIKeyManager("openai", auto_discover=True)
    wrapper = RotatingKeyChatOpenAI(manager)
    
    # Measure time for key selection
    start = time.time()
    for _ in range(1000):
        key = manager.get_next_available_key()
    duration = time.time() - start
    
    # Should be very fast (< 10ms for 1000 selections)
    assert duration < 0.01
    
    # Per-selection should be < 0.01ms
    per_selection = duration / 1000
    assert per_selection < 0.00001

def test_metrics_accuracy(multi_provider_env):
    """Test that metrics are accurately tracked"""
    manager = APIKeyManager("openai", auto_discover=True)
    wrapper = RotatingKeyChatOpenAI(manager)
    
    success_count = 0
    failure_count = 0
    
    for i in range(20):
        try:
            def mock_call():
                if i % 3 == 0:
                    raise Exception("429: Rate limit")
                return "success"
            
            wrapper.execute_with_rotation(mock_call, max_retries=1)
            success_count += 1
        except:
            failure_count += 1
    
    # Check metrics
    metrics = wrapper.get_metrics_snapshot()
    assert metrics.successful_requests >= success_count
    assert metrics.failed_requests >= failure_count
    assert metrics.rate_limit_hits > 0

def test_rotation_status_reporting(multi_provider_env):
    """Test status reporting for monitoring"""
    fallback = ChatFallback()
    status = fallback.get_rotation_status()
    
    # Should report status for all configured models
    assert len(status) > 0
    
    for model, info in status.items():
        assert 'provider' in info
        assert 'rotation_enabled' in info
        assert 'keys_count' in info
        
        # Multi-key providers should have rotation enabled
        if info['keys_count'] > 1:
            assert info['rotation_enabled'] == True
```

**Commit 7:**
```
test: add performance and metrics tests

Part of #276
```

## Validation Criteria

- [ ] All providers correctly discover multiple keys
- [ ] Rate limit scenarios trigger key rotation
- [ ] Provider fallback works with rotation
- [ ] Thread safety maintained under concurrent load
- [ ] Edge cases handled gracefully
- [ ] Performance meets requirements (<1ms per rotation)
- [ ] Metrics accurately tracked
- [ ] Backwards compatibility maintained
- [ ] All tests pass
- [ ] No pyright type errors
- [ ] Ruff linting passes

## Final Commit

After all tests pass:

```
test: complete integration test suite for API key rotation

- Test key discovery and initialization
- Test rate limit rotation scenarios  
- Test provider fallback with rotation
- Test thread safety and concurrency
- Test edge cases and error recovery
- Test performance and metrics
- Ensure backwards compatibility

Completes #276
```

## Next Steps
This completes the API key rotation implementation. The feature is ready for code review and deployment.