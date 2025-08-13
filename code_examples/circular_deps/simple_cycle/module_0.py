"""Module 0 with circular dependency."""


def function_0(value: int) -> int:
    """Function 0 that calls function 1."""
    if value <= 0:
        return value

    # This creates the circular dependency
    from .module_1 import function_1

    return function_1(value - 1)


def helper_function_0() -> str:
    """Helper function without dependencies."""
    return "Helper 0"