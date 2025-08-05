# Examples

This document provides practical examples and use cases for Blarify, showing how to analyze different types of projects and solve common problems.

## Table of Contents

1. [Basic Examples](#basic-examples)
2. [Language-Specific Examples](#language-specific-examples)
3. [Database Integration Examples](#database-integration-examples)
4. [Analysis and Reporting Examples](#analysis-and-reporting-examples)
5. [CI/CD Integration Examples](#cicd-integration-examples)
6. [Advanced Use Cases](#advanced-use-cases)

## Basic Examples

### Example 1: Simple Python Project Analysis

```python
"""
Analyze a simple Python project and print basic statistics
"""
from blarify.prebuilt.graph_builder import GraphBuilder

def analyze_python_project():
    # Build the graph
    builder = GraphBuilder(
        root_path="/path/to/python/project",
        extensions_to_skip=[".pyc", ".pyo", ".json"],
        names_to_skip=["__pycache__", ".venv", "venv"]
    )
    
    graph = builder.build()
    nodes = graph.get_nodes_as_objects()
    relationships = graph.get_relationships_as_objects()
    
    # Print basic statistics
    print(f"Total nodes: {len(nodes)}")
    print(f"Total relationships: {len(relationships)}")
    
    # Count by node type
    node_types = {}
    for node in nodes:
        node_type = node["type"]
        node_types[node_type] = node_types.get(node_type, 0) + 1
    
    print("\nNode distribution:")
    for node_type, count in node_types.items():
        print(f"  {node_type}: {count}")
    
    # Find the largest files (by number of definitions)
    file_nodes = [node for node in nodes if node["type"] == "FILE"]
    
    print("\nFiles with most definitions:")
    for file_node in sorted(file_nodes, 
                          key=lambda x: x["attributes"].get("level", 0), 
                          reverse=True)[:5]:
        path = file_node["attributes"]["path"]
        name = file_node["attributes"]["name"]
        print(f"  {name}: {path}")

if __name__ == "__main__":
    analyze_python_project()
```

### Example 2: Save to Database

```python
"""
Complete example: analyze project and save to database
"""
import os
from dotenv import load_dotenv
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.db_managers.neo4j_manager import Neo4jManager

def analyze_and_save():
    # Load environment variables
    load_dotenv()
    
    # Build graph
    builder = GraphBuilder(
        root_path=os.getenv("ROOT_PATH", "."),
        extensions_to_skip=[".json", ".md", ".txt"],
        names_to_skip=["node_modules", "__pycache__", ".git"]
    )
    
    graph = builder.build()
    nodes = graph.get_nodes_as_objects()
    relationships = graph.get_relationships_as_objects()
    
    # Save to Neo4j
    manager = Neo4jManager(
        repo_id=os.getenv("REPO_ID", "example-repo"),
        entity_id=os.getenv("ENTITY_ID", "example-org")
    )
    
    print(f"Saving {len(nodes)} nodes and {len(relationships)} relationships...")
    manager.save_graph(nodes, relationships)
    manager.close()
    
    print("✅ Graph saved successfully!")

if __name__ == "__main__":
    analyze_and_save()
```

## Language-Specific Examples

### JavaScript/TypeScript Project

```python
"""
Analyze a Node.js/TypeScript project
"""
from blarify.prebuilt.graph_builder import GraphBuilder
import json

def analyze_js_project():
    builder = GraphBuilder(
        root_path="/path/to/js/project",
        extensions_to_skip=[
            ".json", ".map", ".min.js", ".min.css",
            ".png", ".jpg", ".svg", ".ico"
        ],
        names_to_skip=[
            "node_modules", "dist", "build", ".next",
            "coverage", ".nyc_output", ".parcel-cache",
            "public", "static"
        ]
    )
    
    graph = builder.build()
    nodes = graph.get_nodes_as_objects()
    
    # Analyze JavaScript/TypeScript specific patterns
    js_files = []
    ts_files = []
    
    for node in nodes:
        if node["type"] == "FILE":
            path = node["attributes"]["path"]
            if path.endswith('.js') or path.endswith('.jsx'):
                js_files.append(node)
            elif path.endswith('.ts') or path.endswith('.tsx'):
                ts_files.append(node)
    
    print(f"JavaScript files: {len(js_files)}")
    print(f"TypeScript files: {len(ts_files)}")
    
    # Find React components (files with JSX/TSX)
    react_components = [
        node for node in nodes 
        if node["type"] == "FILE" and 
        (node["attributes"]["path"].endswith('.jsx') or 
         node["attributes"]["path"].endswith('.tsx'))
    ]
    
    print(f"React components: {len(react_components)}")
    
    # Export analysis results
    analysis = {
        "total_files": len(js_files) + len(ts_files),
        "javascript_files": len(js_files),
        "typescript_files": len(ts_files),
        "react_components": len(react_components),
        "components": [
            {
                "name": comp["attributes"]["name"],
                "path": comp["attributes"]["path"]
            }
            for comp in react_components
        ]
    }
    
    with open("js_analysis.json", "w") as f:
        json.dump(analysis, f, indent=2)
    
    print("Analysis saved to js_analysis.json")

if __name__ == "__main__":
    analyze_js_project()
```

### Multi-Language Project

```python
"""
Analyze a project with multiple programming languages
"""
from blarify.prebuilt.graph_builder import GraphBuilder
from collections import defaultdict
import os

def analyze_multilang_project():
    builder = GraphBuilder(
        root_path="/path/to/multilang/project",
        extensions_to_skip=[
            ".json", ".xml", ".yaml", ".yml",
            ".md", ".txt", ".pdf", ".docx"
        ],
        names_to_skip=[
            "node_modules", "__pycache__", "target",
            "vendor", "deps", "packages"
        ]
    )
    
    graph = builder.build()
    nodes = graph.get_nodes_as_objects()
    
    # Language detection based on file extensions
    language_mapping = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.ts': 'TypeScript',
        '.jsx': 'React',
        '.tsx': 'React',
        '.java': 'Java',
        '.rb': 'Ruby',
        '.go': 'Go',
        '.cs': 'C#',
        '.cpp': 'C++',
        '.c': 'C',
        '.php': 'PHP',
        '.rs': 'Rust',
        '.kt': 'Kotlin',
        '.swift': 'Swift'
    }
    
    language_stats = defaultdict(lambda: {
        'files': 0,
        'classes': 0,
        'functions': 0,
        'lines_of_code': 0
    })
    
    for node in nodes:
        node_type = node["type"]
        attributes = node["attributes"]
        path = attributes.get("path", "")
        
        # Determine language
        ext = os.path.splitext(path)[1].lower()
        language = language_mapping.get(ext, "Unknown")
        
        if node_type == "FILE" and language != "Unknown":
            language_stats[language]['files'] += 1
            
        elif node_type == "CLASS":
            # Find the language of the parent file
            file_path = path
            ext = os.path.splitext(file_path)[1].lower()
            language = language_mapping.get(ext, "Unknown")
            if language != "Unknown":
                language_stats[language]['classes'] += 1
                
        elif node_type == "FUNCTION":
            # Find the language of the parent file
            file_path = path
            ext = os.path.splitext(file_path)[1].lower()
            language = language_mapping.get(ext, "Unknown")
            if language != "Unknown":
                language_stats[language]['functions'] += 1
    
    # Print language statistics
    print("Multi-Language Project Analysis")
    print("=" * 40)
    
    total_files = sum(stats['files'] for stats in language_stats.values())
    
    for language, stats in sorted(language_stats.items()):
        if stats['files'] > 0:
            percentage = (stats['files'] / total_files) * 100
            print(f"{language}:")
            print(f"  Files: {stats['files']} ({percentage:.1f}%)")
            print(f"  Classes: {stats['classes']}")
            print(f"  Functions: {stats['functions']}")
            print()
    
    # Find potential integration points
    print("Potential Integration Points:")
    relationships = graph.get_relationships_as_objects()
    
    cross_language_relationships = []
    node_languages = {}
    
    # Build language mapping for nodes
    for node in nodes:
        path = node["attributes"]["path"]
        ext = os.path.splitext(path)[1].lower()
        language = language_mapping.get(ext, "Unknown")
        node_languages[node["attributes"]["node_id"]] = language
    
    # Find cross-language relationships
    for rel in relationships:
        source_lang = node_languages.get(rel["sourceId"], "Unknown")
        target_lang = node_languages.get(rel["targetId"], "Unknown")
        
        if source_lang != target_lang and source_lang != "Unknown" and target_lang != "Unknown":
            cross_language_relationships.append({
                "source_language": source_lang,
                "target_language": target_lang,
                "relationship_type": rel["type"]
            })
    
    print(f"Cross-language relationships: {len(cross_language_relationships)}")
    
    # Group by language pairs
    lang_pairs = defaultdict(int)
    for rel in cross_language_relationships:
        pair = f"{rel['source_language']} -> {rel['target_language']}"
        lang_pairs[pair] += 1
    
    for pair, count in sorted(lang_pairs.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {pair}: {count}")

if __name__ == "__main__":
    analyze_multilang_project()
```

## Database Integration Examples

### Using FalkorDB

```python
"""
Complete FalkorDB integration example
"""
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.db_managers.falkordb_manager import FalkorDBManager
import os

def falkordb_integration():
    # Build graph
    builder = GraphBuilder(
        root_path="/path/to/project",
        extensions_to_skip=[".json"],
        names_to_skip=["__pycache__"]
    )
    
    graph = builder.build()
    nodes = graph.get_nodes_as_objects()
    relationships = graph.get_relationships_as_objects()
    
    # Connect to FalkorDB
    manager = FalkorDBManager(
        repo_id="my-awesome-project",
        entity_id="my-organization",
        uri=os.getenv("FALKORDB_URI", "localhost"),
        port=int(os.getenv("FALKORDB_PORT", 6379))
    )
    
    try:
        print(f"Saving {len(nodes)} nodes and {len(relationships)} relationships to FalkorDB...")
        manager.save_graph(nodes, relationships)
        print("✅ Data saved successfully!")
        
        # Verify data was saved
        print("\nDatabase verification:")
        print(f"Repository ID: {manager.repo_id}")
        print(f"Entity ID: {manager.entity_id}")
        
    except Exception as e:
        print(f"❌ Error saving to FalkorDB: {e}")
    finally:
        manager.close()

if __name__ == "__main__":
    falkordb_integration()
```

### Database Comparison

```python
"""
Compare performance between Neo4j and FalkorDB
"""
import time
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.db_managers.neo4j_manager import Neo4jManager
from blarify.db_managers.falkordb_manager import FalkorDBManager

def compare_databases():
    # Build graph once
    print("Building graph...")
    builder = GraphBuilder(
        root_path="/path/to/project",
        extensions_to_skip=[".json"],
        names_to_skip=["__pycache__"]
    )
    
    graph = builder.build()
    nodes = graph.get_nodes_as_objects()
    relationships = graph.get_relationships_as_objects()
    
    print(f"Graph built: {len(nodes)} nodes, {len(relationships)} relationships")
    
    # Test Neo4j
    print("\nTesting Neo4j...")
    neo4j_manager = Neo4jManager(repo_id="test-neo4j", entity_id="comparison")
    
    start_time = time.time()
    try:
        neo4j_manager.save_graph(nodes, relationships)
        neo4j_time = time.time() - start_time
        print(f"✅ Neo4j save time: {neo4j_time:.2f} seconds")
    except Exception as e:
        print(f"❌ Neo4j error: {e}")
        neo4j_time = None
    finally:
        neo4j_manager.close()
    
    # Test FalkorDB
    print("\nTesting FalkorDB...")
    falkor_manager = FalkorDBManager(repo_id="test-falkor", entity_id="comparison")
    
    start_time = time.time()
    try:
        falkor_manager.save_graph(nodes, relationships)
        falkor_time = time.time() - start_time
        print(f"✅ FalkorDB save time: {falkor_time:.2f} seconds")
    except Exception as e:
        print(f"❌ FalkorDB error: {e}")
        falkor_time = None
    finally:
        falkor_manager.close()
    
    # Compare results
    if neo4j_time and falkor_time:
        if neo4j_time < falkor_time:
            faster = "Neo4j"
            ratio = falkor_time / neo4j_time
        else:
            faster = "FalkorDB"
            ratio = neo4j_time / falkor_time
        
        print(f"\n📊 Results: {faster} is {ratio:.2f}x faster")
    
    return {
        "nodes": len(nodes),
        "relationships": len(relationships),
        "neo4j_time": neo4j_time,
        "falkor_time": falkor_time
    }

if __name__ == "__main__":
    results = compare_databases()
    print(f"\nFinal results: {results}")
```

## Analysis and Reporting Examples

### Code Complexity Analysis

```python
"""
Analyze code complexity using graph metrics
"""
from blarify.prebuilt.graph_builder import GraphBuilder
import json
from collections import defaultdict

def analyze_complexity():
    builder = GraphBuilder(
        root_path="/path/to/project",
        extensions_to_skip=[".json"],
        names_to_skip=["__pycache__", "tests"]
    )
    
    graph = builder.build()
    nodes = graph.get_nodes_as_objects()
    relationships = graph.get_relationships_as_objects()
    
    # Calculate complexity metrics
    complexity_metrics = {
        "total_files": 0,
        "total_functions": 0,
        "total_classes": 0,
        "max_nesting_depth": 0,
        "average_nesting_depth": 0,
        "files_by_complexity": defaultdict(int),
        "functions_by_complexity": [],
        "classes_by_methods": []
    }
    
    nesting_depths = []
    
    for node in nodes:
        node_type = node["type"]
        attributes = node["attributes"]
        level = attributes.get("level", 0)
        
        if node_type == "FILE":
            complexity_metrics["total_files"] += 1
            
        elif node_type == "FUNCTION":
            complexity_metrics["total_functions"] += 1
            nesting_depths.append(level)
            
            # Function complexity analysis
            function_info = {
                "name": attributes.get("name"),
                "path": attributes.get("path"),
                "nesting_level": level,
                "start_line": attributes.get("start_line"),
                "end_line": attributes.get("end_line")
            }
            
            if function_info["start_line"] and function_info["end_line"]:
                function_info["line_count"] = function_info["end_line"] - function_info["start_line"] + 1
            
            complexity_metrics["functions_by_complexity"].append(function_info)
            
        elif node_type == "CLASS":
            complexity_metrics["total_classes"] += 1
            
            # Count methods in class
            methods_count = attributes.get("stats_methods_defined", 0)
            class_info = {
                "name": attributes.get("name"),
                "path": attributes.get("path"),
                "methods_count": methods_count,
                "nesting_level": level
            }
            complexity_metrics["classes_by_methods"].append(class_info)
    
    # Calculate averages and maxes
    if nesting_depths:
        complexity_metrics["max_nesting_depth"] = max(nesting_depths)
        complexity_metrics["average_nesting_depth"] = sum(nesting_depths) / len(nesting_depths)
    
    # Categorize files by complexity
    for node in nodes:
        if node["type"] == "FILE":
            # Count functions and classes in file
            file_path = node["attributes"]["path"]
            functions_in_file = [
                n for n in nodes 
                if n["type"] == "FUNCTION" and n["attributes"]["path"] == file_path
            ]
            classes_in_file = [
                n for n in nodes 
                if n["type"] == "CLASS" and n["attributes"]["path"] == file_path
            ]
            
            total_definitions = len(functions_in_file) + len(classes_in_file)
            
            if total_definitions == 0:
                complexity = "empty"
            elif total_definitions <= 5:
                complexity = "simple"
            elif total_definitions <= 15:
                complexity = "moderate"
            else:
                complexity = "complex"
            
            complexity_metrics["files_by_complexity"][complexity] += 1
    
    # Sort by complexity
    complexity_metrics["functions_by_complexity"].sort(
        key=lambda x: (x.get("line_count", 0), x["nesting_level"]), 
        reverse=True
    )
    
    complexity_metrics["classes_by_methods"].sort(
        key=lambda x: x["methods_count"], 
        reverse=True
    )
    
    # Generate report
    print("Code Complexity Analysis")
    print("=" * 50)
    print(f"Total files: {complexity_metrics['total_files']}")
    print(f"Total functions: {complexity_metrics['total_functions']}")
    print(f"Total classes: {complexity_metrics['total_classes']}")
    print(f"Max nesting depth: {complexity_metrics['max_nesting_depth']}")
    print(f"Average nesting depth: {complexity_metrics['average_nesting_depth']:.2f}")
    
    print("\nFile complexity distribution:")
    for complexity, count in complexity_metrics["files_by_complexity"].items():
        print(f"  {complexity}: {count}")
    
    print("\nMost complex functions (by line count):")
    for func in complexity_metrics["functions_by_complexity"][:10]:
        line_count = func.get("line_count", "unknown")
        print(f"  {func['name']}: {line_count} lines (nesting: {func['nesting_level']})")
    
    print("\nClasses with most methods:")
    for cls in complexity_metrics["classes_by_methods"][:10]:
        print(f"  {cls['name']}: {cls['methods_count']} methods")
    
    # Save detailed report
    with open("complexity_analysis.json", "w") as f:
        json.dump(complexity_metrics, f, indent=2, default=str)
    
    print("\nDetailed analysis saved to complexity_analysis.json")
    
    return complexity_metrics

if __name__ == "__main__":
    analyze_complexity()
```

### Dependency Analysis

```python
"""
Analyze project dependencies and relationships
"""
from blarify.prebuilt.graph_builder import GraphBuilder
import networkx as nx
from collections import defaultdict

def analyze_dependencies():
    builder = GraphBuilder(
        root_path="/path/to/project",
        extensions_to_skip=[".json"],
        names_to_skip=["__pycache__"]
    )
    
    graph = builder.build()
    nodes = graph.get_nodes_as_objects()
    relationships = graph.get_relationships_as_objects()
    
    # Build NetworkX graph for analysis
    G = nx.DiGraph()
    
    # Add nodes
    for node in nodes:
        node_id = node["attributes"]["node_id"]
        G.add_node(node_id, **node["attributes"])
    
    # Add edges
    for rel in relationships:
        G.add_edge(rel["sourceId"], rel["targetId"], 
                   type=rel["type"], scope=rel.get("scopeText", ""))
    
    # Analyze graph structure
    print("Dependency Analysis")
    print("=" * 40)
    print(f"Nodes: {G.number_of_nodes()}")
    print(f"Edges: {G.number_of_edges()}")
    print(f"Connected components: {nx.number_connected_components(G.to_undirected())}")
    
    # Find most connected nodes
    in_degrees = dict(G.in_degree())
    out_degrees = dict(G.out_degree())
    
    print("\nMost referenced nodes (high in-degree):")
    most_referenced = sorted(in_degrees.items(), key=lambda x: x[1], reverse=True)[:10]
    for node_id, degree in most_referenced:
        node_data = G.nodes[node_id]
        print(f"  {node_data.get('name', 'unknown')}: {degree} incoming references")
    
    print("\nMost dependent nodes (high out-degree):")
    most_dependent = sorted(out_degrees.items(), key=lambda x: x[1], reverse=True)[:10]
    for node_id, degree in most_dependent:
        node_data = G.nodes[node_id]
        print(f"  {node_data.get('name', 'unknown')}: {degree} outgoing references")
    
    # Find cycles
    try:
        cycles = list(nx.simple_cycles(G))
        print(f"\nCircular dependencies found: {len(cycles)}")
        
        if cycles:
            print("Sample cycles:")
            for i, cycle in enumerate(cycles[:5]):
                cycle_names = []
                for node_id in cycle:
                    node_data = G.nodes[node_id]
                    cycle_names.append(node_data.get('name', 'unknown'))
                print(f"  Cycle {i+1}: {' -> '.join(cycle_names)} -> {cycle_names[0]}")
    
    except nx.NetworkXError:
        print("\nNo cycles found")
    
    # Find strongly connected components
    scc = list(nx.strongly_connected_components(G))
    large_components = [comp for comp in scc if len(comp) > 1]
    
    print(f"\nStrongly connected components: {len(large_components)}")
    for i, comp in enumerate(large_components[:5]):
        comp_names = []
        for node_id in comp:
            node_data = G.nodes[node_id]
            comp_names.append(node_data.get('name', 'unknown'))
        print(f"  Component {i+1}: {comp_names}")
    
    # Analyze relationship types
    relationship_types = defaultdict(int)
    for _, _, data in G.edges(data=True):
        rel_type = data.get('type', 'unknown')
        relationship_types[rel_type] += 1
    
    print("\nRelationship type distribution:")
    for rel_type, count in sorted(relationship_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {rel_type}: {count}")
    
    # Find potential refactoring opportunities
    print("\nRefactoring opportunities:")
    
    # Files with many dependencies
    file_dependencies = defaultdict(int)
    for node in nodes:
        if node["type"] == "FILE":
            node_id = node["attributes"]["node_id"]
            file_dependencies[node_id] = out_degrees.get(node_id, 0)
    
    high_dependency_files = sorted(file_dependencies.items(), key=lambda x: x[1], reverse=True)[:5]
    print("Files with many dependencies (consider breaking down):")
    for node_id, dep_count in high_dependency_files:
        node_data = G.nodes[node_id]
        print(f"  {node_data.get('name', 'unknown')}: {dep_count} dependencies")
    
    # Files with many dependents
    file_dependents = defaultdict(int)
    for node in nodes:
        if node["type"] == "FILE":
            node_id = node["attributes"]["node_id"]
            file_dependents[node_id] = in_degrees.get(node_id, 0)
    
    high_dependent_files = sorted(file_dependents.items(), key=lambda x: x[1], reverse=True)[:5]
    print("Files with many dependents (critical components):")
    for node_id, dep_count in high_dependent_files:
        node_data = G.nodes[node_id]
        print(f"  {node_data.get('name', 'unknown')}: {dep_count} dependents")

if __name__ == "__main__":
    analyze_dependencies()
```

## CI/CD Integration Examples

### GitHub Actions Integration

```yaml
# .github/workflows/code-analysis.yml
name: Code Analysis with Blarify

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  analyze:
    runs-on: ubuntu-latest
    
    services:
      neo4j:
        image: neo4j:latest
        env:
          NEO4J_AUTH: neo4j/password
        ports:
          - 7687:7687
          - 7474:7474
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install blarify python-dotenv
    
    - name: Run Blarify analysis
      env:
        NEO4J_URI: bolt://localhost:7687
        NEO4J_USERNAME: neo4j
        NEO4J_PASSWORD: password
        REPO_ID: ${{ github.repository }}
        ENTITY_ID: ${{ github.repository_owner }}
      run: python .github/scripts/analyze.py
    
    - name: Upload results
      uses: actions/upload-artifact@v3
      with:
        name: analysis-results
        path: analysis_results.json
```

```python
# .github/scripts/analyze.py
"""
GitHub Actions script for code analysis
"""
import os
import json
import sys
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.db_managers.neo4j_manager import Neo4jManager

def main():
    try:
        # Get environment variables
        repo_id = os.getenv("REPO_ID", "unknown-repo")
        entity_id = os.getenv("ENTITY_ID", "unknown-org")
        workspace = os.getenv("GITHUB_WORKSPACE", ".")
        
        print(f"Analyzing repository: {repo_id}")
        print(f"Workspace: {workspace}")
        
        # Build graph
        builder = GraphBuilder(
            root_path=workspace,
            extensions_to_skip=[".json", ".md", ".yml", ".yaml"],
            names_to_skip=["node_modules", "__pycache__", ".git", ".github"]
        )
        
        graph = builder.build()
        nodes = graph.get_nodes_as_objects()
        relationships = graph.get_relationships_as_objects()
        
        # Save to database
        manager = Neo4jManager(repo_id=repo_id, entity_id=entity_id)
        manager.save_graph(nodes, relationships)
        manager.close()
        
        # Generate analysis report
        report = {
            "repository": repo_id,
            "timestamp": str(datetime.now()),
            "summary": {
                "total_nodes": len(nodes),
                "total_relationships": len(relationships),
                "files": len([n for n in nodes if n["type"] == "FILE"]),
                "functions": len([n for n in nodes if n["type"] == "FUNCTION"]),
                "classes": len([n for n in nodes if n["type"] == "CLASS"])
            }
        }
        
        # Save report
        with open("analysis_results.json", "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"✅ Analysis complete: {report['summary']}")
        return 0
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return 1

if __name__ == "__main__":
    from datetime import datetime
    sys.exit(main())
```

### Jenkins Pipeline

```groovy
// Jenkinsfile
pipeline {
    agent any
    
    environment {
        NEO4J_URI = 'bolt://neo4j:7687'
        NEO4J_USERNAME = 'neo4j'
        NEO4J_PASSWORD = credentials('neo4j-password')
        REPO_ID = "${env.JOB_NAME}"
        ENTITY_ID = 'jenkins'
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Setup') {
            steps {
                sh '''
                python -m venv venv
                . venv/bin/activate
                pip install blarify python-dotenv
                '''
            }
        }
        
        stage('Analyze') {
            steps {
                sh '''
                . venv/bin/activate
                python scripts/jenkins_analyze.py
                '''
            }
        }
        
        stage('Archive') {
            steps {
                archiveArtifacts artifacts: 'analysis_*.json', fingerprint: true
                publishHTML([
                    allowMissing: false,
                    alwaysLinkToLastBuild: true,
                    keepAll: true,
                    reportDir: 'reports',
                    reportFiles: 'analysis.html',
                    reportName: 'Code Analysis Report'
                ])
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
    }
}
```

## Advanced Use Cases

### Change Impact Analysis

```python
"""
Analyze the impact of code changes using diff analysis
"""
from blarify.project_graph_diff_creator import ProjectGraphDiffCreator, PreviousNodeState
from blarify.graph.graph_environment import GraphEnvironment
from blarify.code_references.lsp_helper import LspQueryHelper
from blarify.project_file_explorer.project_files_iterator import ProjectFilesIterator

def analyze_change_impact(root_path, previous_commit_data):
    """
    Analyze impact of changes between current state and previous commit
    """
    
    # Create PR environment
    pr_environment = GraphEnvironment(
        environment="pr",
        diff_identifier="feature-123",
        root_path=root_path
    )
    
    # Set up LSP and file iterator
    lsp_helper = LspQueryHelper(root_uri=root_path)
    lsp_helper.start()
    
    file_iterator = ProjectFilesIterator(
        root_path=root_path,
        extensions_to_skip=[".json"],
        names_to_skip=["__pycache__"]
    )
    
    try:
        # Create previous node states from commit data
        previous_states = []
        for node_data in previous_commit_data:
            previous_states.append(PreviousNodeState(
                relative_id=node_data["relative_id"],
                hashed_id=node_data["hashed_id"],
                code_text=node_data["code_text"]
            ))
        
        # Create diff analyzer
        diff_creator = ProjectGraphDiffCreator(
            root_path=root_path,
            lsp_query_helper=lsp_helper,
            project_files_iterator=file_iterator,
            pr_environment=pr_environment
        )
        
        # Build diff graph
        graph_update = diff_creator.build_with_previous_node_states(previous_states)
        
        # Analyze changes
        nodes = graph_update.get_nodes_as_objects()
        relationships = graph_update.get_relationships_as_objects()
        
        # Categorize changes
        changes = {
            "added": [n for n in nodes if "ADDED" in n.get("extra_labels", [])],
            "modified": [n for n in nodes if "MODIFIED" in n.get("extra_labels", [])],
            "deleted": [n for n in nodes if n["type"] == "DELETED"]
        }
        
        # Analyze impact
        impact_analysis = analyze_impact(changes, relationships)
        
        # Generate report
        generate_impact_report(changes, impact_analysis)
        
        return changes, impact_analysis
        
    finally:
        lsp_helper.shutdown_exit_close()

def analyze_impact(changes, relationships):
    """Analyze the potential impact of changes"""
    
    impact = {
        "high_risk_changes": [],
        "affected_components": [],
        "test_coverage_needed": [],
        "documentation_updates": []
    }
    
    # Find high-risk changes (functions/classes with many dependents)
    relationship_map = {}
    for rel in relationships:
        target_id = rel["targetId"]
        if target_id not in relationship_map:
            relationship_map[target_id] = []
        relationship_map[target_id].append(rel)
    
    for node in changes["modified"] + changes["added"]:
        node_id = node["attributes"]["node_id"]
        dependents = relationship_map.get(node_id, [])
        
        if len(dependents) > 5:  # Threshold for high-risk
            impact["high_risk_changes"].append({
                "node": node,
                "dependent_count": len(dependents),
                "dependents": dependents[:10]  # Sample of dependents
            })
    
    return impact

def generate_impact_report(changes, impact_analysis):
    """Generate a human-readable impact report"""
    
    print("Change Impact Analysis")
    print("=" * 50)
    
    print(f"Added: {len(changes['added'])} nodes")
    print(f"Modified: {len(changes['modified'])} nodes")
    print(f"Deleted: {len(changes['deleted'])} nodes")
    
    print("\nHigh-Risk Changes:")
    for change in impact_analysis["high_risk_changes"]:
        node = change["node"]
        name = node["attributes"]["name"]
        count = change["dependent_count"]
        print(f"  {name}: {count} dependents")
    
    print("\nRecommendations:")
    if impact_analysis["high_risk_changes"]:
        print("  - Thorough testing required for high-risk changes")
        print("  - Consider gradual rollout")
        print("  - Update documentation for modified public APIs")
    else:
        print("  - Low-risk changes detected")
        print("  - Standard testing should be sufficient")

# Example usage
if __name__ == "__main__":
    # Mock previous commit data (normally from git or database)
    previous_data = [
        {
            "relative_id": "src/main.py#main",
            "hashed_id": "abc123",
            "code_text": "def main():\n    print('Hello')"
        }
    ]
    
    analyze_change_impact("/path/to/project", previous_data)
```

### Custom Metrics Collection

```python
"""
Collect custom metrics from code analysis
"""
from blarify.prebuilt.graph_builder import GraphBuilder
import ast
import os
from collections import defaultdict

class CodeMetricsCollector:
    """Collect various code quality metrics"""
    
    def __init__(self, root_path):
        self.root_path = root_path
        self.metrics = defaultdict(dict)
    
    def collect_all_metrics(self):
        """Collect all available metrics"""
        
        # Build graph
        builder = GraphBuilder(
            root_path=self.root_path,
            extensions_to_skip=[".json"],
            names_to_skip=["__pycache__", "tests"]
        )
        
        graph = builder.build()
        nodes = graph.get_nodes_as_objects()
        relationships = graph.get_relationships_as_objects()
        
        # Collect basic metrics
        self.collect_basic_metrics(nodes, relationships)
        
        # Collect complexity metrics
        self.collect_complexity_metrics(nodes)
        
        # Collect dependency metrics
        self.collect_dependency_metrics(relationships)
        
        # Collect Python-specific metrics
        self.collect_python_metrics(nodes)
        
        return self.metrics
    
    def collect_basic_metrics(self, nodes, relationships):
        """Collect basic count metrics"""
        
        node_counts = defaultdict(int)
        for node in nodes:
            node_counts[node["type"]] += 1
        
        relationship_counts = defaultdict(int)
        for rel in relationships:
            relationship_counts[rel["type"]] += 1
        
        self.metrics["basic"] = {
            "total_nodes": len(nodes),
            "total_relationships": len(relationships),
            "node_counts": dict(node_counts),
            "relationship_counts": dict(relationship_counts)
        }
    
    def collect_complexity_metrics(self, nodes):
        """Collect complexity-related metrics"""
        
        complexities = {
            "max_nesting": 0,
            "avg_nesting": 0,
            "function_lengths": [],
            "class_sizes": []
        }
        
        nesting_levels = []
        
        for node in nodes:
            attributes = node["attributes"]
            level = attributes.get("level", 0)
            
            if node["type"] == "FUNCTION":
                nesting_levels.append(level)
                
                # Calculate function length
                start_line = attributes.get("start_line")
                end_line = attributes.get("end_line")
                if start_line and end_line:
                    length = end_line - start_line + 1
                    complexities["function_lengths"].append(length)
            
            elif node["type"] == "CLASS":
                methods_count = attributes.get("stats_methods_defined", 0)
                complexities["class_sizes"].append(methods_count)
        
        if nesting_levels:
            complexities["max_nesting"] = max(nesting_levels)
            complexities["avg_nesting"] = sum(nesting_levels) / len(nesting_levels)
        
        # Calculate percentiles
        if complexities["function_lengths"]:
            complexities["function_length_percentiles"] = {
                "50th": self._percentile(complexities["function_lengths"], 50),
                "90th": self._percentile(complexities["function_lengths"], 90),
                "95th": self._percentile(complexities["function_lengths"], 95)
            }
        
        self.metrics["complexity"] = complexities
    
    def collect_dependency_metrics(self, relationships):
        """Collect dependency-related metrics"""
        
        # Build dependency graph
        dependencies = defaultdict(set)
        dependents = defaultdict(set)
        
        for rel in relationships:
            source = rel["sourceId"]
            target = rel["targetId"]
            dependencies[source].add(target)
            dependents[target].add(source)
        
        # Calculate metrics
        dep_counts = [len(deps) for deps in dependencies.values()]
        dependent_counts = [len(deps) for deps in dependents.values()]
        
        self.metrics["dependencies"] = {
            "total_dependencies": len(relationships),
            "max_dependencies": max(dep_counts) if dep_counts else 0,
            "avg_dependencies": sum(dep_counts) / len(dep_counts) if dep_counts else 0,
            "max_dependents": max(dependent_counts) if dependent_counts else 0,
            "avg_dependents": sum(dependent_counts) / len(dependent_counts) if dependent_counts else 0,
            "cyclic_dependencies": self._detect_cycles(dependencies)
        }
    
    def collect_python_metrics(self, nodes):
        """Collect Python-specific metrics"""
        
        python_metrics = {
            "docstring_coverage": 0,
            "type_hint_coverage": 0,
            "test_coverage_estimate": 0
        }
        
        python_functions = []
        python_classes = []
        
        for node in nodes:
            if node["type"] in ["FUNCTION", "CLASS"]:
                path = node["attributes"]["path"]
                if path.endswith('.py'):
                    if node["type"] == "FUNCTION":
                        python_functions.append(node)
                    else:
                        python_classes.append(node)
        
        # Analyze Python files for additional metrics
        for node in python_functions + python_classes:
            path = node["attributes"]["path"].replace("file://", "")
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    try:
                        tree = ast.parse(f.read())
                        # Analyze AST for docstrings, type hints, etc.
                        # This is a simplified example
                        python_metrics["docstring_coverage"] += 0.5  # Placeholder
                    except:
                        pass
        
        self.metrics["python_specific"] = python_metrics
    
    def _percentile(self, data, percentile):
        """Calculate percentile of a list"""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def _detect_cycles(self, dependencies):
        """Simple cycle detection"""
        # This is a simplified implementation
        visited = set()
        rec_stack = set()
        
        def has_cycle(node):
            if node in rec_stack:
                return True
            if node in visited:
                return False
            
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in dependencies.get(node, []):
                if has_cycle(neighbor):
                    return True
            
            rec_stack.remove(node)
            return False
        
        cycle_count = 0
        for node in dependencies:
            if node not in visited:
                if has_cycle(node):
                    cycle_count += 1
        
        return cycle_count

# Usage example
if __name__ == "__main__":
    collector = CodeMetricsCollector("/path/to/python/project")
    metrics = collector.collect_all_metrics()
    
    import json
    print(json.dumps(metrics, indent=2, default=str))
```

These examples demonstrate the versatility and power of Blarify for various code analysis scenarios. Each example can be adapted and extended based on your specific requirements and use cases.
