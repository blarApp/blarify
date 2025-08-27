---
title: "Task 1: API Key Manager Core Infrastructure"
parent_issue: 276
task_number: 1
description: "Create the foundational APIKeyManager class with thread-safe state management"
---

# Task 1: API Key Manager Core Infrastructure

## Context
This is the first task in implementing API key rotation for LLM providers (Issue #276). We need to create the core infrastructure that will manage multiple API keys, track their states, and provide thread-safe operations.

## Objective
Create the foundational `APIKeyManager` class that will be the backbone of our key rotation system. This class will handle key states, cooldown periods, and provide thread-safe key selection.

## Implementation Steps with Commits

### Step 1: Create KeyStatus Enum
**Files to create/modify:**
- `blarify/agents/api_key_manager.py` (create)
- `tests/unit/agents/test_api_key_manager.py` (create)

**Implementation:**
```python
from enum import Enum

class KeyStatus(Enum):
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    INVALID = "invalid"
```

**Tests:**
- Test enum values are unique
- Test string representation

**Commit 1:**
```
feat: add KeyStatus enum for API key state tracking

Part of #276
```

### Step 2: Add KeyState Dataclass
**Files to modify:**
- `blarify/agents/api_key_manager.py`
- `tests/unit/agents/test_api_key_manager.py`

**Implementation:**
```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

@dataclass
class KeyState:
    key: str
    state: KeyStatus
    cooldown_until: Optional[datetime] = None
    last_used: Optional[datetime] = None
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_available(self) -> bool:
        """Check if key is available for use"""
        if self.state != KeyStatus.AVAILABLE:
            return False
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return False
        return True
```

**Tests:**
- Test initialization with defaults
- Test is_available logic
- Test cooldown expiration

**Commit 2:**
```
feat: add KeyState dataclass for individual key tracking

Part of #276
```

### Step 3: Create Basic APIKeyManager Class
**Files to modify:**
- `blarify/agents/api_key_manager.py`
- `tests/unit/agents/test_api_key_manager.py`

**Implementation:**
```python
import threading
from typing import Dict, Optional, List

class APIKeyManager:
    def __init__(self, provider: str):
        self.provider = provider
        self.keys: Dict[str, KeyState] = {}
        self._lock = threading.RLock()
        self._key_order: List[str] = []
        self._current_index = 0
    
    def add_key(self, key: str) -> None:
        """Add a new API key to the manager"""
        with self._lock:
            if key not in self.keys:
                self.keys[key] = KeyState(key=key, state=KeyStatus.AVAILABLE)
                self._key_order.append(key)
```

**Tests:**
- Test initialization
- Test add_key functionality
- Test duplicate key handling

**Commit 3:**
```
feat: add basic APIKeyManager class structure

Part of #276
```

### Step 4: Implement Round-Robin Key Selection
**Files to modify:**
- `blarify/agents/api_key_manager.py`
- `tests/unit/agents/test_api_key_manager.py`

**Implementation:**
```python
def get_next_available_key(self) -> Optional[str]:
    """Get next available key using round-robin selection"""
    with self._lock:
        self.reset_expired_cooldowns()
        
        if not self._key_order:
            return None
        
        # Try each key once
        for _ in range(len(self._key_order)):
            key = self._key_order[self._current_index]
            self._current_index = (self._current_index + 1) % len(self._key_order)
            
            key_state = self.keys[key]
            if key_state.is_available():
                key_state.last_used = datetime.now()
                return key
        
        return None  # No available keys
```

**Tests:**
- Test round-robin order
- Test skips unavailable keys
- Test returns None when all exhausted

**Commit 4:**
```
feat: implement round-robin key selection logic

Part of #276
```

### Step 5: Add State Transition Methods
**Files to modify:**
- `blarify/agents/api_key_manager.py`
- `tests/unit/agents/test_api_key_manager.py`

**Implementation:**
```python
def mark_rate_limited(self, key: str, retry_after: Optional[int] = None) -> None:
    """Mark a key as rate limited with optional cooldown"""
    with self._lock:
        if key in self.keys:
            self.keys[key].state = KeyStatus.RATE_LIMITED
            if retry_after:
                self.keys[key].cooldown_until = datetime.now() + timedelta(seconds=retry_after)

def mark_invalid(self, key: str) -> None:
    """Mark a key as permanently invalid"""
    with self._lock:
        if key in self.keys:
            self.keys[key].state = KeyStatus.INVALID
            self.keys[key].error_count += 1

def mark_quota_exceeded(self, key: str) -> None:
    """Mark a key as having exceeded quota"""
    with self._lock:
        if key in self.keys:
            self.keys[key].state = KeyStatus.QUOTA_EXCEEDED
```

**Tests:**
- Test each state transition
- Test cooldown setting
- Test error count increment

**Commit 5:**
```
feat: add state transition methods for key management

Part of #276
```

### Step 6: Implement Cooldown Expiration
**Files to modify:**
- `blarify/agents/api_key_manager.py`
- `tests/unit/agents/test_api_key_manager.py`

**Implementation:**
```python
def reset_expired_cooldowns(self) -> None:
    """Reset keys whose cooldown period has expired"""
    now = datetime.now()
    with self._lock:
        for key_state in self.keys.values():
            if key_state.state == KeyStatus.RATE_LIMITED:
                if key_state.cooldown_until and now >= key_state.cooldown_until:
                    key_state.state = KeyStatus.AVAILABLE
                    key_state.cooldown_until = None
```

**Tests:**
- Test automatic cooldown expiration
- Test multiple keys with different cooldowns
- Test no change when cooldown not expired

**Commit 6:**
```
feat: add automatic cooldown expiration logic

Part of #276
```

### Step 7: Add State Inspection Methods
**Files to modify:**
- `blarify/agents/api_key_manager.py`
- `tests/unit/agents/test_api_key_manager.py`

**Implementation:**
```python
def get_key_states(self) -> Dict[str, KeyState]:
    """Get current state of all keys"""
    with self._lock:
        return dict(self.keys)

def get_available_count(self) -> int:
    """Get count of currently available keys"""
    with self._lock:
        self.reset_expired_cooldowns()
        return sum(1 for state in self.keys.values() if state.is_available())
```

**Tests:**
- Test state inspection accuracy
- Test available count with mixed states

**Commit 7:**
```
feat: add state inspection methods for monitoring

Part of #276
```

### Step 8: Add Thread Safety Tests
**Files to modify:**
- `tests/unit/agents/test_api_key_manager.py`

**Tests:**
```python
def test_concurrent_key_selection():
    """Test thread safety with concurrent access"""
    manager = APIKeyManager("test")
    for i in range(5):
        manager.add_key(f"key-{i}")
    
    results = []
    def get_key():
        for _ in range(100):
            key = manager.get_next_available_key()
            results.append(key)
    
    threads = [threading.Thread(target=get_key) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # Verify no corruption and fair distribution
    assert len(results) == 1000
    assert all(key in [f"key-{i}" for i in range(5)] for key in results)
```

**Commit 8:**
```
test: add thread safety tests for APIKeyManager

Part of #276
```

### Step 9: Add Logging Support
**Files to modify:**
- `blarify/agents/api_key_manager.py`

**Implementation:**
```python
import logging

logger = logging.getLogger(__name__)

# Add logging to all state transitions
def mark_rate_limited(self, key: str, retry_after: Optional[int] = None) -> None:
    """Mark a key as rate limited with optional cooldown"""
    with self._lock:
        if key in self.keys:
            self.keys[key].state = KeyStatus.RATE_LIMITED
            if retry_after:
                self.keys[key].cooldown_until = datetime.now() + timedelta(seconds=retry_after)
            logger.debug(f"Key {key[:8]}... marked as rate limited for {retry_after}s")
```

**Commit 9:**
```
feat: add debug logging for key state transitions

Part of #276
```

### Step 10: Add Performance Tests
**Files to modify:**
- `tests/unit/agents/test_api_key_manager.py`

**Tests:**
```python
def test_key_selection_performance():
    """Ensure key selection is fast enough"""
    manager = APIKeyManager("test")
    for i in range(100):
        manager.add_key(f"key-{i}")
    
    start = time.time()
    for _ in range(10000):
        manager.get_next_available_key()
    duration = time.time() - start
    
    # Should complete 10k selections in under 100ms
    assert duration < 0.1
```

**Commit 10:**
```
test: add performance benchmarks for key selection

Part of #276
```

## Validation Criteria

- [ ] All unit tests pass
- [ ] Thread safety verified
- [ ] No pyright type errors
- [ ] Ruff linting passes
- [ ] Performance: <1ms for key selection
- [ ] All commits made incrementally

## Next Steps
After completing this task, proceed to Task 2: Implement key discovery from environment variables.