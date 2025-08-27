"""Module 2 with circular dependency."""


def function_2(value: int) -> int:
    """Function 2 that calls function 0."""
    if value <= 0:
        return value

    # Completes the cycle
    from .module_0 import function_0

    return function_0(value - 1)


def helper_function_2() -> str:
    """Helper function without dependencies."""
    return "Helper 2"