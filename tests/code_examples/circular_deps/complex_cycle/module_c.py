"""Module C completing the main cycle."""


def function_c(depth: int) -> str:
    """Function that completes main circular dependency."""
    if depth <= 0:
        return "function_c_result"

    from .module_a import function_a

    result = function_a(depth - 1)
    return f"function_c->{result}"


def independent_function() -> str:
    """Function without circular dependencies."""
    return "independent_result"