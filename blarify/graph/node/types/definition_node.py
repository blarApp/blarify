from typing import List, Optional, Tuple, Union, TYPE_CHECKING, Dict
from blarify.graph.node.types.node import Node

import re

from blarify.stats.complexity import CodeComplexityCalculator, NestingStats

if TYPE_CHECKING:
    from ..class_node import ClassNode
    from ..function_node import FunctionNode
    from blarify.graph.relationship import Relationship
    from blarify.code_references.types import Reference
    from tree_sitter import Node as TreeSitterNode
    from blarify.graph.graph_environment import GraphEnvironment


class DefinitionNode(Node):
    _defines: List[Union["ClassNode", "FunctionNode"]]
    definition_range: "Reference"
    node_range: "Reference"
    code_text: str
    _is_diff: bool
    extra_labels: List[str]
    extra_attributes: Dict[str, str]
    body_node: Optional["TreeSitterNode"] = None
    _tree_sitter_node: Optional["TreeSitterNode"] = None

    def __init__(
        self, 
        definition_range: "Reference", 
        node_range: "Reference", 
        code_text: str, 
        body_node: Optional["TreeSitterNode"], 
        tree_sitter_node: "TreeSitterNode", 
        *args, 
        **kwargs
    ) -> None:
        self._defines: List[Union["ClassNode", "FunctionNode"]] = []
        self.definition_range = definition_range
        self.node_range = node_range
        self.code_text = code_text
        self.body_node = body_node
        self._tree_sitter_node = tree_sitter_node
        self.extra_labels = []
        self.extra_attributes = {}

        super().__init__(*args, **kwargs)

    @property
    def stats(self) -> "NestingStats":
        if self.body_node is None:
            return NestingStats(0, 0, 0, 0)
        return CodeComplexityCalculator.calculate_nesting_stats(self.body_node, extension=self.extension)

    def relate_node_as_define_relationship(self, node: Union["ClassNode", "FunctionNode"]) -> None:
        self._defines.append(node)

    def relate_nodes_as_define_relationship(self, nodes: List[Union["ClassNode", "FunctionNode"]]) -> None:
        self._defines.extend(nodes)

    def get_relationships(self) -> List["Relationship"]:
        from blarify.graph.relationship import RelationshipCreator
        relationships: List["Relationship"] = []
        for node in self._defines:
            relationships.append(RelationshipCreator.create_defines_relationship(self, node))

        return relationships

    def get_start_and_end_line(self) -> Tuple[int, int]:
        return self.node_range.range.start.line, self.node_range.range.end.line

    def reference_search(self, reference: "Reference") -> "DefinitionNode":
        reference_start = reference.range.start.line
        reference_end = reference.range.end.line

        for node in self._defines:
            start_line, end_line = node.get_start_and_end_line()

            if self.is_reference_within_scope(
                reference_start=reference_start,
                reference_end=reference_end,
                scope_start=start_line,
                scope_end=end_line,
            ):
                return node.reference_search(reference=reference)

            if self.is_reference_end_before_scope_start(reference_end, start_line):
                break

        return self

    def is_reference_within_scope(
        self, reference_start: int, reference_end: int, scope_start: int, scope_end: int
    ) -> bool:
        return scope_start <= reference_start and scope_end >= reference_end

    def is_reference_end_before_scope_start(self, reference_end: int, scope_start: int) -> bool:
        return reference_end < scope_start

    def skeletonize(self) -> None:
        if self._tree_sitter_node is None:
            return

        parent_node = self._tree_sitter_node
        text_bytes = parent_node.text
        bytes_offset = -self._tree_sitter_node.start_byte - 1
        for node in self._defines:
            if node.body_node is None:
                continue
            start_text, start_byte = node.get_start_text_bytes(parent_text_bytes=text_bytes, bytes_offset=bytes_offset)
            end_text, end_byte = node.get_end_text_bytes(parent_text_bytes=text_bytes, bytes_offset=bytes_offset)
            text_bytes = start_text + node._get_text_for_skeleton() + end_text

            bytes_offset += node.calculate_new_offset(start_byte=start_byte, end_byte=end_byte)

            # TODO: This is a workaround to avoid decoding errors. We should find a better solution.
            self.code_text = text_bytes.decode("utf-8", errors="ignore")

            node.skeletonize()

    def calculate_new_offset(self, start_byte: int, end_byte: int) -> int:
        return len(self._get_text_for_skeleton()) - (end_byte - start_byte)

    def get_start_text_bytes(self, parent_text_bytes: bytes, bytes_offset: int) -> Tuple[bytes, int]:
        start_byte = self.body_node.start_byte + bytes_offset - 1
        return parent_text_bytes[:start_byte], start_byte

    def get_end_text_bytes(self, parent_text_bytes: bytes, bytes_offset: int) -> Tuple[bytes, int]:
        end_byte = self.body_node.end_byte + bytes_offset + 1
        return self.remove_line_break_if_present(text=parent_text_bytes[end_byte:]), end_byte

    def remove_line_break_if_present(self, text: bytes) -> Tuple[bytes, int]:
        if text[0:1] == b"\n":
            return text[1:]
        return text

    def _get_text_for_skeleton(self) -> bytes:
        return f"# Code replaced for brevity, see node: {self.hashed_id}\n".encode("utf-8")

    def get_all_definition_ranges(self) -> List["Reference"]:
        definition_ranges = [self.definition_range]
        for node in self._defines:
            definition_ranges.extend(node.get_all_definition_ranges())
        return definition_ranges

    def add_extra_label_to_self_and_children(self, label: str) -> None:
        self.add_extra_label(label)
        for node in self._defines:
            node.add_extra_label_to_self_and_children(label)

    def add_extra_label(self, label: str) -> None:
        self.extra_labels.append(label)

    def add_extra_attribute_to_self_and_children(self, key: str, value: str) -> None:
        self.add_extra_attribute(key, value)
        for node in self._defines:
            node.add_extra_attribute_to_self_and_children(key, value)

    def add_extra_attribute(self, key: str, value: str) -> None:
        self.extra_attributes[key] = value

    def update_graph_environment_to_self_and_children(self, graph_environment: "GraphEnvironment") -> None:
        self.update_graph_environment(graph_environment)
        for node in self._defines:
            node.update_graph_environment_to_self_and_children(graph_environment)

    def is_code_text_equivalent(self, code_text: str) -> bool:
        # Removing _get_text_for_skeleton() from code_text with a regex
        stripped_code_text = re.sub(r"# Code replaced for brevity, see node: \w+\n", "", self.code_text)
        other_code_text = re.sub(r"# Code replaced for brevity, see node: \w+\n", "", code_text)

        return stripped_code_text == other_code_text

    def __copy__(self):
        cls = self.__class__
        result = cls.__new__(cls)
        result.__dict__.update(self.__dict__)
        result.extra_labels = self.extra_labels.copy()
        result.extra_attributes = self.extra_attributes.copy()
        return result

    def as_object(self):
        obj = super().as_object()
        obj["extra_labels"] = self.extra_labels
        obj["attributes"] = {
            **obj["attributes"],
            **self.extra_attributes,
            "stats_max_indentation": self.stats.max_indentation,
            "stats_min_indentation": self.stats.min_indentation,
            "stats_average_indentation": self.stats.average_indentation,
            "stats_sd_indentation": self.stats.sd,
        }
        return obj

    def filter_children_by_path(self, paths_to_keep: List[str]) -> None:
        self._defines = [node for node in self._defines if node.path in paths_to_keep]
        for node in self._defines:
            node.filter_children_by_path(paths_to_keep)

    def has_tree_sitter_node(self):
        return self._tree_sitter_node is not None
