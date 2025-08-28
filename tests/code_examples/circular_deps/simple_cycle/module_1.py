"""Module 1 with circular dependency."""


def function_1(value: int) -> int:
    """Function 1 that calls function 2."""
    if value <= 0:
        return value

    from .module_2 import function_2

    return function_2(value - 1)


def helper_function_1() -> str:
    """Helper function without dependencies."""
    return "Helper 1"