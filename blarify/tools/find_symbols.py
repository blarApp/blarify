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
    name: Optional[str] = Field(default=None, description="Name of the symbol to search for (exact match)")
    type: str = Field(description="Type of symbol to search for. Must be one of: 'FUNCTION', 'CLASS', 'FILE', 'FOLDER'")
    path_contains: Optional[str] = Field(default=None, description="Filter by file path containing this pattern (e.g., 'components/auth' or 'page.tsx')")


class FindSymbols(BaseTool):
    name: str = "find_symbols"
    description: str = (
        "Search for code symbols (functions, classes, files, or folders) by EXACT name match "
        "or by path pattern. Use 'name' for exact symbol name matching, or 'path_contains' "
        "to find symbols where the file path contains a pattern (e.g., 'page.tsx', 'components/auth'). "
        "Returns matching symbols with their IDs, file locations, and code previews."
    )
    db_manager: AbstractDbManager = Field(description="Database manager for queries")

    args_schema: type[BaseModel] = Input  # type: ignore[assignment]

    def _run(
        self,
        type: str,
        name: Optional[str] = None,
        path_contains: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> dict[str, Any] | str:
        """Find symbols by exact name and/or path pattern."""
        if not name and not path_contains:
            return "Invalid input: Provide either 'name' (exact match) or 'path_contains' (path pattern), or both."

        node_type = type.upper()
        if node_type not in {"FUNCTION", "CLASS", "FILE", "FOLDER"}:
            return "Invalid type. Must be one of: 'FUNCTION', 'CLASS', 'FILE', 'FOLDER'"

        dto_nodes = self.db_manager.get_nodes_by_name_type_and_path(
            name=name,
            node_type=node_type,
            path_contains=path_contains,
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
