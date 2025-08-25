---
title: "API Key Rotation for LLM Providers Implementation"
issue_number: 276
created_by: prompt-writer
date: 2025-01-25
description: "Add API key rotation functionality to handle rate limits within providers before falling back to different providers"
---

# API Key Rotation for LLM Providers Implementation

## Overview

This prompt guides the implementation of API key rotation functionality for the Blarify codebase's LLM provider system. The goal is to enhance the existing ChatFallback mechanism by adding the ability to rotate between multiple API keys for the same provider when encountering rate limits (429 errors), before falling back to a different provider entirely.

## Problem Statement

### Current Limitations
The Blarify codebase currently uses LangChain's ChatOpenAI, ChatAnthropic, and ChatGoogleGenerativeAI through a ChatFallback system that provides provider-level fallback when errors occur. However, this system has significant limitations:

1. **Single Key Per Provider**: Each provider can only use one API key at a time
2. **Immediate Provider Switching**: When a 429 rate limit error occurs, the system immediately switches to a different provider
3. **No Rate Limit Intelligence**: The system doesn't parse or respect rate limit headers like `Retry-After` or `X-RateLimit-Reset`
4. **Inefficient Resource Utilization**: Organizations with multiple API keys for the same provider cannot leverage them effectively
5. **No Key State Tracking**: There's no mechanism to track which keys are rate-limited, invalid, or available

### Impact on Users
- **Increased Costs**: Unnecessary provider switching may trigger usage on more expensive providers
- **Reduced Reliability**: Cannot utilize all available API keys before declaring a provider unavailable
- **Poor Observability**: No visibility into which keys are being used or why rotations occur
- **Manual Intervention Required**: Users must manually rotate keys by restarting the application

### Business and Technical Impact
- **Scalability Issues**: Cannot handle high-throughput scenarios effectively
- **Resource Waste**: Available API keys remain unused while the system switches providers
- **Compliance Concerns**: Some organizations require staying within specific providers for data residency

## Provider-Specific Rate Limit Behavior

Understanding how each provider handles rate limits is crucial for implementing effective key rotation. Each provider has different approaches to rate limit headers, error codes, and retry mechanisms.

### OpenAI API
**Rate Limit Headers:**
- `X-RateLimit-Limit-Requests`: Maximum requests per minute for your tier
- `X-RateLimit-Remaining-Requests`: Requests remaining in current window
- `X-RateLimit-Reset-Requests`: Time until request count resets
- `X-RateLimit-Limit-Tokens`: Maximum tokens per minute
- `X-RateLimit-Remaining-Tokens`: Tokens remaining in current window
- `X-RateLimit-Reset-Tokens`: Time until token count resets

**Error Response (429):**
```json
{
  "error": {
    "message": "Rate limit reached for gpt-4 model (requests per min). Please try again in 20s.",
    "type": "rate_limit_error",
    "param": null,
    "code": "rate_limit_exceeded"
  }
}
```

**Key Characteristics:**
- Provides comprehensive headers for proactive rate limit monitoring
- Error messages include specific wait times
- Distinguishes between request and token limits
- Recommends exponential backoff strategy

### Anthropic Claude API
**Rate Limit Headers:**
- `Retry-After`: Seconds to wait before retrying (on 429 responses)
- `anthropic-ratelimit-requests-limit`: Request limit for organization
- `anthropic-ratelimit-requests-remaining`: Remaining requests
- `anthropic-ratelimit-requests-reset`: Reset timestamp (RFC 3339)
- `anthropic-ratelimit-tokens-limit`: Token limit
- `anthropic-ratelimit-tokens-remaining`: Remaining tokens
- `anthropic-ratelimit-tokens-reset`: Token reset timestamp
- Separate headers for input/output token tracking

**Error Response (429):**
```json
{
  "type": "error",
  "error": {
    "type": "rate_limit_error",
    "message": "Your account has hit a rate limit. Please wait and try again."
  },
  "request_id": "req_ABC123..."
}
```

**Key Characteristics:**
- Provides `Retry-After` header for explicit wait times
- Includes request IDs for debugging
- Can trigger 429 on sharp usage spikes even before steady-state limits
- Tracks input and output tokens separately

### Google Gemini API (Vertex AI)
**Rate Limit Headers:**
- No custom `X-RateLimit` headers provided
- Rate limiting conveyed only through error codes and messages
- No specific reset time information in headers

