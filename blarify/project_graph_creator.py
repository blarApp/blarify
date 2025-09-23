import time
from blarify.code_hierarchy.languages.go_definitions import GoDefinitions
from blarify.code_hierarchy.languages.language_definitions import LanguageDefinitions
from blarify.code_hierarchy.languages.php_definitions import PhpDefinitions
from blarify.code_references import FileExtensionNotSupported
from blarify.code_references.hybrid_resolver import HybridReferenceResolver
from blarify.code_references.types.Reference import Reference
from blarify.project_file_explorer import ProjectFilesIterator
from blarify.graph.node import NodeLabels, NodeFactory
from blarify.graph.relationship import RelationshipCreator
from blarify.graph.graph import Graph
from blarify.code_hierarchy import TreeSitterHelper
from blarify.code_hierarchy.languages import (
    PythonDefinitions,
    JavascriptDefinitions,
    TypescriptDefinitions,
    FallbackDefinitions,
    RubyDefinitions,
    CsharpDefinitions,
    JavaDefinitions,
)
from typing import Dict, List, TYPE_CHECKING, Optional, Type, cast
from blarify.logger import Logger
from blarify.graph.graph_environment import GraphEnvironment
from blarify.graph.node import Node, FileNode
import logging

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from blarify.graph.node import FolderNode
    from blarify.project_file_explorer import File, Folder
    from blarify.graph.relationship import Relationship


