"""API entry points with branching logic."""

from typing import Dict, Any
from .handlers import handle_get_request, handle_post_request


def api_get_endpoint(params: Dict[str, Any]) -> Dict[str, Any]:
    """GET endpoint that branches to handler."""
    return handle_get_request(params)


def api_post_endpoint(data: Dict[str, Any]) -> Dict[str, Any]:
    """POST endpoint that branches to handler."""
    return handle_post_request(data)