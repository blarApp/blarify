"""Utility for loading pre-created test code with circular dependencies."""

from pathlib import Path


class CircularDependencyLoader:
    """Loads pre-created test code with circular function dependencies."""

    @staticmethod
    def get_simple_cycle_path() -> Path:
        """Get path to simple cycle test case."""
        # Get the absolute path relative to this file's location
        base_path = Path(__file__).parent.parent.parent
        return base_path / "code_examples" / "circular_deps" / "simple_cycle"

    @staticmethod
    def get_complex_cycle_path() -> Path:
        """Get path to complex cycle test case."""
        # Get the absolute path relative to this file's location
        base_path = Path(__file__).parent.parent.parent
        return base_path / "code_examples" / "circular_deps" / "complex_cycle"

    @staticmethod
    def get_high_concurrency_path() -> Path:
        """Get path to high concurrency test case."""
        # Get the absolute path relative to this file's location
        base_path = Path(__file__).parent.parent.parent
        return base_path / "code_examples" / "circular_deps" / "high_concurrency"