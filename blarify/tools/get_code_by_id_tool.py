import re
from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_validator


# Pydantic Response Models (replacement for blarify DTOs)
class EdgeResponse(BaseModel):
    """Edge/relationship response model."""
    node_id: str
    node_name: str
    node_type: list[str]
    relationship_type: str


class NodeSearchResultResponse(BaseModel):
    """Node search result response model."""
    node_id: str
    node_name: str
    node_labels: list[str]
    code: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    file_path: Optional[str] = None
    # Enhanced fields for relationships
    inbound_relations: Optional[list[EdgeResponse]] = None
    outbound_relations: Optional[list[EdgeResponse]] = None
    # Documentation nodes that describe this code node
    documentation_nodes: Optional[list[dict]] = None


class NodeIdInput(BaseModel):
    node_id: str = Field(
        description="The node id (an UUID like hash id) of the node to get the code and/or the diff text."
    )

    @field_validator("node_id", mode="before")
    @classmethod
    def format_node_id(cls, value: Any) -> Any:
        if isinstance(value, str) and len(value) == 32:
            return value
        raise ValueError("Node id must be a 32 character string UUID like hash id")


class GetCodeByIdTool(BaseTool):
    name: str = "get_code_by_id"
    description: str = "Searches for node by id in the Neo4j database"

    args_schema: type[BaseModel] = NodeIdInput

    db_manager: Any = Field(description="Neo4jManager object to interact with the database")
    company_id: str = Field(description="Company ID to search for in the Neo4j database")

    def __init__(
        self,
        db_manager: Any,
        company_id: str,
        handle_validation_error: bool = False,
    ):
        super().__init__(
            db_manager=db_manager,
            company_id=company_id,
            handle_validation_error=handle_validation_error,
        )

    def _get_relations_str(self, *, node_name: str, relations: list[EdgeResponse], direction: str) -> str:
        if direction == "outbound":
            relationship_str = "{node_name} -> {relation.relationship_type} -> {relation.node_name}"
        else:
            relationship_str = "{relation.node_name} -> {relation.relationship_type} -> {node_name}"
        relation_str = ""
        for relation in relations:
            relation_str += f"""
RELATIONSHIP: {relationship_str.format(node_name=node_name, relation=relation)}
RELATION NODE ID: {relation.node_id}
RELATION NODE TYPE: {" | ".join(relation.node_type)}
"""
        return relation_str

    def _format_code_with_line_numbers(
        self, code: str, start_line: Optional[int] = None, child_nodes: Optional[list[dict]] = None
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

    def _get_result_prompt(self, node_result: NodeSearchResultResponse) -> str:
        output = f"""
NODE: ID: {node_result.node_id} | NAME: {node_result.node_name}
LABELS: {" | ".join(node_result.node_labels)}
CODE for {node_result.node_name}:
```
{node_result.code}
```
"""
        return output

    def _run(
        self,
        node_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Returns a function code given a node_id. returns the node text and the neighbors of the node."""
        try:
            node_result: NodeSearchResultResponse = self.db_manager.get_node_by_id_v2(
                node_id=node_id, company_id=self.company_id
            )
        except ValueError:
            return f"No code found for the given query: {node_id}"

        # Format the output nicely like the script example
        output = "=" * 80 + "\n"
        output += f"📄 FILE: {node_result.node_name}\n"
        output += "=" * 80 + "\n"
        output += f"🏷️  Labels: {', '.join(node_result.node_labels)}\n"
        output += f"🆔 Node ID: {node_id}\n"
        output += "-" * 80 + "\n"
        output += "📝 CODE:\n"
        output += "-" * 80 + "\n"

        # Print the code with line numbers
        if node_result.code:
            # Extract node IDs from "Code replaced for brevity" comments in the code
            child_nodes = None
            pattern = re.compile(r"# Code replaced for brevity, see node: ([a-f0-9]+)")
            node_ids = pattern.findall(node_result.code)

            if node_ids:
                try:
                    # Get the child nodes by their IDs
                    child_nodes = self.db_manager.get_nodes_by_ids(node_ids)
                except Exception:
                    # If we can't get child nodes, continue without them
                    pass

            # Format code with line numbers and collapsed child nodes
            formatted_code = self._format_code_with_line_numbers(
                code=node_result.code, start_line=node_result.start_line, child_nodes=child_nodes
            )
            output += formatted_code + "\n"
        else:
            output += "(No code content available)\n"
        output += "-" * 80 + "\n"

        # Display relationships if available
        has_relationships = (
            node_result.inbound_relations and any(rel.node_id for rel in node_result.inbound_relations)
        ) or (node_result.outbound_relations and any(rel.node_id for rel in node_result.outbound_relations))

        if has_relationships:
            output += "🔗 RELATIONSHIPS:\n"
            output += "-" * 80 + "\n"

            # Display inbound relations
            if node_result.inbound_relations:
                inbound_filtered = [rel for rel in node_result.inbound_relations if rel.node_id]
                if inbound_filtered:
                    output += "📥 Inbound Relations:\n"
                    for rel in inbound_filtered:
                        node_types = ", ".join(rel.node_type) if rel.node_type else "Unknown"
                        output += f"  • {rel.node_name} ({node_types}) -> {rel.relationship_type} -> {node_result.node_name} ID:({rel.node_id})\n"
                    output += "\n"

            # Display outbound relations
            if node_result.outbound_relations:
                outbound_filtered = [rel for rel in node_result.outbound_relations if rel.node_id]
                if outbound_filtered:
                    output += "📤 Outbound Relations:\n"
                    for rel in outbound_filtered:
                        node_types = ", ".join(rel.node_type) if rel.node_type else "Unknown"
                        output += f"  • {node_result.node_name} -> {rel.relationship_type} -> {rel.node_name} ID:({rel.node_id}) ({node_types})\n"
                    output += "\n"

            # Check if we actually displayed any relationships
            inbound_count = len([rel for rel in (node_result.inbound_relations or []) if rel.node_id])
            outbound_count = len([rel for rel in (node_result.outbound_relations or []) if rel.node_id])

            if inbound_count == 0 and outbound_count == 0:
                output += "No relationships found\n"
        else:
            output += "🔗 RELATIONSHIPS: None found\n"
            output += "-" * 80 + "\n"

        # Display documentation if available
        if node_result.documentation_nodes:
            doc_nodes = [doc for doc in node_result.documentation_nodes if doc.get('node_id')]
            if doc_nodes:
                output += "📚 DOCUMENTATION:\n"
                output += "-" * 80 + "\n"
                for doc in doc_nodes:
                    output += f"📖 Doc ID: {doc.get('node_id', 'Unknown')}\n"
                    output += f"📄 Name: {doc.get('node_name', 'Unknown')}\n"
                    
                    # Show content or description
                    content = doc.get('content', '') or doc.get('description', '')
                    if content:
                        output += f"📝 Content:\n{content}\n"
                    else:
                        output += "📝 Content: (No content available)\n"
                    
                    output += "\n"
                output += "-" * 80 + "\n"
        else:
            output += "📚 DOCUMENTATION: None found\n"
            output += "-" * 80 + "\n"

        return output
