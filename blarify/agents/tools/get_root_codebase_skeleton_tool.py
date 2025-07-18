"""
Tool for retrieving the root codebase skeleton structure from the graph database.

This tool wraps the get_codebase_skeleton function to provide a LangChain-compatible
interface for agent workflows to access the hierarchical structure of the codebase.
"""

from typing import Optional, Type

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from blarify.db_managers.db_manager import AbstractDbManager
from blarify.db_managers.queries import get_codebase_skeleton


class CodebaseSkeletonInput(BaseModel):
    """Input schema for the codebase skeleton tool."""

    entity_id: str = Field(description="The entity ID (company_id) to retrieve the codebase skeleton for")
    repo_id: str = Field(description="The repository ID to retrieve the codebase skeleton for")


class GetRootCodebaseSkeletonTool(BaseTool):
    """
    Tool for retrieving the root codebase skeleton structure.

    This tool provides access to the hierarchical structure of the codebase
    by querying the graph database and returning a formatted string representation
    of files, classes, and functions.
    """

    name: str = "get_root_codebase_skeleton"
    description: str = """
    Retrieves the hierarchical structure of the codebase from the graph database.
    Returns a formatted string representation showing the organization of files,
    classes, and functions in a tree structure. This is useful for understanding
    the overall architecture and organization of the codebase.
    """

    args_schema: Type[BaseModel] = CodebaseSkeletonInput

    db_manager: AbstractDbManager = Field(description="Database manager instance for querying the graph database")

    def __init__(
        self,
        db_manager: AbstractDbManager,
        handle_validation_error: bool = False,
    ):
        super().__init__(
            db_manager=db_manager,
            handle_validation_error=handle_validation_error,
        )

    def _run(
        self,
        entity_id: str,
        repo_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """
        Retrieve the codebase skeleton structure.

        Args:
            entity_id: The entity ID (company_id) to retrieve the skeleton for
            repo_id: The repository ID to retrieve the skeleton for
            run_manager: Optional callback manager for tool execution

        Returns:
            Formatted string representation of the codebase structure
        """
        try:
            # Call the existing get_codebase_skeleton function
            skeleton_result = get_codebase_skeleton(
                db_manager=self.db_manager, entity_id=entity_id, repo_id=repo_id
            )

            return skeleton_result

        except Exception as e:
            error_msg = f"Error retrieving codebase skeleton: {str(e)}"
            if run_manager:
                run_manager.on_tool_error(error_msg)
            return error_msg

    async def _arun(
        self,
        entity_id: str,
        repo_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """
        Async version of the codebase skeleton retrieval.

        Args:
            entity_id: The entity ID (company_id) to retrieve the skeleton for
            repo_id: The repository ID to retrieve the skeleton for
            run_manager: Optional callback manager for tool execution

        Returns:
            Formatted string representation of the codebase structure
        """
        # For now, we'll just call the synchronous version
        # In the future, this could be optimized for async database operations
        return self._run(entity_id, repo_id, run_manager)
