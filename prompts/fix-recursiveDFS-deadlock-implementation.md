# RecursiveDFSProcessor Deadlock Fix Implementation Guide

## Overview

This implementation guide provides a comprehensive solution for fixing deadlock issues in the RecursiveDFSProcessor when processing functions with circular dependencies at any distance. The current implementation can deadlock when using many worker threads (e.g., 75+ workers) due to circular wait dependencies.

**Important**: This implementation follows Test-Driven Development (TDD) principles. Each component includes its tests immediately after the implementation details. Tests must be written first, fail initially, then pass after implementation. Both unit tests and integration tests are included following `@docs/testing-guide.md`.

## Problem Analysis

### Current Implementation Issues

1. **Circular Wait Dependencies**: When processing nodes with circular dependencies (A→B→...→Z→A), multiple threads can end up waiting for each other via `fut.result()` calls
2. **No Deadlock Detection**: The current implementation lacks mechanisms to detect potential circular wait conditions
3. **Blocking Wait Strategy**: Threads block indefinitely on `fut.result()` without timeout or alternative handling
4. **High Concurrency Vulnerability**: The issue becomes more pronounced with higher thread counts (75+ workers)

### Architecture Context

The RecursiveDFSProcessor processes code hierarchies using:
- **Future-based coordination**: Uses `Dict[str, Future[DocumentationNode]]` to coordinate thread processing
- **Thread-local processing paths**: Each thread maintains a processing path to detect immediate cycles
- **Call stack vs hierarchy navigation**: Different strategies for functions vs folders/files

## Implementation Plan

### Phase 1: Deadlock Detection Infrastructure

#### 1.1 Thread Dependency Tracking

Add thread dependency tracking to detect potential deadlock conditions:

```python
class ThreadDependencyTracker:
    """Tracks which threads are waiting for which nodes to detect potential deadlocks."""
    
    def __init__(self):
        self._waiting_threads: Dict[str, Set[str]] = {}  # thread_id -> set of node_ids
        self._processing_threads: Dict[str, str] = {}    # node_id -> thread_id
        self._lock = threading.Lock()
    
    def register_processor(self, node_id: str, thread_id: str) -> None:
        """Register a thread as the processor for a node."""
        with self._lock:
            self._processing_threads[node_id] = thread_id
    
    def register_waiter(self, node_id: str, thread_id: str) -> bool:
        """
        Register a thread as waiting for a node.
        Returns False if this would create a deadlock.
        """
        with self._lock:
            if thread_id not in self._waiting_threads:
                self._waiting_threads[thread_id] = set()
            
            # Check for potential deadlock before adding the wait dependency
            if self._would_create_deadlock(node_id, thread_id):
                return False
            
            self._waiting_threads[thread_id].add(node_id)
            return True
    
    def unregister_waiter(self, node_id: str, thread_id: str) -> None:
        """Unregister a thread from waiting for a node."""
        with self._lock:
            if thread_id in self._waiting_threads:
                self._waiting_threads[thread_id].discard(node_id)
                if not self._waiting_threads[thread_id]:
                    del self._waiting_threads[thread_id]
    
    def unregister_processor(self, node_id: str) -> None:
        """Unregister the processor for a node."""
        with self._lock:
            self._processing_threads.pop(node_id, None)
    
    def _would_create_deadlock(self, target_node_id: str, requester_thread_id: str) -> bool:
        """
        Check if waiting for target_node_id would create a circular dependency.
        
        A deadlock occurs if:
        1. Thread A wants to wait for node X
        2. Thread B is processing node X  
        3. Thread B is already waiting (directly or transitively) for a node processed by Thread A
        """
        processor_thread = self._processing_threads.get(target_node_id)
        if not processor_thread:
            return False  # No processor yet, safe to wait
        
        if processor_thread == requester_thread_id:
            return True  # Thread trying to wait for itself
        
        # Check for transitive dependencies
        return self._has_transitive_dependency(processor_thread, requester_thread_id)
    
    def _has_transitive_dependency(self, start_thread: str, target_thread: str) -> bool:
        """Check if start_thread transitively depends on target_thread."""
        visited = set()
        stack = [start_thread]
        
        while stack:
            current_thread = stack.pop()
            if current_thread in visited:
                continue
            visited.add(current_thread)
            
            if current_thread == target_thread:
                return True
            
            # Find nodes this thread is waiting for
            waiting_for_nodes = self._waiting_threads.get(current_thread, set())
            for node_id in waiting_for_nodes:
                processor = self._processing_threads.get(node_id)
                if processor and processor not in visited:
                    stack.append(processor)
        
        return False
```

**Tests for ThreadDependencyTracker (TDD):**

```python
# tests/unit/test_thread_dependency_tracker.py
import pytest
from blarify.documentation.utils.recursive_dfs_processor import ThreadDependencyTracker

class TestThreadDependencyTracker:
    """Unit tests for ThreadDependencyTracker following TDD approach."""
    
    def test_register_processor(self):
        """Test that a thread can be registered as processor for a node."""
        # Test should verify: register_processor stores thread_id for node_id
        
    def test_register_waiter_no_deadlock(self):
        """Test registering a waiter when no deadlock would occur."""
        # Test should verify: returns True when safe to wait
        
    def test_detect_direct_deadlock(self):
        """Test detection of direct circular dependency (A waits for B, B waits for A)."""
        # Test should verify: returns False when would create deadlock
        
    def test_detect_transitive_deadlock(self):
        """Test detection of transitive circular dependency (A->B->C->A)."""
        # Test should verify: detects multi-hop circular dependencies
        
    def test_unregister_waiter(self):
        """Test that waiters can be unregistered properly."""
        # Test should verify: cleanup of waiting threads
        
    def test_thread_waiting_for_itself(self):
        """Test that a thread cannot wait for a node it's processing."""
        # Test should verify: returns False when thread tries to wait for itself
```

#### 1.2 Enhanced RecursiveDFSProcessor Structure

Add the dependency tracker and fallback mechanisms to the processor:

```python
class RecursiveDFSProcessor:
    def __init__(self, ...):
        # Existing initialization...
        self.dependency_tracker = ThreadDependencyTracker()
        self.deadlock_fallback_cache: Dict[str, DocumentationNode] = {}
        self.processing_timeouts: Dict[str, float] = {}  # node_id -> timeout timestamp
        self.fallback_timeout_seconds = 30.0  # Maximum wait time before fallback
```

### Phase 2: Deadlock-Safe Processing Logic

#### 2.1 Enhanced Node Processing with Deadlock Detection

Replace the core processing logic in `_process_node_recursive`:

```python
def _process_node_recursive(self, node: NodeWithContentDto) -> DocumentationNode:
    """
    Core recursive method with deadlock detection and fallback handling.
    """
    node_id = node.id
    thread_id = threading.get_ident()
    
    # Check existing cache first
    if node_id in self.node_descriptions:
        return self.node_descriptions[node_id]
    
    # Check database for existing documentation
    existing_doc = self._check_database_for_existing_documentation(node)
    if existing_doc:
        self.node_descriptions[node_id] = existing_doc
        self.node_source_mapping[existing_doc.hashed_id] = node_id
        self.source_nodes_cache[node_id] = node
        self.source_to_description[node_id] = existing_doc.content
        return existing_doc
    
    # Try to register as processor or waiter
    with self.futures_lock:
        fut = self.processing_futures.get(node_id)
        if fut is None:
            # We're the first thread - register as processor
            fut = Future()
            self.processing_futures[node_id] = fut
            self.dependency_tracker.register_processor(node_id, str(thread_id))
            should_process = True
        else:
            # Another thread is processing - check if we can safely wait
            can_wait = self.dependency_tracker.register_waiter(node_id, str(thread_id))
            should_process = False
            
            if not can_wait:
                # Would create deadlock - use fallback strategy
                logger.warning(
                    f"Potential deadlock detected for node {node.name} ({node_id}), "
                    f"using fallback strategy"
                )
                return self._handle_deadlock_fallback(node)
    
    if should_process:
        return self._process_as_primary_thread(node, fut)
    else:
        return self._process_as_waiting_thread(node, fut, thread_id)

def _process_as_primary_thread(self, node: NodeWithContentDto, fut: Future) -> DocumentationNode:
    """Process node as the primary processing thread."""
    node_id = node.id
    thread_id = str(threading.get_ident())
    
    try:
        # Set timeout for this processing
        self.processing_timeouts[node_id] = time.time() + self.fallback_timeout_seconds
        
        # Get and update the processing path to detect direct cycles
        processing_path = self._get_processing_path()
        processing_path.add(node_id)
        
        try:
            # Process the node normally
            children = self._get_navigation_children(node)
            
            if not children:  # LEAF NODE
                description = self._process_leaf_node(node)
            else:  # PARENT NODE
                child_descriptions = self._process_children_parallel(children, node)
                description = self._process_parent_node(node, child_descriptions)
            
            # Cache and broadcast result
            self.node_descriptions[node_id] = description
            fut.set_result(description)
            return description
            
        except Exception as e:
            fut.set_exception(e)
            raise
        finally:
            processing_path.discard(node_id)
    
    finally:
        # Clean up tracking
        with self.futures_lock:
            self.processing_futures.pop(node_id, None)
        self.dependency_tracker.unregister_processor(node_id)
        self.processing_timeouts.pop(node_id, None)

def _process_as_waiting_thread(
    self, 
    node: NodeWithContentDto, 
    fut: Future, 
    thread_id: str
) -> DocumentationNode:
    """Process node as a waiting thread with timeout and fallback."""
    node_id = node.id
    
    try:
        # Wait with timeout to avoid infinite blocking
        timeout = self.fallback_timeout_seconds
        start_time = time.time()
        
        try:
            result = fut.result(timeout=timeout)
            return result
        except concurrent.futures.TimeoutError:
            logger.warning(
                f"Timeout waiting for node {node.name} ({node_id}) after {timeout}s, "
                f"using fallback strategy"
            )
            return self._handle_timeout_fallback(node)
            
    finally:
        self.dependency_tracker.unregister_waiter(node_id, thread_id)
```

**Integration Test for Deadlock Detection with 75 Workers (TDD):**

```python
# tests/integration/test_recursive_dfs_deadlock.py
@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestRecursiveDFSDeadlockPrevention:
    """Integration tests following TDD to ensure no deadlock with high worker counts."""
    
    async def test_high_worker_count_no_deadlock(self, neo4j_instance, test_code_examples_path):
        """
        CRITICAL TEST: Must pass with 75 workers (reproduces original hang issue).
        This test MUST complete within 30 seconds for test data.
        """
        # Test should verify:
        # 1. Processing with 75 workers completes without hanging
        # 2. No deadlock occurs (timeout < 30s)
        # 3. Documentation nodes are generated successfully
        
    async def test_circular_dependency_fallback(self, neo4j_instance, temp_project_dir):
        """Test that circular dependencies trigger fallback mechanism."""
        # Test should verify:
        # 1. Circular dependencies are detected
        # 2. Fallback strategy is used (check metadata)
        # 3. Documentation is still generated with partial context
```

#### 2.2 Fallback Strategy Implementation