**Error Response (429):**
```json
{
  "code": 429,
  "message": "Quota exceeded for ... Please submit a quota increase request.",
  "status": "RESOURCE_EXHAUSTED"
}
```

**Key Characteristics:**
- Maps to internal `RESOURCE_EXHAUSTED` status
- No programmatic rate limit tracking via headers
- Quota-based system without fixed reset times
- Requires client-side backoff strategy without server guidance

### Implementation Implications

These provider differences require our rotation system to:

1. **Header Parsing Strategy**: Implement provider-specific header parsers
2. **Fallback Mechanisms**: Use exponential backoff when headers are unavailable (Google)
3. **State Tracking**: Different cooldown calculations per provider
4. **Error Parsing**: Provider-specific error message extraction
5. **Proactive Monitoring**: Leverage headers when available to prevent 429s

## Feature Requirements

### Functional Requirements

#### FR1: Multiple API Key Support
- Support environment variables with numbered suffixes: `OPENAI_API_KEY`, `OPENAI_API_KEY_1`, `OPENAI_API_KEY_2`, etc.
- Same pattern for `ANTHROPIC_API_KEY_*` and `GOOGLE_API_KEY_*`
- Dynamically discover all available keys at startup
- Support hot-reloading of keys without restart (optional, future enhancement)

#### FR2: Intelligent Rate Limit Handling
- Parse provider-specific HTTP response headers:
  - **OpenAI**: `X-RateLimit-*` headers for requests and tokens
  - **Anthropic**: `Retry-After` and `anthropic-ratelimit-*` headers
  - **Google**: No headers available, rely on error messages
- Implement provider-aware retry strategies:
  - Use explicit wait times when provided (OpenAI, Anthropic)
  - Exponential backoff for Google and missing headers
- Track cooldown periods per key with provider-specific logic

#### FR3: Key State Management
- Track states for each API key:
  - `available`: Ready for use
  - `rate_limited`: Temporarily unavailable due to rate limits
  - `quota_exceeded`: Monthly/daily quota exhausted
  - `invalid`: Authentication failed (401/403 errors)
- Automatically transition keys back to `available` after cooldown
- Persist state across requests (in-memory for MVP, Redis for production)

#### FR4: Rotation Strategy
- Implement round-robin selection for available keys
- Skip keys in cooldown or invalid states
- Fall back to provider switching only when all keys for a provider are exhausted
- Support weighted distribution based on remaining quotas (future enhancement)

#### FR5: Backwards Compatibility
- Single API key configurations must work without any changes
- Existing code using LLMProvider and ChatFallback should not require modifications
- Configuration should be zero-touch for users not needing rotation

### Technical Requirements

#### TR1: Architecture Constraints
- Must integrate with existing LangChain provider classes
- Cannot modify LangChain library code directly
- Must work with the existing ChatFallback and RunnableWithFallbacks pattern
- Thread-safe implementation for concurrent request handling

#### TR2: Performance Requirements
- Key rotation decision must add < 10ms latency
- State lookups should be O(1) operations
- No blocking I/O in the rotation logic
- Support at least 100 concurrent requests

#### TR3: Integration Points
- ChatFallback.get_chat_model() method
- EmbeddingService for OpenAI embeddings
- LLMProvider's invoke methods
- Existing error handling and retry logic

#### TR4: Monitoring and Observability
- Log all key rotation events with context
- Emit metrics for rotation frequency and success rates
- Track time spent in rate-limited state per key
- Alert when all keys for a provider are exhausted

### User Stories

1. **As a developer**, I want to configure multiple API keys per provider so that I can handle higher request volumes without hitting rate limits.

2. **As a system administrator**, I want the system to automatically rotate between available keys so that I don't need to manually intervene during rate limit events.

3. **As a DevOps engineer**, I want to monitor which keys are being used and their health status so that I can proactively manage API quotas.

4. **As a cost-conscious user**, I want the system to exhaust all keys for a cheaper provider before switching to a more expensive one.

## Technical Analysis

### Current Implementation Review

#### LLMProvider Class (`/blarify/agents/llm_provider.py`)
- Manages different AI agents (dumb, average, reasoning)
- Uses ChatFallback for model instantiation
- Handles prompt construction and response parsing
- No direct API key management

