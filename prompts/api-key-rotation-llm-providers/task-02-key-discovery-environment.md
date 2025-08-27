---
title: "Task 2: Environment Variable Key Discovery"
parent_issue: 276
task_number: 2
description: "Implement automatic discovery of API keys from environment variables"
---

# Task 2: Environment Variable Key Discovery

## Context
Following Task 1's APIKeyManager core infrastructure, we now need to implement automatic discovery of API keys from environment variables. This will allow users to configure multiple keys using a numbered suffix pattern.

## Objective
Extend the APIKeyManager to automatically discover and load API keys from environment variables following patterns like `OPENAI_API_KEY`, `OPENAI_API_KEY_1`, `OPENAI_API_KEY_2`, etc.

## Implementation Steps with Commits

### Step 1: Create Key Discovery Utility
**Files to create/modify:**
- `blarify/agents/key_discovery.py` (create)
- `tests/unit/agents/test_key_discovery.py` (create)

**Implementation:**
```python
import os
from typing import List

def discover_keys_for_provider(provider: str) -> List[str]:
    """Discover all API keys for a given provider from environment variables
    
    Args:
        provider: Provider name (e.g., 'openai', 'anthropic', 'google')
    
    Returns:
        List of discovered API keys
    """
    # Direct mapping - provider names match env var prefix
    base_key = f"{provider.upper()}_API_KEY"
    
    keys = []
    
    # Check base key (e.g., OPENAI_API_KEY)
    if base_key in os.environ:
        keys.append(os.environ[base_key])
    
    # Check numbered keys (e.g., OPENAI_API_KEY_1, OPENAI_API_KEY_2, ...)
    i = 1
    while True:
        numbered_key = f"{base_key}_{i}"
        if numbered_key in os.environ:
            keys.append(os.environ[numbered_key])
            i += 1
        else:
            break
    
    return keys
```

**Tests:**
- Test discovery with no keys
- Test discovery with base key only
- Test discovery with numbered keys
- Test gaps in numbering are handled correctly

**Commit 1:**
```
feat: add key discovery utility for environment variables

Part of #276
```

### Step 2: Integrate Discovery with APIKeyManager
**Files to modify:**
- `blarify/agents/api_key_manager.py`
- `tests/unit/agents/test_api_key_manager.py`

**Implementation:**
```python
from blarify.agents.key_discovery import discover_keys_for_provider

class APIKeyManager:
    def __init__(self, provider: str, auto_discover: bool = True):
        self.provider = provider
        self.keys: Dict[str, KeyState] = {}
        self._lock = threading.RLock()
        self._key_order: List[str] = []
        self._current_index = 0
        
        if auto_discover:
            self._auto_discover_keys()
    
    def _auto_discover_keys(self) -> None:
        """Automatically discover and add keys from environment"""
        discovered_keys = discover_keys_for_provider(self.provider)
        for key in discovered_keys:
            self.add_key(key)
        
        if discovered_keys:
            logger.info(f"Discovered {len(discovered_keys)} keys for {self.provider}")
```

**Tests:**
- Test auto-discovery on initialization
- Test disabling auto-discovery
- Test with mocked environment variables

**Commit 2:**
```
feat: integrate key discovery with APIKeyManager

Part of #276
```

### Step 3: Add Key Validation
**Files to modify:**
- `blarify/agents/api_key_manager.py`
- `tests/unit/agents/test_api_key_manager.py`

**Implementation:**
```python
def validate_key(key: str, provider: str) -> bool:
    """Validate API key format for provider"""
    if not key or not isinstance(key, str):
        return False
    
    # Provider-specific validation
    if provider.lower() == "openai":
        return key.startswith("sk-") and len(key) > 20
    elif provider.lower() == "anthropic":
        return key.startswith("sk-ant-") and len(key) > 20
    elif provider.lower() == "google":
        return len(key) > 20  # Google keys don't have a specific prefix
    
    # Default: accept any non-empty string
    return True

def add_key(self, key: str) -> bool:
    """Add a new API key with validation"""
    if not validate_key(key, self.provider):
        logger.warning(f"Invalid key format for {self.provider}: {key[:10]}...")
        return False
    
    with self._lock:
        if key not in self.keys:
            self.keys[key] = KeyState(key=key, state=KeyStatus.AVAILABLE)
            self._key_order.append(key)
            return True
    return False
```

**Tests:**
- Test OpenAI key validation
- Test Anthropic key validation
- Test Google key validation
- Test invalid key rejection

**Commit 3:**
```
feat: add API key format validation

Part of #276
```

### Step 4: Add Configuration Options
**Files to modify:**
- `blarify/agents/api_key_manager.py`
- `tests/unit/agents/test_api_key_manager.py`

**Implementation:**
```python
from dataclasses import dataclass

@dataclass
class KeyManagerConfig:
    """Configuration for APIKeyManager"""
    auto_discover: bool = True
    validate_keys: bool = True
    max_error_count: int = 3
    default_cooldown_seconds: int = 60
    
class APIKeyManager:
    def __init__(self, provider: str, config: Optional[KeyManagerConfig] = None):
        self.provider = provider
        self.config = config or KeyManagerConfig()
        # ... rest of initialization
```

**Tests:**
- Test default configuration
- Test custom configuration
- Test configuration effects on behavior

**Commit 4:**
```
feat: add configuration options for APIKeyManager

Part of #276
```