```python
def _handle_deadlock_fallback(self, node: NodeWithContentDto) -> DocumentationNode:
    """
    Handle deadlock scenario by using available context or processing as leaf.
    """
    node_id = node.id
    
    # Check if we already have a fallback result for this node
    if node_id in self.deadlock_fallback_cache:
        return self.deadlock_fallback_cache[node_id]
    
    logger.info(f"Processing node {node.name} ({node_id}) with deadlock fallback strategy")
    
    # Strategy 1: Try to get partial context from already-processed children
    children = self._get_navigation_children(node)
    available_children = []
    
    for child in children:
        if child.id in self.node_descriptions:
            # Child is already processed - we can use it
            available_children.append(self.node_descriptions[child.id])
    
    if available_children:
        # We have some child context - process as parent with partial information
        description = self._process_parent_node_with_partial_context(
            node, available_children, is_fallback=True
        )
    else:
        # No child context available - process as enhanced leaf
        description = self._process_node_as_enhanced_leaf(node, is_fallback=True)
    
    # Cache the fallback result
    self.deadlock_fallback_cache[node_id] = description
    self.node_descriptions[node_id] = description
    
    return description

def _handle_timeout_fallback(self, node: NodeWithContentDto) -> DocumentationNode:
    """Handle timeout by using available context or creating fallback description."""
    return self._handle_deadlock_fallback(node)  # Same strategy for now

def _process_parent_node_with_partial_context(
    self, 
    node: NodeWithContentDto, 
    available_children: List[DocumentationNode],
    is_fallback: bool = False
) -> DocumentationNode:
    """
    Process parent node with only partially available child context.
    Uses PARENT_NODE_PARTIAL_CONTEXT_TEMPLATE from prompt_templates.
    """
    try:
        # Import the prompt template
        from blarify.agents.prompt_templates.recursive_dfs_fallback import (
            PARENT_NODE_PARTIAL_CONTEXT_TEMPLATE
        )
        
        # Prepare child descriptions
        child_descriptions = "\n\n".join([
            f"- **{child.source_name}**: {child.content}"
            for child in available_children
        ])
        
        # Prepare fallback note
        fallback_note = ""
        if is_fallback:
            fallback_note = (
                "**Note**: This analysis uses partial information due to circular "
                "dependencies in the codebase. Some child function details may be incomplete."
            )
        
        # Get prompts from template
        system_prompt, input_prompt = PARENT_NODE_PARTIAL_CONTEXT_TEMPLATE.get_prompts()
        
        # Prepare input dictionary
        input_dict = {
            "node_name": node.name,
            "node_labels": " | ".join(node.labels) if node.labels else "UNKNOWN",
            "node_path": node.path,
            "node_content": node.content,
            "child_descriptions": child_descriptions,
            "fallback_note": fallback_note
        }
        
        # Generate response
        runnable_config = {"run_name": f"{node.name}_partial_parent"}
        response = self.agent_caller.call_dumb_agent(
            system_prompt=system_prompt,
            input_dict=input_dict,
            output_schema=None,
            input_prompt=input_prompt,
            config=runnable_config,
            timeout=10,
        )
        
        response_content = response.content if hasattr(response, "content") else str(response)
        
        # Create documentation node with fallback metadata
        info_node = DocumentationNode(
            title=f"Description of {node.name}",
            content=response_content,
            info_type="parent_description_fallback" if is_fallback else "parent_description",
            source_path=node.path,
            source_name=node.name,
            source_labels=node.labels,
            source_id=node.id,
            source_type="recursive_parent_analysis_fallback" if is_fallback else "recursive_parent_analysis",
            enhanced_content=node.content,
            children_count=len(available_children),
            graph_environment=self.graph_environment,
            metadata={
                "is_fallback": is_fallback,
                "partial_children_count": len(available_children),
                "fallback_reason": "circular_dependency_deadlock" if is_fallback else None
            }
        )
        
        # Update mappings
        self.node_source_mapping[info_node.hashed_id] = node.id
        self.source_nodes_cache[node.id] = node
        self.source_to_description[node.id] = response_content
        
        return info_node
        
    except Exception as e:
        logger.exception(f"Error in fallback parent processing for {node.name}: {e}")
        return self._create_fallback_description(node, f"Fallback processing error: {e}")

def _process_node_as_enhanced_leaf(
    self, 
    node: NodeWithContentDto,
    is_fallback: bool = False
) -> DocumentationNode:
    """
    Process node as an enhanced leaf when child context is not available.
    Uses ENHANCED_LEAF_FALLBACK_TEMPLATE from prompt_templates.
    """
    try:
        # Import the prompt template
        from blarify.agents.prompt_templates.recursive_dfs_fallback import (
            ENHANCED_LEAF_FALLBACK_TEMPLATE
        )
        
        # Prepare fallback note
        fallback_note = ""
        if is_fallback:
            fallback_note = (
                "**Note**: This analysis is limited due to circular dependencies "
                "in the codebase that prevented full context analysis."
            )
        
        # Get prompts from template
        system_prompt, input_prompt = ENHANCED_LEAF_FALLBACK_TEMPLATE.get_prompts()
        
        # Prepare input dictionary
        input_dict = {
            "node_name": node.name,
            "node_labels": " | ".join(node.labels) if node.labels else "UNKNOWN",
            "node_path": node.path,
            "node_content": node.content,
            "fallback_note": fallback_note
        }
        
        # Generate description
        runnable_config = {"run_name": f"{node.name}_enhanced_leaf"}
        response = self.agent_caller.call_dumb_agent(
            system_prompt=system_prompt,
            input_dict=input_dict,
            output_schema=None,
            input_prompt=input_prompt,
            config=runnable_config,
            timeout=5,
        )
        
        response_content = response.content if hasattr(response, "content") else str(response)
        
        # Create documentation node
        info_node = DocumentationNode(
            title=f"Description of {node.name}",
            content=response_content,
            info_type="enhanced_leaf_fallback" if is_fallback else "enhanced_leaf_description",
            source_path=node.path,
            source_name=node.name,
            source_labels=node.labels,
            source_id=node.id,
            source_type="enhanced_leaf_analysis_fallback" if is_fallback else "enhanced_leaf_analysis",
            graph_environment=self.graph_environment,
            metadata={
                "is_fallback": is_fallback,
                "fallback_reason": "circular_dependency_deadlock" if is_fallback else None
            }
        )
        
        # Update mappings
        self.node_source_mapping[info_node.hashed_id] = node.id
        self.source_nodes_cache[node.id] = node
        self.source_to_description[node.id] = response_content
        
        return info_node
        
    except Exception as e:
        logger.exception(f"Error in enhanced leaf processing for {node.name}: {e}")
        return self._create_fallback_description(node, f"Enhanced leaf processing error: {e}")
```

#### 2.3 Prompt Templates

The prompt templates for LLM agents handling deadlock scenarios should be placed in `@blarify/agents/prompt_templates/recursive_dfs_fallback.py`:

```python
# File: blarify/agents/prompt_templates/recursive_dfs_fallback.py

"""
Recursive DFS fallback prompt templates.

This module provides prompt templates for handling circular dependencies and deadlock
scenarios in the RecursiveDFSProcessor when processing code hierarchies with circular
references at any distance.
"""

from .base import PromptTemplate

PARENT_NODE_PARTIAL_CONTEXT_TEMPLATE = PromptTemplate(
    name="parent_node_partial_context",
    description="Analyzes parent nodes with only partially available child context due to circular dependencies",
    variables=["node_name", "node_labels", "node_path", "node_content", "child_descriptions", "fallback_note"],
    system_prompt="""You are a code analysis expert. Create descriptions for parent code elements 
that have circular dependencies, using only the available partial context from child elements.

Requirements:
- Focus on the parent element's structure and purpose
- Acknowledge incomplete child context without dwelling on it
- Extract maximum information from available children
- Maintain clarity despite missing information
- Use active voice and specific language

Response format: Clear description emphasizing what can be determined from available context.

Important: Some child elements may be missing due to circular dependencies in the codebase.
Work with the partial information available to provide the best possible analysis.""",
    input_prompt="""Analyze this parent code element with partial child context:

**Element**: {node_name}
**Type**: {node_labels}
**Path**: {node_path}

**Available Child Descriptions**:
{child_descriptions}

**Code**:
```
{node_content}
```

{fallback_note}

Provide a comprehensive description based on the available context."""
)

ENHANCED_LEAF_FALLBACK_TEMPLATE = PromptTemplate(
    name="enhanced_leaf_fallback",
    description="Analyzes nodes as enhanced leaf elements when child context is unavailable due to circular dependencies",
    variables=["node_name", "node_labels", "node_path", "node_content", "fallback_note"],
    system_prompt="""You are analyzing a code element that may have dependencies or call other functions, 
but detailed context about those dependencies is not available due to circular references.

Focus on what you can determine from the code itself:
- The element's primary purpose and responsibility
- Its structure and interface
- Observable patterns and behaviors
- Direct functionality visible in the code
- Input/output relationships if apparent

Do not speculate about missing dependency details. Work with what is directly observable.""",
    input_prompt="""Analyze the following code element:

**Name**: {node_name}
**Type**: {node_labels}
**Path**: {node_path}

**Content**:
```
{node_content}
```

{fallback_note}

Provide a description focusing on the element's purpose, structure, and any 
observable patterns, even without complete dependency information."""
)

CIRCULAR_DEPENDENCY_DETECTION_TEMPLATE = PromptTemplate(
    name="circular_dependency_detection",
    description="Documents detected circular dependencies for debugging and analysis",
    variables=["cycle_nodes", "cycle_paths", "affected_modules"],
    system_prompt="""You are documenting circular dependencies detected in a codebase.

Create a clear summary that:
- Identifies the circular dependency chain
- Explains the relationships between components
- Notes potential impacts on code analysis
- Suggests possible refactoring approaches if apparent

Be factual and technical. This documentation helps developers understand and resolve circular dependencies.""",
    input_prompt="""Document the following circular dependency:

**Cycle Components**:
{cycle_nodes}

**File Paths Involved**:
{cycle_paths}

**Affected Modules**:
{affected_modules}

Provide a technical summary of this circular dependency pattern."""
)

DEADLOCK_RECOVERY_TEMPLATE = PromptTemplate(
    name="deadlock_recovery",
    description="Documents code elements processed through deadlock recovery mechanisms",
    variables=["node_name", "node_type", "recovery_reason", "partial_context", "node_content"],
    system_prompt="""You are analyzing a code element that was processed through a deadlock recovery mechanism
due to complex circular dependencies in the codebase.

Create a description that:
- Focuses on the element's core functionality
- Uses any available partial context effectively
- Maintains accuracy despite incomplete information
- Documents what can be reliably determined

This is a recovery scenario - provide the best analysis possible with limited context.""",
    input_prompt="""Analyze this code element (processed via deadlock recovery):

**Element**: {node_name}
**Type**: {node_type}
**Recovery Reason**: {recovery_reason}

**Available Partial Context**:
{partial_context}

**Code**:
```
{node_content}
```

Generate a description focusing on observable functionality and structure."""
)
```

**Unit Tests for Fallback Strategies (TDD):**

```python
# tests/unit/test_recursive_dfs_fallback.py
import pytest
from unittest.mock import Mock, MagicMock
from blarify.documentation.utils.recursive_dfs_processor import RecursiveDFSProcessor

class TestRecursiveDFSFallbackStrategies:
    """Unit tests for fallback strategies following TDD approach."""
    
    def test_handle_deadlock_fallback_with_partial_children(self):
        """Test fallback handling when some children are already processed."""
        # Test should verify:
        # 1. Uses available child context
        # 2. Creates documentation with partial context
        # 3. Sets appropriate metadata flags
        
    def test_handle_deadlock_fallback_no_children(self):
        """Test fallback handling when no child context is available."""
        # Test should verify:
        # 1. Falls back to enhanced leaf processing
        # 2. Documentation created from node content only
        # 3. Metadata indicates fallback reason
        
    def test_timeout_fallback_mechanism(self):
        """Test that timeout triggers fallback processing."""
        # Test should verify:
        # 1. Timeout is detected
        # 2. Fallback strategy is invoked
        # 3. Processing continues without hanging
        
    def test_fallback_cache_prevents_reprocessing(self):
        """Test that fallback cache prevents duplicate processing."""
        # Test should verify:
        # 1. First call processes node
        # 2. Second call returns cached result
        # 3. No duplicate LLM calls
```

### Phase 3: Enhanced DocumentationNode Support

#### 3.1 Metadata Support for Fallback Information

Update the DocumentationNode class to support metadata for tracking fallback scenarios:

```python
# In blarify/graph/node/documentation_node.py

@dataclass
class DocumentationNode:
    # ... existing fields ...
    metadata: Optional[Dict[str, Any]] = None
    
    def as_object(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        obj = {
            # ... existing fields ...
        }
        
        if self.metadata:
            obj["metadata"] = self.metadata
            
        return obj
```

