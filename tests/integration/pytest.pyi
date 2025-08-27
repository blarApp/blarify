"""Type stub for pytest module."""

from typing import Any, Callable, List, Optional, TypeVar, Union

F = TypeVar("F", bound=Callable[..., Any])

def fixture(
    fixture_function: Optional[F] = None,
    *,
    scope: str = "function",
    params: Optional[List[Any]] = None,
    autouse: bool = False,
    ids: Optional[Union[List[str], Callable[[Any], str]]] = None,
    name: Optional[str] = None,
) -> Union[F, Callable[[F], F]]: ...

class mark:
    @staticmethod
    def integration(func: F) -> F: ...
    @staticmethod
    def parametrize(
        argnames: str,
        argvalues: List[Any],
        indirect: Union[bool, List[str]] = False,
        ids: Optional[Union[List[str], Callable[[Any], str]]] = None,
        scope: Optional[str] = None,
    ) -> Callable[[F], F]: ...
