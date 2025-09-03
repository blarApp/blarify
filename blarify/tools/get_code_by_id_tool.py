import logging
import re
from typing import Any, Optional, List

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from blarify.documentation.documentation_creator import DocumentationCreator
from blarify.documentation.workflow_creator import WorkflowCreator
from blarify.agents.llm_provider import LLMProvider
from blarify.graph.graph_environment import GraphEnvironment
from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager
from blarify.repositories.graph_db_manager.dtos.node_search_result_dto import NodeSearchResultDTO
from blarify.repositories.graph_db_manager.dtos.edge_dto import EdgeDTO
from blarify.graph.relationship.relationship_type import RelationshipType

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
    auto_generate_documentation: bool = Field(
        default=True, description="Whether to auto-generate documentation when missing"
    )
    auto_generate_workflows: bool = Field(default=True, description="Whether to auto-generate workflows when missing")

    def __init__(
        self,
        db_manager: AbstractDbManager,
        handle_validation_error: bool = False,
        auto_generate_documentation: bool = True,
        auto_generate_workflows: bool = True,
    ):
        super().__init__(
            db_manager=db_manager,
            handle_validation_error=handle_validation_error,
            auto_generate_documentation=auto_generate_documentation,
            auto_generate_workflows=auto_generate_workflows,
        )
        self._graph_environment = GraphEnvironment(environment="main", diff_identifier="0", root_path="/")
        self._documentation_creator = DocumentationCreator(
            db_manager=self.db_manager,
            agent_caller=LLMProvider(),
            graph_environment=self._graph_environment,
            max_workers=20,
            overwrite_documentation=False,
        )
        self._workflow_creator = WorkflowCreator(
            db_manager=self.db_manager,
            graph_environment=self._graph_environment,
        )

    def _generate_documentation_for_node(self, node: NodeSearchResultDTO) -> Optional[str]:
        """Generate documentation for a specific node."""
        try:
            logger.info(f"Auto-generating documentation for node {node.node_id}")

            # Use node_name as the target path
            target_path = node.node_path

            # Generate documentation for this specific node
            result = self._documentation_creator.create_documentation(
                target_paths=[target_path], save_to_database=True, generate_embeddings=False
            )

            if result.error:
                logger.error(f"Documentation generation error: {result.error}")
                return None

            # Re-query for the newly created documentation
            node_result = self.db_manager.get_node_by_id(node_id=node.node_id)

            return node_result.documentation

        except Exception as e:
            logger.error(f"Failed to auto-generate documentation: {e}")
            return None

    def _generate_workflows_for_node(self, node: NodeSearchResultDTO) -> Optional[list[dict[str, Any]]]:
        """Generate workflows for a specific node."""
        try:
            logger.info(f"Auto-generating workflows for node {node.node_id}")

            # Use node_path for targeted workflow discovery
            target_path = node.node_path

            # Generate workflows for this specific node
            result = self._workflow_creator.discover_workflows(
                node_path=target_path, max_depth=20, save_to_database=True
            )

            if result.error:
                logger.error(f"Workflow generation error: {result.error}")
                return None

            # Re-query for the newly created workflows
            node_result = self.db_manager.get_node_by_id(node_id=node.node_id)

            return node_result.workflows

        except Exception as e:
            logger.error(f"Failed to auto-generate workflows: {e}")
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
            node_result: NodeSearchResultDTO = self.db_manager.get_node_by_id(node_id=node_id)
        except ValueError:
            return f"No code found for the given query: {node_id}"

        # Format the output nicely like the script example
        output = "=" * 80 + "\n"
        output += f"📄 FILE: {node_result.node_name}\n"
        output += "=" * 80 + "\n"
        output += f"🏷️  Labels: {', '.join(node_result.node_labels)}\n"
        output += f"🆔 Node ID: {node_id}\n"
        output += "-" * 80 + "\n"

        # Generate missing documentation if needed (but don't wait for workflows)
        doc_content = node_result.documentation

        if not doc_content and self.auto_generate_documentation:
            doc_content = self._generate_documentation_for_node(node_result)

        # Generate workflows in background if needed (fire and forget)
        if not node_result.workflows and self.auto_generate_workflows:
            # Start workflow generation but don't wait for it
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(self._generate_workflows_for_node, node_result)

        # Display documentation first
        if doc_content:
            output += "📚 DOCUMENTATION:\n"
            output += "-" * 80 + "\n"
            output += f"{doc_content}\n"
            output += "-" * 80 + "\n"
        else:
            if self.auto_generate_documentation:
                output += "📚 DOCUMENTATION: None found (generation attempted)\n"
            else:
                output += "📚 DOCUMENTATION: None found\n"
            output += "-" * 80 + "\n"

        # Display code
        output += "📝 CODE:\n"
        output += "-" * 80 + "\n"
        
        # Format and display the actual code
        formatted_code = self._format_code_with_line_numbers(
            node_result.code, 
            node_result.start_line, 
            None  # child_nodes not available in NodeSearchResultDTO
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
                    node_types = ", ".join(rel.node_type) if rel.node_type else "Unknown"
                    output += f"  • {rel.node_name} ({node_types}) -> {rel.relationship_type} -> {node_result.node_name} ID:({rel.node_id})\n"
                output += "\n"

            # Display outbound relations
            if filtered_outbound:
                output += "📤 Outbound Relations:\n"
                for rel in filtered_outbound:
                    node_types = ", ".join(rel.node_type) if rel.node_type else "Unknown"
                    output += f"  • {node_result.node_name} -> {rel.relationship_type} -> {rel.node_name} ID:({rel.node_id}) ({node_types})\n"
                output += "\n"
        else:
            output += "🔗 RELATIONSHIPS (Code-Generated): None found\n"
            output += "-" * 80 + "\n"

        return output
