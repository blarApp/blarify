import re
import textwrap
from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager
from blarify.repositories.graph_db_manager.queries import get_file_context_by_id


class NodeIdInput(BaseModel):
    """
    Input schema for node ID-based file context retrieval.
    """

    node_id: str = Field(
        description="The node id (an UUID like hash id) of the node to get the code and/or the diff text."
    )

    @field_validator("node_id", mode="before")
    @classmethod
    def validate_node_id(cls, value: Any) -> Any:
        """
        Validates that the node_id is a 32-character string.
        """
        if isinstance(value, str) and len(value) == 32:
            return value
        raise ValueError("Node id must be a 32 character string UUID like hash id")


class GetFileContextByIdTool(BaseTool):
    """
    Tool for retrieving file context by node ID from the Neo4j database.
    """

    name: str = "see_node_in_file_context"
    description: str = "Searches for node by id in the Neo4j database and returns node code in the file context"

    args_schema: type[BaseModel] = NodeIdInput  # type: ignore

    db_manager: AbstractDbManager = Field(description="Neo4jManager object to interact with the database")

    def _recursively_inject_code(self, code: str, node_map: dict[str, str], visited: Optional[set] = None) -> str:
        """
        Recursively replaces placeholders in the code with corresponding code snippets from node_map.
        Placeholders are in the form: '# Code replaced for brevity, see node: <id>'.
        The line above each placeholder is removed, and the injected code preserves indentation for the first line only.

        Args:
            code (str): The code containing placeholders.
            node_map (Dict[str, str]): Mapping from node_id to code snippet.
            visited (set, optional): Set of already visited node_ids to prevent infinite recursion.

        Returns:
            str: The code with all placeholders replaced by their corresponding code snippets.
        """
        if visited is None:
            visited = set()

        lines = code.splitlines()
        out: list[str] = []
        i = 0
        pattern = re.compile(r"# Code replaced for brevity, see node: ([a-f0-9]+)")

        while i < len(lines):
            line = lines[i]
            m = pattern.search(line.strip())

            if m:
                node_id = m.group(1)

                # Determine what the surrounding indentation should be
                indent_prefix = re.match(r"\s*", out[-1]).group(0) if out else re.match(r"\s*", line).group(0)
                # Inject, preserving indent for the first line
                if node_id in node_map and node_id not in visited:
                    if out:
                        out.pop()
                    visited.add(node_id)
                    injected = self._recursively_inject_code(node_map[node_id], node_map, visited)
                    # Normalize & re-indent only the first line
                    dedented_lines = textwrap.dedent(injected).splitlines()
                    if dedented_lines:
                        # Add the first line with the indent prefix
                        out.append(f"{indent_prefix}{dedented_lines[0]}")
                        # Add the rest of the lines without additional indentation
                        out.extend(dedented_lines[1:])
                # Skip the placeholder line itself
                else:
                    out.append(line)
                i += 1
            else:
                out.append(line)
                i += 1

        return "\n".join(out)

    def _assemble_source_from_chain(self, chain) -> str:
        """
        Assembles the full source code from a chain of (node_id, text) tuples.
        The last tuple is considered the root (parent) code, and all others are children.
        Child code snippets are injected recursively into the parent code at the appropriate placeholders.

        Args:
            chain (List[Tuple[str, str]]): List of (node_id, code) tuples in order [child, ..., parent].

        Returns:
            str: The fully assembled source code with all placeholders replaced.
        """
        if not chain:
            raise ValueError("No nodes returned from Neo4j chain query")

        if len(chain) == 1:
            return chain[0][1]

        # The oldest ancestor (parent) is the LAST element in the chain
        *children, (parent_id, parent_code) = chain

        # Map each child node_id to its code snippet
        node_map: dict[str, str] = {nid: txt for nid, txt in children}

        return self._recursively_inject_code(parent_code, node_map)

    def _run(
        self,
        node_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> dict[str, str]:
        """
        Returns the file context for a given node_id, including the assembled code and its neighbors.

        Args:
            node_id (str): The node id to look up.
            run_manager (Optional[CallbackManagerForToolRun]): Optional callback manager for tool run.

        Returns:
            Dict[str, str]: Dictionary with the assembled code under the 'text' key.
        """
        try:
            node_result = get_file_context_by_id(db_manager=self.db_manager, node_id=node_id)
            result = self._assemble_source_from_chain(node_result)
        except ValueError:
            return {"message": f"No code found for the given query: {node_id}"}

        return_dict = {"text": result}

        return return_dict
