"""
GrepCode Tool for Pattern-Based Code Search

Searches through code content using pattern matching, similar to grep but optimized
for searching source code. Abstracts away graph database details.
"""

import logging
import re
from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager

logger = logging.getLogger(__name__)


class GrepCodeInput(BaseModel):
    """Input schema for grep code search."""

    pattern: str = Field(
        description="Code pattern to search for (e.g., 'def authenticate', '.send_email(', 'import pandas')",
        min_length=1,
    )
    case_sensitive: bool = Field(default=True, description="Whether search should be case-sensitive (default: True)")
    file_pattern: Optional[str] = Field(
        default=None, description="Filter results to files matching pattern (e.g., '*.py', 'src/auth/*')"
    )
    max_results: int = Field(
        default=20, description="Maximum number of results to return (default: 20)", ge=1, le=50
    )


class GrepCodeMatch(BaseModel):
    """Single grep match result."""

    file_path: str = Field(description="File location")
    line_number: int = Field(description="Line where pattern was found")
    symbol_name: str = Field(description="Name of containing function/class")
    symbol_type: list[str] = Field(description="Types like FUNCTION, CLASS, etc.")
    code_snippet: str = Field(description="Code around the match with context")
    id: str = Field(description="Reference ID for further analysis")


class GrepCode(BaseTool):
    """Tool for searching code patterns across the codebase."""

    name: str = "grep_code"
    description: str = (
        "Search for code patterns across the codebase. Use this to find code snippets, function calls, "
        "specific syntax patterns, or implementation details when you know what the code looks like but "
        "not necessarily where it is. Returns matching code with line numbers and file locations. "
        "NOTE: This tool searches CODE CONTENT only, not file paths or file names."
    )

    args_schema: type[BaseModel] = GrepCodeInput  # type: ignore[assignment]

    db_manager: AbstractDbManager = Field(description="Database manager for queries")

    def __init__(
        self,
        db_manager: Any,
        handle_validation_error: bool = False,
    ):
        """Initialize the grep code tool."""
        super().__init__(
            db_manager=db_manager,
            handle_validation_error=handle_validation_error,
        )
        logger.info("GrepCode tool initialized")

    def _extract_matching_lines(
        self, code: str, pattern: str, case_sensitive: bool, context_lines: int = 2
    ) -> list[tuple[int, str]]:
        """
        Extract lines from code that match the pattern with context.

        Args:
            code: Full code text
            pattern: Pattern to search for
            case_sensitive: Whether to use case-sensitive matching
            context_lines: Number of context lines before and after match

        Returns:
            List of (line_number, code_snippet) tuples
        """
        lines = code.split("\n")
        matches: list[tuple[int, str]] = []

        # Prepare pattern for matching
        search_pattern = pattern if case_sensitive else pattern.lower()

        for i, line in enumerate(lines):
            search_line = line if case_sensitive else line.lower()

            if search_pattern in search_line:
                # Extract context around the match
                start_idx = max(0, i - context_lines)
                end_idx = min(len(lines), i + context_lines + 1)

                snippet_lines = []
                for j in range(start_idx, end_idx):
                    line_num = j + 1  # Line numbers start at 1
                    snippet_lines.append(f"{line_num:4d} | {lines[j]}")

                snippet = "\n".join(snippet_lines)
                matches.append((i + 1, snippet))  # Return 1-based line number

        return matches

    def _convert_glob_to_regex(self, glob_pattern: str) -> str:
        """
        Convert a glob pattern to a regex pattern for Cypher.

        Args:
            glob_pattern: Glob pattern (e.g., '*.py', 'src/auth/*')

        Returns:
            Regex pattern for Cypher
        """
        # Escape special regex characters except * and ?
        pattern = re.escape(glob_pattern)

        # Convert glob wildcards to regex
        pattern = pattern.replace(r"\*\*", ".*")  # ** matches any path
        pattern = pattern.replace(r"\*", "[^/]*")  # * matches within path segment
        pattern = pattern.replace(r"\?", ".")  # ? matches single char

        # Anchor the pattern
        pattern = f".*{pattern}$"

        return pattern

    def _run(
        self,
        pattern: str,
        case_sensitive: bool = True,
        file_pattern: Optional[str] = None,
        max_results: int = 20,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> dict[str, Any] | str:
        """
        Search for code patterns in the codebase.

        Args:
            pattern: Code pattern to search for
            case_sensitive: Whether search should be case-sensitive
            file_pattern: Optional file path pattern filter
            max_results: Maximum number of results
            run_manager: Callback manager for tool execution

        Returns:
            Dictionary with matches or error string
        """
        try:
            # Convert file glob pattern to regex if provided
            file_regex = self._convert_glob_to_regex(file_pattern) if file_pattern else None

            # Build Cypher query
            from blarify.repositories.graph_db_manager.queries import grep_code_query

            parameters = {
                "pattern": pattern,
                "case_sensitive": case_sensitive,
                "file_pattern": file_regex,
                "max_results": max_results,
            }

            # Execute query
            results = self.db_manager.query(grep_code_query(), parameters)

            if not results:
                return f"No matches found for pattern: '{pattern}'"

            # Process results
            matches: list[GrepCodeMatch] = []

            for record in results:
                node_id = record.get("id", "")
                symbol_name = record.get("symbol_name", "Unknown")
                symbol_type_raw = record.get("symbol_type", [])
                file_path = record.get("file_path", "")
                code = record.get("code", "")

                # Filter out 'NODE' label (following FindSymbols pattern)
                symbol_type = [label for label in symbol_type_raw if label != "NODE"]

                # Extract matching lines with context
                matching_lines = self._extract_matching_lines(code, pattern, case_sensitive, context_lines=2)

                # Create a match for each occurrence in this symbol
                for line_number, code_snippet in matching_lines:
                    match = GrepCodeMatch(
                        file_path=file_path,
                        line_number=line_number,
                        symbol_name=symbol_name,
                        symbol_type=symbol_type,
                        code_snippet=code_snippet,
                        id=node_id,
                    )
                    matches.append(match)

                    # Stop if we've hit max results
                    if len(matches) >= max_results:
                        break

                if len(matches) >= max_results:
                    break

            if not matches:
                return f"No matches found for pattern: '{pattern}'"

            # Convert to dict format
            matches_dict = [match.model_dump() for match in matches]

            logger.info(f"Found {len(matches)} matches for pattern: {pattern[:50]}...")

            return {"matches": matches_dict}

        except Exception as e:
            logger.error(f"Grep code search failed: {e}")
            return f"Error searching for pattern: {str(e)}"
