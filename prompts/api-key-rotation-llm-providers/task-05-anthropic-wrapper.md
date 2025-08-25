---
title: "Task 5: Anthropic Provider Wrapper Implementation"
parent_issue: 276
task_number: 5
description: "Implement Anthropic-specific provider wrapper with rate limit detection and header parsing"
---

# Task 5: Anthropic Provider Wrapper Implementation

## Context
Implement the Anthropic-specific wrapper that handles Claude API's rate limit headers and error responses.

## Objective
Create `RotatingKeyChatAnthropic` class that extends `RotatingProviderBase` and integrates with LangChain's ChatAnthropic.

## Anthropic-Specific Behavior
Based on the original plan, Anthropic provides:
- `Retry-After`: Seconds to wait before retrying (on 429 responses)
- `anthropic-ratelimit-requests-limit`: Request limit
- `anthropic-ratelimit-requests-remaining`: Remaining requests
- `anthropic-ratelimit-requests-reset`: Reset timestamp (RFC 3339)
- Separate headers for input/output token tracking
- Can trigger 429 on sharp usage spikes

## Implementation Steps with Commits

### Step 1: Create Anthropic Wrapper Class
**Files to create/modify:**
- `blarify/agents/rotating_anthropic.py` (create)
- `tests/unit/agents/test_rotating_anthropic.py` (create)

**Implementation:**
```python
from typing import Any, Dict, Optional, Tuple
from datetime import datetime
import re

from langchain_anthropic import ChatAnthropic
from blarify.agents.rotating_providers import RotatingProviderBase, ErrorType
from blarify.agents.api_key_manager import APIKeyManager

import logging
logger = logging.getLogger(__name__)

class RotatingKeyChatAnthropic(RotatingProviderBase):
    """Anthropic chat model with automatic key rotation"""
    
    def __init__(self, key_manager: APIKeyManager, **kwargs: Any):
        super().__init__(key_manager, **kwargs)
        self.model_kwargs = {k: v for k, v in kwargs.items() if k != 'api_key'}
    
    def _create_client(self, api_key: str) -> ChatAnthropic:
        """Create ChatAnthropic instance with specific API key"""
        return ChatAnthropic(anthropic_api_key=api_key, **self.model_kwargs)
    
    def get_provider_name(self) -> str:
        """Return provider name for logging"""
        return "anthropic"
```

**Commit 1:**
```
feat: create RotatingKeyChatAnthropic wrapper class

Part of #276
```

### Step 2: Implement Anthropic Error Analysis
**Files to modify:**
- `blarify/agents/rotating_anthropic.py`
- `tests/unit/agents/test_rotating_anthropic.py`

**Implementation:**
```python
def analyze_error(self, error: Exception) -> Tuple[ErrorType, Optional[int]]:
    """Analyze Anthropic-specific errors
    
    Anthropic errors include:
    - rate_limit_error with Retry-After header
    - authentication errors
    - Can trigger on usage spikes
    """
    error_str = str(error).lower()
    
    # Check for rate limit error
    if "rate_limit_error" in error_str or "429" in error_str or "rate limit" in error_str:
        # Anthropic provides Retry-After header
        retry_after = self._extract_retry_after(error)
        return (ErrorType.RATE_LIMIT, retry_after)
    
    # Check for authentication errors
    elif "401" in error_str or "403" in error_str or "authentication" in error_str:
        return (ErrorType.AUTH_ERROR, None)
    
    # Check for quota exceeded
    elif "quota" in error_str:
        return (ErrorType.QUOTA_EXCEEDED, None)
    
    # Check if retryable
    elif any(term in error_str for term in ["timeout", "connection", "network"]):
        return (ErrorType.RETRYABLE, None)
    
    return (ErrorType.NON_RETRYABLE, None)

def _extract_retry_after(self, error: Any) -> int:
    """Extract Retry-After value from error or default"""
    # Check for Retry-After in headers
    headers = self.extract_headers_from_error(error)
    if 'retry-after' in headers:
        try:
            return int(headers['retry-after'])
        except ValueError:
            pass
    
    # Default for Anthropic
    return 30  # Anthropic typically has shorter cooldowns
```

**Commit 2:**
```
feat: implement Anthropic-specific error analysis

Part of #276
```

### Step 3: Add Header Extraction for Anthropic
**Files to modify:**
- `blarify/agents/rotating_anthropic.py`
- `tests/unit/agents/test_rotating_anthropic.py`

**Implementation:**
```python
def extract_headers_from_error(self, error: Exception) -> Dict[str, str]:
    """Extract rate limit headers from Anthropic errors
    
    Anthropic headers:
    - retry-after
    - anthropic-ratelimit-requests-limit
    - anthropic-ratelimit-requests-remaining
    - anthropic-ratelimit-requests-reset
    - anthropic-ratelimit-input-tokens-*
    - anthropic-ratelimit-output-tokens-*
    """
    headers = {}
    
    if hasattr(error, 'response') and hasattr(error.response, 'headers'):
        response_headers = error.response.headers
        
        # Extract Anthropic-specific headers
        anthropic_headers = [
            'retry-after',
            'anthropic-ratelimit-requests-limit',
            'anthropic-ratelimit-requests-remaining',
            'anthropic-ratelimit-requests-reset',
            'anthropic-ratelimit-input-tokens-limit',
            'anthropic-ratelimit-input-tokens-remaining',
            'anthropic-ratelimit-input-tokens-reset',
            'anthropic-ratelimit-output-tokens-limit',
            'anthropic-ratelimit-output-tokens-remaining',
            'anthropic-ratelimit-output-tokens-reset'
        ]
        
        for header in anthropic_headers:
            if header in response_headers:
                headers[header] = response_headers[header]
    
    return headers
```

