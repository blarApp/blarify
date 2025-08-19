"""Recursive function examples for cyclic workflow testing."""

from typing import List


def factorial(n: int) -> int:
    """Calculate factorial recursively."""
    if n <= 1:
        return 1
    return n * factorial(n - 1)


def fibonacci(n: int) -> int:
    """Calculate fibonacci number recursively."""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def process_list(items: List[int]) -> List[int]:
    """Process list recursively."""
    if not items:
        return []
    return [items[0] * 2] + process_list(items[1:])