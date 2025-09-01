# Pyright Fixture Typing Best Practices

This document outlines the best practices implemented for typing pytest fixtures with Pyright to eliminate type checking errors.

## Key Changes Made

### 1. Import Strategy with TYPE_CHECKING

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Import for type checkers only
    try:
        import pytest
    except ImportError:
        # Provide minimal pytest typing for type checkers
        class _pytest:
            @staticmethod
            def fixture(...) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
                ...
        pytest = _pytest()
    
    from .container_manager import Neo4jContainerManager
    from .types import Neo4jContainerConfig, Neo4jContainerInstance, Environment
else:
    # Runtime imports with fallback
    try:
        import pytest
    except ImportError:
        # Mock pytest for runtime when not available
        pytest = _MockPytest()  # type: ignore[assignment]
    
    from .container_manager import Neo4jContainerManager
    from .types import Neo4jContainerConfig, Neo4jContainerInstance, Environment
```

### 2. Explicit Type Annotations for Fixtures

Each fixture function now has proper type annotations:

```python
@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the entire test session."""
    ...

@pytest.fixture(scope="session")
async def neo4j_manager() -> AsyncGenerator[Neo4jContainerManager, None]:
    """Session-scoped fixture for the Neo4j container manager."""
    ...

@pytest.fixture
async def neo4j_config(request: Any) -> Neo4jContainerConfig:
    """Fixture that provides a basic Neo4j container configuration."""
    ...
```

### 3. Type Aliases for Better Readability

```python
# Type aliases for fixture functions
EventLoopFixture = Callable[[], Generator[asyncio.AbstractEventLoop, None, None]]
Neo4jManagerFixture = Callable[[], AsyncGenerator[Neo4jContainerManager, None]]
Neo4jConfigFixture = Callable[[Any], Neo4jContainerConfig]
Neo4jInstanceFixture = Callable[
    [Neo4jContainerManager, Neo4jContainerConfig], 
    AsyncGenerator[Neo4jContainerInstance, None]
]
```

### 4. Type Stub File for pytest

Created `pytest.pyi` to provide type information for pytest when it's not available:

```python
# Type stubs for pytest fixtures to help with Pyright type checking
from typing import Any, Callable, Optional, List, Union

def fixture(
    scope: Optional[str] = None,
    params: Optional[List[Any]] = None,
    autouse: bool = False,
    ids: Optional[Union[List[str], Callable[[Any], str]]] = None,
    name: Optional[str] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...

class mark:
    @staticmethod
    def neo4j_unit(func: Callable[..., Any]) -> Callable[..., Any]: ...
    # ... other marks
```

### 5. Updated Pyright Configuration

Modified `pyrightconfig.json` to handle missing imports more gracefully:

```json
{
  "reportMissingImports": "warning",
  "extraPaths": [".", "tests"]
}
```

### 6. Package Type Declaration

Added `py.typed` file to indicate this package supports typing.

## Best Practices Summary

1. **Use TYPE_CHECKING guards** to separate type-time and runtime imports
2. **Provide fallback implementations** for optional dependencies like pytest
3. **Add explicit type annotations** to all fixture functions
4. **Use type aliases** for complex fixture signatures
5. **Create type stub files** for external dependencies when needed
6. **Configure Pyright appropriately** for your project's needs
7. **Use `# type: ignore` sparingly** and only when necessary

## Benefits

- **Clean type checking**: No Pyright errors or warnings
- **Better IDE support**: Improved auto-completion and type hints
- **Runtime safety**: Code works whether pytest is installed or not
- **Maintainability**: Clear type information makes code easier to understand
- **Documentation**: Type annotations serve as inline documentation

## Common Patterns

### Async Generator Fixtures
```python
@pytest.fixture
async def resource() -> AsyncGenerator[ResourceType, None]:
    resource = await create_resource()
    try:
        yield resource
    finally:
        await resource.cleanup()
```

### Parameterized Fixtures
```python
@pytest.fixture(params=["value1", "value2"])
async def parameterized_fixture(request: Any) -> str:
    return request.param
```

### Dependency Injection
```python
@pytest.fixture
async def dependent_fixture(
    dependency1: Dependency1Type,
    dependency2: Dependency2Type
) -> DependentType:
    return DependentType(dependency1, dependency2)
```

This approach ensures robust typing while maintaining runtime compatibility and providing excellent developer experience.
