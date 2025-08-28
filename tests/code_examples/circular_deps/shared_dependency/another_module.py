"""Another module that uses shared dependencies from module_with_shared."""

from .module_with_shared import validate_input, log_activity, format_output


def api_endpoint_1(request_data):
    """API endpoint that uses shared utilities."""
    # Uses the same shared utilities as other functions
    validated = validate_input(request_data)
    log_activity("api_1", validated)
    result = process_request(validated)
    return format_output(result)


def api_endpoint_2(request_data):
    """Another API endpoint using shared utilities."""
    validated = validate_input(request_data)
    log_activity("api_2", validated)
    result = process_request(validated)
    return format_output(result)


def process_request(data):
    """Internal processing function."""
    # This function is also shared between endpoints
    return {"processed": data, "timestamp": "2024-01-01"}


def background_task():
    """Background task that also uses shared utilities."""
    data = fetch_data()
    validated = validate_input(data)
    log_activity("background", validated)
    return process_request(validated)


def fetch_data():
    """Fetch some data for processing."""
    return {"sample": "data"}