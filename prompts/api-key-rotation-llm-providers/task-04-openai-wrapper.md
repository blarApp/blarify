---
title: "Task 4: OpenAI Provider Wrapper Implementation"
parent_issue: 276
task_number: 4
description: "Implement OpenAI-specific provider wrapper with rate limit detection and header parsing"
---

# Task 4: OpenAI Provider Wrapper Implementation

## Context
With the abstract base class in place, we now implement the OpenAI-specific wrapper that handles OpenAI's rate limit headers and error responses.

## Objective
Create `RotatingKeyChatOpenAI` class that extends `RotatingProviderBase` and integrates with LangChain's ChatOpenAI, providing OpenAI-specific error detection and header parsing.

## OpenAI-Specific Behavior
Based on the original plan, OpenAI provides:
- `X-RateLimit-Limit-Requests`: Maximum requests per minute
- `X-RateLimit-Remaining-Requests`: Requests remaining
- `X-RateLimit-Reset-Requests`: Time until request count resets
- `X-RateLimit-Limit-Tokens`: Maximum tokens per minute
- `X-RateLimit-Remaining-Tokens`: Tokens remaining
- `X-RateLimit-Reset-Tokens`: Time until token count resets
- Error messages include specific wait times

## Implementation Steps with Commits

### Step 1: Create OpenAI Wrapper Class
**Files to create/modify:**
- `blarify/agents/rotating_openai.py` (create)
- `tests/unit/agents/test_rotating_openai.py` (create)

**Implementation:**
```python
from typing import Any, Dict, Optional, Tuple
import re
from datetime import datetime, timedelta

from langchain_openai import ChatOpenAI
from blarify.agents.rotating_providers import RotatingProviderBase, ErrorType
from blarify.agents.api_key_manager import APIKeyManager

import logging
logger = logging.getLogger(__name__)

class RotatingKeyChatOpenAI(RotatingProviderBase):
    """OpenAI chat model with automatic key rotation"""
    
    def __init__(self, key_manager: APIKeyManager, **kwargs: Any):
        super().__init__(key_manager, **kwargs)
        # Remove api_key from kwargs if present (we'll set it per request)
        self.model_kwargs = {k: v for k, v in kwargs.items() if k != 'api_key'}
    
    def _create_client(self, api_key: str) -> ChatOpenAI:
        """Create ChatOpenAI instance with specific API key"""
        return ChatOpenAI(api_key=api_key, **self.model_kwargs)
    
    def get_provider_name(self) -> str:
        """Return provider name for logging"""
        return "openai"
```

**Tests:**
- Test initialization
- Test client creation

**Commit 1:**
```
feat: create RotatingKeyChatOpenAI wrapper class

Part of #276
```

### Step 2: Implement OpenAI Error Analysis
**Files to modify:**
- `blarify/agents/rotating_openai.py`
- `tests/unit/agents/test_rotating_openai.py`

**Implementation:**
```python
def analyze_error(self, error: Exception) -> Tuple[ErrorType, Optional[int]]:
    """Analyze OpenAI-specific errors
    
    OpenAI errors include:
    - Rate limit errors (429) with retry timing
    - Authentication errors (401/403)
    - Quota exceeded errors
    """
    error_str = str(error).lower()
    error_type_name = type(error).__name__.lower()
    
    # Check for rate limit error (429)
    if "429" in error_str or "rate_limit" in error_type_name or "rate limit" in error_str:
        # Extract wait time from error message
        # Example: "Rate limit reached for gpt-4 model (requests per min). Please try again in 20s."
        retry_after = self._extract_retry_seconds(error_str)
        return (ErrorType.RATE_LIMIT, retry_after)
    
    # Check for authentication errors
    elif "401" in error_str or "403" in error_str or "unauthorized" in error_str or "invalid api key" in error_str:
        return (ErrorType.AUTH_ERROR, None)
    
    # Check for quota exceeded
    elif "quota" in error_str and "exceeded" in error_str:
        return (ErrorType.QUOTA_EXCEEDED, None)
    
    # Check if retryable (connection errors, timeouts)
    elif any(term in error_str for term in ["timeout", "connection", "network"]):
        return (ErrorType.RETRYABLE, None)
    
    # Default to non-retryable
    return (ErrorType.NON_RETRYABLE, None)

def _extract_retry_seconds(self, error_str: str) -> int:
    """Extract retry seconds from OpenAI error message"""
    # Pattern: "try again in 20s" or "retry after 60 seconds"
    patterns = [
        r"try again in (\d+)s",
        r"try again in (\d+) second",
        r"retry after (\d+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, error_str, re.IGNORECASE)
        if match:
            return int(match.group(1))
    
    # Default to 60 seconds if not found
    return 60
```