### Phase 4: Test Infrastructure and Utilities

Following the testing guide in `@docs/testing-guide.md` and using TDD approach, tests are integrated throughout the implementation phases above. This phase provides additional test utilities and comprehensive integration tests.

#### 4.1 Test Utilities for Circular Dependencies

Create test utilities for generating circular dependency scenarios:

```python
# In tests/utils/circular_dependency_generator.py

from pathlib import Path
from typing import List, Tuple
import textwrap

class CircularDependencyGenerator:
    """Generates test code with circular function dependencies."""
    
    @staticmethod
    def create_simple_cycle(temp_dir: Path, cycle_length: int = 3) -> List[Path]:
        """
        Create a simple A->B->C->A cycle.
        
        Args:
            temp_dir: Directory to create files in
            cycle_length: Number of functions in the cycle
            
        Returns:
            List of created file paths
        """
        files = []
        
        for i in range(cycle_length):
            current_func = f"function_{i}"
            next_func = f"function_{(i + 1) % cycle_length}"
            
            file_path = temp_dir / f"module_{i}.py"
            
            content = textwrap.dedent(f'''
            """Module {i} with circular dependency."""
            
            def {current_func}(value: int) -> int:
                """Function {i} that calls function {(i + 1) % cycle_length}."""
                if value <= 0:
                    return value
                
                # This creates the circular dependency
                from module_{(i + 1) % cycle_length} import {next_func}
                return {next_func}(value - 1)
            
            def helper_function_{i}() -> str:
                """Helper function without dependencies."""
                return "Helper {i}"
            ''')
            
            file_path.write_text(content.strip())
            files.append(file_path)
        
        return files
    
    @staticmethod
    def create_complex_cycle_with_branches(temp_dir: Path) -> List[Path]:
        """
        Create a complex cycle: A->B->C->A, with B also calling D->E->F->B.
        """
        files = []
        
        # Main cycle: A->B->C->A
        main_cycle = [
            ("module_a.py", "function_a", "module_b", "function_b"),
            ("module_b.py", "function_b", "module_c", "function_c"), 
            ("module_c.py", "function_c", "module_a", "function_a"),
        ]
        
        # Branch cycle: D->E->F->B
        branch_cycle = [
            ("module_d.py", "function_d", "module_e", "function_e"),
            ("module_e.py", "function_e", "module_f", "function_f"),
            ("module_f.py", "function_f", "module_b", "function_b"),
        ]
        
        all_modules = main_cycle + branch_cycle
        
        for module_file, current_func, next_module, next_func in all_modules:
            file_path = temp_dir / module_file
            
            content = textwrap.dedent(f'''
            """Module with complex circular dependencies."""
            
            def {current_func}(depth: int) -> str:
                """Function that participates in circular call chain."""
                if depth <= 0:
                    return "{current_func}_result"
                
                from {next_module} import {next_func}
                result = {next_func}(depth - 1)
                return f"{current_func}->{{result}}"
            
            def independent_function() -> str:
                """Function without circular dependencies."""
                return "independent_result"
            ''')
            
            file_path.write_text(content.strip())
            files.append(file_path)
        
        # Add module_b calls to module_d to create the branch connection
        module_b_path = temp_dir / "module_b.py"
        module_b_content = module_b_path.read_text()
        
        # Insert call to module_d in function_b
        enhanced_content = module_b_content.replace(
            'from module_c import function_c\n                result = function_c(depth - 1)',
            '''from module_c import function_c
                from module_d import function_d
                
                # Create branch to second cycle
                if depth > 5:
                    branch_result = function_d(depth // 2)
                    result = function_c(depth - 1)
                    return f"function_b->{{branch_result}}->{{result}}"
                else:
                    result = function_c(depth - 1)'''
        )
        
        module_b_path.write_text(enhanced_content)
        
        return files
    
    @staticmethod
    def create_high_concurrency_test_case(temp_dir: Path, num_cycles: int = 10) -> List[Path]:
        """
        Create multiple interconnected cycles to stress test high concurrency scenarios.
        
        Args:
            temp_dir: Directory to create files in
            num_cycles: Number of independent cycles to create
            
        Returns:
            List of created file paths
        """
        files = []
        
        # Create multiple independent cycles
        for cycle_id in range(num_cycles):
            cycle_files = CircularDependencyGenerator.create_simple_cycle(
                temp_dir / f"cycle_{cycle_id}", 
                cycle_length=3
            )
            files.extend(cycle_files)
        
        # Create interconnections between cycles
        for i in range(num_cycles - 1):
            # Connect cycle i to cycle i+1
            source_file = temp_dir / f"cycle_{i}" / "module_0.py"
            target_module = f"cycle_{i+1}.module_0"
            target_function = "function_0"
            
            content = source_file.read_text()
            
            # Add cross-cycle call
            enhanced_content = content.replace(
                'return function_1(value - 1)',
                f'''# Cross-cycle connection
                if value > 10:
                    from {target_module} import {target_function}
                    return {target_function}(value - 5)
                else:
                    return function_1(value - 1)'''
            )
            
            source_file.write_text(enhanced_content)
        
        return files
```

#### 4.2 Comprehensive Integration Test Suite

The complete integration test suite, building on the TDD tests defined above:

