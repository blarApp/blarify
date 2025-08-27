---
title: "Task 3: Provider Wrapper Base Class"
parent_issue: 276
task_number: 3
description: "Create abstract base wrapper class for intercepting LangChain provider API calls"
---

# Task 3: Provider Wrapper Base Class

## Context
With the APIKeyManager infrastructure in place, we now need to create an abstract wrapper class that provider-specific wrappers will inherit from. Each provider will implement its own error detection and rate limit handling logic.

## Objective
Create an abstract base wrapper class that defines the interface for provider-specific implementations. This class will handle the common retry and rotation logic while delegating provider-specific decisions to subclasses. Must be thread-safe for concurrent usage.

## Implementation Steps with Commits

### Step 1: Create Error Type Enum and Abstract Base Class
**Files to create/modify:**
- `blarify/agents/rotating_providers.py` (create)
- `tests/unit/agents/test_rotating_providers.py` (create)

**Implementation:**
```python
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional, Tuple
import logging
import threading

from blarify.agents.api_key_manager import APIKeyManager

logger = logging.getLogger(__name__)

class ErrorType(Enum):
    """Types of errors that can occur when calling providers"""
    RATE_LIMIT = "rate_limit"
    AUTH_ERROR = "auth_error"
    QUOTA_EXCEEDED = "quota_exceeded"
    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"

class RotatingProviderBase(ABC):
    """Abstract base class for providers with rotating API keys"""
    
    def __init__(self, key_manager: APIKeyManager, **kwargs: Any):
        self.key_manager = key_manager
        self.kwargs = kwargs
        self._current_key: Optional[str] = None
        self._lock = threading.RLock()  # For thread-safe operations
    
    @abstractmethod
    def _create_client(self, api_key: str) -> Any:
        """Create the underlying provider client with the given API key
        
        Args:
            api_key: The API key to use
            
        Returns:
            The provider-specific client instance
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the provider name for logging and identification"""
        pass
```

**Tests:**
- Test cannot instantiate abstract class
- Test ErrorType enum values

**Commit 1:**
```
feat: create ErrorType enum and abstract base class

Part of #276
```

### Step 2: Add Abstract Error Analysis Methods
**Files to modify:**
- `blarify/agents/rotating_providers.py`
- `tests/unit/agents/test_rotating_providers.py`

**Implementation:**
```python
@abstractmethod
def analyze_error(self, error: Exception) -> Tuple[ErrorType, Optional[int]]:
    """Analyze an error and determine its type and retry timing
    
    Args:
        error: The exception to analyze
        
    Returns:
        Tuple of (ErrorType, retry_after_seconds)
        retry_after_seconds is only set for RATE_LIMIT errors
    """
    pass

@abstractmethod
def extract_headers_from_error(self, error: Exception) -> Dict[str, str]:
    """Extract HTTP headers from provider-specific error if available
    
    Args:
        error: The exception that may contain headers
        
    Returns:
        Dictionary of headers (empty if none available)
    """
    pass
```

**Tests:**
- Test abstract method enforcement
- Create mock provider for testing

**Commit 2:**
```
feat: add abstract error analysis methods

Part of #276
```

### Step 3: Add Thread-Safe Core Retry Logic
**Files to modify:**
- `blarify/agents/rotating_providers.py`
- `tests/unit/agents/test_rotating_providers.py`

**Implementation:**
```python
import time
from typing import Callable, TypeVar

T = TypeVar('T')

def execute_with_rotation(self, func: Callable[[], T], max_retries: int = 3) -> T:
    """Execute function with automatic key rotation on errors
    
    Thread-safe execution with key rotation support.
    
    Args:
        func: The function to execute
        max_retries: Maximum number of retry attempts
        
    Returns:
        The result from func
        
    Raises:
        The last error if all retries fail
    """
    last_error = None
    keys_tried = set()
    
    for attempt in range(max_retries):
        # Thread-safe key selection
        with self._lock:
            key = self.key_manager.get_next_available_key()
            
            if not key:
                logger.error(f"No available keys for {self.get_provider_name()}")
                if last_error:
                    raise last_error
                raise RuntimeError(f"No available API keys for {self.get_provider_name()}")
            
            if key in keys_tried and len(keys_tried) == self.key_manager.get_available_count():
                # We've tried all available keys
                if last_error:
                    raise last_error
                raise RuntimeError(f"All available keys exhausted for {self.get_provider_name()}")
            
            keys_tried.add(key)
            self._current_key = key
        
        try:
            # Create client with current key and execute
            client = self._create_client(key)
            result = func()
            
            # Success - update metadata
            self._record_success(key)
            return result
            
        except Exception as e:
            last_error = e
            error_type, retry_after = self.analyze_error(e)
            
            if error_type == ErrorType.RATE_LIMIT:
                self.key_manager.mark_rate_limited(key, retry_after)
                logger.warning(f"Rate limit hit for {self.get_provider_name()} key {key[:10]}...")
                
            elif error_type == ErrorType.AUTH_ERROR:
                self.key_manager.mark_invalid(key)
                logger.error(f"Auth failed for {self.get_provider_name()} key {key[:10]}...")
                
            elif error_type == ErrorType.QUOTA_EXCEEDED:
                self.key_manager.mark_quota_exceeded(key)
                logger.error(f"Quota exceeded for {self.get_provider_name()} key {key[:10]}...")
                
            elif error_type == ErrorType.NON_RETRYABLE:
                # Don't retry non-retryable errors
                raise
            
            # Continue to next iteration for retryable errors
    
    # All retries exhausted
    raise last_error or RuntimeError(f"Max retries exceeded for {self.get_provider_name()}")
```

