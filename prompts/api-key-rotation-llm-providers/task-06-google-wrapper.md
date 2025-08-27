---
title: "Task 6: Google Provider Wrapper Implementation"
parent_issue: 276
task_number: 6
description: "Implement Google-specific provider wrapper with rate limit detection"
---

# Task 6: Google Provider Wrapper Implementation

## Context
Implement the Google-specific wrapper that handles Gemini/Vertex AI API's rate limit errors. Google is unique in not providing rate limit headers.

## Objective
Create `RotatingKeyChatGoogle` class that extends `RotatingProviderBase` and integrates with LangChain's ChatGoogleGenerativeAI.

## Google-Specific Behavior
Based on the original plan, Google:
- Does NOT provide custom `X-RateLimit` headers
- Rate limiting conveyed only through error codes and messages
- No specific reset time information in headers
- Maps to internal `RESOURCE_EXHAUSTED` status
- Requires client-side backoff strategy

## Implementation Steps with Commits

### Step 1: Create Google Wrapper Class
**Files to create/modify:**
- `blarify/agents/rotating_google.py` (create)
- `tests/unit/agents/test_rotating_google.py` (create)

**Implementation:**
```python
from typing import Any, Dict, Optional, Tuple
import re

from langchain_google_genai import ChatGoogleGenerativeAI
from blarify.agents.rotating_providers import RotatingProviderBase, ErrorType
from blarify.agents.api_key_manager import APIKeyManager

import logging
logger = logging.getLogger(__name__)

class RotatingKeyChatGoogle(RotatingProviderBase):
    """Google chat model with automatic key rotation"""
    
    def __init__(self, key_manager: APIKeyManager, **kwargs: Any):
        super().__init__(key_manager, **kwargs)
        self.model_kwargs = {k: v for k, v in kwargs.items() if k != 'google_api_key'}
        # Track exponential backoff per key
        self._backoff_multipliers: Dict[str, int] = {}
    
    def _create_client(self, api_key: str) -> ChatGoogleGenerativeAI:
        """Create ChatGoogleGenerativeAI instance with specific API key"""
        return ChatGoogleGenerativeAI(google_api_key=api_key, **self.model_kwargs)
    
    def get_provider_name(self) -> str:
        """Return provider name for logging"""
        return "google"
```

**Commit 1:**
```
feat: create RotatingKeyChatGoogle wrapper class

Part of #276
```

### Step 2: Implement Google Error Analysis
**Files to modify:**
- `blarify/agents/rotating_google.py`
- `tests/unit/agents/test_rotating_google.py`

**Implementation:**
```python
def analyze_error(self, error: Exception) -> Tuple[ErrorType, Optional[int]]:
    """Analyze Google-specific errors
    
    Google errors include:
    - 429 / RESOURCE_EXHAUSTED for rate limits
    - No headers available, must use exponential backoff
    """
    error_str = str(error).lower()
    
    # Check for rate limit error (429 or RESOURCE_EXHAUSTED)
    if "429" in error_str or "resource_exhausted" in error_str or "quota exceeded" in error_str:
        # Google doesn't provide retry-after, use exponential backoff
        retry_after = self._calculate_backoff()
        return (ErrorType.RATE_LIMIT, retry_after)
    
    # Check for authentication errors
    elif "401" in error_str or "403" in error_str or "unauthenticated" in error_str:
        return (ErrorType.AUTH_ERROR, None)
    
    # Check for quota exceeded (different from rate limit)
    elif "quota" in error_str and "increase" in error_str:
        return (ErrorType.QUOTA_EXCEEDED, None)
    
    # Check if retryable
    elif any(term in error_str for term in ["timeout", "connection", "network", "unavailable"]):
        return (ErrorType.RETRYABLE, None)
    
    return (ErrorType.NON_RETRYABLE, None)

def _calculate_backoff(self) -> int:
    """Calculate exponential backoff for current key"""
    if not self._current_key:
        return 60
    
    # Get current backoff multiplier for this key
    multiplier = self._backoff_multipliers.get(self._current_key, 0)
    
    # Calculate backoff: 2^multiplier seconds, max 300 seconds
    backoff = min(2 ** multiplier, 300)
    
    # Increment multiplier for next time
    self._backoff_multipliers[self._current_key] = multiplier + 1
    
    logger.info(f"Google: Using exponential backoff of {backoff}s for key {self._current_key[:10]}...")
    return backoff

def _reset_backoff(self, key: str) -> None:
    """Reset backoff multiplier after successful request"""
    if key in self._backoff_multipliers:
        del self._backoff_multipliers[key]
```

**Commit 2:**
```
feat: implement Google error analysis with exponential backoff

Part of #276
```

### Step 3: Add Header Extraction (Minimal for Google)
**Files to modify:**
- `blarify/agents/rotating_google.py`
- `tests/unit/agents/test_rotating_google.py`

