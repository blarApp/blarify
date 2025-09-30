import re
import textwrap
from typing import Any, Dict, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, model_validator

from blarify.tools.utils import resolve_reference_id


# Pydantic Response Models (replacement for blarify DTOs)
class EdgeResponse(BaseModel):
    """Edge/relationship response model."""

    node_id: str
    node_name: str
    node_type: list[str]
    relationship_type: str


class NodeSearchResultResponse(BaseModel):
    """Code element search result response model."""

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
    # Documentation references that describe this code element
    documentation_nodes: Optional[list[dict]] = None


def recursively_inject_code(code: str, node_map: Dict[str, str], visited: Optional[set] = None) -> str:
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
    if code is None:
        return ""

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
                injected = recursively_inject_code(node_map[node_id], node_map, visited)
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


def assemble_source_from_chain(chain) -> str:
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
        raise ValueError("No code references returned from query")

    if len(chain) == 1:
        # Ensure we return a string, not None
        return chain[0][1] or ""

    # The oldest ancestor (parent) is the LAST element in the chain
    *children, (parent_id, parent_code) = chain

    # Map each child node_id to its code snippet
    node_map: Dict[str, str] = {nid: txt for nid, txt in children}

    # Ensure parent_code is not None
    if parent_code is None:
        return ""

    return recursively_inject_code(parent_code, node_map)


def format_code_with_line_numbers(
    code: str, start_line: Optional[int] = None, child_references: Optional[list[dict]] = None
) -> str:
    """Format code with line numbers, finding and replacing collapse placeholders with correct line numbers."""
    if not code:
        return ""

    lines = code.split("\n")
    line_start = start_line if start_line is not None else 1

    # If no child references, return simple formatting
    if not child_references:
        formatted_lines = []
        for i, line in enumerate(lines):
            line_number = line_start + i
            formatted_lines.append(f"{line_number:4d} | {line}")
        return "\n".join(formatted_lines)

    # Create a mapping from node_id to child reference info
    node_id_map = {}
    for child in child_references:
        node_id = child.get("node_id")
        if node_id:
            node_id_map[node_id] = child

    formatted_lines = []
    pattern = re.compile(r"# Code replaced for brevity, see node: ([a-f0-9]+)")
    current_line_number = line_start

    for line in lines:
        # Check if this line contains a "Code replaced for brevity" comment
        match = pattern.search(line)
        if match:
            node_id = match.group(1)
            if node_id in node_id_map:
                # This is a collapse placeholder - use the actual end_line from the child reference
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


def get_relations_str(*, node_name: str, relations: list[EdgeResponse], direction: str) -> str:
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


def add_get_file_context_method(db_manager: Any) -> None:
    """Dynamically add get_file_context_by_id method to Neo4jManager if it doesn't exist."""
    if not hasattr(db_manager, "get_file_context_by_id"):

        def get_file_context_by_id(self, node_id: str) -> list[tuple[str, str]]:
            query = """
            MATCH path = (ancestor)-[:FUNCTION_DEFINITION|CLASS_DEFINITION*0..]->(n:NODE {node_id: $node_id, entityId: $entity_id, repoId: $repo_id})
            WITH path
            ORDER BY length(path) DESC
            LIMIT 1
            WITH [node IN reverse(nodes(path)) | {id: node.node_id, txt: node.text}] AS chain
            UNWIND chain AS entry
            RETURN entry.id AS node_id, entry.txt AS text
            """
            # entity_id is automatically added by the db_manager
            params = {"node_id": node_id}
            results = self.query(query, parameters=params)
            return [(rec["node_id"], rec["text"]) for rec in results]

        # Bind the method to the instance
        import types

        db_manager.get_file_context_by_id = types.MethodType(get_file_context_by_id, db_manager)


