"""Module demonstrating shared dependencies that are NOT cycles."""


def process_data_a(data):
    """First function that uses shared utilities."""
    validated = validate_input(data)
    logged = log_activity("process_a", validated)
    return transform_data(logged)


def process_data_b(data):
    """Second function that uses shared utilities."""
    validated = validate_input(data)
    logged = log_activity("process_b", validated)
    return transform_data(logged)


def process_data_c(data):
    """Third function that uses shared utilities."""
    validated = validate_input(data)
    logged = log_activity("process_c", validated)
    return transform_data(logged)


# Shared utility functions - these are called by multiple functions
# but do NOT create cycles

def validate_input(data):
    """Shared validation utility."""
    if data is None:
        raise ValueError("Data cannot be None")
    return data


def log_activity(activity_name, data):
    """Shared logging utility."""
    print(f"[LOG] {activity_name}: processing {len(str(data))} bytes")
    return data


def transform_data(data):
    """Shared transformation utility."""
    if isinstance(data, str):
        return data.upper()
    return str(data)


def format_output(result):
    """Another shared utility used by multiple functions."""
    return f"Result: {result}"