**Tests:**
- Test rate limit error detection
- Test retry time extraction
- Test auth error detection
- Test various error formats

**Commit 2:**
```
feat: implement OpenAI-specific error analysis

Part of #276
```

### Step 3: Add Header Extraction for OpenAI
**Files to modify:**
- `blarify/agents/rotating_openai.py`
- `tests/unit/agents/test_rotating_openai.py`

**Implementation:**
```python
def extract_headers_from_error(self, error: Exception) -> Dict[str, str]:
    """Extract rate limit headers from OpenAI errors
    
    OpenAI includes headers in some error responses:
    - X-RateLimit-Limit-Requests
    - X-RateLimit-Remaining-Requests
    - X-RateLimit-Reset-Requests
    - X-RateLimit-Limit-Tokens
    - X-RateLimit-Remaining-Tokens
    - X-RateLimit-Reset-Tokens
    """
    headers = {}
    
    # Check if error has response attribute (common in HTTP errors)
    if hasattr(error, 'response') and hasattr(error.response, 'headers'):
        response_headers = error.response.headers
        
        # Extract OpenAI-specific headers
        openai_headers = [
            'x-ratelimit-limit-requests',
            'x-ratelimit-remaining-requests',
            'x-ratelimit-reset-requests',
            'x-ratelimit-limit-tokens',
            'x-ratelimit-remaining-tokens',
            'x-ratelimit-reset-tokens'
        ]
        
        for header in openai_headers:
            if header in response_headers:
                headers[header] = response_headers[header]
    
    return headers
```

**Tests:**
- Test header extraction from error
- Test missing headers handling
- Test header normalization

**Commit 3:**
```
feat: add OpenAI rate limit header extraction

Part of #276
```

### Step 4: Add Proactive Rate Limit Monitoring
**Files to modify:**
- `blarify/agents/rotating_openai.py`
- `tests/unit/agents/test_rotating_openai.py`

**Implementation:**
```python
def _should_preemptively_rotate(self, headers: Dict[str, str]) -> bool:
    """Check if we should rotate keys proactively based on headers"""
    if not headers:
        return False
    
    # Check remaining requests
    remaining_requests = headers.get('x-ratelimit-remaining-requests')
    if remaining_requests:
        try:
            if int(remaining_requests) <= 1:
                logger.info("OpenAI: Proactively rotating due to low remaining requests")
                return True
        except ValueError:
            pass
    
    # Check remaining tokens
    remaining_tokens = headers.get('x-ratelimit-remaining-tokens')
    if remaining_tokens:
        try:
            if int(remaining_tokens) <= 100:  # Threshold for token rotation
                logger.info("OpenAI: Proactively rotating due to low remaining tokens")
                return True
        except ValueError:
            pass
    
    return False

def _calculate_cooldown_from_headers(self, headers: Dict[str, str]) -> Optional[int]:
    """Calculate cooldown period from reset headers"""
    # Try to get reset time for requests
    reset_requests = headers.get('x-ratelimit-reset-requests')
    reset_tokens = headers.get('x-ratelimit-reset-tokens')
    
    reset_time = reset_requests or reset_tokens
    if reset_time:
        try:
            # Parse timestamp and calculate seconds until reset
            reset_dt = datetime.fromisoformat(reset_time.replace('Z', '+00:00'))
            now = datetime.now(reset_dt.tzinfo)
            delta = (reset_dt - now).total_seconds()
            return max(1, int(delta))  # At least 1 second
        except (ValueError, AttributeError):
            pass
    
    return None
```

**Tests:**
- Test proactive rotation logic
- Test cooldown calculation from headers
- Test edge cases