class GetExpandedContext(BaseTool):
    name: str = "get_expanded_context"
    description: str = (
        "Get the full file context with expanded code for deep understanding. "
        "Includes surrounding code and embedded reference IDs for navigation."
    )

    args_schema: type[BaseModel] = FlexibleInput  # type: ignore[assignment]

    db_manager: Any = Field(description="Database manager for queries")

    def __init__(
        self,
        db_manager: Any,
        handle_validation_error: bool = False,
    ):
        # Add the get_file_context_by_id method if it doesn't exist
        add_get_file_context_method(db_manager)

        super().__init__(
            db_manager=db_manager,
            handle_validation_error=handle_validation_error,
        )

    def _run(
        self,
        reference_id: Optional[str] = None,
        file_path: Optional[str] = None,
        symbol_name: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Returns both code details and file context with expanded child references."""
        # Resolve the reference ID from inputs
        node_id = resolve_reference_id(
            self.db_manager, reference_id=reference_id, file_path=file_path, symbol_name=symbol_name
        )

        try:
            node_result: NodeSearchResultResponse = self.db_manager.get_node_by_id(node_id=node_id)
        except ValueError:
            return f"No code found for the given query: {node_id}"

        # Get child references for context expansion
        child_nodes = None
        if node_result.code:
            pattern = re.compile(r"# Code replaced for brevity, see node: ([a-f0-9]+)")
            node_ids = pattern.findall(node_result.code)

            if node_ids:
                try:
                    # Get the child references by their IDs
                    child_nodes = self.db_manager.get_nodes_by_ids(node_ids)
                except Exception:
                    # If we can't get child references, continue without them
                    child_nodes = None

        # Format the output with both detailed information and file context
        output = "=" * 80 + "\n"
        output += f"📄 FILE: {node_result.node_name}\n"
        output += "=" * 80 + "\n"
        # Filter out NODE label from display
        labels = [label for label in node_result.node_labels if label != "NODE"]
        output += f"🏷️  Type: {', '.join(labels)}\n"
        output += f"🆔 ID: {node_id}\n"
        output += "-" * 80 + "\n"
        output += "📝 CODE (with line numbers):\n"
        output += "-" * 80 + "\n"

        # Print the code with line numbers (collapsed version)
        if node_result.code:
            formatted_code = format_code_with_line_numbers(
                code=node_result.code, start_line=node_result.start_line, child_references=child_nodes
            )
            output += formatted_code + "\n"
        else:
            output += "(No code content available)\n"

        # Add file context section with expanded code
        if "FILE" not in node_result.node_labels:
            output += "-" * 80 + "\n"
            output += "📂 FILE CONTEXT (with expanded child elements):\n"
            output += "-" * 80 + "\n"

            try:
                file_context = self.db_manager.get_file_context_by_id(node_id=node_id)
                file_context_result = assemble_source_from_chain(file_context)
                if file_context_result is not None:
                    output += file_context_result + "\n"
                else:
                    output += "(No file context available)\n"
            except ValueError:
                return f"No code found for the given query: {node_id}"

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
                        # Filter out NODE label from types
                        types = [t for t in rel.node_type if t != "NODE"] if rel.node_type else []
                        symbol_types = ", ".join(types) if types else "Unknown"
                        output += f"  • {rel.node_name} ({symbol_types}) -> {rel.relationship_type} -> {node_result.node_name} ID:({rel.node_id})\n"
                    output += "\n"

            # Display outbound relations
            if node_result.outbound_relations:
                outbound_filtered = [rel for rel in node_result.outbound_relations if rel.node_id]
                if outbound_filtered:
                    output += "📤 Outbound Relations:\n"
                    for rel in outbound_filtered:
                        # Filter out NODE label from types
                        types = [t for t in rel.node_type if t != "NODE"] if rel.node_type else []
                        symbol_types = ", ".join(types) if types else "Unknown"
                        output += f"  • {node_result.node_name} -> {rel.relationship_type} -> {rel.node_name} ID:({rel.node_id}) ({symbol_types})\n"
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
        if hasattr(node_result, "documentation_nodes") and node_result.documentation_nodes:
            doc_entries = [doc for doc in node_result.documentation_nodes if doc.get("node_id")]
            if doc_entries:
                output += "📚 DOCUMENTATION:\n"
                output += "-" * 80 + "\n"
                for doc in doc_entries:
                    output += f"📖 Doc ID: {doc.get('node_id', 'Unknown')}\n"
                    output += f"📄 Name: {doc.get('node_name', 'Unknown')}\n"
                    # Show content or description
                    content = doc.get("content", "") or doc.get("description", "")
                    if content:
                        output += f"📝 Content:\n{content}\n"
                    else:
                        output += "📝 Content: (No content available)\n"
                    output += "\n"
                output += "-" * 80 + "\n"
            else:
                output += "📚 DOCUMENTATION: None found\n"
                output += "-" * 80 + "\n"
        else:
            output += "📚 DOCUMENTATION: None found\n"
            output += "-" * 80 + "\n"

        return output
