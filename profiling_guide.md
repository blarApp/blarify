# Graph Creation Profiling & Optimization Guide

## 🚀 Quick Start Benchmarking

```bash
# Run the benchmark on your project
python benchmark_graph_creation.py /path/to/your/project

# Run on the blarify project itself
python benchmark_graph_creation.py .
```

## 📊 Profiling Tools & Techniques

### 1. Built-in Benchmarking Script
The `benchmark_graph_creation.py` script provides comprehensive analysis:

**Features:**
- **Memory profiling**: Peak memory usage and current consumption
- **CPU monitoring**: Process CPU utilization
- **Time analysis**: Total execution time breakdown
- **Performance comparison**: Hierarchy vs full graph creation
- **File processing patterns**: Time per file extension
- **cProfile integration**: Function-level performance analysis

### 2. Memory Profiling with `tracemalloc`

```python
import tracemalloc
tracemalloc.start()

# Your graph creation code here
graph = creator.build()

current, peak = tracemalloc.get_traced_memory()
print(f"Current memory usage: {current / 1024 / 1024:.1f} MB")
print(f"Peak memory usage: {peak / 1024 / 1024:.1f} MB")
tracemalloc.stop()
```

### 3. Line-by-Line Profiling with `line_profiler`

```bash
# Install line_profiler
pip install line_profiler

# Add @profile decoration to methods you want to profile
# Then run:
kernprof -l -v your_script.py
```

**Target methods for line profiling:**
- `ProjectGraphCreator._create_code_hierarchy()` (blarify/project_graph_creator.py:80)
- `ProjectGraphCreator._create_relationships_from_references_for_files()` (blarify/project_graph_creator.py:162)
- `Graph.add_node()` (blarify/graph/graph.py:34)

### 4. Memory Profiling with `memory_profiler`

```bash
# Install memory_profiler
pip install memory_profiler

# Add @profile decoration to methods
# Run with:
python -m memory_profiler your_script.py
```

### 5. Advanced Profiling with `py-spy`

```bash
# Install py-spy
pip install py-spy

# Profile a running process
py-spy record -o profile.svg -- python your_script.py

# Sample an existing process
py-spy record -p <PID> -o profile.svg
```

## 🎯 Key Optimization Areas

Based on the codebase analysis, focus on these areas:

### 1. File Processing Pipeline
**Location**: `ProjectGraphCreator._process_file()` (blarify/project_graph_creator.py:122)

**Bottlenecks:**
- Tree-sitter parsing for each file
- LSP initialization per file
- Node creation and relationship building

**Optimization strategies:**
- Batch LSP initialization
- Parallel file processing
- Caching parsed ASTs

### 2. LSP Reference Resolution
**Location**: `ProjectGraphCreator._create_relationships_from_references_for_files()` (blarify/project_graph_creator.py:162)

**Bottlenecks:**
- LSP queries for each node
- Network/IPC overhead
- Sequential processing

**Optimization strategies:**
- Batch LSP queries
- Async/concurrent processing
- Reference caching

### 3. Graph Data Structures
**Location**: `Graph` class (blarify/graph/graph.py)

**Current implementation:**
- Multiple dictionaries for indexing
- Set operations for node storage
- Linear search in some operations

**Optimization strategies:**
- Use more efficient data structures
- Implement lazy loading
- Add indexing for common queries

### 4. Tree-sitter Processing
**Location**: Various language definition files

**Bottlenecks:**
- File parsing overhead
- AST traversal
- Node creation

**Optimization strategies:**
- Parse files in parallel
- Reuse parsers
- Implement incremental parsing

## 🔧 Performance Monitoring Commands

### System Resource Monitoring
```bash
# Monitor CPU and memory during execution
top -p $(pgrep -f "python.*benchmark")

# Or use htop for better visualization
htop -p $(pgrep -f "python.*benchmark")
```

### Process-specific Monitoring
```python
import psutil
import os

process = psutil.Process(os.getpid())
print(f"CPU: {process.cpu_percent()}%")
print(f"Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB")
print(f"Open files: {len(process.open_files())}")
```

## 📈 Interpreting Results

### Time Analysis
- **Hierarchy creation**: Should be linear with file count
- **Relationship creation**: Often O(n²) with code complexity
- **File processing**: Varies by language and file size

### Memory Analysis
- **Peak memory**: Maximum memory used during execution
- **Memory growth**: Watch for memory leaks in long-running processes
- **Memory per file**: Should be relatively constant

### Bottleneck Identification
1. **If hierarchy creation is slow**: Focus on file parsing and node creation
2. **If relationship creation is slow**: Optimize LSP queries and reference resolution
3. **If memory usage is high**: Look for object retention and caching strategies

## 🚨 Warning Signs

Watch for these performance issues:

- **Exponential time growth**: Usually indicates algorithmic issues
- **Memory leaks**: Steadily increasing memory without cleanup
- **High CPU with low progress**: Often indicates inefficient algorithms
- **Excessive file I/O**: May need better caching strategies

## 🛠️ Quick Fixes

### 1. Enable Logging for Timing
The codebase already includes timing logs in `_create_code_hierarchy()`:

```python
logger.info(f"Execution time of create_code_hierarchy: {execution_time:.2f} seconds")
```

### 2. Reduce LSP Overhead
Consider batching LSP operations or using async processing for reference resolution.

### 3. Optimize Graph Operations
The `Graph` class uses multiple indexing dictionaries. Consider using a single, more efficient data structure.

### 4. Implement Caching
Cache parsed ASTs, LSP responses, and processed nodes to avoid redundant work.

## 📝 Creating Custom Benchmarks

```python
import time
from contextlib import contextmanager

@contextmanager
def timer(name):
    start = time.perf_counter()
    yield
    end = time.perf_counter()
    print(f"{name}: {end - start:.2f}s")

# Usage
with timer("Graph Creation"):
    graph = creator.build()
```

Run the benchmark script to get detailed performance insights and identify optimization opportunities in your specific use case.