**Commit 4:**
```
feat: add proactive rate limit monitoring for OpenAI

Part of #276
```

### Step 5: Add OpenAI-Specific Configuration
**Files to modify:**
- `blarify/agents/rotating_openai.py`
- `tests/unit/agents/test_rotating_openai.py`

**Implementation:**
```python
from dataclasses import dataclass

@dataclass
class OpenAIRotationConfig:
    """Configuration specific to OpenAI rotation"""
    proactive_rotation_threshold_requests: int = 1
    proactive_rotation_threshold_tokens: int = 100
    default_cooldown_seconds: int = 60
    respect_retry_after: bool = True
    
class RotatingKeyChatOpenAI(RotatingProviderBase):
    def __init__(self, key_manager: APIKeyManager, 
                 rotation_config: Optional[OpenAIRotationConfig] = None,
                 **kwargs: Any):
        super().__init__(key_manager, **kwargs)
        self.rotation_config = rotation_config or OpenAIRotationConfig()
        self.model_kwargs = {k: v for k, v in kwargs.items() if k != 'api_key'}
```

**Tests:**
- Test custom configuration
- Test default configuration
- Test configuration effects

**Commit 5:**
```
feat: add OpenAI-specific rotation configuration

Part of #276
```

### Step 6: Add Unit Tests for OpenAI Wrapper
**Files to modify:**
- `tests/unit/agents/test_rotating_openai.py`

**Implementation:**
```python
import pytest
from unittest.mock import Mock, patch
from blarify.agents.rotating_openai import RotatingKeyChatOpenAI
from blarify.agents.api_key_manager import APIKeyManager

def test_openai_rate_limit_detection():
    """Test OpenAI-specific rate limit error detection"""
    manager = APIKeyManager("openai", auto_discover=False)
    manager.add_key("sk-test123")
    
    wrapper = RotatingKeyChatOpenAI(manager)
    
    # Test various OpenAI error formats
    error1 = Exception("Rate limit reached for gpt-4 model (requests per min). Please try again in 20s.")
    error_type, retry = wrapper.analyze_error(error1)
    assert error_type == ErrorType.RATE_LIMIT
    assert retry == 20
    
    error2 = Exception("Error code: 429 - You exceeded your current quota")
    error_type, retry = wrapper.analyze_error(error2)
    assert error_type == ErrorType.RATE_LIMIT
    assert retry == 60  # Default

def test_openai_auth_error_detection():
    """Test OpenAI authentication error detection"""
    manager = APIKeyManager("openai", auto_discover=False)
    manager.add_key("sk-test123")
    
    wrapper = RotatingKeyChatOpenAI(manager)
    
    error = Exception("Error code: 401 - Invalid API key provided")
    error_type, retry = wrapper.analyze_error(error)
    assert error_type == ErrorType.AUTH_ERROR
    assert retry is None

def test_header_extraction():
    """Test extraction of OpenAI rate limit headers"""
    manager = APIKeyManager("openai", auto_discover=False)
    manager.add_key("sk-test123")
    
    wrapper = RotatingKeyChatOpenAI(manager)
    
    # Mock error with headers
    error = Mock()
    error.response = Mock()
    error.response.headers = {
        'x-ratelimit-remaining-requests': '5',
        'x-ratelimit-reset-requests': '2024-01-01T00:00:00Z'
    }
    
    headers = wrapper.extract_headers_from_error(error)
    assert 'x-ratelimit-remaining-requests' in headers
    assert headers['x-ratelimit-remaining-requests'] == '5'
```

**Commit 6:**
```
test: add comprehensive tests for OpenAI wrapper

Part of #276
```

## Validation Criteria

- [ ] OpenAI wrapper correctly extends base class
- [ ] Error analysis handles all OpenAI error formats
- [ ] Header extraction works for rate limit headers
- [ ] Proactive rotation based on remaining quota
- [ ] LangChain methods properly wrapped
- [ ] Thread-safe operation maintained
- [ ] No pyright type errors
- [ ] Ruff linting passes
- [ ] All commits made incrementally

## Next Steps
After completing this task, proceed to Task 5: Implement Anthropic-specific provider wrapper.