```python
# In tests/integration/test_recursive_dfs_deadlock.py

import pytest
import time
from pathlib import Path
from typing import Any, Dict, Optional, List
from concurrent.futures import ThreadPoolExecutor

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.graph.graph import Graph
from blarify.documentation.utils.recursive_dfs_processor import RecursiveDFSProcessor
from blarify.documentation.documentation_creator import DocumentationCreator
from blarify.db_managers.neo4j_manager import Neo4jManager
from blarify.agents.llm_provider import LLMProvider
from neo4j_container_manager.types import Neo4jContainerInstance
from tests.utils.graph_assertions import GraphAssertions
from tests.utils.circular_dependency_generator import CircularDependencyGenerator
from pydantic import BaseModel
from langchain_core.tools import BaseTool


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestRecursiveDFSDeadlockHandling:
    """Test deadlock detection and handling in RecursiveDFSProcessor."""
    
    async def test_high_worker_count_no_deadlock(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """
        Test that documentation creation doesn't deadlock with 75 workers.
        This test reproduces the issue from test_documentation_creation.py
        where using 75 workers causes a hang.
        """
        # Use the Python examples directory
        python_examples_path = test_code_examples_path / "python"
        
        # Step 1: Create GraphBuilder and build the code graph
        builder = GraphBuilder(
            root_path=str(python_examples_path),
            extensions_to_skip=[".pyc", ".pyo"],
            names_to_skip=["__pycache__"],
        )
        
        graph = builder.build()
        assert isinstance(graph, Graph)
        
        # Step 2: Save graph to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
            entity_id="test-entity",
            repo_id="test-repo",
        )
        
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        # Debug: Print graph summary
        await graph_assertions.debug_print_graph_summary()
        
        # Step 3: Create RecursiveDFSProcessor with 75 workers (reproduces the hang)
        processor = RecursiveDFSProcessor(
            db_manager=db_manager,
            agent_caller=MockLLMProvider(),
            company_id="test-entity",
            repo_id="test-repo",
            graph_environment=builder.graph_environment,
            max_workers=75,  # This is the critical test - 75 workers causes hang
        )
        
        # Process with timeout to detect deadlock
        start_time = time.time()
        
        # Process a specific file to test
        result = processor.process_node(str(python_examples_path))
        
        processing_time = time.time() - start_time
        
        # Verify no deadlock occurred (should complete within 30 seconds for test data)
        assert processing_time < 30.0, (
            f"Processing with 75 workers took {processing_time:.2f}s - likely deadlocked! "
            f"This indicates the deadlock prevention is not working."
        )
        
        # Verify successful processing
        assert result is not None, "Result should not be None"
        assert result.error is None, f"Processing failed with error: {result.error}"
        assert len(result.documentation_nodes) > 0, "Should have generated documentation nodes"
        
        print(f"Successfully processed with 75 workers in {processing_time:.2f}s")
        print(f"Generated {len(result.documentation_nodes)} documentation nodes")
        
        # Clean up
        db_manager.close()
    
    async def test_simple_circular_dependency_handling(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test handling of simple A->B->C->A circular dependencies."""
        
        # Create circular dependency test case
        test_files = CircularDependencyGenerator.create_simple_cycle(temp_project_dir, cycle_length=3)
        
        # Build graph with GraphBuilder
        builder = GraphBuilder(root_path=str(temp_project_dir))
        graph = builder.build()
        
        # Save to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        # Create RecursiveDFSProcessor with high worker count to trigger potential deadlocks
        processor = RecursiveDFSProcessor(
            db_manager=db_manager,
            agent_caller=MockLLMProvider(),  # Use mock for testing
            company_id="test_company",
            repo_id="test_repo",
            graph_environment=graph.get_graph_environment(),
            max_workers=75,  # High worker count to stress test
        )
        
        # Process the root directory - this should not deadlock
        start_time = time.time()
        result = processor.process_node(str(temp_project_dir))
        processing_time = time.time() - start_time
        
        # Verify processing completed without deadlock
        assert processing_time < 60.0, f"Processing took too long ({processing_time}s), possible deadlock"
        assert result.error is None, f"Processing failed with error: {result.error}"
        assert len(result.documentation_nodes) > 0, "Should have generated documentation nodes"
        
        # Verify fallback handling was used for circular dependencies
        fallback_nodes = [
            node for node in result.documentation_nodes 
            if node.metadata and node.metadata.get("is_fallback", False)
        ]
        
        # Should have some fallback nodes due to circular dependencies
        assert len(fallback_nodes) > 0, "Expected fallback handling for circular dependencies"
        
        # Verify fallback reasons
        deadlock_fallbacks = [
            node for node in fallback_nodes
            if node.metadata.get("fallback_reason") == "circular_dependency_deadlock"
        ]
        assert len(deadlock_fallbacks) > 0, "Expected deadlock fallback handling"
        
        db_manager.close()
    
    async def test_complex_circular_dependency_with_branches(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test handling of complex circular dependencies with multiple branches."""
        
        # Create complex circular dependency scenario
        test_files = CircularDependencyGenerator.create_complex_cycle_with_branches(temp_project_dir)
        
        # Build graph with GraphBuilder
        builder = GraphBuilder(root_path=str(temp_project_dir))
        graph = builder.build()
        
        # Save to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        # Process with high concurrency
        processor = RecursiveDFSProcessor(
            db_manager=db_manager,
            agent_caller=MockLLMProvider(),
            company_id="test_company", 
            repo_id="test_repo",
            graph_environment=graph.get_graph_environment(),
            max_workers=50,
        )
        
        start_time = time.time()
        result = processor.process_node(str(temp_project_dir))
        processing_time = time.time() - start_time
        
        # Verify no deadlock and successful processing
        assert processing_time < 90.0, f"Complex processing took too long ({processing_time}s)"
        assert result.error is None, f"Processing failed: {result.error}"
        
        # Verify comprehensive documentation generation
        assert len(result.documentation_nodes) >= 6, "Should document all modules in complex scenario"
        
        db_manager.close()
    
    async def test_high_concurrency_stress_test(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Stress test with many interconnected cycles and high worker count."""
        
        # Create high concurrency test case
        test_files = CircularDependencyGenerator.create_high_concurrency_test_case(
            temp_project_dir, 
            num_cycles=5
        )
        
        # Build graph
        builder = GraphBuilder(root_path=str(temp_project_dir))
        graph = builder.build()
        
        # Save to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        # Test with maximum worker count
        processor = RecursiveDFSProcessor(
            db_manager=db_manager,
            agent_caller=MockLLMProvider(),
            company_id="test_company",
            repo_id="test_repo", 
            graph_environment=graph.get_graph_environment(),
            max_workers=100,  # Very high worker count
        )
        
        # Process multiple times to ensure consistent behavior
        for iteration in range(3):
            start_time = time.time()
            result = processor.process_node(str(temp_project_dir))
            processing_time = time.time() - start_time
            
            assert processing_time < 120.0, f"Iteration {iteration} took too long ({processing_time}s)"
            assert result.error is None, f"Iteration {iteration} failed: {result.error}"
        
        db_manager.close()
    
    async def test_deadlock_detection_mechanism(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        temp_project_dir: Path,
    ) -> None:
        """Test the deadlock detection mechanism directly."""
        from blarify.documentation.utils.recursive_dfs_processor import ThreadDependencyTracker
        
        tracker = ThreadDependencyTracker()
        
        # Simulate thread dependency scenario
        thread1 = "thread_1"
        thread2 = "thread_2"
        node_a = "node_a"
        node_b = "node_b"
        
        # Thread 1 processes node A
        tracker.register_processor(node_a, thread1)
        
        # Thread 2 processes node B
        tracker.register_processor(node_b, thread2)
        
        # Thread 1 wants to wait for node B (should be OK)
        can_wait = tracker.register_waiter(node_b, thread1)
        assert can_wait, "Thread 1 should be able to wait for node B"
        
        # Thread 2 wants to wait for node A (would create deadlock)
        can_wait = tracker.register_waiter(node_a, thread2)
        assert not can_wait, "Thread 2 waiting for node A should be detected as potential deadlock"
        
        # Clean up
        tracker.unregister_waiter(node_b, thread1)
        tracker.unregister_processor(node_a)
        tracker.unregister_processor(node_b)
    
    async def test_timeout_fallback_mechanism(
        self,
        docker_check: Any,
        neo4j_instance: Neo4jContainerInstance,
        temp_project_dir: Path,
    ) -> None:
        """Test timeout-based fallback when waiting threads exceed timeout."""
        
        # Create simple circular dependency
        test_files = CircularDependencyGenerator.create_simple_cycle(temp_project_dir)
        
        # Build graph
        builder = GraphBuilder(root_path=str(temp_project_dir))
        graph = builder.build()
        
        # Save to Neo4j
        db_manager = Neo4jManager(
            uri=neo4j_instance.uri,
            user="neo4j",
            password="test-password",
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
        
        # Create processor with very short timeout for testing
        processor = RecursiveDFSProcessor(
            db_manager=db_manager,
            agent_caller=SlowMockLLMProvider(),  # Intentionally slow for timeout testing
            company_id="test_company",
            repo_id="test_repo",
            graph_environment=graph.get_graph_environment(),
            max_workers=20,
        )
        processor.fallback_timeout_seconds = 5.0  # Short timeout for testing
        
        start_time = time.time()
        result = processor.process_node(str(temp_project_dir))
        processing_time = time.time() - start_time
        
        # Should complete within reasonable time due to timeout fallbacks
        assert processing_time < 30.0, f"Should complete quickly with timeouts ({processing_time}s)"
        assert result.error is None, "Should not error with timeout fallbacks"
        
        # Should have timeout fallback nodes
        timeout_fallbacks = [
            node for node in result.documentation_nodes
            if (node.metadata and 
                node.metadata.get("fallback_reason") in ["circular_dependency_deadlock", "timeout"])
        ]
        assert len(timeout_fallbacks) > 0, "Expected timeout/deadlock fallback handling"
        
        db_manager.close()


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""
    
    def call_dumb_agent(
        self,
        system_prompt: str,  # noqa: ARG002
        input_dict: Dict[str, Any],
        output_schema: Optional[BaseModel] = None,  # noqa: ARG002
        ai_model: Optional[str] = None,  # noqa: ARG002
        input_prompt: Optional[str] = "Start",  # noqa: ARG002
        config: Optional[Dict[str, Any]] = None,  # noqa: ARG002
        timeout: Optional[int] = None,  # noqa: ARG002
    ) -> Any:
        """Mock implementation that returns consistent responses."""
        node_name = input_dict.get("node_name", "unknown")
        # Return object with content attribute for compatibility
        return type('Response', (), {
            'content': f"Mock description for {node_name}. This is a test response analyzing the code structure."
        })()
    
    def call_react_agent(
        self,
        system_prompt: str,  # noqa: ARG002
        tools: List[BaseTool],  # noqa: ARG002
        input_dict: Dict[str, Any],  # noqa: ARG002
        input_prompt: Optional[str],  # noqa: ARG002
        output_schema: Optional[BaseModel] = None,  # noqa: ARG002
        main_model: Optional[str] = "gpt-4.1",  # noqa: ARG002
    ) -> Any:
        """Mock React agent response."""
        return {"framework": "Test Framework", "main_folders": ["."]}


class SlowMockLLMProvider(MockLLMProvider):
    """Intentionally slow mock provider for timeout testing."""
    
    def call_dumb_agent(
        self,
        system_prompt: str,
        input_dict: Dict[str, Any],
        output_schema: Optional[BaseModel] = None,
        ai_model: Optional[str] = None,
        input_prompt: Optional[str] = "Start",
        config: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        """Slow mock implementation to trigger timeout scenarios."""
        time.sleep(2.0)  # Introduce delay
        return super().call_dumb_agent(
            system_prompt, input_dict, output_schema, 
            ai_model, input_prompt, config, timeout
        )
```

