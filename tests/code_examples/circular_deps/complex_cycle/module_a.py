"""Module A with complex circular dependencies."""


def function_a(depth: int) -> str:
    """Function that participates in circular call chain."""
    if depth <= 0:
        return "function_a_result"

    from .module_b import function_b

    result = function_b(depth - 1)
    return f"function_a->{result}"


def independent_function() -> str:
    """Function without circular dependencies."""
    return "independent_result"