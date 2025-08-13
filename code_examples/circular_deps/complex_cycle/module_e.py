"""Module E in the branch cycle."""


def function_e(depth: int) -> str:
    """Function in the branch circular dependency."""
    if depth <= 0:
        return "function_e_result"

    from .module_f import function_f

    result = function_f(depth - 1)
    return f"function_e->{result}"


def independent_function() -> str:
    """Function without circular dependencies."""
    return "independent_result"