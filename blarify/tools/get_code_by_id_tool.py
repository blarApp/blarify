import logging
import re
from typing import Any, Optional, List

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from blarify.documentation.documentation_creator import DocumentationCreator
from blarify.agents.llm_provider import LLMProvider
from blarify.graph.graph_environment import GraphEnvironment
from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager
from blarify.repositories.graph_db_manager.dtos.node_search_result_dto import NodeSearchResultDTO
from blarify.repositories.graph_db_manager.dtos.edge_dto import EdgeDTO

logger = logging.getLogger(__name__)


# We use DTOs directly from the database manager


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

    args_schema: type[BaseModel] = NodeIdInput  # type: ignore[assignment]

    db_manager: AbstractDbManager = Field(description="Neo4jManager object to interact with the database")
    company_id: str = Field(description="Company ID to search for in the Neo4j database")
    auto_generate: bool = Field(default=True, description="Whether to auto-generate documentation when missing")
    _documentation_creator: DocumentationCreator

    def __init__(
        self,
        db_manager: Any,
        company_id: str,
        handle_validation_error: bool = False,
        auto_generate: bool = True,
    ):
        super().__init__(
            db_manager=db_manager,
            company_id=company_id,
            handle_validation_error=handle_validation_error,
            auto_generate=auto_generate,
        )

        # Initialize DocumentationCreator if auto_generate is enabled
        self._documentation_creator = DocumentationCreator(
            db_manager=self.db_manager,
            agent_caller=LLMProvider(),
            graph_environment=GraphEnvironment(environment="production", diff_identifier="main", root_path="/"),
            company_id=self.company_id,
            repo_id=self.company_id,
            max_workers=1,
            overwrite_documentation=False,
        )

    def _generate_documentation_for_node(self, node_id: str) -> Optional[str]:
        """Generate documentation for a specific node."""
        try:
            if not self.auto_generate or not self._documentation_creator:
                return None

            logger.debug(f"Auto-generating documentation for node {node_id}")

            # Get node info to extract the path
            node_info = self.db_manager.get_node_by_id(node_id=node_id, company_id=self.company_id)

            if not node_info:
                return None

            # Use node_name as the target path
            target_path = node_info.node_name

            # Generate documentation for this specific node
            result = self._documentation_creator.create_documentation(
                target_paths=[target_path], save_to_database=True, generate_embeddings=False
            )

            if result.error:
                logger.error(f"Documentation generation error: {result.error}")
                return None

            # Re-query for the newly created documentation
            node_result = self.db_manager.get_node_by_id(node_id=node_id, company_id=self.company_id)

            return node_result.documentation

        except Exception as e:
            logger.error(f"Failed to auto-generate documentation: {e}")
            return None

    def _get_relations_str(self, *, node_name: str, relations: list[EdgeDTO], direction: str) -> str:
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

    def _get_result_prompt(self, node_result: NodeSearchResultDTO) -> str:
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
            node_result: NodeSearchResultDTO = self.db_manager.get_node_by_id(
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
        if node_result.documentation:
            output += "📚 DOCUMENTATION:\n"
            output += "-" * 80 + "\n"
            output += f"📝 Content:\n{node_result.documentation}\n"
            output += "-" * 80 + "\n"
        else:
            # Try auto-generation if enabled
            if self.auto_generate:
                generated_docs = self._generate_documentation_for_node(node_id)
                if generated_docs:
                    output += "📚 DOCUMENTATION (auto-generated):\n"
                    output += "-" * 80 + "\n"
                    output += f"📝 Content:\n{generated_docs}\n"
                    output += "-" * 80 + "\n"
                else:
                    output += "📚 DOCUMENTATION: None found (generation attempted)\n"
                    output += "-" * 80 + "\n"
            else:
                output += "📚 DOCUMENTATION: None found\n"
                output += "-" * 80 + "\n"

        return output