**Commit 3:**
```
feat: add Anthropic rate limit header extraction

Part of #276
```

### Step 4: Add Spike Detection and Cooldown Calculation
**Files to modify:**
- `blarify/agents/rotating_anthropic.py`
- `tests/unit/agents/test_rotating_anthropic.py`

**Implementation:**
```python
def _calculate_cooldown_from_headers(self, headers: Dict[str, str]) -> Optional[int]:
    """Calculate cooldown from Anthropic headers
    
    Uses RFC 3339 timestamps in reset headers
    """
    # First check Retry-After (highest priority)
    if 'retry-after' in headers:
        try:
            return int(headers['retry-after'])
        except ValueError:
            pass
    
    # Check reset timestamps
    for reset_header in ['anthropic-ratelimit-requests-reset',
                         'anthropic-ratelimit-input-tokens-reset',
                         'anthropic-ratelimit-output-tokens-reset']:
        if reset_header in headers:
            try:
                # Parse RFC 3339 timestamp
                reset_time = datetime.fromisoformat(headers[reset_header].replace('Z', '+00:00'))
                now = datetime.now(reset_time.tzinfo)
                delta = (reset_time - now).total_seconds()
                if delta > 0:
                    return int(delta) + 1  # Add 1 second buffer
            except (ValueError, AttributeError):
                pass
    
    return None

def _is_spike_triggered(self, headers: Dict[str, str]) -> bool:
    """Check if rate limit was triggered by usage spike"""
    # Anthropic can trigger 429 even with remaining quota on spikes
    remaining = headers.get('anthropic-ratelimit-requests-remaining', '0')
    try:
        if int(remaining) > 0:
            logger.warning(f"Anthropic: Rate limit triggered by spike (remaining: {remaining})")
            return True
    except ValueError:
        pass
    return False
```

**Commit 4:**
```
feat: add spike detection and cooldown calculation for Anthropic

Part of #276
```

### Step 5: Add Unit Tests
**Files to modify:**
- `tests/unit/agents/test_rotating_anthropic.py`

**Implementation:**
```python
import pytest
from unittest.mock import Mock
from blarify.agents.rotating_anthropic import RotatingKeyChatAnthropic
from blarify.agents.api_key_manager import APIKeyManager
from blarify.agents.rotating_providers import ErrorType

def test_anthropic_rate_limit_with_retry_after():
    """Test Anthropic rate limit with Retry-After header"""
    manager = APIKeyManager("anthropic", auto_discover=False)
    manager.add_key("sk-ant-test123")
    
    wrapper = RotatingKeyChatAnthropic(manager)
    
    # Mock error with Retry-After
    error = Mock()
    error.__str__ = lambda self: "rate_limit_error: Your account has hit a rate limit"
    error.response = Mock()
    error.response.headers = {'retry-after': '15'}
    
    error_type, retry = wrapper.analyze_error(error)
    assert error_type == ErrorType.RATE_LIMIT
    assert retry == 15

def test_anthropic_spike_detection():
    """Test detection of spike-triggered rate limits"""
    manager = APIKeyManager("anthropic", auto_discover=False)
    manager.add_key("sk-ant-test123")
    
    wrapper = RotatingKeyChatAnthropic(manager)
    
    headers = {
        'anthropic-ratelimit-requests-remaining': '50',
        'retry-after': '5'
    }
    
    assert wrapper._is_spike_triggered(headers) == True

def test_rfc3339_timestamp_parsing():
    """Test parsing of RFC 3339 timestamps in headers"""
    manager = APIKeyManager("anthropic", auto_discover=False)
    manager.add_key("sk-ant-test123")
    
    wrapper = RotatingKeyChatAnthropic(manager)
    
    from datetime import datetime, timedelta, timezone
    future_time = datetime.now(timezone.utc) + timedelta(seconds=30)
    headers = {
        'anthropic-ratelimit-requests-reset': future_time.isoformat()
    }
    
    cooldown = wrapper._calculate_cooldown_from_headers(headers)
    assert cooldown is not None
    assert 28 <= cooldown <= 32  # Allow some variance for test execution

def test_anthropic_auth_error():
    """Test Anthropic authentication error detection"""
    manager = APIKeyManager("anthropic", auto_discover=False)
    manager.add_key("sk-ant-test123")
    
    wrapper = RotatingKeyChatAnthropic(manager)
    
    error = Exception("Error: 401 - Authentication failed")
    error_type, retry = wrapper.analyze_error(error)
    assert error_type == ErrorType.AUTH_ERROR
    assert retry is None
```

**Commit 5:**
```
test: add comprehensive tests for Anthropic wrapper

Part of #276
```

## Validation Criteria

- [ ] Anthropic wrapper correctly extends base class
- [ ] Error analysis handles Anthropic-specific errors
- [ ] Retry-After header properly extracted and used
- [ ] RFC 3339 timestamps parsed correctly
- [ ] Spike detection identifies unusual rate limits
- [ ] Thread-safe operation maintained
- [ ] No pyright type errors
- [ ] Ruff linting passes
- [ ] All commits made incrementally

## Next Steps
After completing this task, proceed to Task 6: Implement Google provider wrapper.