# Contributing Guide

Thank you for your interest in contributing to Blarify! This guide will help you get started with contributing to the project.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Setup](#development-setup)
3. [Project Structure](#project-structure)
4. [Development Workflow](#development-workflow)
5. [Testing](#testing)
6. [Code Style](#code-style)
7. [Documentation](#documentation)
8. [Pull Request Process](#pull-request-process)
9. [Issue Guidelines](#issue-guidelines)
10. [Community](#community)

## Getting Started

### Ways to Contribute

- 🐛 **Bug Reports**: Report bugs and issues
- 💡 **Feature Requests**: Suggest new features
- 📝 **Documentation**: Improve documentation
- 🔧 **Code**: Fix bugs or implement features
- 🧪 **Testing**: Add or improve tests
- 🌐 **Language Support**: Add support for new programming languages

### Before You Start

1. Check existing [issues](https://github.com/blarApp/blarify/issues) and [pull requests](https://github.com/blarApp/blarify/pulls)
2. Join our [Discord community](https://discord.gg/s8pqnPt5AP) for discussions
3. Read this contributing guide thoroughly
4. Familiarize yourself with the [architecture](architecture.md)

## Development Setup

### Prerequisites

- Python 3.10 - 3.14
- Git
- A graph database (Neo4j or FalkorDB) for testing
- Poetry (recommended) or pip

### Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/blarify.git
cd blarify

# Add upstream remote
git remote add upstream https://github.com/blarApp/blarify.git
```

### Environment Setup

#### Using Poetry (Recommended)

```bash
# Install Poetry if you haven't already
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

#### Using pip

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .

# Install development dependencies
pip install -r requirements-dev.txt
```

### Database Setup for Development

#### FalkorDB (Easier for development)

```bash
# Using Docker
docker run -d --name falkordb-dev -p 6379:6379 falkordb/falkordb:latest

# Set environment variables
export FALKORDB_URI=localhost
export FALKORDB_PORT=6379
```

#### Neo4j

```bash
# Using Docker
docker run -d --name neo4j-dev \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/devpassword \
  neo4j:latest

# Set environment variables
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USERNAME=neo4j
export NEO4J_PASSWORD=devpassword
```

### Verify Setup

```bash
# Run a simple test
python -c "
from blarify.prebuilt.graph_builder import GraphBuilder
print('✅ Blarify setup successful!')
"
```

## Project Structure

Understanding the codebase structure:

```
blarify/
├── blarify/                    # Main package
│   ├── __init__.py
│   ├── main.py                # CLI entry point
│   ├── prebuilt/              # User-facing APIs
│   │   └── graph_builder.py   # Main GraphBuilder class
│   ├── code_hierarchy/        # Code parsing and structure
│   │   ├── tree_sitter_helper.py
│   │   └── languages/         # Language-specific definitions
│   ├── code_references/       # LSP integration
│   │   └── lsp_helper.py
│   ├── graph/                 # Graph data structures
│   │   ├── graph.py
│   │   ├── node/             # Node types
│   │   └── relationship/     # Relationship types
│   ├── db_managers/           # Database abstractions
│   │   ├── neo4j_manager.py
│   │   └── falkordb_manager.py
│   ├── project_file_explorer/ # File system utilities
│   └── utils/                 # Common utilities
├── docs/                      # Documentation
├── tests/                     # Test suite
├── examples/                  # Example scripts
└── pyproject.toml            # Project configuration
```

### Key Files to Know

- `blarify/prebuilt/graph_builder.py`: Main user API
- `blarify/project_graph_creator.py`: Core graph creation logic
- `blarify/project_graph_diff_creator.py`: Change tracking logic
- `blarify/code_hierarchy/languages/`: Language-specific parsers
- `blarify/db_managers/`: Database integrations

## Development Workflow

### Creating a Feature Branch

```bash
# Update your main branch
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/bug-description
```

### Making Changes

1. **Start with tests**: Write tests for new functionality
2. **Implement changes**: Write the minimal code to make tests pass
3. **Update documentation**: Update relevant documentation
4. **Test thoroughly**: Run the full test suite

### Commit Guidelines

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Format: type(scope): description
git commit -m "feat(languages): add support for Rust language"
git commit -m "fix(lsp): handle connection timeout gracefully"
git commit -m "docs(api): update GraphBuilder examples"
git commit -m "test(core): add tests for diff creator"
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Adding or updating tests
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `chore`: Maintenance tasks

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=blarify

# Run specific test file
python -m pytest tests/test_graph_builder.py

# Run specific test
python -m pytest tests/test_graph_builder.py::test_basic_build
```

### Writing Tests

#### Unit Tests

```python
# tests/test_new_feature.py
import pytest
from blarify.your_module import YourClass

class TestYourClass:
    def test_basic_functionality(self):
        # Arrange
        instance = YourClass()
        
        # Act
        result = instance.your_method()
        
        # Assert
        assert result == expected_value
    
    def test_error_handling(self):
        instance = YourClass()
        
        with pytest.raises(ValueError):
            instance.your_method(invalid_input)
```

#### Integration Tests

```python
# tests/integration/test_graph_building.py
import tempfile
import os
from blarify.prebuilt.graph_builder import GraphBuilder

def test_python_project_analysis():
    # Create temporary project
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test files
        test_file = os.path.join(temp_dir, "test.py")
        with open(test_file, "w") as f:
            f.write("def hello():\n    return 'world'")
        
        # Test analysis
        builder = GraphBuilder(root_path=temp_dir)
        graph = builder.build()
        
        nodes = graph.get_nodes_as_objects()
        assert len(nodes) > 0
        
        # Verify function node exists
        function_nodes = [n for n in nodes if n["type"] == "FUNCTION"]
        assert len(function_nodes) == 1
        assert function_nodes[0]["attributes"]["name"] == "hello"
```

### Test Database Setup

```python
# tests/conftest.py
import pytest
from blarify.db_managers.falkordb_manager import FalkorDBManager

@pytest.fixture
def test_db_manager():
    """Provide a test database manager"""
    manager = FalkorDBManager(
        repo_id="test-repo",
        entity_id="test-entity"
    )
    yield manager
    
    # Cleanup
    try:
        manager.detatch_delete_nodes_with_path("file://")
    except:
        pass
    manager.close()
```

## Code Style

### Python Style Guide

We follow [PEP 8](https://peps.python.org/pep-0008/) with some modifications:

- **Line length**: 120 characters (configured in `pyproject.toml`)
- **Import sorting**: Use `isort` (configured)
- **Code formatting**: Use `black` (configured)
- **Type hints**: Required for new code

### Linting and Formatting

```bash
# Check code style
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
black .

# Sort imports
isort .

# Type checking (if mypy is installed)
mypy blarify/
```

### Pre-commit Hooks

Set up pre-commit hooks to ensure code quality:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Documentation

### Docstring Format

Use Google-style docstrings:

```python
def create_graph(root_path: str, extensions_to_skip: List[str]) -> Graph:
    """Create a code graph from the given project.
    
    Args:
        root_path: The root directory of the project to analyze.
        extensions_to_skip: List of file extensions to ignore during analysis.
        
    Returns:
        A Graph object containing the project structure and relationships.
        
    Raises:
        ValueError: If root_path doesn't exist or is not a directory.
        FileNotFoundError: If no analyzable files are found.
        
    Example:
        >>> graph = create_graph("/path/to/project", [".json", ".md"])
        >>> print(f"Found {len(graph.get_nodes_as_objects())} nodes")
    """
```

### Type Hints

Use comprehensive type hints:

```python
from typing import List, Dict, Optional, Union, Any
from pathlib import Path

def process_files(
    file_paths: List[Path],
    config: Dict[str, Any],
    output_format: Optional[str] = None
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """Process multiple files with given configuration."""
```

### README Updates

When adding new features, update relevant sections in:
- Main README.md
- docs/quickstart.md (if user-facing)
- docs/api-reference.md (for API changes)
- docs/examples.md (for new examples)

## Pull Request Process

### Before Submitting

1. **Ensure tests pass**: `python -m pytest`
2. **Check code style**: `ruff check .`
3. **Update documentation**: Add/update relevant docs
4. **Test manually**: Verify your changes work as expected
5. **Update CHANGELOG**: Add entry if applicable

### PR Template

```markdown
## Description
Brief description of the changes.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows the project's style guidelines
- [ ] Self-review of code completed
- [ ] Documentation updated
- [ ] Tests added for new functionality
- [ ] All tests pass
```

### Review Process

1. **Automated checks**: CI will run tests and linting
2. **Code review**: Maintainers will review your code
3. **Feedback**: Address any requested changes
4. **Approval**: Once approved, your PR will be merged

## Issue Guidelines

### Bug Reports

Use the bug report template:

```markdown
**Bug Description**
A clear description of the bug.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected Behavior**
What you expected to happen.

**Environment**
- OS: [e.g. macOS 12.0]
- Python version: [e.g. 3.11]
- Blarify version: [e.g. 1.1.0]
- Database: [e.g. Neo4j 5.0]

**Additional Context**
Any other context about the problem.
```

### Feature Requests

Use the feature request template:

```markdown
**Feature Description**
A clear description of what you want to happen.

**Motivation**
Why is this feature needed? What problem does it solve?

**Proposed Solution**
A clear description of what you want to happen.

**Alternatives Considered**
Alternative solutions you've considered.

**Additional Context**
Any other context or screenshots about the feature request.
```

## Community

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and discussions
- **Discord**: Real-time chat and community support
- **Email**: For sensitive issues, contact the maintainers

### Code of Conduct

We follow the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/). Please be respectful and inclusive in all interactions.

### Getting Help

- **Documentation**: Check the docs first
- **GitHub Discussions**: Ask questions
- **Discord**: Real-time help from the community
- **Stack Overflow**: Tag with `blarify`

## Advanced Contributing

### Adding Language Support

To add support for a new programming language:

1. **Create language definitions**:
   ```python
   # blarify/code_hierarchy/languages/new_language_definitions.py
   class NewLanguageDefinitions(LanguageDefinitions):
       @staticmethod
       def get_query_for_definitions() -> str:
           return "YOUR_TREESITTER_QUERY"
   ```

2. **Add TreeSitter grammar**:
   ```bash
   # Add to pyproject.toml dependencies
   tree-sitter-newlang = "^0.20.0"
   ```

3. **Register the language**:
   ```python
   # In blarify/project_graph_creator.py
   elif extension == ".newlang":
       return TreeSitterHelper(NewLanguageDefinitions())
   ```

4. **Add tests**:
   ```python
   # tests/test_new_language.py
   def test_new_language_parsing():
       # Test language-specific parsing
   ```

### Database Backend

To add a new database backend:

1. **Implement the interface**:
   ```python
   # blarify/db_managers/new_db_manager.py
   class NewDbManager(AbstractDbManager):
       def save_graph(self, nodes, edges):
           # Implementation
   ```

2. **Add configuration**:
   ```python
   # Environment variables and connection logic
   ```

3. **Add tests**:
   ```python
   # tests/test_new_db_manager.py
   def test_connection_and_operations():
       # Test database operations
   ```

### Performance Optimization

When contributing performance improvements:

1. **Benchmark first**: Measure current performance
2. **Profile the code**: Identify bottlenecks
3. **Test thoroughly**: Ensure correctness is maintained
4. **Document changes**: Explain the optimization

## Release Process

For maintainers:

1. **Update version**: Update `pyproject.toml`
2. **Update CHANGELOG**: Document all changes
3. **Create release**: Tag and create GitHub release
4. **Publish to PyPI**: `poetry publish`

## Questions?

If you have any questions about contributing, feel free to:
- Open a GitHub Discussion
- Join our Discord server
- Create an issue with the "question" label

Thank you for contributing to Blarify! 🎉