#### ChatFallback Class (`/blarify/agents/chat_fallback.py`)
- Creates RunnableWithFallbacks from a primary model and fallback list
- Instantiates provider classes directly without key rotation
- Maps model names to provider classes via MODEL_PROVIDER_DICT
- Key instantiation point: `get_chat_model()` method

#### EmbeddingService Class (`/blarify/services/embedding_service.py`)
- Uses OpenAIEmbeddings directly
- Implements basic retry logic with exponential backoff
- Single API key from environment variable
- No coordination with chat model key usage

### Proposed Technical Approach

#### 1. API Key Manager Component
Create a centralized `APIKeyManager` class that:
- Discovers keys from environment variables
- Tracks key states and cooldowns
- Provides thread-safe key selection
- Handles state transitions and cleanup

```python
class APIKeyManager:
    def __init__(self, provider: str):
        self.provider = provider
        self.keys = self._discover_keys()
        self.key_states = {}  # key -> KeyState
        self._lock = threading.RLock()
    
    def get_next_available_key(self) -> Optional[str]:
        """Returns next available key or None if all exhausted"""
        
    def mark_rate_limited(self, key: str, retry_after: Optional[int]):
        """Mark a key as rate limited with cooldown"""
        
    def mark_invalid(self, key: str):
        """Mark a key as permanently invalid"""
```

#### 2. Provider Wrapper Classes
Create wrapper classes that intercept LangChain provider calls:

```python
class RotatingKeyChatOpenAI(ChatOpenAI):
    def __init__(self, key_manager: APIKeyManager, **kwargs):
        self.key_manager = key_manager
        super().__init__(**kwargs)
    
    def _call(self, *args, **kwargs):
        """Override to handle key rotation on 429 errors"""
```

#### 3. Error Interception Strategy
- Override the `_call` or `invoke` methods in wrapper classes
- Catch rate limit exceptions before they propagate
- Parse response headers for rate limit information
- Rotate keys and retry transparently

#### 4. Integration with ChatFallback
Modify `ChatFallback.get_chat_model()` to:
- Check if multiple keys exist for the provider
- Use rotating wrapper if multiple keys found
- Fall back to standard provider for single key

### Architecture and Design Decisions

#### Decision 1: Wrapper vs Middleware Pattern
**Choice**: Wrapper classes over middleware
**Rationale**: 
- Cleaner integration with LangChain's class hierarchy
- Easier to maintain provider-specific logic
- Better type safety and IDE support

#### Decision 2: State Storage
**Choice**: In-memory state for MVP, Redis adapter for production
**Rationale**:
- Simplifies initial implementation
- Allows for easy migration to distributed state
- Reduces external dependencies for basic usage

#### Decision 3: Key Discovery
**Choice**: Environment variable scanning at startup
**Rationale**:
- Consistent with current configuration approach
- Simple for users to understand and configure
- No additional configuration files needed

### Dependencies and Integration Points

#### External Dependencies
- No new external libraries required for MVP
- Optional: Redis for distributed state management
- Optional: Prometheus client for metrics

#### Internal Integration Points
1. **ChatFallback.get_chat_model()**: Primary integration point
2. **LLMProvider._invoke_agent()**: May need minor adjustments for logging
3. **EmbeddingService._initialize_client()**: Share key manager instance
4. **Logging infrastructure**: Enhance for rotation events

### Performance Considerations

#### Memory Usage
- ~1KB per API key for state tracking
- Negligible for typical configurations (< 10 keys per provider)

#### CPU Impact
- Key selection: O(n) where n = number of keys (typically < 10)
- Can optimize to O(1) with available key queue

#### Network Impact
- No additional network calls for rotation logic
- Reduced overall API calls due to better key utilization

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)

#### 1.1 Create API Key Manager
**Deliverables**:
- `blarify/agents/api_key_manager.py` with APIKeyManager class
- Key discovery from environment variables
- Thread-safe state management
- Basic round-robin selection

**Tasks**:
1. Implement key discovery logic
2. Create KeyState dataclass
3. Implement state transition methods
4. Add thread safety with locks
5. Write comprehensive unit tests

#### 1.2 Create Provider Wrapper Base Class
**Deliverables**:
- `blarify/agents/rotating_providers.py` with base wrapper class
- Error interception logic
- Header parsing utilities
- Retry mechanism with key rotation

**Tasks**:
1. Create RotatingProviderMixin base class
2. Implement error interception
3. Add header parsing for rate limits
4. Create retry logic with rotation
5. Add logging for rotation events