### Step 5: Add Key Removal and Cleanup
**Files to modify:**
- `blarify/agents/api_key_manager.py`
- `tests/unit/agents/test_api_key_manager.py`

**Implementation:**
```python
def remove_key(self, key: str) -> bool:
    """Remove a key from management"""
    with self._lock:
        if key in self.keys:
            del self.keys[key]
            self._key_order.remove(key)
            # Adjust current index if needed
            if self._current_index >= len(self._key_order) and self._key_order:
                self._current_index = 0
            return True
    return False

def cleanup_invalid_keys(self) -> int:
    """Remove keys that have exceeded error threshold"""
    removed = 0
    with self._lock:
        keys_to_remove = [
            key for key, state in self.keys.items()
            if state.state == KeyStatus.INVALID 
            and state.error_count >= self.config.max_error_count
        ]
        for key in keys_to_remove:
            self.remove_key(key)
            removed += 1
    
    if removed:
        logger.info(f"Removed {removed} invalid keys for {self.provider}")
    return removed
```

**Tests:**
- Test key removal
- Test cleanup of invalid keys
- Test index adjustment after removal

**Commit 5:**
```
feat: add key removal and cleanup functionality

Part of #276
```

### Step 6: Add Key Statistics
**Files to modify:**
- `blarify/agents/api_key_manager.py`
- `tests/unit/agents/test_api_key_manager.py`

**Implementation:**
```python
from dataclasses import dataclass

@dataclass
class KeyStatistics:
    """Statistics for API key usage"""
    total_keys: int
    available_keys: int
    rate_limited_keys: int
    invalid_keys: int
    quota_exceeded_keys: int
    total_requests: int
    successful_requests: int
    failed_requests: int

def get_statistics(self) -> KeyStatistics:
    """Get current statistics for all keys"""
    with self._lock:
        self.reset_expired_cooldowns()
        
        stats = KeyStatistics(
            total_keys=len(self.keys),
            available_keys=sum(1 for s in self.keys.values() if s.state == KeyStatus.AVAILABLE),
            rate_limited_keys=sum(1 for s in self.keys.values() if s.state == KeyStatus.RATE_LIMITED),
            invalid_keys=sum(1 for s in self.keys.values() if s.state == KeyStatus.INVALID),
            quota_exceeded_keys=sum(1 for s in self.keys.values() if s.state == KeyStatus.QUOTA_EXCEEDED),
            total_requests=sum(s.metadata.get('request_count', 0) for s in self.keys.values()),
            successful_requests=sum(s.metadata.get('success_count', 0) for s in self.keys.values()),
            failed_requests=sum(s.metadata.get('failure_count', 0) for s in self.keys.values())
        )
        return stats
```

**Tests:**
- Test statistics calculation
- Test statistics after state changes

**Commit 6:**
```
feat: add key usage statistics tracking

Part of #276
```

### Step 7: Add Key Refresh Capability
**Files to modify:**
- `blarify/agents/api_key_manager.py`
- `tests/unit/agents/test_api_key_manager.py`

**Implementation:**
```python
def refresh_keys(self) -> int:
    """Re-discover keys from environment and add new ones"""
    initial_count = len(self.keys)
    discovered_keys = discover_keys_for_provider(self.provider)
    
    new_keys = 0
    for key in discovered_keys:
        if key not in self.keys:
            if self.add_key(key):
                new_keys += 1
    
    if new_keys:
        logger.info(f"Added {new_keys} new keys for {self.provider}")
    
    return new_keys
```

**Tests:**
- Test refresh with new keys
- Test refresh with no changes
- Test refresh preserves existing key states

**Commit 7:**
```
feat: add key refresh capability for hot-reloading

Part of #276
```

### Step 8: Add Export/Import State
**Files to modify:**
- `blarify/agents/api_key_manager.py`
- `tests/unit/agents/test_api_key_manager.py`

**Implementation:**
```python
import json
from datetime import datetime

def export_state(self) -> Dict[str, Any]:
    """Export current state for persistence"""
    with self._lock:
        state = {
            'provider': self.provider,
            'keys': {}
        }
        for key, key_state in self.keys.items():
            state['keys'][key] = {
                'state': key_state.state.value,
                'cooldown_until': key_state.cooldown_until.isoformat() if key_state.cooldown_until else None,
                'error_count': key_state.error_count,
                'metadata': key_state.metadata
            }
        return state

def import_state(self, state: Dict[str, Any]) -> None:
    """Import previously exported state"""
    with self._lock:
        for key, key_data in state.get('keys', {}).items():
            if key in self.keys:
                self.keys[key].state = KeyStatus(key_data['state'])
                self.keys[key].error_count = key_data.get('error_count', 0)
                if key_data.get('cooldown_until'):
                    self.keys[key].cooldown_until = datetime.fromisoformat(key_data['cooldown_until'])
                self.keys[key].metadata = key_data.get('metadata', {})
```

**Tests:**
- Test state export format
- Test state import restoration
- Test round-trip export/import

**Commit 8:**
```
feat: add state export/import for persistence

Part of #276
```

## Validation Criteria

- [ ] All unit tests pass
- [ ] Key discovery works with various environment configurations
- [ ] Key validation prevents invalid keys
- [ ] Statistics accurately reflect key states
- [ ] No pyright type errors
- [ ] Ruff linting passes
- [ ] All commits made incrementally

## Next Steps
After completing this task, proceed to Task 3: Create provider wrapper base class for intercepting API calls.