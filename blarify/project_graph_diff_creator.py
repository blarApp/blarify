from blarify.code_references.hybrid_resolver import HybridReferenceResolver
from blarify.code_references.types import Reference
from blarify.graph.node.utils.node_factory import NodeFactory
from blarify.project_graph_creator import ProjectGraphCreator
from blarify.graph.relationship import RelationshipType
from blarify.graph.graph import Graph
from blarify.graph.graph_environment import GraphEnvironment
from blarify.project_file_explorer import ProjectFilesIterator
from blarify.graph.node import FileNode
from typing import List, Optional, cast
from dataclasses import dataclass
from enum import Enum
from blarify.graph.external_relationship_store import ExternalRelationshipStore
from blarify.graph.graph_update import GraphUpdate
from blarify.graph.node.utils.id_calculator import IdCalculator
from blarify.utils.path_calculator import PathCalculator
from blarify.graph.node import Node, DefinitionNode
from blarify.utils.relative_id_calculator import RelativeIdCalculator


class ChangeType(Enum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"


@dataclass
class FileDiff:
    path: str
    diff_text: str
    change_type: ChangeType


@dataclass
class PreviousNodeState:
    node_path: str
    code_text: str

    @property
    def relative_id(self):
        return RelativeIdCalculator.calculate(self.node_path)

    @property
    def hashed_id(self):
        return IdCalculator.hash_id(self.node_path)


class ProjectGraphDiffCreator(ProjectGraphCreator):
    diff_identifier: str
    added_and_modified_paths: List[str]
    file_diffs: List[FileDiff]
    pr_environment: "GraphEnvironment"

    def __init__(
        self,
        root_path: str,
        reference_query_helper: HybridReferenceResolver,
        project_files_iterator: ProjectFilesIterator,
        file_diffs: List[FileDiff],
        graph_environment: Optional["GraphEnvironment"] = None,
        pr_environment: Optional["GraphEnvironment"] = None,
    ):
        super().__init__(root_path, reference_query_helper, project_files_iterator, graph_environment=graph_environment)
        self.graph = Graph()
        self.external_relationship_store = ExternalRelationshipStore()

        self.file_diffs = file_diffs
        self.graph_environment = graph_environment or GraphEnvironment("main", "0", root_path)
        self.pr_environment = pr_environment or GraphEnvironment("main", "0", root_path)

        self.added_paths = self.get_added_paths()
        self.modified_paths = self.get_modified_paths()

        self.added_and_modified_paths = self.added_paths + self.modified_paths
        self.deleted_nodes_added_paths = []

    def get_added_paths(self) -> List[str]:
        return [file_diff.path for file_diff in self.file_diffs if file_diff.change_type == ChangeType.ADDED]

    def get_modified_paths(self) -> List[str]:
        return [file_diff.path for file_diff in self.file_diffs if file_diff.change_type == ChangeType.MODIFIED]

    def build(self) -> Graph:
        self._create_code_hierarchy()
        self.mark_updated_and_added_nodes_as_diff()
        self.create_relationship_from_references_for_modified_and_added_files()
        self.keep_only_files_to_create()
        self.add_deleted_relationships_and_nodes()

        return cast(Graph, GraphUpdate(self.graph, self.external_relationship_store))

    def build_hierarchy_only(self) -> Graph:
        self._create_code_hierarchy()
        self.mark_updated_and_added_nodes_as_diff()
        self.keep_only_files_to_create()
        self.add_deleted_relationships_and_nodes()

        return cast(Graph, GraphUpdate(self.graph, self.external_relationship_store))

    def build_with_previous_node_states(self, previous_node_states: List[PreviousNodeState]) -> GraphUpdate:
        """
        This method will also create "MODIFIED" relationships between the specific nodes that were modified

        For example, if a function was modified, a "MODIFIED" relationship will be created between the previous and current function nodes
        """
        self._create_code_hierarchy()
        self.mark_updated_and_added_nodes_as_diff()
        self.create_relationships_from_previous_node_states(previous_node_states)
        self.create_relationship_from_references_for_modified_and_added_files()
        self.keep_only_files_to_create()
        self.add_deleted_relationships_and_nodes()

        return GraphUpdate(self.graph, self.external_relationship_store)

    def build_hierarchy_only_with_previous_node_states(
        self, previous_node_states: List[PreviousNodeState]
    ) -> GraphUpdate:
        self._create_code_hierarchy()
        self.mark_updated_and_added_nodes_as_diff()
        self.create_relationships_from_previous_node_states(previous_node_states)
        self.keep_only_files_to_create()
        self.add_deleted_relationships_and_nodes()

        return GraphUpdate(self.graph, self.external_relationship_store)

    def create_relationships_from_previous_node_states(self, previous_node_states: List[PreviousNodeState]):
        self._create_modified_relationships(previous_node_states)
        self._mark_new_nodes_with_label(previous_node_states)
        self._mark_deleted_nodes_with_label(previous_node_states)

    def _create_modified_relationships(self, previous_node_states: List[PreviousNodeState]):
        for previous_node in previous_node_states:
            equivalent_node: DefinitionNode | None = cast(
                DefinitionNode, self.graph.get_node_by_relative_id(previous_node.relative_id)
            )

            is_equivalent_node_modified = equivalent_node and not equivalent_node.is_code_text_equivalent(
                previous_node.code_text
            )

            if is_equivalent_node_modified:
                self.external_relationship_store.create_and_add_relationship(
                    start_node_id=equivalent_node.hashed_id,
                    end_node_id=previous_node.hashed_id,
                    rel_type=RelationshipType.MODIFIED,
                )

                equivalent_node.add_extra_label(ChangeType.MODIFIED.value)

    def _mark_new_nodes_with_label(self, previous_node_states: List[PreviousNodeState]):
        previous_nodes_relative_id = {previous_node.relative_id for previous_node in previous_node_states}

        for path in self.added_and_modified_paths:
            for node in self.graph.get_nodes_by_path(path):
                self._mark_new_node_if_absent(previous_nodes_relative_id, node)

    def _mark_new_node_if_absent(self, previous_nodes_relative_id: set[str], node: Node):
        is_relative_id_in_previous_nodes = node.relative_id in previous_nodes_relative_id
        if not is_relative_id_in_previous_nodes and isinstance(node, DefinitionNode):
            node.add_extra_label(ChangeType.ADDED.value)

    def _mark_deleted_nodes_with_label(self, previous_node_states: List[PreviousNodeState]):
        for previous_node in previous_node_states:
            equivalent_node: DefinitionNode = cast(
                DefinitionNode, self.graph.get_node_by_relative_id(previous_node.relative_id)
            )
            if not equivalent_node:
                deleted_node = NodeFactory.create_deleted_node(
                    graph_environment=self.pr_environment,
                )

                self.graph.add_node(deleted_node)
                self.deleted_nodes_added_paths.append(deleted_node.path)

                self.external_relationship_store.create_and_add_relationship(
                    start_node_id=previous_node.hashed_id,
                    end_node_id=deleted_node.hashed_id,
                    rel_type=RelationshipType.DELETED,
                )

    def _mark_deleted_node_if_absent(self, previous_nodes_relative_id: str, node: Node):
        is_relative_id_in_previous_nodes = node.relative_id in previous_nodes_relative_id
        if not is_relative_id_in_previous_nodes and isinstance(node, DefinitionNode):
            node.add_extra_label(ChangeType.DELETED.value)

    def mark_updated_and_added_nodes_as_diff(self):
        self.mark_file_nodes_as_diff(self.get_file_nodes_from_path_list(self.added_and_modified_paths))

    def keep_only_files_to_create(self):
        paths_to_keep = self.get_parent_paths_from_paths(self.added_and_modified_paths)
        paths_to_keep.extend(self.added_and_modified_paths)
        paths_to_keep.extend(self.deleted_nodes_added_paths)

        self.graph = self.graph.filtered_graph_by_paths(paths_to_keep)

    def get_parent_paths_from_paths(self, paths: List[str]) -> List[str]:
        parent_paths = []
        for path in paths:
            parent_paths.extend(self.get_parent_paths_from_path(path))

        return parent_paths

    def get_parent_paths_from_path(self, path: str) -> List[str]:
        parents = []

        iterations = 0
        while self.graph_environment.root_path in path:
            path = PathCalculator.get_parent_folder_path(path)
            parents.append(path)

            self.raise_error_if_deeply_nested_file(iterations, path)
            iterations += 1

        return parents

    def raise_error_if_deeply_nested_file(self, iteration: int, path: str):
        MAX_ITERATIONS = 100000
        if iteration > MAX_ITERATIONS:
            raise ValueError(f"Deeply nested file, probably an infinite loop: {path}")

    def create_relationship_from_references_for_modified_and_added_files(self):
        file_nodes = self.get_file_nodes_from_path_list(self.added_and_modified_paths)

        paths = self.get_paths_referenced_by_file_nodes(file_nodes)
        paths = self.remove_paths_to_create_from_paths_referenced(paths)

        file_nodes.extend(self.get_file_nodes_from_path_list(paths))
        self._create_relationships_from_references_for_files(files_nodes=file_nodes)

    def get_paths_referenced_by_file_nodes(self, file_nodes: List[FileNode]) -> set[str]:
        paths = set()
        for file in file_nodes:
            if self.is_file_node_raw(file):
                # Raw files can't be parsed, so we can't get references from them
                continue

            paths.update(self.get_paths_referenced_by_file_node(file))

        return paths

    def is_file_node_raw(self, file_node: FileNode):
        return not file_node.has_tree_sitter_node()

    def mark_file_nodes_as_diff(self, file_nodes: List[FileNode]):
        for file_node in file_nodes:
            diff = self.get_file_diff_for_path(file_node.path)
            file_node.add_extra_label_to_self_and_children("DIFF")
            file_node.add_extra_attribute_to_self_and_children("diff_text", diff.diff_text)
            file_node.update_graph_environment_to_self_and_children(self.pr_environment)
            file_node.skeletonize()

    def get_file_diff_for_path(self, path: str) -> FileDiff:
        for file_diff in self.file_diffs:
            if file_diff.path == path:
                return file_diff

        raise ValueError(f"Path {path} not found in file diffs")

    def remove_paths_to_create_from_paths_referenced(self, paths_referenced: set[str]) -> List[str]:
        return [path for path in paths_referenced if path not in self.added_and_modified_paths]

    def get_paths_referenced_by_file_node(self, file_node: FileNode) -> set[str]:
        helper = self._get_tree_sitter_for_file_extension(file_node.extension)
        definitions = file_node.get_all_definition_ranges()
        identifiers = helper.get_all_identifiers(file_node)
        filtered_identifiers = self.remove_definitions_from_identifiers(definitions, identifiers)

        return {
            self.reference_query_helper.lsp_resolver.get_definition_path_for_reference(ref, file_node.extension)
            for ref in filtered_identifiers
        }

    def remove_definitions_from_identifiers(
        self, definitions: List[Reference], identifiers: List[Reference]
    ) -> List[Reference]:
        return [identifier for identifier in identifiers if identifier not in definitions]

    def get_file_nodes_from_path_list(self, paths: List[str]) -> List[FileNode]:
        file_nodes = []
        for path in paths:
            file_node = self.graph.get_file_node_by_path(path)

            if file_node:
                file_nodes.append(file_node)
        return file_nodes

    def add_deleted_relationships_and_nodes(self):
        for diff in self.file_diffs:
            if diff.change_type == ChangeType.DELETED:
                deleted_node_pr_env = NodeFactory.create_deleted_node(
                    graph_environment=self.pr_environment,
                )

                path = PathCalculator.uri_to_path(diff.path)
                original_file_node_id = self.generate_file_id_from_path(path)

                self.graph.add_node(deleted_node_pr_env)
                self.external_relationship_store.create_and_add_relationship(
                    start_node_id=original_file_node_id,
                    end_node_id=deleted_node_pr_env.hashed_id,
                    rel_type=RelationshipType.DELETED,
                )

    def generate_file_id_from_path(self, path: str) -> str:
        relative_path = PathCalculator.compute_relative_path_with_prefix(path, self.graph_environment.root_path)
        original_file_node_id = IdCalculator.generate_hashed_file_id(
            self.graph_environment.environment, self.graph_environment.diff_identifier, relative_path
        )

        return original_file_node_id
