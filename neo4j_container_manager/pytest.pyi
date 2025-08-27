# Type stubs for pytest fixtures to help with Pyright type checking
from typing import Any, Callable, Optional, List, Union

class FixtureRequest:
    node: Any
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

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
    @staticmethod
    def neo4j_integration(func: Callable[..., Any]) -> Callable[..., Any]: ...
    @staticmethod
    def neo4j_performance(func: Callable[..., Any]) -> Callable[..., Any]: ...
    @staticmethod
    def slow(func: Callable[..., Any]) -> Callable[..., Any]: ...
