"""Module F connecting branch back to main cycle."""


def function_f(depth: int) -> str:
    """Function connecting branch cycle back to main."""
    if depth <= 0:
        return "function_f_result"

    from .module_b import function_b

    result = function_b(depth - 1)
    return f"function_f->{result}"


def independent_function() -> str:
    """Function without circular dependencies."""
    return "independent_result"