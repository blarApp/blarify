"""Unit tests for MCP tool wrapper."""

from typing import Any, Dict, Optional
from unittest.mock import Mock

import pytest
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.mcp_server.tools import MCPToolWrapper


class MockInput(BaseModel):
    """Mock input schema for testing."""
    
    required_field: str = Field(description="A required field")
    optional_field: Optional[int] = Field(default=None, description="An optional field")
    list_field: list[str] = Field(default_factory=list, description="A list field")
    bool_field: bool = Field(default=False, description="A boolean field")


class MockTool(BaseTool):
    """Mock Langchain tool for testing."""
    
    name: str = "mock_tool"
    description: str = "A mock tool for testing"
    args_schema: type[BaseModel] = MockInput  # type: ignore
    
    def _run(self, run_manager: Any, **kwargs: Any) -> str:
        """Mock run implementation."""
        return f"Mock result: {kwargs}"


class TestMCPToolWrapper:
    """Test suite for MCPToolWrapper."""
    
    @pytest.fixture
    def mock_tool(self) -> MockTool:
        """Create a mock tool instance."""
        return MockTool()
    
    @pytest.fixture
    def wrapper(self, mock_tool: MockTool) -> MCPToolWrapper:
        """Create a wrapper instance."""
        return MCPToolWrapper(mock_tool)
    
    def test_wrapper_initialization(self, wrapper: MCPToolWrapper, mock_tool: MockTool) -> None:
        """Test wrapper initialization."""
        assert wrapper.name == "mock_tool"
        assert wrapper.description == "A mock tool for testing"
        assert wrapper.langchain_tool == mock_tool
    
    def test_get_mcp_schema(self, wrapper: MCPToolWrapper) -> None:
        """Test MCP schema generation."""
        schema = wrapper.get_mcp_schema()
        
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        
        # Check properties
        properties = schema["properties"]
        assert "required_field" in properties
        assert "optional_field" in properties
        assert "list_field" in properties
        assert "bool_field" in properties
        
        # Check required fields
        assert "required_field" in schema["required"]
        assert "optional_field" not in schema["required"]
        assert "list_field" not in schema["required"]
        assert "bool_field" not in schema["required"]
    
    def test_schema_field_types(self, wrapper: MCPToolWrapper) -> None:
        """Test correct type mapping in schema."""
        schema = wrapper.get_mcp_schema()
        properties = schema["properties"]
        
        assert properties["required_field"]["type"] == "string"
        assert properties["required_field"]["description"] == "A required field"
        
        assert properties["optional_field"]["type"] == "integer"
        assert properties["optional_field"]["description"] == "An optional field"
        assert properties["optional_field"]["default"] is None
        
        assert properties["list_field"]["type"] == "array"
        assert properties["list_field"]["items"]["type"] == "string"
        
        assert properties["bool_field"]["type"] == "boolean"
        assert properties["bool_field"]["default"] is False
    
    @pytest.mark.asyncio
    async def test_invoke_success(self, wrapper: MCPToolWrapper, mock_tool: MockTool) -> None:
        """Test successful tool invocation."""
        arguments = {
            "required_field": "test_value",
            "optional_field": 42,
            "list_field": ["item1", "item2"],
            "bool_field": True
        }
        
        result = await wrapper.invoke(arguments)
        assert "Mock result:" in result
        assert "test_value" in result
        assert "42" in result
    
    @pytest.mark.asyncio
    async def test_invoke_with_minimal_args(self, wrapper: MCPToolWrapper) -> None:
        """Test tool invocation with minimal arguments."""
        arguments = {
            "required_field": "minimal"
        }
        
        result = await wrapper.invoke(arguments)
        assert "Mock result:" in result
        assert "minimal" in result
    
    @pytest.mark.asyncio
    async def test_invoke_error_handling(self, wrapper: MCPToolWrapper, mock_tool: MockTool) -> None:
        """Test error handling during invocation."""
        # Mock the tool to raise an exception
        mock_tool._run = Mock(side_effect=Exception("Tool error"))
        
        arguments = {
            "required_field": "test"
        }
        
        result = await wrapper.invoke(arguments)
        assert "Error:" in result
        assert "Tool error" in result
    
    def test_to_mcp_tool_definition(self, wrapper: MCPToolWrapper) -> None:
        """Test complete MCP tool definition generation."""
        definition = wrapper.to_mcp_tool_definition()
        
        assert definition["name"] == "mock_tool"
        assert definition["description"] == "A mock tool for testing"
        assert "inputSchema" in definition
        assert definition["inputSchema"]["type"] == "object"
    
    def test_wrapper_with_no_schema(self) -> None:
        """Test wrapper with a tool that has no schema."""
        
        class NoSchemaTool(BaseTool):
            name: str = "no_schema_tool"
            description: str = "Tool without schema"
            
            def _run(self, run_manager: Any, **kwargs: Any) -> str:
                return "No schema result"
        
        tool = NoSchemaTool()
        wrapper = MCPToolWrapper(tool)
        
        schema = wrapper.get_mcp_schema()
        assert schema["type"] == "object"
        assert schema["properties"] == {}
        assert schema["required"] == []
    
    def test_complex_field_types(self) -> None:
        """Test handling of complex field types."""
        
        class ComplexInput(BaseModel):
            dict_field: Dict[str, Any] = Field(default_factory=dict, description="A dict field")
            float_field: float = Field(default=0.0, description="A float field")
        
        class ComplexTool(BaseTool):
            name: str = "complex_tool"
            description: str = "Tool with complex types"
            args_schema: type[BaseModel] = ComplexInput  # type: ignore
            
            def _run(self, run_manager: Any, **kwargs: Any) -> str:
                return "Complex result"
        
        tool = ComplexTool()
        wrapper = MCPToolWrapper(tool)
        
        schema = wrapper.get_mcp_schema()
        properties = schema["properties"]
        
        assert properties["dict_field"]["type"] == "object"
        assert properties["float_field"]["type"] == "number"