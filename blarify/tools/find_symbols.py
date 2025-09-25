from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager


# Pydantic Response Models
class SymbolSearchResult(BaseModel):
    """Symbol search result response model."""

    id: str = Field(description="Unique UUID identifier for the symbol")
    name: str = Field(description="Name of the symbol")
    type: list[str] = Field(description="Type(s) of the symbol")
    file_path: str = Field(description="File path where the symbol is located")
    code: Optional[str] = Field(default=None, description="Code preview of the symbol")


# Simplified utility functions (removing blar dependencies)
def mark_deleted_or_added_lines(text: str) -> str:
    """Mark deleted or added lines (simplified implementation)."""
    return text


class Input(BaseModel):
    name: str = Field(description="Name of the symbol to search for (exact match)", min_length=1)
    type: str = Field(description="Type of symbol to search for. Must be one of: 'FUNCTION', 'CLASS', 'FILE', 'FOLDER'")


class FindSymbols(BaseTool):
    name: str = "find_symbols"
    description: str = (
        "Search for code symbols (functions, classes, files, or folders) by exact name. "
        "Returns matching symbols with their IDs, file locations, and code previews. "
        "Both 'name' and 'type' parameters are required."
    )
    db_manager: AbstractDbManager = Field(description="Database manager for queries")

    args_schema: type[BaseModel] = Input  # type: ignore[assignment]

    def _run(
        self,
        name: str,
        type: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> dict[str, Any] | str:
        """Find symbols by exact name and type."""
        node_type = type.upper()
        if node_type not in {"FUNCTION", "CLASS", "FILE", "FOLDER"}:
            return "Invalid type. Must be one of: 'FUNCTION', 'CLASS', 'FILE', 'FOLDER'"

        dto_nodes = self.db_manager.get_node_by_name_and_type(
            name=name,
            node_type=node_type,
        )

        # Convert DTOs to response models
        symbols: list[SymbolSearchResult] = []
        for dto in dto_nodes:
            symbol = SymbolSearchResult(
                id=dto.node_id,
                name=dto.node_name,
                type=dto.node_type,
                file_path=dto.file_path,
                code=dto.code,
            )
            symbols.append(symbol)

        if len(symbols) > 15:
            return "Too many symbols found. Please refine your query or use another tool"

        symbol_dicts = [symbol.model_dump() for symbol in symbols]
        for symbol in symbol_dicts:
            # Handle diff_text if it exists, otherwise skip
            diff_text = symbol.get("diff_text")
            if diff_text is not None:
                symbol["diff_text"] = mark_deleted_or_added_lines(diff_text)

        return {
            "symbols": symbol_dicts,
        }
