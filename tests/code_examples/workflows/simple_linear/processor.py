"""Middle tier processor for workflow."""

from typing import Dict, Any
from .utils import transform_value


def process_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process the input data through transformation."""
    value = data.get("value", 0)
    transformed = transform_value(value)
    return {"result": transformed, "original": value}