**Tests:**
- Test successful execution
- Test rotation on rate limit
- Test thread safety with concurrent calls
- Test non-retryable error propagation

**Commit 3:**
```
feat: add thread-safe retry logic with key rotation

Part of #276
```

### Step 4: Add Thread-Safe Metadata Management
**Files to modify:**
- `blarify/agents/rotating_providers.py`
- `tests/unit/agents/test_rotating_providers.py`

**Implementation:**
```python
from datetime import datetime

def _record_success(self, key: str) -> None:
    """Record successful request for a key (thread-safe)"""
    with self._lock:
        if key in self.key_manager.keys:
            metadata = self.key_manager.keys[key].metadata
            metadata['request_count'] = metadata.get('request_count', 0) + 1
            metadata['success_count'] = metadata.get('success_count', 0) + 1
            metadata['last_success'] = datetime.now().isoformat()

def _record_failure(self, key: str, error_type: ErrorType) -> None:
    """Record failed request for a key (thread-safe)"""
    with self._lock:
        if key in self.key_manager.keys:
            metadata = self.key_manager.keys[key].metadata
            metadata['request_count'] = metadata.get('request_count', 0) + 1
            metadata['failure_count'] = metadata.get('failure_count', 0) + 1
            metadata[f'{error_type.value}_count'] = metadata.get(f'{error_type.value}_count', 0) + 1
            metadata['last_failure'] = datetime.now().isoformat()
```

**Tests:**
- Test success recording with concurrent access
- Test failure recording with concurrent access
- Test metadata consistency

**Commit 4:**
```
feat: add thread-safe request metadata management

Part of #276
```

### Step 5: Add Thread-Safe Provider Metrics
**Files to modify:**
- `blarify/agents/rotating_providers.py`
- `tests/unit/agents/test_rotating_providers.py`

**Implementation:**
```python
from dataclasses import dataclass, field

@dataclass
class ProviderMetrics:
    """Metrics for provider usage"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limit_hits: int = 0
    auth_failures: int = 0
    quota_exceeded_count: int = 0
    key_rotations: int = 0
    last_rotation: Optional[datetime] = None
    error_breakdown: Dict[str, int] = field(default_factory=dict)

class RotatingProviderBase(ABC):
    def __init__(self, key_manager: APIKeyManager, **kwargs: Any):
        self.key_manager = key_manager
        self.kwargs = kwargs
        self._current_key: Optional[str] = None
        self._lock = threading.RLock()
        self.metrics = ProviderMetrics()
    
    def _update_metrics(self, error_type: Optional[ErrorType] = None) -> None:
        """Update provider metrics (thread-safe)"""
        with self._lock:
            self.metrics.total_requests += 1
            
            if error_type:
                self.metrics.failed_requests += 1
                self.metrics.error_breakdown[error_type.value] = \
                    self.metrics.error_breakdown.get(error_type.value, 0) + 1
                
                if error_type == ErrorType.RATE_LIMIT:
                    self.metrics.rate_limit_hits += 1
                elif error_type == ErrorType.AUTH_ERROR:
                    self.metrics.auth_failures += 1
                elif error_type == ErrorType.QUOTA_EXCEEDED:
                    self.metrics.quota_exceeded_count += 1
            else:
                self.metrics.successful_requests += 1
    
    def get_success_rate(self) -> float:
        """Get success rate as percentage (thread-safe)"""
        with self._lock:
            if self.metrics.total_requests == 0:
                return 0.0
            return (self.metrics.successful_requests / self.metrics.total_requests) * 100
    
    def get_metrics_snapshot(self) -> ProviderMetrics:
        """Get a snapshot of current metrics (thread-safe)"""
        with self._lock:
            import copy
            return copy.deepcopy(self.metrics)
```

**Tests:**
- Test metrics tracking with concurrent updates
- Test success rate calculation
- Test metrics snapshot consistency

**Commit 5:**
```
feat: add thread-safe provider metrics tracking

Part of #276
```

### Step 6: Add Test Utilities with Mock Provider
**Files to modify:**
- `tests/unit/agents/test_rotating_providers.py`

