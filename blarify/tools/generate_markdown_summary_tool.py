#!/usr/bin/env python3
"""
Simple tool stub for generating markdown summary.
The actual generation is handled by ReactAgent's __should_stop method.
"""
from typing import Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool


class GenerateMarkdownSummaryTool(BaseTool):
    name: str = "generate_markdown_summary"
    description: str = "Generate a comprehensive markdown summary of analysis findings"

    def _run(
        self,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """This tool is intercepted by ReactAgent and doesn't actually run."""
        return "✅ Markdown summary generation triggered."
