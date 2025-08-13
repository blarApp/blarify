"""Module B with complex circular dependencies and branch."""


def function_b(depth: int) -> str:
    """Function that participates in main cycle and branches to secondary cycle."""
    if depth <= 0:
        return "function_b_result"

    from .module_c import function_c
    from .module_d import function_d

    # Create branch to second cycle
    if depth > 5:
        branch_result = function_d(depth // 2)
        result = function_c(depth - 1)
        return f"function_b->{branch_result}->{result}"
    else:
        result = function_c(depth - 1)
        return f"function_b->{result}"


def independent_function() -> str:
    """Function without circular dependencies."""
    return "independent_result"