**Implementation:**
```python
class MockProvider(RotatingProviderBase):
    """Mock provider for testing base class functionality"""
    
    def _create_client(self, api_key: str) -> Any:
        return f"client_with_{api_key}"
    
    def get_provider_name(self) -> str:
        return "mock"
    
    def analyze_error(self, error: Exception) -> Tuple[ErrorType, Optional[int]]:
        error_str = str(error).lower()
        if "rate_limit" in error_str or "429" in error_str:
            # Extract retry time if present
            import re
            match = re.search(r'retry_after:(\d+)', error_str)
            retry_after = int(match.group(1)) if match else 60
            return (ErrorType.RATE_LIMIT, retry_after)
        elif "unauthorized" in error_str or "401" in error_str:
            return (ErrorType.AUTH_ERROR, None)
        elif "quota" in error_str:
            return (ErrorType.QUOTA_EXCEEDED, None)
        elif "retry" in error_str:
            return (ErrorType.RETRYABLE, None)
        else:
            return (ErrorType.NON_RETRYABLE, None)
    
    def extract_headers_from_error(self, error: Exception) -> Dict[str, str]:
        # Mock implementation
        if hasattr(error, 'headers'):
            return error.headers
        return {}
```

**Tests:**
- Test abstract base cannot be instantiated
- Test mock provider error analysis
- Test rotation behavior

**Commit 6:**
```
test: add mock provider for testing base class

Part of #276
```

### Step 7: Add LangChain Method Overrides
**Files to modify:**
- `blarify/agents/rotating_providers.py`
- `tests/unit/agents/test_rotating_providers.py`

**Implementation:**
```python
def invoke(self, *args: Any, **kwargs: Any) -> Any:
    """Override invoke to use rotation logic"""
    def _invoke():
        client = self._create_client(self._current_key)
        return client.invoke(*args, **kwargs)
    
    return self.execute_with_rotation(_invoke)

def stream(self, *args: Any, **kwargs: Any) -> Any:
    """Override stream to use rotation logic"""
    def _stream():
        client = self._create_client(self._current_key)
        return client.stream(*args, **kwargs)
    
    return self.execute_with_rotation(_stream)

def batch(self, *args: Any, **kwargs: Any) -> Any:
    """Override batch to use rotation logic"""
    def _batch():
        client = self._create_client(self._current_key)
        return client.batch(*args, **kwargs)
    
    return self.execute_with_rotation(_batch)
```

**Tests:**
- Test invoke with rotation
- Test stream with rotation
- Test batch with rotation

**Commit 7:**
```
feat: add LangChain method overrides to base class

Part of #276
```

### Step 8: Add Thread Safety Tests
**Files to modify:**
- `tests/unit/agents/test_rotating_providers.py`

**Implementation:**
```python
import threading
import time

def test_concurrent_key_rotation():
    """Test thread safety with concurrent requests"""
    manager = APIKeyManager("test", auto_discover=False)
    manager.add_key("key1")
    manager.add_key("key2")
    manager.add_key("key3")
    
    provider = MockProvider(manager)
    
    results = []
    errors = []
    
    def make_request(request_id: int):
        try:
            # Simulate some requests failing with rate limits
            def api_call():
                if request_id % 3 == 0:
                    raise Exception("rate_limit retry_after:5")
                return f"success_{request_id}"
            
            result = provider.execute_with_rotation(api_call)
            results.append(result)
        except Exception as e:
            errors.append(str(e))
    
    # Launch multiple threads
    threads = []
    for i in range(50):
        t = threading.Thread(target=make_request, args=(i,))
        threads.append(t)
        t.start()
    
    # Wait for all threads
    for t in threads:
        t.join()
    
    # Verify metrics consistency
    metrics = provider.get_metrics_snapshot()
    assert metrics.total_requests == 50
    assert metrics.rate_limit_hits > 0
    assert len(results) + len(errors) == 50

def test_metrics_thread_safety():
    """Test that metrics updates are thread-safe"""
    manager = APIKeyManager("test", auto_discover=False)
    manager.add_key("key1")
    
    provider = MockProvider(manager)
    
    def update_metrics():
        for _ in range(100):
            provider._update_metrics()
            provider._update_metrics(ErrorType.RATE_LIMIT)
    
    threads = [threading.Thread(target=update_metrics) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    metrics = provider.get_metrics_snapshot()
    # 10 threads * 200 updates each = 2000 total
    assert metrics.total_requests == 2000
    assert metrics.successful_requests == 1000
    assert metrics.rate_limit_hits == 1000
```

**Commit 8:**
```
test: add thread safety tests for concurrent usage

Part of #276
```

## Validation Criteria

- [ ] Abstract class cannot be instantiated directly
- [ ] ErrorType enum is used for all error classification
- [ ] All operations are thread-safe with proper locking
- [ ] Metrics updates are atomic and consistent
- [ ] Concurrent requests don't cause race conditions
- [ ] Mock provider enables comprehensive testing
- [ ] No pyright type errors
- [ ] Ruff linting passes
- [ ] All commits made incrementally

## Next Steps
After completing this task, proceed to Task 4: Implement OpenAI-specific provider wrapper with OpenAI's specific rate limit detection and header parsing.