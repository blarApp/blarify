"""Base wrapper for adapting Langchain tools to MCP."""

import logging
from typing import Any, Dict, Type, Union, get_args, get_origin

from langchain_core.tools import BaseTool
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

logger = logging.getLogger(__name__)


class MCPToolWrapper:
    """Wrapper to adapt Langchain tools to MCP protocol."""

    def __init__(self, langchain_tool: BaseTool) -> None:
        """Initialize wrapper with a Langchain tool."""
        self.langchain_tool = langchain_tool
        self.name = langchain_tool.name
        self.description = langchain_tool.description or ""

    def get_mcp_schema(self) -> Dict[str, Any]:
        """Convert Langchain tool schema to MCP format."""
        if not hasattr(self.langchain_tool, "args_schema") or not self.langchain_tool.args_schema:
            return {"type": "object", "properties": {}, "required": []}

        schema_class = self.langchain_tool.args_schema
        # Check if it's actually a Pydantic model class
        if not isinstance(schema_class, type):
            return {"type": "object", "properties": {}, "required": []}
        return self._pydantic_to_mcp_schema(schema_class)

    def _pydantic_to_mcp_schema(self, model: Type[BaseModel]) -> Dict[str, Any]:
        """Convert Pydantic model to MCP JSON schema."""
        properties = {}
        required = []

        for field_name, field_info in model.model_fields.items():
            field_schema = self._field_to_json_schema(field_info)
            properties[field_name] = field_schema

            # Check if field is required
            if field_info.is_required():
                required.append(field_name)

        return {"type": "object", "properties": properties, "required": required}

    def _field_to_json_schema(self, field_info: FieldInfo) -> Dict[str, Any]:
        """Convert a Pydantic field to JSON schema."""
        schema: Dict[str, Any] = {}

        # Add description if available
        if field_info.description:
            schema["description"] = field_info.description

        # Handle the type
        field_type = field_info.annotation

        # Handle Optional types (Union with None)
        origin = get_origin(field_type)
        if origin is Union:
            # This handles Optional types (Union[T, None])
            args = get_args(field_type)
            if len(args) == 2 and type(None) in args:
                # This is Optional[T]
                field_type = args[0] if args[0] is not type(None) else args[1]
                # Note: In JSON Schema, we don't need to explicitly mark as nullable

        # Map Python types to JSON schema types
        if field_type is str:
            schema["type"] = "string"
        elif field_type is int:
            schema["type"] = "integer"
        elif field_type is float:
            schema["type"] = "number"
        elif field_type is bool:
            schema["type"] = "boolean"
        elif get_origin(field_type) is list:
            schema["type"] = "array"
            args = get_args(field_type)
            if args:
                item_type = args[0]
                if item_type is str:
                    schema["items"] = {"type": "string"}
                elif item_type is int:
                    schema["items"] = {"type": "integer"}
                elif item_type is float:
                    schema["items"] = {"type": "number"}
                elif item_type is bool:
                    schema["items"] = {"type": "boolean"}
                else:
                    schema["items"] = {"type": "object"}
        elif get_origin(field_type) is dict:
            schema["type"] = "object"
        else:
            # Default to string for unknown types
            schema["type"] = "string"

        # Add default value if present
        if (
            hasattr(field_info, "default")
            and field_info.default is not PydanticUndefined
            and field_info.default is not None
        ):
            schema["default"] = field_info.default
        elif hasattr(field_info, "default") and field_info.default is None:
            schema["default"] = None

        return schema

    async def invoke(self, arguments: Dict[str, Any]) -> Any:
        """Invoke the wrapped Langchain tool."""
        try:
            # Use the tool's invoke method if available, otherwise fall back to _run
            if hasattr(self.langchain_tool, "invoke"):
                result = self.langchain_tool.invoke(arguments)
            else:
                # The Langchain tool expects a run_manager as first argument
                # which we'll pass as None for now
                result = self.langchain_tool._run(None, **arguments)  # type: ignore[attr-defined]
            return result
        except Exception as e:
            logger.error(f"Error invoking tool {self.name}: {e}")
            return f"Error: {str(e)}"

    def to_mcp_tool_definition(self) -> Dict[str, Any]:
        """Get the complete MCP tool definition."""
        return {"name": self.name, "description": self.description, "inputSchema": self.get_mcp_schema()}
