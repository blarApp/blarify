# User Guide

This comprehensive guide covers advanced usage patterns, best practices, and detailed explanations of Blarify's features.

## Table of Contents

1. [Basic Usage](#basic-usage)
2. [Advanced Configuration](#advanced-configuration)
3. [Working with Different Languages](#working-with-different-languages)
4. [Database Operations](#database-operations)
5. [Graph Analysis](#graph-analysis)
6. [Filtering and Optimization](#filtering-and-optimization)
7. [Diff and Change Tracking](#diff-and-change-tracking)
8. [Integration Patterns](#integration-patterns)
9. [Performance Tuning](#performance-tuning)
10. [Troubleshooting](#troubleshooting)

## Basic Usage

### Simple Project Analysis

```python
from blarify.prebuilt.graph_builder import GraphBuilder

# Analyze a Python project
builder = GraphBuilder(
    root_path="/path/to/your/project",
    extensions_to_skip=[".json", ".md", ".txt"],
    names_to_skip=["__pycache__", ".venv", ".git"]
)

graph = builder.build()
print(f"Found {len(graph.get_nodes_as_objects())} nodes")
print(f"Found {len(graph.get_relationships_as_objects())} relationships")
```

### Saving to Database

```python
from blarify.db_managers.neo4j_manager import Neo4jManager
from blarify.db_managers.falkordb_manager import FalkorDBManager

# Get graph data
nodes = graph.get_nodes_as_objects()
relationships = graph.get_relationships_as_objects()

# Save to Neo4j
neo4j_manager = Neo4jManager(repo_id="my-repo", entity_id="my-org")
neo4j_manager.save_graph(nodes, relationships)
neo4j_manager.close()

# Or save to FalkorDB
falkor_manager = FalkorDBManager(repo_id="my-repo", entity_id="my-org")
falkor_manager.save_graph(nodes, relationships)
falkor_manager.close()
```

## Advanced Configuration

### Custom Graph Environment

```python
from blarify.graph.graph_environment import GraphEnvironment

# Create custom environment for specific analysis context
environment = GraphEnvironment(
    environment="production",
    diff_identifier="v2.0.0",
    root_path="/path/to/project"
)

builder = GraphBuilder(
    root_path="/path/to/project",
    graph_environment=environment
)
```

### Hierarchy-Only Analysis

For faster analysis when you only need the file/folder structure:

```python
builder = GraphBuilder(
    root_path="/path/to/project",
    only_hierarchy=True  # Skip relationship analysis
)
graph = builder.build()
```

### Complex Filtering

```python
# Comprehensive filtering for large projects
builder = GraphBuilder(
    root_path="/path/to/project",
    extensions_to_skip=[
        # Documentation
        ".md", ".txt", ".rst", ".pdf",
        # Configuration
        ".json", ".yaml", ".yml", ".toml", ".ini",
        # Build artifacts
        ".pyc", ".pyo", ".pyd", ".so", ".dll",
        # Media files
        ".png", ".jpg", ".jpeg", ".gif", ".svg",
        # Log files
        ".log", ".out"
    ],
    names_to_skip=[
        # Version control
        ".git", ".svn", ".hg",
        # Dependencies
        "node_modules", "vendor", "__pycache__",
        # Virtual environments
        ".venv", "venv", ".virtualenv",
        # Build directories
        "build", "dist", "target", "bin", "obj",
        # IDE files
        ".vscode", ".idea", ".vs",
        # OS files
        ".DS_Store", "Thumbs.db",
        # Package management
        "poetry.lock", "package-lock.json", "yarn.lock"
    ]
)
```

## Working with Different Languages

### Python Projects

```python
# Python-specific optimizations
builder = GraphBuilder(
    root_path="/path/to/python/project",
    extensions_to_skip=[".pyc", ".pyo", ".pyd"],
    names_to_skip=[
        "__pycache__", ".pytest_cache", "venv", ".venv",
        "site-packages", "pip-wheel-metadata"
    ]
)
```

### JavaScript/TypeScript Projects

```python
# JavaScript/TypeScript optimizations
builder = GraphBuilder(
    root_path="/path/to/js/project",
    extensions_to_skip=[".map", ".min.js"],
    names_to_skip=[
        "node_modules", "dist", "build", ".next",
        "coverage", ".nyc_output", ".parcel-cache"
    ]
)
```

### Multi-Language Projects

```python
# Configuration for mixed codebases
builder = GraphBuilder(
    root_path="/path/to/mixed/project",
    extensions_to_skip=[
        # Compiled files
        ".pyc", ".class", ".o", ".obj", ".exe",
        # Package files
        ".jar", ".war", ".ear", ".zip",
        # Generated files
        ".generated", ".auto"
    ],
    names_to_skip=[
        # Multiple language dependencies
        "node_modules", "__pycache__", "target",
        "vendor", "packages", "deps"
    ]
)
```

## Database Operations

### Batch Operations

```python
# For large datasets, use batch operations
manager = Neo4jManager(repo_id="large-repo", entity_id="org")

# Process in chunks for better memory management
chunk_size = 1000
for i in range(0, len(nodes), chunk_size):
    node_chunk = nodes[i:i + chunk_size]
    manager.create_nodes(node_chunk)
    print(f"Processed {min(i + chunk_size, len(nodes))}/{len(nodes)} nodes")
```

### Database-Specific Optimizations

#### Neo4j Optimization

```python
# Configure Neo4j for large datasets
manager = Neo4jManager(
    repo_id="repo",
    entity_id="org",
    max_connections=100  # Increase connection pool
)

# Use environment variables for memory settings
# In your Neo4j configuration:
# dbms.memory.heap.initial_size=2G
# dbms.memory.heap.max_size=4G
```

#### FalkorDB Optimization

```python
# FalkorDB is generally faster for read operations
manager = FalkorDBManager(
    repo_id="repo",
    entity_id="org",
    uri="localhost",
    port=6379
)

# FalkorDB automatically optimizes for graph operations
```

### Data Cleanup

```python
# Clean up nodes by path before updating
manager.detatch_delete_nodes_with_path("/old/path/file.py")

# Save new graph data
manager.save_graph(updated_nodes, updated_relationships)
```

## Graph Analysis

### Exploring Node Types

```python
# Get all nodes of specific types
graph = builder.build()

# Get all function nodes
function_nodes = [
    node for node in graph.get_nodes_as_objects()
    if node["type"] == "FUNCTION"
]

# Get all class nodes
class_nodes = [
    node for node in graph.get_nodes_as_objects()
    if node["type"] == "CLASS"
]

print(f"Functions: {len(function_nodes)}")
print(f"Classes: {len(class_nodes)}")
```

### Relationship Analysis

```python
# Analyze relationship types
relationships = graph.get_relationships_as_objects()

relationship_types = {}
for rel in relationships:
    rel_type = rel["type"]
    relationship_types[rel_type] = relationship_types.get(rel_type, 0) + 1

print("Relationship distribution:")
for rel_type, count in relationship_types.items():
    print(f"  {rel_type}: {count}")
```

### Path-Based Analysis

```python
# Analyze specific files or directories
specific_nodes = graph.get_nodes_by_path("file:///path/to/specific/file.py")

for node in specific_nodes:
    print(f"Node: {node.name} (Type: {node.label})")
    for relationship in node.get_relationships():
        print(f"  -> {relationship.rel_type}: {relationship.end_node.name}")
```

## Filtering and Optimization

### Runtime Filtering

```python
# Filter graph after building for specific analysis
all_paths = [node["attributes"]["path"] for node in graph.get_nodes_as_objects()]

# Keep only Python files
python_paths = [path for path in all_paths if path.endswith('.py')]
filtered_graph = graph.filtered_graph_by_paths(python_paths)

print(f"Original nodes: {len(graph.get_nodes_as_objects())}")
print(f"Filtered nodes: {len(filtered_graph.get_nodes_as_objects())}")
```

### Performance Monitoring

```python
import time
import logging

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG)

start_time = time.time()
graph = builder.build()
build_time = time.time() - start_time

print(f"Graph built in {build_time:.2f} seconds")
print(f"Nodes: {len(graph.get_nodes_as_objects())}")
print(f"Relationships: {len(graph.get_relationships_as_objects())}")
```

## Diff and Change Tracking

### Project Update Workflow

```python
from blarify.project_graph_diff_creator import ProjectGraphDiffCreator, PreviousNodeState
from blarify.graph.graph_environment import GraphEnvironment

# Create environment for diff analysis
pr_environment = GraphEnvironment(
    environment="pr",
    diff_identifier="feature-branch-123",
    root_path="/path/to/project"
)

# Get previous state (from database or cache)
previous_states = [
    PreviousNodeState(
        relative_id="old_node_id",
        hashed_id="old_hashed_id", 
        code_text="old_code_content"
    )
    # ... more previous states
]

# Create diff analyzer
diff_creator = ProjectGraphDiffCreator(
    root_path="/path/to/project",
    lsp_query_helper=lsp_helper,
    project_files_iterator=file_iterator,
    pr_environment=pr_environment
)

# Build diff graph
graph_update = diff_creator.build_with_previous_node_states(previous_states)

# Get nodes and relationships with change information
nodes = graph_update.get_nodes_as_objects()
relationships = graph_update.get_relationships_as_objects()

# Nodes will have extra labels like "ADDED", "MODIFIED", "DELETED"
```

### Change Type Analysis

```python
# Analyze what changed
added_nodes = [node for node in nodes if "ADDED" in node.get("extra_labels", [])]
modified_nodes = [node for node in nodes if "MODIFIED" in node.get("extra_labels", [])]
deleted_nodes = [node for node in nodes if node["type"] == "DELETED"]

print(f"Added: {len(added_nodes)} nodes")
print(f"Modified: {len(modified_nodes)} nodes") 
print(f"Deleted: {len(deleted_nodes)} nodes")
```

## Integration Patterns

### CI/CD Integration

```python
#!/usr/bin/env python3
"""
CI/CD script for analyzing code changes
"""
import os
import sys
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.db_managers.neo4j_manager import Neo4jManager

def analyze_project():
    """Analyze project and save to database"""
    root_path = os.getenv("GITHUB_WORKSPACE", ".")
    repo_id = os.getenv("GITHUB_REPOSITORY", "unknown-repo")
    
    try:
        builder = GraphBuilder(
            root_path=root_path,
            extensions_to_skip=[".json", ".md"],
            names_to_skip=["node_modules", "__pycache__"]
        )
        
        graph = builder.build()
        nodes = graph.get_nodes_as_objects()
        relationships = graph.get_relationships_as_objects()
        
        # Save to database
        manager = Neo4jManager(repo_id=repo_id, entity_id="ci")
        manager.save_graph(nodes, relationships)
        manager.close()
        
        print(f"✅ Analysis complete: {len(nodes)} nodes, {len(relationships)} relationships")
        return 0
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(analyze_project())
```

### Custom Analysis Pipeline

```python
class CodeAnalysisPipeline:
    """Custom pipeline for code analysis with validation"""
    
    def __init__(self, config):
        self.config = config
        self.results = {}
    
    def analyze(self, root_path):
        """Run complete analysis pipeline"""
        # Step 1: Build graph
        builder = GraphBuilder(
            root_path=root_path,
            **self.config.get("builder_options", {})
        )
        graph = builder.build()
        
        # Step 2: Validate graph
        self._validate_graph(graph)
        
        # Step 3: Extract metrics
        self._extract_metrics(graph)
        
        # Step 4: Save results
        self._save_results(graph)
        
        return self.results
    
    def _validate_graph(self, graph):
        """Validate graph structure"""
        nodes = graph.get_nodes_as_objects()
        relationships = graph.get_relationships_as_objects()
        
        # Check for minimum expected nodes
        if len(nodes) < self.config.get("min_nodes", 1):
            raise ValueError(f"Too few nodes: {len(nodes)}")
        
        # Validate relationships
        orphaned_relationships = 0
        node_ids = {node["attributes"]["node_id"] for node in nodes}
        
        for rel in relationships:
            if rel["sourceId"] not in node_ids or rel["targetId"] not in node_ids:
                orphaned_relationships += 1
        
        if orphaned_relationships > 0:
            print(f"Warning: {orphaned_relationships} orphaned relationships")
        
        self.results["validation"] = {
            "nodes": len(nodes),
            "relationships": len(relationships),
            "orphaned_relationships": orphaned_relationships
        }
    
    def _extract_metrics(self, graph):
        """Extract code metrics"""
        nodes = graph.get_nodes_as_objects()
        
        metrics = {
            "total_files": 0,
            "total_classes": 0,
            "total_functions": 0,
            "max_nesting_depth": 0,
            "languages": set()
        }
        
        for node in nodes:
            node_type = node["type"]
            attributes = node["attributes"]
            
            if node_type == "FILE":
                metrics["total_files"] += 1
                # Extract language from file extension
                path = attributes.get("path", "")
                if "." in path:
                    ext = path.split(".")[-1]
                    metrics["languages"].add(ext)
            
            elif node_type == "CLASS":
                metrics["total_classes"] += 1
                
            elif node_type == "FUNCTION":
                metrics["total_functions"] += 1
                
            # Track nesting depth
            level = attributes.get("level", 0)
            metrics["max_nesting_depth"] = max(metrics["max_nesting_depth"], level)
        
        metrics["languages"] = list(metrics["languages"])
        self.results["metrics"] = metrics
    
    def _save_results(self, graph):
        """Save analysis results"""
        # Save to database
        db_config = self.config.get("database", {})
        manager = Neo4jManager(**db_config)
        
        nodes = graph.get_nodes_as_objects()
        relationships = graph.get_relationships_as_objects()
        
        manager.save_graph(nodes, relationships)
        manager.close()
        
        # Save metrics to file
        import json
        with open("analysis_results.json", "w") as f:
            json.dump(self.results, f, indent=2)

# Usage
config = {
    "builder_options": {
        "extensions_to_skip": [".json", ".md"],
        "names_to_skip": ["__pycache__", "node_modules"]
    },
    "database": {
        "repo_id": "my-repo",
        "entity_id": "analysis"
    },
    "min_nodes": 10
}

pipeline = CodeAnalysisPipeline(config)
results = pipeline.analyze("/path/to/project")
print(json.dumps(results, indent=2))
```

## Performance Tuning

### Memory Management

```python
import gc
import psutil
import os

def analyze_with_memory_monitoring(root_path):
    """Analyze project with memory monitoring"""
    process = psutil.Process(os.getpid())
    
    print(f"Initial memory: {process.memory_info().rss / 1024 / 1024:.1f} MB")
    
    # Build graph with periodic garbage collection
    builder = GraphBuilder(root_path=root_path)
    
    # Monitor memory during build
    initial_memory = process.memory_info().rss
    graph = builder.build()
    post_build_memory = process.memory_info().rss
    
    print(f"Memory after build: {post_build_memory / 1024 / 1024:.1f} MB")
    print(f"Memory increase: {(post_build_memory - initial_memory) / 1024 / 1024:.1f} MB")
    
    # Force garbage collection
    gc.collect()
    
    # Extract data
    nodes = graph.get_nodes_as_objects()
    relationships = graph.get_relationships_as_objects()
    
    final_memory = process.memory_info().rss
    print(f"Final memory: {final_memory / 1024 / 1024:.1f} MB")
    
    return nodes, relationships
```

### Parallel Processing Considerations

```python
# Blarify uses LSP which may not be thread-safe
# For parallel processing, use multiple processes instead

from multiprocessing import Pool
import os

def analyze_directory(directory_path):
    """Analyze a single directory"""
    builder = GraphBuilder(root_path=directory_path)
    graph = builder.build()
    return {
        "path": directory_path,
        "nodes": len(graph.get_nodes_as_objects()),
        "relationships": len(graph.get_relationships_as_objects())
    }

def analyze_multiple_projects(project_paths):
    """Analyze multiple projects in parallel"""
    with Pool(processes=4) as pool:
        results = pool.map(analyze_directory, project_paths)
    
    return results

# Usage
projects = ["/path/to/project1", "/path/to/project2", "/path/to/project3"]
results = analyze_multiple_projects(projects)
for result in results:
    print(f"{result['path']}: {result['nodes']} nodes, {result['relationships']} relationships")
```

## Troubleshooting

### Debug Mode

```python
import logging

# Enable detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Build graph with detailed logging
builder = GraphBuilder(root_path="/path/to/project")
graph = builder.build()
```

### Common Issues and Solutions

#### LSP Server Not Starting

```python
from blarify.code_references.lsp_helper import LspQueryHelper

# Test LSP connection manually
lsp_helper = LspQueryHelper(root_uri="/path/to/project")
try:
    lsp_helper.start()
    print("✅ LSP server started successfully")
    lsp_helper.shutdown_exit_close()
except Exception as e:
    print(f"❌ LSP server failed: {e}")
```

#### Large Project Analysis

```python
# For very large projects, analyze incrementally
import os

def analyze_incrementally(root_path, max_files_per_batch=1000):
    """Analyze large projects in batches"""
    all_files = []
    for root, dirs, files in os.walk(root_path):
        for file in files:
            if file.endswith(('.py', '.js', '.ts', '.rb', '.go', '.cs')):
                all_files.append(os.path.join(root, file))
    
    print(f"Found {len(all_files)} files to analyze")
    
    # Process in batches
    for i in range(0, len(all_files), max_files_per_batch):
        batch_files = all_files[i:i + max_files_per_batch]
        print(f"Processing batch {i//max_files_per_batch + 1}: {len(batch_files)} files")
        
        # Create temporary directory with just this batch
        # ... implement batch processing logic
```

### Performance Metrics

```python
def analyze_with_metrics(root_path):
    """Analyze project and collect performance metrics"""
    import time
    import tracemalloc
    
    # Start memory tracing
    tracemalloc.start()
    start_time = time.time()
    
    # Build graph
    builder = GraphBuilder(root_path=root_path)
    graph = builder.build()
    
    # Collect metrics
    end_time = time.time()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    nodes = graph.get_nodes_as_objects()
    relationships = graph.get_relationships_as_objects()
    
    metrics = {
        "execution_time": end_time - start_time,
        "memory_current": current / 1024 / 1024,  # MB
        "memory_peak": peak / 1024 / 1024,        # MB
        "nodes_count": len(nodes),
        "relationships_count": len(relationships),
        "nodes_per_second": len(nodes) / (end_time - start_time),
    }
    
    print("Performance Metrics:")
    for key, value in metrics.items():
        if "time" in key:
            print(f"  {key}: {value:.2f} seconds")
        elif "memory" in key:
            print(f"  {key}: {value:.1f} MB")
        elif "per_second" in key:
            print(f"  {key}: {value:.1f}")
        else:
            print(f"  {key}: {value}")
    
    return nodes, relationships, metrics
```

This user guide provides comprehensive coverage of Blarify's capabilities and best practices for different use cases. For specific implementation details, refer to the [API Reference](api-reference.md) and [Examples](examples.md).
