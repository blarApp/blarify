"""Request handlers with shared service usage."""

from typing import Dict, Any
from .services import validate_data, format_response


def handle_get_request(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GET request with validation."""
    if validate_data(params):
        return format_response({"status": "success", "data": params})
    return format_response({"status": "error", "message": "Invalid params"})


def handle_post_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle POST request with validation."""
    if validate_data(data):
        return format_response({"status": "created", "data": data})
    return format_response({"status": "error", "message": "Invalid data"})