import logging
import re
from typing import Any, Optional, List

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, model_validator

from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager
from blarify.tools.utils import resolve_reference_id
from blarify.repositories.graph_db_manager.dtos.node_search_result_dto import ReferenceSearchResultDTO
from blarify.repositories.graph_db_manager.dtos.edge_dto import EdgeDTO
from blarify.graph.relationship.relationship_type import RelationshipType

logger = logging.getLogger(__name__)


# We use DTOs directly from the database manager


class FlexibleInput(BaseModel):
    reference_id: Optional[str] = Field(None, description="Reference ID (32-char handle) for the symbol")
    file_path: Optional[str] = Field(None, description="Path to the file containing the symbol")
    symbol_name: Optional[str] = Field(None, description="Name of the function/class/method")

    @model_validator(mode="after")
    def validate_inputs(self):
        if self.reference_id:
            if len(self.reference_id) != 32:
                raise ValueError("Reference ID must be a 32 character string")
            return self
        if not (self.file_path and self.symbol_name):
            raise ValueError("Provide either reference_id OR (file_path AND symbol_name)")
        return self


class GetCodeAnalysis(BaseTool):
    name: str = "get_code_analysis"
    description: str = (
        "Get complete code implementation with relationships and dependencies. "
        "Shows which functions call this one and which ones it calls, "
        "with reference IDs for navigation."
    )

    args_schema: type[BaseModel] = FlexibleInput  # type: ignore[assignment]

    db_manager: AbstractDbManager = Field(description="Database manager for queries")

    def __init__(
        self,
        db_manager: AbstractDbManager,
        handle_validation_error: bool = False,
    ):
        super().__init__(
            db_manager=db_manager,
            handle_validation_error=handle_validation_error,
        )

    def _get_relations_str(self, *, node_name: str, relations: list[EdgeDTO], direction: str) -> str:
        if direction == "outbound":
            relationship_str = "{node_name} -> {relation.relationship_type} -> {relation.node_name}"
        else:
            relationship_str = "{relation.node_name} -> {relation.relationship_type} -> {node_name}"
        relation_str = ""
        for relation in relations:
            relation_str += f"""
RELATIONSHIP: {relationship_str.format(node_name=node_name, relation=relation)}
RELATION ID: {relation.node_id}
RELATION TYPE: {" | ".join(relation.node_type)}
"""
        return relation_str

    def _format_code_with_line_numbers(
        self, code: str, start_line: Optional[int] = None, child_nodes: Optional[List[dict[str, Any]]] = None
    ) -> str:
        """Format code with line numbers, finding and replacing collapse placeholders with correct line numbers."""
        if not code:
            return ""

        lines = code.split("\n")
        line_start = start_line if start_line is not None else 1

        # If no child nodes, return simple formatting
        if not child_nodes:
            formatted_lines = []
            for i, line in enumerate(lines):
                line_number = line_start + i
                formatted_lines.append(f"{line_number:4d} | {line}")
            return "\n".join(formatted_lines)

        # Create a mapping from node_id to child node info
        node_id_map = {}
        for child in child_nodes:
            node_id = child.get("node_id")
            if node_id:
                node_id_map[node_id] = child

        formatted_lines = []
        pattern = re.compile(r"# Code replaced for brevity, see node: ([a-f0-9]+)")
        current_line_number = line_start

        for i, line in enumerate(lines):
            # Check if this line contains a "Code replaced for brevity" comment
            match = pattern.search(line)
            if match:
                node_id = match.group(1)
                if node_id in node_id_map:
                    # This is a collapse placeholder - use the actual end_line from the child node
                    child = node_id_map[node_id]
                    end_line = child.get("end_line")
                    if end_line:
                        # Show the end_line number and adjust current position
                        formatted_lines.append(f"{end_line:4d} | {line}")
                        current_line_number = end_line + 1  # Next line continues from after the collapsed section
                    else:
                        formatted_lines.append(f"{current_line_number:4d} | {line}")
                        current_line_number += 1
                else:
                    formatted_lines.append(f"{current_line_number:4d} | {line}")
                    current_line_number += 1
            else:
                # Regular line
                formatted_lines.append(f"{current_line_number:4d} | {line}")
                current_line_number += 1

        return "\n".join(formatted_lines)

    def _is_code_generated_relationship(self, relationship_type: str) -> bool:
        """Check if a relationship type is generated by code analysis."""
        code_generated_types = {
            # Code hierarchy
            RelationshipType.CONTAINS.value,
            RelationshipType.FUNCTION_DEFINITION.value,
            RelationshipType.CLASS_DEFINITION.value,
            # Code references
            RelationshipType.IMPORTS.value,
            RelationshipType.CALLS.value,
            RelationshipType.INHERITS.value,
            RelationshipType.INSTANTIATES.value,
            RelationshipType.TYPES.value,
            RelationshipType.ASSIGNS.value,
            RelationshipType.USES.value,
            # Code diff
            RelationshipType.MODIFIED.value,
            RelationshipType.DELETED.value,
            RelationshipType.ADDED.value,
        }
        return relationship_type in code_generated_types

    def _get_result_prompt(self, node_result: ReferenceSearchResultDTO) -> str:
        output = f"""
ID: {node_result.node_id} | NAME: {node_result.node_name}
LABELS: {" | ".join(node_result.node_labels)}
CODE for {node_result.node_name}:
```
{node_result.code}
```
"""
        return output

    def _run(
        self,
        reference_id: Optional[str] = None,
        file_path: Optional[str] = None,
        symbol_name: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Returns code analysis for a symbol with relationships."""
        try:
            # Resolve the reference ID from inputs
            node_id = resolve_reference_id(
                self.db_manager, reference_id=reference_id, file_path=file_path, symbol_name=symbol_name
            )
            node_result = self.db_manager.get_node_by_id(node_id=node_id)
        except ValueError as e:
            return f"No code found: {str(e)}"

        # Format the output nicely like the script example
        output = "=" * 80 + "\n"
        output += f"📄 FILE: {node_result.node_name}\n"
        output += "=" * 80 + "\n"
        # Filter out NODE label from display
        labels = [label for label in node_result.node_labels if label != "NODE"]
        output += f"🏷️  Labels: {', '.join(labels)}\n"
        output += f"🆔 Node ID: {node_id}\n"
        output += "-" * 80 + "\n"

        # Display code
        output += "📝 CODE:\n"
        output += "-" * 80 + "\n"

        # Format and display the actual code
        formatted_code = self._format_code_with_line_numbers(
            node_result.code,
            node_result.start_line,
            None,  # child_nodes not available in NodeSearchResultDTO
        )
        output += formatted_code + "\n"
        output += "-" * 80 + "\n"

        # Display filtered relationships (only code-generated ones)
        has_code_relationships = False
        filtered_inbound = []
        filtered_outbound = []

        if node_result.inbound_relations:
            filtered_inbound = [
                rel
                for rel in node_result.inbound_relations
                if rel.node_id and self._is_code_generated_relationship(rel.relationship_type)
            ]
            has_code_relationships = has_code_relationships or bool(filtered_inbound)

        if node_result.outbound_relations:
            filtered_outbound = [
                rel
                for rel in node_result.outbound_relations
                if rel.node_id and self._is_code_generated_relationship(rel.relationship_type)
            ]
            has_code_relationships = has_code_relationships or bool(filtered_outbound)

        if has_code_relationships:
            output += "🔗 RELATIONSHIPS (Code-Generated):\n"
            output += "-" * 80 + "\n"

            # Display inbound relations
            if filtered_inbound:
                output += "📥 Inbound Relations:\n"
                for rel in filtered_inbound:
                    # Filter out NODE label from types
                    types = [t for t in rel.node_type if t != "NODE"] if rel.node_type else []
                    node_types = ", ".join(types) if types else "Unknown"
                    output += f"  • {rel.node_name} ({node_types}) -> {rel.relationship_type} -> {node_result.node_name} ID:({rel.node_id})\n"
                output += "\n"

            # Display outbound relations
            if filtered_outbound:
                output += "📤 Outbound Relations:\n"
                for rel in filtered_outbound:
                    # Filter out NODE label from types
                    types = [t for t in rel.node_type if t != "NODE"] if rel.node_type else []
                    node_types = ", ".join(types) if types else "Unknown"
                    output += f"  • {node_result.node_name} -> {rel.relationship_type} -> {rel.node_name} ID:({rel.node_id}) ({node_types})\n"
                output += "\n"
        else:
            output += "🔗 RELATIONSHIPS (Code-Generated): None found\n"
            output += "-" * 80 + "\n"

        return output