### Phase 5: Configuration and Performance Optimization

#### 5.1 Configurable Deadlock Prevention Parameters

```python
class DeadlockPreventionConfig:
    """Configuration for deadlock prevention mechanisms."""
    
    def __init__(
        self,
        enable_deadlock_detection: bool = True,
        fallback_timeout_seconds: float = 30.0,
        max_dependency_chain_length: int = 50,
        enable_timeout_fallback: bool = True,
        fallback_cache_size: int = 1000,
    ):
        self.enable_deadlock_detection = enable_deadlock_detection
        self.fallback_timeout_seconds = fallback_timeout_seconds
        self.max_dependency_chain_length = max_dependency_chain_length
        self.enable_timeout_fallback = enable_timeout_fallback
        self.fallback_cache_size = fallback_cache_size

# Usage in RecursiveDFSProcessor
def __init__(self, ..., deadlock_config: Optional[DeadlockPreventionConfig] = None):
    # ... existing initialization ...
    self.deadlock_config = deadlock_config or DeadlockPreventionConfig()
    self.fallback_timeout_seconds = self.deadlock_config.fallback_timeout_seconds
```

### Phase 6: Test Execution and Validation

#### 6.1 Running the Tests

Following the testing guide, run the deadlock tests using pytest:

```bash
# Run all deadlock-related tests
poetry run pytest tests/integration/test_recursive_dfs_deadlock.py -v

# Run specific high worker count test (reproduces the original issue)
poetry run pytest tests/integration/test_recursive_dfs_deadlock.py::TestRecursiveDFSDeadlockHandling::test_high_worker_count_no_deadlock -v

# Run with coverage to ensure implementation is tested
poetry run pytest tests/integration/test_recursive_dfs_deadlock.py --cov=blarify.documentation.utils.recursive_dfs_processor

# Run tests in parallel to stress test concurrency
poetry run pytest tests/integration/test_recursive_dfs_deadlock.py -n auto

# Run with Neo4j integration mark
poetry run pytest -m neo4j_integration tests/integration/test_recursive_dfs_deadlock.py
```

