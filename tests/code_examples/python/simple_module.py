"""
Simple Python module for testing basic functionality.

This module contains basic Python constructs to test
GraphBuilder's ability to parse and analyze Python code.
"""


def simple_function() -> str:
    """A simple function that returns a greeting."""
    return "Hello from Python"


def function_with_parameter(name: str) -> str:
    """A function that takes a parameter and returns a personalized greeting."""
    return f"Hello, {name}!"


class SimpleClass:
    """A simple class for testing class parsing."""

    def __init__(self, value: str) -> None:
        """Initialize with a value."""
        self.value = value

    def get_value(self) -> str:
        """Return the stored value."""
        return self.value

    def process_value(self) -> str:
        """Process the value by calling another method."""
        processed = self._internal_process()
        return processed

    def _internal_process(self) -> str:
        """Internal processing method."""
        return f"Processed: {self.value}"


# Module-level variable
MODULE_CONSTANT: str = "test_constant"


# Function call at module level
result = simple_function()