**Implementation:**
```python
def extract_headers_from_error(self, error: Exception) -> Dict[str, str]:
    """Extract headers from Google errors
    
    Google doesn't provide rate limit headers, but we extract
    any available headers for debugging
    """
    headers = {}
    
    if hasattr(error, 'response') and hasattr(error.response, 'headers'):
        # Get any headers that might be useful for debugging
        response_headers = error.response.headers
        
        # Google might have some standard headers
        standard_headers = ['date', 'content-type', 'server']
        
        for header in standard_headers:
            if header in response_headers:
                headers[header] = response_headers[header]
    
    return headers
```

**Commit 3:**
```
feat: add minimal header extraction for Google

Part of #276
```

### Step 4: Override Execute Method with Backoff Reset
**Files to modify:**
- `blarify/agents/rotating_google.py`
- `tests/unit/agents/test_rotating_google.py`

**Implementation:**
```python
def execute_with_rotation(self, func: Callable[[], T], max_retries: int = 3) -> T:
    """Override to add backoff reset on success"""
    try:
        result = super().execute_with_rotation(func, max_retries)
        # Reset backoff on success
        if self._current_key:
            self._reset_backoff(self._current_key)
        return result
    except Exception as e:
        # Re-raise the exception
        raise
```

**Commit 4:**
```
feat: add backoff reset on successful requests

Part of #276
```

### Step 5: Add Unit Tests
**Files to modify:**
- `tests/unit/agents/test_rotating_google.py`

**Implementation:**
```python
import pytest
from unittest.mock import Mock
from blarify.agents.rotating_google import RotatingKeyChatGoogle
from blarify.agents.api_key_manager import APIKeyManager
from blarify.agents.rotating_providers import ErrorType

def test_google_resource_exhausted_detection():
    """Test Google RESOURCE_EXHAUSTED error detection"""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")
    
    wrapper = RotatingKeyChatGoogle(manager)
    wrapper._current_key = "test-key-123"
    
    error = Exception("Error code: 429, Status: RESOURCE_EXHAUSTED")
    error_type, retry = wrapper.analyze_error(error)
    assert error_type == ErrorType.RATE_LIMIT
    assert retry == 1  # First backoff is 2^0 = 1

def test_google_exponential_backoff():
    """Test exponential backoff calculation"""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")
    
    wrapper = RotatingKeyChatGoogle(manager)
    wrapper._current_key = "test-key-123"
    
    # First backoff
    assert wrapper._calculate_backoff() == 1
    # Second backoff
    assert wrapper._calculate_backoff() == 2
    # Third backoff
    assert wrapper._calculate_backoff() == 4
    # Fourth backoff
    assert wrapper._calculate_backoff() == 8

def test_google_backoff_reset():
    """Test backoff reset after success"""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")
    
    wrapper = RotatingKeyChatGoogle(manager)
    wrapper._current_key = "test-key-123"
    
    # Set some backoff
    wrapper._backoff_multipliers["test-key-123"] = 3
    
    # Reset backoff
    wrapper._reset_backoff("test-key-123")
    
    # Next backoff should start from beginning
    assert wrapper._calculate_backoff() == 1

def test_google_quota_vs_rate_limit():
    """Test distinguishing quota exceeded from rate limit"""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")
    
    wrapper = RotatingKeyChatGoogle(manager)
    
    # Rate limit error
    error1 = Exception("429: RESOURCE_EXHAUSTED")
    error_type, _ = wrapper.analyze_error(error1)
    assert error_type == ErrorType.RATE_LIMIT
    
    # Quota error
    error2 = Exception("Quota exceeded for project. Please submit a quota increase request.")
    error_type, _ = wrapper.analyze_error(error2)
    assert error_type == ErrorType.QUOTA_EXCEEDED

def test_google_no_headers():
    """Test that Google doesn't return rate limit headers"""
    manager = APIKeyManager("google", auto_discover=False)
    manager.add_key("test-key-123")
    
    wrapper = RotatingKeyChatGoogle(manager)
    
    error = Mock()
    error.response = Mock()
    error.response.headers = {'date': '2024-01-01', 'server': 'Google'}
    
    headers = wrapper.extract_headers_from_error(error)
    # Should not have rate limit headers
    assert 'x-ratelimit' not in str(headers).lower()
    assert 'retry-after' not in headers
```

**Commit 5:**
```
test: add comprehensive tests for Google wrapper

Part of #276
```

## Validation Criteria

- [ ] Google wrapper correctly extends base class
- [ ] Error analysis detects RESOURCE_EXHAUSTED status
- [ ] Exponential backoff implemented correctly
- [ ] Backoff resets on successful requests
- [ ] No reliance on rate limit headers
- [ ] Thread-safe operation maintained
- [ ] No pyright type errors
- [ ] Ruff linting passes
- [ ] All commits made incrementally

## Next Steps
After completing this task, proceed to Task 7: Integrate with ChatFallback.