#### 6.2 Manual Testing Procedure

1. **Create Test Repository with Circular Dependencies**:
   ```bash
   # Create test directory structure
   mkdir -p test_circular_deps
   cd test_circular_deps
   
   # Use CircularDependencyGenerator to create test files
   python -c "
   from tests.utils.circular_dependency_generator import CircularDependencyGenerator
   from pathlib import Path
   CircularDependencyGenerator.create_simple_cycle(Path('.'), 3)
   "
   ```

2. **Run RecursiveDFSProcessor with High Concurrency**:
   ```python
   from blarify.documentation.utils.recursive_dfs_processor import RecursiveDFSProcessor
   
   # Test with high worker count
   processor = RecursiveDFSProcessor(
       # ... configuration ...
       max_workers=75,  # High concurrency
   )
   
   result = processor.process_node("./test_circular_deps")
   ```

3. **Monitor for Deadlock Indicators**:
   - Processing time > 60 seconds for small codebases
   - Thread count continuously increasing
   - Log messages about circular dependencies
   - Fallback mechanism activation

#### 6.2 Automated Verification

```python
# In tests/integration/test_deadlock_verification.py

def test_deadlock_verification_suite():
    """Comprehensive deadlock verification test suite."""
    
    test_scenarios = [
        ("simple_cycle", lambda d: CircularDependencyGenerator.create_simple_cycle(d, 3)),
        ("complex_branches", CircularDependencyGenerator.create_complex_cycle_with_branches),
        ("high_concurrency", lambda d: CircularDependencyGenerator.create_high_concurrency_test_case(d, 10)),
    ]
    
    worker_counts = [10, 25, 50, 75, 100]
    
    for scenario_name, scenario_generator in test_scenarios:
        for worker_count in worker_counts:
            with temp_project_dir() as project_dir:
                # Generate test case
                scenario_generator(project_dir)
                
                # Test processing
                start_time = time.time()
                processor = RecursiveDFSProcessor(
                    # ... configuration ...
                    max_workers=worker_count,
                )
                
                result = processor.process_node(str(project_dir))
                processing_time = time.time() - start_time
                
                # Verify no deadlock
                assert processing_time < 120.0, (
                    f"Scenario {scenario_name} with {worker_count} workers "
                    f"took {processing_time}s (possible deadlock)"
                )
                
                assert result.error is None, (
                    f"Scenario {scenario_name} failed: {result.error}"
                )
                
                print(f"✓ {scenario_name} with {worker_count} workers: {processing_time:.2f}s")
```

## Success Criteria

### Functional Requirements
1. **No Deadlocks**: Processing completes within reasonable time (< 2 minutes for typical codebases)
2. **Fallback Quality**: Fallback documentation maintains acceptable quality even with limited context
3. **Metadata Tracking**: All fallback scenarios are properly documented with metadata
4. **High Concurrency Support**: Successfully handles 75+ worker threads without deadlocks
5. **Critical Test Pass**: The `test_high_worker_count_no_deadlock` test with 75 workers must pass (this reproduces the original hang issue)

### Performance Requirements  
1. **Minimal Overhead**: Deadlock detection adds < 5% processing time overhead
2. **Memory Efficiency**: Thread tracking structures don't cause memory leaks
3. **Scalability**: Performance degrades gracefully with increasing concurrency

### Quality Requirements
1. **Documentation Completeness**: All nodes receive some form of documentation
2. **Fallback Indication**: Clear indication when fallback strategies are used
3. **Error Handling**: Graceful handling of LLM timeouts and processing errors
4. **Test Coverage**: Comprehensive test coverage for circular dependency scenarios

## Implementation Timeline (TDD Approach)

- **Phase 1** (Week 1): Write tests for deadlock detection → Implement ThreadDependencyTracker
- **Phase 2** (Week 2): Write tests for fallback strategies → Implement core processing logic  
- **Phase 3** (Week 2): Write tests for metadata support → Enhance DocumentationNode
- **Phase 4** (Week 3): Complete integration test suite → Verify all tests pass
- **Phase 5** (Week 3): Performance testing → Optimize configuration
- **Phase 6** (Week 4): Final validation with 75+ worker stress tests

## Conclusion

This implementation guide provides a comprehensive solution to the deadlock issues in RecursiveDFSProcessor. The key innovations include:

1. **Proactive Deadlock Detection**: Prevents circular wait conditions before they occur
2. **Multi-Strategy Fallback**: Uses partial context or enhanced leaf processing when deadlocks would occur
3. **Comprehensive Testing**: Extensive test suite covering various circular dependency scenarios
4. **Quality Preservation**: Maintains documentation quality even in fallback scenarios
5. **Performance Monitoring**: Built-in metrics and monitoring for deadlock prevention effectiveness

The solution balances performance, reliability, and documentation quality while ensuring that the system can handle complex circular dependencies without deadlocking, even under high concurrency conditions.