class ProjectGraphCreator:
    root_path: str
    reference_query_helper: HybridReferenceResolver
    project_files_iterator: ProjectFilesIterator
    graph: Graph
    languages: Dict[str, Type[LanguageDefinitions]] = {
        ".py": PythonDefinitions,
        ".js": JavascriptDefinitions,
        ".jsx": JavascriptDefinitions,
        ".ts": TypescriptDefinitions,
        ".tsx": TypescriptDefinitions,
        ".rb": RubyDefinitions,
        ".cs": CsharpDefinitions,
        ".go": GoDefinitions,
        ".php": PhpDefinitions,
        ".java": JavaDefinitions,
    }

    def __init__(
        self,
        root_path: str,
        reference_query_helper: HybridReferenceResolver,
        project_files_iterator: ProjectFilesIterator,
        graph_environment: Optional["GraphEnvironment"] = None,
    ):
        self.root_path = root_path
        self.reference_query_helper = reference_query_helper
        self.project_files_iterator = project_files_iterator
        self.graph_environment = graph_environment or GraphEnvironment("blarify", "0", self.root_path)

        self.graph = Graph()

    def build(self) -> Graph:
        self._create_code_hierarchy()
        self._create_relationships_from_references_for_files()
        return self.graph

    def build_hierarchy_only(self) -> Graph:
        """
        Build the graph with only the code hierarchy (folders, files, class definitions, function definitions)

        This will modify the graph in place and return it.
        """
        self._create_code_hierarchy()
        return self.graph

    def _create_code_hierarchy(self):
        start_time = time.time()

        for folder in self.project_files_iterator:
            self._process_folder(folder)

        end_time = time.time()
        execution_time = end_time - start_time
        logger.info(f"Execution time of create_code_hierarchy: {execution_time:.2f} seconds")

    def _process_folder(self, folder: "Folder") -> None:
        folder_node = self._add_or_get_folder_node(folder)
        folder_nodes = self._create_subfolder_nodes(folder, folder_node)
        folder_node.relate_nodes_as_contain_relationship(nodes=folder_nodes)

        self.graph.add_nodes(folder_nodes)

        files = folder.files
        self._process_files(files, parent_folder=folder_node)

    def _add_or_get_folder_node(self, folder: "Folder", parent_folder: Optional["FolderNode"] = None) -> "FolderNode":
        if self.graph.has_folder_node_with_path(folder.uri_path):
            return self.graph.get_folder_node_by_path(folder.uri_path)
        else:
            folder_node = NodeFactory.create_folder_node(
                folder, parent=parent_folder, graph_environment=self.graph_environment
            )
            self.graph.add_node(folder_node)
            return folder_node

    def _create_subfolder_nodes(self, folder: "Folder", folder_node: "FolderNode") -> List["FolderNode"]:
        nodes = []
        for sub_folder in folder.folders:
            node = self._add_or_get_folder_node(sub_folder, parent_folder=folder_node)
            nodes.append(node)

        return nodes

    def _process_files(self, files: List["File"], parent_folder: "FolderNode") -> None:
        for file in files:
            self._process_file(file, parent_folder)

    def _process_file(self, file: "File", parent_folder: "FolderNode") -> None:
        tree_sitter_helper = self._get_tree_sitter_for_file_extension(file.extension)
        self._try_initialize_directory(file)
        file_nodes = self._create_file_nodes(
            file=file,
            parent_folder=parent_folder,
            tree_sitter_helper=tree_sitter_helper,
        )
        self.graph.add_nodes(file_nodes)

        file_node = self._get_file_node_from_file_nodes(file_nodes)
        file_node.skeletonize()

        parent_folder.relate_node_as_contain_relationship(file_node)

    def _try_initialize_directory(self, file: "File") -> None:
        try:
            self.reference_query_helper.initialize_directory(file)
        except FileExtensionNotSupported:
            pass

    def _get_tree_sitter_for_file_extension(self, file_extension: str) -> TreeSitterHelper:
        language = self._get_language_definition(file_extension=file_extension)
        return TreeSitterHelper(language_definitions=language, graph_environment=self.graph_environment)

    def _get_language_definition(self, file_extension: str) -> Type[LanguageDefinitions]:
        return self.languages.get(file_extension, FallbackDefinitions)

    def _get_file_node_from_file_nodes(self, file_nodes: List["FileNode"]) -> "FileNode":
        # File node should always be the first node in the list
        for node in file_nodes:
            if node.label == NodeLabels.FILE:
                return node

        raise ValueError("File node not found in file nodes")

    def _create_file_nodes(
        self,
        file: "File",
        parent_folder: "FolderNode",
        tree_sitter_helper: TreeSitterHelper,
    ) -> List["FileNode"]:
        document_symbols = tree_sitter_helper.create_nodes_and_relationships_in_file(file, parent_folder=parent_folder)
        return [cast(FileNode, node) for node in document_symbols]

    def _create_relationships_from_references_for_files(self, files_nodes: Optional[List[FileNode]] = None) -> None:
        start_time = time.time()
        file_nodes = files_nodes or self.graph.get_nodes_by_label(NodeLabels.FILE.value)
        logger.info(f"Processing {len(file_nodes)} files for reference relationships")

        references_relationships = []
        total_files = len(file_nodes)
        log_interval = max(1, total_files // 10)

        # Collect all nodes that need reference processing
        all_nodes_to_process = []
        nodes_by_file = {}  # Track which file each node belongs to for logging

        for index, file_node in enumerate(file_nodes):
            self._log_if_multiple_of_x(
                index=index,
                x=log_interval,
                text=f"Collecting nodes from file {file_node.name}: {index + 1}/{total_files} -- {100 * index / total_files:.2f}%",
            )

            nodes = self.graph.get_nodes_by_path(file_node.path)
            for node in nodes:
                if node.label == NodeLabels.FILE:
                    continue

                all_nodes_to_process.append(node)
                nodes_by_file[node] = file_node

        # Batch process all reference requests
        batch_start_time = time.time()
        batch_results = self.reference_query_helper.get_paths_where_nodes_are_referenced_batch(all_nodes_to_process)
        batch_end_time = time.time()

        logger.info(f"Batch LSP queries completed in {batch_end_time - batch_start_time:.2f} seconds")

        # Process the results and create relationships
        processed_files = set()
        for node, references in batch_results.items():
            file_node = nodes_by_file[node]

            # Log progress per file (only once per file)
            if file_node not in processed_files:
                processed_files.add(file_node)
                file_index = list(file_nodes).index(file_node)
                self._log_if_multiple_of_x(
                    index=file_index,
                    x=log_interval,
                    text=f"Processing relationships for {file_node.name}: {file_index + 1}/{total_files} -- {100 * file_index / total_files:.2f}%",
                )

            tree_sitter_helper = self._get_tree_sitter_for_file_extension(node.extension)
            relationships = self._create_node_relationships_from_references(
                node=node, references=references, tree_sitter_helper=tree_sitter_helper
            )
            references_relationships.extend(relationships)

        self.graph.add_references_relationships(references_relationships=references_relationships)

        end_time = time.time()
        execution_time = end_time - start_time
        logger.info(
            f"Total execution time for _create_relationships_from_references_for_files: {execution_time:.2f} seconds"
        )
        logger.info(f"Created {len(references_relationships)} reference relationships")

    def _log_if_multiple_of_x(self, index: int, x: int, text: str) -> None:
        if index % x == 0:
            Logger.log(text)

    def _create_node_relationships_from_references(
        self,
        node: "Node",
        references: List[Reference],
        tree_sitter_helper: TreeSitterHelper,
    ) -> List["Relationship"]:
        """
        Create relationships for a node using pre-fetched references.
        This is used by the batch processing method.
        """
        relationships = RelationshipCreator.create_relationships_from_paths_where_node_is_referenced(
            references=references,
            node=node,
            graph=self.graph,
            tree_sitter_helper=tree_sitter_helper,
        )

        return relationships
