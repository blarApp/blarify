"""Module 0 with circular dependency."""

# Import at module level for simplicity in testing
import module_1


def function_0(value: int) -> int:
    """Function 0 that calls function 1."""
    if value <= 0:
        return value

    # This creates the circular dependency via direct call
    return module_1.function_1(value - 1)


def helper_function_0() -> str:
    """Helper function without dependencies."""
    return "Helper 0"