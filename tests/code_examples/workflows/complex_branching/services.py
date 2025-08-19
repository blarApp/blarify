"""Shared services used by multiple handlers."""

from typing import Dict, Any


def validate_data(data: Dict[str, Any]) -> bool:
    """Validate input data."""
    return bool(data) and "value" not in data or data.get("value") != ""


def format_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """Format the response with metadata."""
    return {
        "response": response,
        "timestamp": "2024-01-01T00:00:00Z",
        "version": "1.0"
    }