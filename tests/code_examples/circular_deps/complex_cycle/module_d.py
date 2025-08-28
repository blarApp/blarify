"""Module D starting the branch cycle."""


def function_d(depth: int) -> str:
    """Function starting the branch circular dependency."""
    if depth <= 0:
        return "function_d_result"

    from .module_e import function_e

    result = function_e(depth - 1)
    return f"function_d->{result}"


def independent_function() -> str:
    """Function without circular dependencies."""
    return "independent_result"