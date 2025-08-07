"""
Python class inheritance example for testing relationship parsing.
"""

from abc import ABC, abstractmethod
from typing import List


class BaseProcessor(ABC):
    """Abstract base class for processors."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def process(self, data: str) -> str:
        """Abstract method that must be implemented by subclasses."""
        pass

    def get_name(self) -> str:
        """Return the processor name."""
        return self.name


class TextProcessor(BaseProcessor):
    """Concrete implementation of BaseProcessor for text processing."""

    def __init__(self, name: str, prefix: str = "") -> None:
        super().__init__(name)
        self.prefix = prefix

    def process(self, data: str) -> str:
        """Process text data by adding a prefix."""
        return f"{self.prefix}{data}"

    def batch_process(self, items: List[str]) -> List[str]:
        """Process multiple items."""
        return [self.process(item) for item in items]


class AdvancedTextProcessor(TextProcessor):
    """Advanced text processor with additional functionality."""

    def __init__(self, name: str, prefix: str = "", suffix: str = "") -> None:
        super().__init__(name, prefix)
        self.suffix = suffix

    def process(self, data: str) -> str:
        """Process text data by adding both prefix and suffix."""
        base_result = super().process(data)
        return f"{base_result}{self.suffix}"


# Factory function
def create_processor(processor_type: str, name: str) -> BaseProcessor:
    """Factory function to create processors."""
    if processor_type == "text":
        return TextProcessor(name)
    elif processor_type == "advanced":
        return AdvancedTextProcessor(name)
    else:
        raise ValueError(f"Unknown processor type: {processor_type}")


# Usage example
def example_usage() -> None:
    """Example of how to use the processors."""
    processor = create_processor("text", "example")
    result = processor.process("Hello World")
    print(result)