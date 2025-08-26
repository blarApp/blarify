"""Mutual recursion examples for cyclic workflow testing."""


def is_even(n: int) -> bool:
    """Check if number is even using mutual recursion."""
    if n == 0:
        return True
    return is_odd(n - 1)


def is_odd(n: int) -> bool:
    """Check if number is odd using mutual recursion."""
    if n == 0:
        return False
    return is_even(n - 1)


def process_a(value: int) -> int:
    """Process value through mutual recursion."""
    if value <= 0:
        return 0
    return process_b(value - 1) + 1


def process_b(value: int) -> int:
    """Process value through mutual recursion."""
    if value <= 0:
        return 1
    return process_a(value - 1) * 2