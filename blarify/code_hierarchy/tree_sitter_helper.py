from tree_sitter import Tree, Parser

from blarify.code_hierarchy.languages.FoundRelationshipScope import FoundRelationshipScope
from blarify.graph.node import NodeFactory
from blarify.code_references.types import Reference, Range, Point
from .languages import LanguageDefinitions, BodyNodeNotFound, FallbackDefinitions
from blarify.graph.node import NodeLabels
from blarify.project_file_explorer import File
from typing import List, TYPE_CHECKING, Tuple, Optional, Type
from blarify.graph.relationship import RelationshipType

if TYPE_CHECKING:
    from tree_sitter import Node as TreeSitterNode
    from blarify.graph.node import DefinitionNode, Node, FolderNode, FileNode
    from blarify.code_references.types import Reference
    from blarify.graph.graph_environment import GraphEnvironment


class TreeSitterHelper:
    language_definitions: Type[LanguageDefinitions]
    parser: Parser
    current_path: str
    base_node_source_code: str
    created_nodes: List["Node"]
    graph_environment: Optional["GraphEnvironment"]

    def __init__(
        self, language_definitions: Type[LanguageDefinitions], graph_environment: Optional["GraphEnvironment"] = None
    ):
        self.language_definitions = language_definitions
        self.parsers = self.language_definitions.get_parsers_for_extensions()
        self.graph_environment = graph_environment

    def get_all_identifiers(self, node: "FileNode") -> List["Reference"]:
        self.current_path = node.path
        return self._traverse_and_find_identifiers(node._tree_sitter_node)

    def _traverse_and_find_identifiers(self, node: "TreeSitterNode") -> List["Reference"]:
        identifiers = []

        if node.type == "identifier":
            reference = self._get_reference_from_node(node)
            identifiers.append(reference)

        for child in node.children:
            identifiers.extend(self._traverse_and_find_identifiers(child))

        return identifiers

    def get_reference_type(
        self, original_node: "DefinitionNode", reference: "Reference", node_referenced: "DefinitionNode"
    ) -> FoundRelationshipScope:
        node_in_point_reference = self._get_node_in_point_reference(node=node_referenced, reference=reference)
        found_relationship_scope = self.language_definitions.get_relationship_type(
            node=original_node, node_in_point_reference=node_in_point_reference
        )

        if not found_relationship_scope:
            found_relationship_scope = FoundRelationshipScope(
                node_in_scope=None, relationship_type=RelationshipType.USES
            )

        return found_relationship_scope

    def _get_node_in_point_reference(self, node: "DefinitionNode", reference: "Reference") -> "TreeSitterNode":
        # Get the tree-sitter node for the reference
        start_point = (reference.range.start.line, reference.range.start.character)
        end_point = (reference.range.end.line, reference.range.end.character)

        return node._tree_sitter_node.descendant_for_point_range(start_point, end_point)

    def create_nodes_and_relationships_in_file(
        self, file: File, parent_folder: Optional["FolderNode"] = None
    ) -> List["Node"]:
        self.current_path = file.uri_path
        self.created_nodes = []
        self.base_node_source_code = self._get_content_from_file(file)

        if self._does_path_have_valid_extension(file.uri_path):
            self._handle_paths_with_valid_extension(file=file, parent_folder=parent_folder)
            return self.created_nodes

        file_node = self._create_file_node_from_raw_file(file, parent_folder)
        file_node.add_extra_label("RAW")

        return [file_node]

    def _does_path_have_valid_extension(self, path: str) -> bool:
        if self.language_definitions == FallbackDefinitions:
            return False
        return any(path.endswith(extension) for extension in self.language_definitions.get_language_file_extensions())

    def _handle_paths_with_valid_extension(self, file: File, parent_folder: Optional["FolderNode"] = None) -> None:
        tree = self._parse(self.base_node_source_code, file.extension)

        file_node = self._create_file_node_from_module_node(
            module_node=tree.root_node, file=file, parent_folder=parent_folder
        )
        self.created_nodes.append(file_node)

        self._traverse(tree.root_node, context_stack=[file_node])

    def _parse(self, code: str, extension: str) -> Tree:
        parser = self.parsers[extension]
        as_bytes = bytes(code, "utf-8")
        return parser.parse(as_bytes)

    def _create_file_node_from_module_node(
        self, module_node: "TreeSitterNode", file: File, parent_folder: "FolderNode" = None
    ) -> "Node":
        return NodeFactory.create_file_node(
            path=file.uri_path,
            name=file.name,
            level=file.level,
            node_range=self._get_reference_from_node(module_node),
            definition_range=self._get_reference_from_node(module_node),
            code_text=self.base_node_source_code,
            body_node=module_node,
            parent=parent_folder,
            tree_sitter_node=module_node,
            graph_environment=self.graph_environment,
        )

    def _get_content_from_file(self, file: File) -> str:
        try:
            with open(file.path, "r") as file:
                return file.read()
        except UnicodeDecodeError:
            # if content cannot be read, return empty string
            return ""

    def _traverse(self, tree_sitter_node: "TreeSitterNode", context_stack: List["Node"]) -> None:
        """Perform a recursive preorder traversal of the tree."""

        if context_stack is None:
            context_stack = []

        node_was_created = False
        if node_was_created := self.language_definitions.should_create_node(tree_sitter_node):
            node = self._handle_definition_node(tree_sitter_node, context_stack)

            self.created_nodes.append(node)
            context_stack.append(node)

        for child in tree_sitter_node.named_children:
            self._traverse(child, context_stack)

        if node_was_created:
            context_stack.pop()

    def _handle_definition_node(self, tree_sitter_node: "TreeSitterNode", context_stack: List["Node"]) -> "Node":
        """Handle the printing of node information for class and function definitions."""
        identifier_name, identifier_reference = self._process_identifier_node(node=tree_sitter_node)

        node_reference = self._get_reference_from_node(tree_sitter_node)
        node_snippet = tree_sitter_node.text.decode("utf-8")
        body_node = self._try_process_body_node_snippet(tree_sitter_node)
        parent_node = self.get_parent_node(context_stack)

        node = NodeFactory.create_node_based_on_label(
            kind=self._get_label_from_node(tree_sitter_node),
            name=identifier_name,
            path=self.current_path,
            definition_range=identifier_reference,
            node_range=node_reference,
            code_text=node_snippet,
            body_node=body_node,
            level=parent_node.level + 1,
            parent=parent_node,
            tree_sitter_node=tree_sitter_node,
            graph_environment=self.graph_environment,
        )

        parent_node.relate_node_as_define_relationship(node)
        return node

    def _process_identifier_node(self, node: "TreeSitterNode") -> Tuple[str, "Reference"]:
        identifier_node = self.language_definitions.get_identifier_node(node)
        identifier_reference = self._get_reference_from_node(node=identifier_node)
        identifier_name = self._get_identifier_name(identifier_node=identifier_node)
        return identifier_name, identifier_reference

    def _get_identifier_name(self, identifier_node: str) -> str:
        identifier_name = identifier_node.text.decode("utf-8")
        return identifier_name

    def _get_code_snippet_from_base_file(self, node_range: "Range") -> str:
        start_line = node_range.start.line
        end_line = node_range.end.line
        code_lines = self.base_node_source_code.split("\n")
        code_snippet = "\n".join(code_lines[start_line : end_line + 1])
        return code_snippet

    def _get_reference_from_node(self, node: "TreeSitterNode") -> "Reference":
        return Reference(
            range=Range(
                start=Point(line=node.start_point[0], character=node.start_point[1]),
                end=Point(line=node.end_point[0], character=node.end_point[1]),
            ),
            uri=self.current_path,
        )

    def _process_node_snippet(self, node: "TreeSitterNode") -> Tuple[str, "Reference"]:
        node_reference = self._get_reference_from_node(node)
        node_snippet = self._get_code_snippet_from_base_file(node_reference.range)
        return node_snippet, node_reference

    def _try_process_body_node_snippet(self, node: "TreeSitterNode") -> Tuple[str, "Reference"]:
        try:
            return self._process_body_node_snippet(node)
        except BodyNodeNotFound:
            return None

    def _process_body_node_snippet(self, node: "TreeSitterNode") -> Tuple[str, "Reference"]:
        body_node = self.language_definitions.get_body_node(node)
        return body_node

    def _get_label_from_node(self, node: "TreeSitterNode") -> NodeLabels:
        return self.language_definitions.get_node_label_from_type(node.type)

    def get_parent_node(self, context_stack: List["Node"]) -> "DefinitionNode":
        return context_stack[-1]

    def _create_file_node_from_raw_file(self, file: File, parent_folder: Optional["FolderNode"] = None) -> "FileNode":
        return NodeFactory.create_file_node(
            path=file.uri_path,
            name=file.name,
            level=file.level,
            node_range=self._empty_reference(),
            definition_range=self._empty_reference(),
            code_text=self.base_node_source_code,
            body_node=None,
            parent=parent_folder,
            tree_sitter_node=None,
            graph_environment=self.graph_environment,
        )

    def _empty_reference(self) -> "Reference":
        return Reference(
            range=Range(
                start=Point(line=0, character=0),
                end=Point(line=0, character=0),
            ),
            uri=self.current_path,
        )
