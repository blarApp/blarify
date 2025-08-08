"""
Python imports example for testing import relationship parsing.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Optional

# Local imports (these will reference the other test files)
from .simple_module import SimpleClass, simple_function
from .class_with_inheritance import BaseProcessor, TextProcessor


def demonstrate_imports() -> Dict[str, str]:
    """Demonstrate usage of imported modules and functions."""
    # Use standard library imports
    current_path = os.getcwd()
    python_version = sys.version_info
    path_obj = Path(current_path)
    
    # Use local imports
    simple_obj = SimpleClass("test_value")
    greeting = simple_function()
    processor = TextProcessor("import_test")
    
    return {
        "current_path": current_path,
        "python_version": f"{python_version.major}.{python_version.minor}",
        "path_exists": str(path_obj.exists()),
        "simple_value": simple_obj.get_value(),
        "greeting": greeting,
        "processor_name": processor.get_name()
    }


class ImportExample:
    """Class that uses imported functionality."""

    def __init__(self) -> None:
        self.processor: Optional[BaseProcessor] = None
        self.simple_obj: Optional[SimpleClass] = None

    def initialize(self) -> None:
        """Initialize with imported classes."""
        self.processor = TextProcessor("example_processor", "PREFIX: ")
        self.simple_obj = SimpleClass("imported_value")

    def process_data(self, data: str) -> str:
        """Process data using imported functionality."""
        if not self.processor:
            self.initialize()
        
        # Use the processor
        result = self.processor.process(data) if self.processor else ""
        
        # Use the simple object
        if self.simple_obj:
            value = self.simple_obj.get_value()
            result += f" (with {value})"
        
        return result


# Module-level usage of imports
DEFAULT_PROCESSOR = TextProcessor("default", ">> ")
EXAMPLE_INSTANCE = ImportExample()