### Phase 2: Provider Implementations (Week 1-2)

#### 2.1 Implement OpenAI Wrapper
**Deliverables**:
- RotatingKeyChatOpenAI class
- Parse `X-RateLimit-*` headers for proactive monitoring
- Handle both request and token rate limits
- Integration with ChatFallback

**Tasks**:
1. Create RotatingKeyChatOpenAI class
2. Override necessary methods
3. Parse all six OpenAI rate limit headers
4. Extract wait times from error messages
5. Test with multiple keys and rate limit scenarios

#### 2.2 Implement Anthropic Wrapper
**Deliverables**:
- RotatingKeyChatAnthropic class
- Parse `Retry-After` and `anthropic-ratelimit-*` headers
- Handle spike-triggered 429 errors
- Unit tests for Anthropic-specific behavior

**Tasks**:
1. Create RotatingKeyChatAnthropic class
2. Parse RFC 3339 timestamps in reset headers
3. Handle separate input/output token tracking
4. Use `Retry-After` for precise cooldowns
5. Test spike detection and recovery

#### 2.3 Implement Google Wrapper
**Deliverables**:
- RotatingKeyChatGoogle class
- Exponential backoff implementation (no headers available)
- Parse `RESOURCE_EXHAUSTED` error messages
- Unit tests for Google-specific behavior

**Tasks**:
1. Create RotatingKeyChatGoogle class
2. Implement client-side exponential backoff
3. Parse error messages for quota information
4. Handle quota-based vs rate-based limits
5. Test with missing header scenarios

### Phase 3: Integration (Week 2)

#### 3.1 Modify ChatFallback
**Deliverables**:
- Updated ChatFallback.get_chat_model()
- Automatic wrapper selection logic
- Backwards compatibility tests

**Tasks**:
1. Add key discovery check
2. Implement wrapper selection logic
3. Ensure single-key compatibility
4. Update existing tests
5. Add integration tests

#### 3.2 Update EmbeddingService
**Deliverables**:
- Shared key management for embeddings
- RotatingOpenAIEmbeddings wrapper
- Coordinated rate limit handling

**Tasks**:
1. Create embedding wrapper
2. Share APIKeyManager instance
3. Test concurrent usage
4. Verify state consistency

### Phase 4: Monitoring and Testing (Week 2-3)

#### 4.1 Add Comprehensive Logging
**Deliverables**:
- Structured logging for rotation events
- Debug mode for detailed tracing
- Log aggregation examples

**Tasks**:
1. Add rotation event logs
2. Include context (key, provider, reason)
3. Add performance metrics
4. Create log analysis scripts

#### 4.2 Create Test Suite
**Deliverables**:
- Unit tests for all components
- Integration tests for end-to-end flow
- Load tests for concurrent usage
- Failure scenario tests

**Tasks**:
1. Write unit tests for APIKeyManager
2. Create provider wrapper tests
3. Add integration tests
4. Implement load testing
5. Test failure scenarios

### Risk Assessment and Mitigation

#### Risk 1: Breaking Existing Functionality
**Probability**: Medium
**Impact**: High
**Mitigation**: 
- Extensive backwards compatibility testing
- Feature flag for enabling rotation
- Gradual rollout approach

#### Risk 2: Thread Safety Issues
**Probability**: Medium
**Impact**: Medium
**Mitigation**:
- Comprehensive concurrent testing
- Use of proven synchronization primitives
- Code review focus on concurrency

#### Risk 3: Unexpected Provider Behavior
**Probability**: Low
**Impact**: Medium
**Mitigation**:
- Provider-specific test accounts
- Monitoring in staging environment
- Quick rollback capability

## Testing Requirements

### Unit Testing Strategy

#### Component: APIKeyManager
```python
class TestAPIKeyManager:
    def test_discovers_multiple_keys()
    def test_handles_single_key()
    def test_round_robin_selection()
    def test_marks_key_rate_limited()
    def test_cooldown_expiration()
    def test_thread_safety()
    def test_all_keys_exhausted()
```

#### Component: Provider Wrappers
```python
class TestRotatingProviders:
    def test_successful_call_no_rotation()
    def test_rate_limit_triggers_rotation()
    def test_invalid_key_marked()
    def test_header_parsing()
    def test_exponential_backoff()
    def test_exhausted_keys_raises()
```

### Integration Testing

