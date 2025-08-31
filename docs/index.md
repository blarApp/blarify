# Blarify Documentation

Welcome to the comprehensive documentation for Blarify - a tool that transforms your codebase into a graph structure for analysis and visualization.

## 📚 Documentation Index

### Getting Started
- **[Installation Guide](installation.md)** - Complete setup instructions for all platforms
- **[Quickstart Guide](quickstart.md)** - Get up and running in 5 minutes
- **[FAQ](faq.md)** - Answers to frequently asked questions

### User Guides
- **[User Guide](user-guide.md)** - Comprehensive usage guide with advanced patterns
- **[Examples](examples.md)** - Practical examples for different use cases
- **[API Reference](api-reference.md)** - Complete API documentation
- **[Tools Documentation](tools.md)** - Langchain-compatible tools for AI agent integration

### Advanced Features
- **[DocumentationCreator](documentation-creator.md)** - Main documentation generation system with recursive DFS processing
- **[Workflow Nodes 4-Layer Architecture](implementation_features/workflow_nodes_4layer_architecture.md)** - Edge-based execution flows and business process analysis
- **[Semantic Documentation Layer](implementation_features/semantic_documentation_layer.md)** - AI-powered code documentation
- **[Spec Analysis Layer](implementation_features/spec_analysis_layer.md)** - Business specification analysis

### Development
- **[Architecture Overview](architecture.md)** - Understanding Blarify's internal design
- **[Testing Guide](testing-guide.md)** - Comprehensive guide to testing framework and adding tests
- **[Contributing Guide](contributing.md)** - How to contribute to the project

## 🚀 Quick Navigation

### I want to...

**Get started quickly** → [Quickstart Guide](quickstart.md)

**Install Blarify** → [Installation Guide](installation.md)

**Understand the API** → [API Reference](api-reference.md)

**See real examples** → [Examples](examples.md)

**Integrate with AI agents** → [Tools Documentation](tools.md)

**Troubleshoot issues** → [FAQ](faq.md)

**Write tests for Blarify** → [Testing Guide](testing-guide.md)

**Contribute to the project** → [Contributing Guide](contributing.md)

**Understand the architecture** → [Architecture Overview](architecture.md)

## 📖 What is Blarify?

Blarify is a powerful code analysis tool that:

- **Converts your codebase into a graph structure** with nodes (files, classes, functions) and relationships (calls, imports, dependencies)
- **Supports multiple programming languages** including Python, JavaScript, TypeScript, Ruby, Go, and C#
- **Uses Language Server Protocol (LSP)** for accurate semantic analysis
- **Stores results in graph databases** like Neo4j or FalkorDB for querying and visualization
- **Tracks code changes** and can analyze the impact of modifications

## 🎯 Use Cases

### Code Understanding
- Visualize large codebase architecture
- Understand dependencies and relationships
- Find circular dependencies
- Navigate unfamiliar code

### Refactoring & Maintenance  
- Assess impact of proposed changes
- Find dead code and unused functions
- Identify tightly coupled components
- Plan refactoring strategies

### Documentation & Analysis
- Generate architecture documentation
- Create dependency graphs
- Analyze code complexity
- Track technical debt

### CI/CD Integration
- Automated code analysis in pipelines
- Change impact assessment for PRs
- Code quality monitoring
- Architecture validation

## 🏗️ How It Works

```
Code Files → Tree-sitter Parser → Abstract Syntax Tree
     ↓
LSP Analysis → Semantic References → Code Relationships  
     ↓
Graph Builder → Node & Relationship Objects → Graph Database
     ↓
Query & Visualization → Insights & Analysis
```

## 🔧 Supported Languages

| Language | Tree-sitter | LSP Support | Status |
|----------|-------------|-------------|--------|
| Python | ✅ | ✅ (Jedi) | Full Support |
| JavaScript | ✅ | ✅ (Optional) | Full Support |
| TypeScript | ✅ | ✅ (Optional) | Full Support |
| Ruby | ✅ | ❌ | Structural Only |
| Go | ✅ | ❌ | Structural Only |
| C# | ✅ | ❌ | Structural Only |
| Java | ✅ | ❌ | Structural Only |
| PHP | ✅ | ❌ | Structural Only |

## 💾 Database Support

| Database | Status | Best For |
|----------|--------|----------|
| **FalkorDB** | ✅ Recommended | Beginners, fast setup |
| **Neo4j** | ✅ Full Support | Production, advanced queries |
| **AuraDB** | ✅ Cloud | Managed Neo4j service |

## 📈 Performance Characteristics

- **Small projects** (< 1K files): ~10 seconds
- **Medium projects** (1K-10K files): ~1-5 minutes  
- **Large projects** (> 10K files): ~5-30 minutes

*Performance varies based on language, LSP usage, and system resources.*

## 🛠️ Installation Quick Reference

```bash
# Install Blarify
pip install blarify

# Set up database (choose one)
# FalkorDB (easier)
docker run -d -p 6379:6379 falkordb/falkordb:latest

# Neo4j  
docker run -d -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest
```

## 📝 Basic Usage

```python
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.db_managers.falkordb_manager import FalkorDBManager

# Build graph
builder = GraphBuilder(
    root_path="/path/to/your/project",
    extensions_to_skip=[".json", ".md"],
    names_to_skip=["__pycache__", "node_modules"]
)
graph = builder.build()

# Save to database
manager = FalkorDBManager(repo_id="my-repo", entity_id="my-org")
nodes = graph.get_nodes_as_objects()
relationships = graph.get_relationships_as_objects()
manager.save_graph(nodes, relationships)
manager.close()

print(f"Analyzed {len(nodes)} nodes and {len(relationships)} relationships")
```

## 🔗 External Resources

- **GitHub Repository**: [blarApp/blarify](https://github.com/blarApp/blarify)
- **PyPI Package**: [blarify](https://pypi.org/project/blarify/)
- **Discord Community**: [Join our Discord](https://discord.gg/s8pqnPt5AP)
- **Medium Article**: [How we built a tool to turn any codebase into a graph](https://medium.com/@v4rgas/how-we-built-a-tool-to-turn-any-code-base-into-a-graph-of-its-relationships-23c7bd130f13)

## 📞 Getting Help

### Community Support
- **GitHub Discussions**: General questions and community help
- **Discord**: Real-time chat with the community
- **Stack Overflow**: Tag questions with `blarify`

### Bug Reports & Feature Requests
- **GitHub Issues**: Report bugs or request features
- **Provide details**: Include Python version, OS, and minimal reproduction steps

### Documentation Issues
- **GitHub Issues**: Report documentation problems
- **Pull Requests**: Suggest improvements directly

## 🎉 What's Next?

1. **Start with the [Quickstart Guide](quickstart.md)** to analyze your first project
2. **Explore [Examples](examples.md)** to see different use cases
3. **Read the [User Guide](user-guide.md)** for advanced features
4. **Join our [Discord](https://discord.gg/s8pqnPt5AP)** to connect with the community

## 📄 License

Blarify is open source software licensed under the [MIT License](https://github.com/blarApp/blarify/blob/main/LICENSE.md).

---

*Documentation last updated: December 2024*