#### Test Scenarios
1. **Single Provider, Multiple Keys**
   - Configure 3 API keys for OpenAI
   - Simulate rate limits on first two keys
   - Verify rotation and successful completion

2. **Multiple Providers with Rotation**
   - Configure 2 keys for OpenAI, 2 for Anthropic
   - Exhaust OpenAI keys
   - Verify fallback to Anthropic

3. **Concurrent Request Handling**
   - Send 50 concurrent requests
   - Simulate rate limits on some keys
   - Verify all requests complete successfully

4. **State Persistence**
   - Mark keys as rate-limited
   - Create new instance
   - Verify state is maintained (when using Redis)

### Edge Cases and Error Scenarios

1. **All Keys Invalid**
   - Test behavior when all keys return 401
   - Verify appropriate error messaging

2. **Malformed Headers**
   - Test with missing rate limit headers
   - Test with invalid header values
   - Verify graceful degradation

3. **Network Failures**
   - Simulate connection timeouts
   - Test retry behavior
   - Verify key rotation doesn't occur

4. **Configuration Errors**
   - Test with no API keys
   - Verify clear error messages

## Success Criteria

### Functional Success Metrics
- ✅ Multiple API keys can be configured via environment variables
- ✅ Rate limits trigger rotation within the same provider
- ✅ All configured keys are utilized before provider fallback
- ✅ Invalid keys are permanently excluded from rotation
- ✅ Rate limit cooldowns are respected
- ✅ System remains backwards compatible

### Performance Success Metrics
- ✅ Key rotation adds < 10ms latency
- ✅ Supports 100+ concurrent requests
- ✅ No memory leaks over extended operation
- ✅ CPU usage increase < 5%

### Quality Metrics
- ✅ 90%+ unit test coverage
- ✅ All integration tests passing
- ✅ No regressions in existing functionality
- ✅ Clear documentation and examples
- ✅ Comprehensive error messages

### Operational Metrics
- ✅ Rotation events are logged and traceable
- ✅ Key health status is observable
- ✅ Alerts fire when all keys exhausted
- ✅ Metrics available for monitoring

## Implementation Steps

### Step 1: Create GitHub Issue and Branch
```bash
# Issue already created: #276
# Create feature branch
git checkout -b feature/api-key-rotation-276
```

### Step 2: Research Phase
1. Analyze current ChatFallback implementation in detail
2. Study LangChain's error handling patterns
3. Research provider-specific rate limit headers
4. Document findings in implementation notes

### Step 3: Implement Core Components

#### 3.1: Create APIKeyManager
```bash
# Create new file
touch blarify/agents/api_key_manager.py

# Implement core functionality
# - Key discovery from environment
# - State management
# - Thread-safe operations
# - Key selection logic
```

#### 3.2: Create Provider Wrappers
```bash
# Create wrapper module
touch blarify/agents/rotating_providers.py

# Implement wrapper classes
# - RotatingKeyChatOpenAI
# - RotatingKeyChatAnthropic  
# - RotatingKeyChatGoogle
```

#### 3.3: Write Unit Tests
```bash
# Create test files
touch tests/unit/agents/test_api_key_manager.py
touch tests/unit/agents/test_rotating_providers.py

# Implement comprehensive test coverage
```

### Step 4: Integration Phase

#### 4.1: Modify ChatFallback
```python
# In blarify/agents/chat_fallback.py
def get_chat_model(self, model: str, timeout: Optional[int] = None) -> Runnable:
    # Add logic to check for multiple keys
    # Use rotating wrapper if available
    # Maintain backwards compatibility
```

#### 4.2: Update EmbeddingService
```python
# In blarify/services/embedding_service.py
def _initialize_client(self) -> None:
    # Check for multiple OpenAI keys
    # Use shared APIKeyManager if available
    # Coordinate with chat model key usage
```

### Step 5: Testing Phase

#### 5.1: Run Unit Tests
```bash
# Run all unit tests
poetry run pytest tests/unit/agents/ -v

# Check coverage
poetry run pytest tests/unit/agents/ --cov=blarify.agents --cov-report=html
```

#### 5.2: Run Integration Tests
```bash
# Create integration tests
touch tests/integration/test_api_key_rotation.py

# Run integration suite
poetry run pytest tests/integration/test_api_key_rotation.py -v
```

#### 5.3: Manual Testing
1. Configure multiple API keys in .env
2. Test with real API calls
3. Simulate rate limit scenarios
4. Verify rotation behavior

### Step 6: Documentation Phase

#### 6.1: Update User Documentation
```markdown
# In docs/user-guide.md
## Configuring Multiple API Keys

To enable API key rotation, configure multiple keys:
- OPENAI_API_KEY=key1
- OPENAI_API_KEY_1=key2
- OPENAI_API_KEY_2=key3
```

#### 6.2: Add API Documentation
```python
# Add comprehensive docstrings
# Include usage examples
# Document configuration options
```

### Step 7: Code Review Preparation

#### 7.1: Run Code Quality Checks
```bash
# Run linting
poetry run ruff check blarify/agents/

# Run type checking
poetry run pyright blarify/agents/

# Format code
poetry run isort blarify/agents/
```

#### 7.2: Create Pull Request
```bash
# Commit changes
git add -A
git commit -m "feat: add API key rotation for LLM providers

- Implement APIKeyManager for key discovery and state tracking
- Create rotating provider wrappers for OpenAI, Anthropic, Google  
- Integrate with ChatFallback for transparent rotation
- Add comprehensive test coverage
- Update documentation with configuration examples

Closes #276

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

# Push branch
git push -u origin feature/api-key-rotation-276

# Create PR
gh pr create \
  --title "feat: add API key rotation for LLM providers (#276)" \
  --body "$(cat <<'EOF'
## Summary
- Adds API key rotation capability to handle rate limits within providers
- Implements transparent key rotation before falling back to different providers
- Maintains full backwards compatibility with single-key configurations

## Implementation Details
- **APIKeyManager**: Centralized key discovery and state management
- **Provider Wrappers**: Transparent rotation for OpenAI, Anthropic, Google
- **ChatFallback Integration**: Seamless integration with existing fallback system
- **Thread Safety**: Concurrent request handling with proper synchronization
- **Comprehensive Testing**: Unit, integration, and performance tests

## Test Plan
- [x] Unit tests for APIKeyManager
- [x] Unit tests for provider wrappers
- [x] Integration tests for end-to-end rotation
- [x] Backwards compatibility tests
- [x] Concurrent request handling tests
- [x] Manual testing with real API keys

## Related Issue
Closes #276

🤖 Generated with Claude Code
EOF
)"
```

### Step 8: Code Review and Iteration

#### 8.1: Address Review Feedback
1. Monitor PR for review comments
2. Address any concerns or suggestions
3. Update tests if needed
4. Ensure all CI checks pass

#### 8.2: Final Validation
1. Test in staging environment
2. Verify monitoring and logging
3. Confirm documentation completeness
4. Get approval from reviewers

### Step 9: Deployment

#### 9.1: Merge to Main
```bash
# After approval
gh pr merge --squash
```

#### 9.2: Post-Deployment Monitoring
1. Monitor error rates
2. Track rotation frequency
3. Verify performance metrics
4. Watch for unexpected behavior

## Additional Considerations

### Future Enhancements
1. **Dynamic Key Discovery**: Hot-reload keys without restart
2. **Weighted Distribution**: Distribute load based on quotas
3. **Cost Optimization**: Prefer cheaper providers when possible
4. **Circuit Breaker Pattern**: Temporarily disable problematic keys
5. **Distributed State**: Redis/DynamoDB for multi-instance deployments

### Security Considerations
1. **Key Storage**: Ensure keys are never logged
2. **State Isolation**: Separate state per provider
3. **Access Control**: Limit key manager access
4. **Audit Trail**: Log key usage for compliance

### Monitoring and Alerting
1. **Metrics to Track**:
   - Key rotation frequency
   - Rate limit hit rate
   - Provider fallback frequency
   - Response latencies

2. **Alerts to Configure**:
   - All keys for provider exhausted
   - High rotation frequency
   - Sustained rate limiting
   - Invalid key detection

### Documentation Updates
1. **User Guide**: Configuration examples
2. **API Reference**: New classes and methods
3. **Architecture Docs**: Updated diagrams
4. **Troubleshooting Guide**: Common issues and solutions

## Conclusion

This implementation plan provides a comprehensive approach to adding API key rotation functionality to the Blarify codebase. The phased implementation ensures minimal risk while delivering significant value through better resource utilization and improved reliability. The solution maintains full backwards compatibility while providing powerful new capabilities for users with multiple API keys.