import time
from blarify.code_references import LspQueryHelper, FileExtensionNotSupported
from blarify.project_file_explorer import ProjectFilesIterator
from blarify.graph.node import NodeLabels, NodeFactory
from blarify.graph.relationship import RelationshipCreator
from blarify.graph.graph import Graph
from blarify.code_hierarchy import TreeSitterHelper
from blarify.code_hierarchy.languages import (
    FallbackDefinitions,
    get_language_definition,
    get_available_languages
)
from typing import List, TYPE_CHECKING, Optional, Dict, Any, Union, Sequence, Any
from blarify.logger import Logger
from blarify.graph.graph_environment import GraphEnvironment
from blarify.llm_descriptions import LLMService
from blarify.llm_descriptions.description_generator import DescriptionGenerator
from blarify.filesystem import FilesystemGraphGenerator
from blarify.documentation import DocumentationGraphGenerator
import logging

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from blarify.graph.node import FolderNode
    from blarify.project_file_explorer import File, Folder
    from blarify.graph.node import Node, FileNode
    from blarify.graph.relationship import Relationship


class ProjectGraphCreator:
    root_path: str
    lsp_query_helper: LspQueryHelper
    project_files_iterator: ProjectFilesIterator
    graph: Graph
    languages: Optional[Dict[str, Any]] = None  # Will be initialized in __init__

    def __init__(
        self,
        root_path: str,
        lsp_query_helper: LspQueryHelper,
        project_files_iterator: ProjectFilesIterator,
        graph_environment: Optional["GraphEnvironment"] = None,
        enable_llm_descriptions: Optional[bool] = None,
        enable_filesystem_nodes: Optional[bool] = None,
        enable_documentation_nodes: Optional[bool] = None,
        documentation_patterns: Optional[List[str]] = None,
        max_llm_calls_per_doc: int = 5,
    ):
        self.root_path = root_path
        self.lsp_query_helper = lsp_query_helper
        self.project_files_iterator = project_files_iterator
        self.graph_environment = graph_environment or GraphEnvironment("blarify", "repo", self.root_path)
        
        # Build languages dictionary dynamically based on available imports
        self.languages = self._build_languages_dict()
        
        # Initialize LLM components
        self.enable_llm_descriptions = enable_llm_descriptions
        if enable_llm_descriptions is None:
            import os
            self.enable_llm_descriptions = os.getenv("ENABLE_LLM_DESCRIPTIONS", "true").lower() == "true"
        
        self.llm_service = None
        self.description_generator = None
        if self.enable_llm_descriptions:
            try:
                self.llm_service = LLMService()
                self.description_generator = DescriptionGenerator(self.llm_service, self.graph_environment)
                logger.info("LLM description generation enabled")
            except Exception as e:
                logger.error(f"Failed to initialize LLM service: {e}")
                self.enable_llm_descriptions = False
        
        # Initialize filesystem components
        self.enable_filesystem_nodes = enable_filesystem_nodes
        if enable_filesystem_nodes is None:
            import os
            self.enable_filesystem_nodes = os.getenv("ENABLE_FILESYSTEM_NODES", "true").lower() == "true"
        
        self.filesystem_generator = None
        if self.enable_filesystem_nodes:
            # Get extensions and names to skip from project_files_iterator
            extensions_to_skip = getattr(project_files_iterator, 'extensions_to_skip', [])
            names_to_skip = getattr(project_files_iterator, 'names_to_skip', [])
            
            self.filesystem_generator = FilesystemGraphGenerator(
                root_path=root_path,
                graph_environment=self.graph_environment,
                extensions_to_skip=extensions_to_skip,
                names_to_skip=names_to_skip
            )
            logger.info("Filesystem node generation enabled")
        
        # Initialize documentation components
        self.enable_documentation_nodes = enable_documentation_nodes
        if enable_documentation_nodes is None:
            import os
            self.enable_documentation_nodes = os.getenv("ENABLE_DOCUMENTATION_NODES", "true").lower() == "true"
        
        self.documentation_generator = None
        if self.enable_documentation_nodes:
            # Reuse LLM service if available
            llm_service = self.llm_service if self.enable_llm_descriptions else None
            
            self.documentation_generator = DocumentationGraphGenerator(
                root_path=root_path,
                graph_environment=self.graph_environment,
                llm_service=llm_service,
                documentation_patterns=documentation_patterns,
                max_llm_calls_per_doc=max_llm_calls_per_doc
            )
            logger.info("Documentation node generation enabled")

        self.graph = Graph()

    def _build_languages_dict(self) -> Dict[str, Any]:
        """Build languages dictionary dynamically based on available imports."""
        languages: Dict[str, Any] = {}
        
        # Map language names to file extensions
        language_extension_map = {
            'python': ['.py'],
            'javascript': ['.js', '.jsx'],
            'typescript': ['.ts', '.tsx'],
            'ruby': ['.rb'],
            'csharp': ['.cs'],
            'go': ['.go'],
            'php': ['.php'],
            'java': ['.java'],
        }
        
        # Populate languages dict with successfully imported definitions
        for lang_name, extensions in language_extension_map.items():
            definition_class = get_language_definition(lang_name)
            if definition_class:
                for ext in extensions:
                    languages[ext] = definition_class
            else:
                logger.debug(f"Language support for {lang_name} is not available")
        
        logger.info(f"Available language support: {list(get_available_languages())}")
        return languages

    def build(self) -> Graph:
        self._create_code_hierarchy()
        self._create_relationships_from_references_for_files()
        
        # Generate LLM descriptions if enabled
        if self.enable_llm_descriptions and self.description_generator:
            self._generate_llm_descriptions()
        
        # Generate filesystem nodes if enabled
        if self.enable_filesystem_nodes and self.filesystem_generator:
            self._generate_filesystem_nodes()
        
        # Generate documentation nodes if enabled
        if self.enable_documentation_nodes and self.documentation_generator:
            self._generate_documentation_nodes()
        
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
        folder_node.relate_nodes_as_contain_relationship(folder_nodes)

        self.graph.add_nodes(folder_nodes)

        files = folder.files
        self._process_files(files, parent_folder=folder_node)

    def _add_or_get_folder_node(self, folder: "Folder", parent_folder: "Folder" = None) -> "FolderNode":
        if self.graph.has_folder_node_with_path(folder.uri_path):
            return self.graph.get_folder_node_by_path(folder.uri_path)
        else:
            folder_node = NodeFactory.create_folder_node(
                folder, parent=parent_folder, graph_environment=self.graph_environment
            )
            self.graph.add_node(folder_node)
            return folder_node

    def _create_subfolder_nodes(self, folder: "Folder", folder_node: "FolderNode") -> List["Node"]:
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
            file=file, parent_folder=parent_folder, tree_sitter_helper=tree_sitter_helper
        )
        self.graph.add_nodes(file_nodes)

        file_node = self._get_file_node_from_file_nodes(file_nodes)
        file_node.skeletonize()

        parent_folder.relate_node_as_contain_relationship(file_node)

    def _try_initialize_directory(self, file: "File") -> None:
        try:
            self.lsp_query_helper.initialize_directory(file)
        except FileExtensionNotSupported:
            pass

    def _get_tree_sitter_for_file_extension(self, file_extension: str) -> TreeSitterHelper:
        language = self._get_language_definition(file_extension=file_extension)
        return TreeSitterHelper(language_definitions=language, graph_environment=self.graph_environment)

    def _get_language_definition(self, file_extension: str):
        return self.languages.get(file_extension, FallbackDefinitions)

    def _get_file_node_from_file_nodes(self, file_nodes: List["Node"]) -> "FileNode":
        # File node should always be the first node in the list
        for node in file_nodes:
            if node.label == NodeLabels.FILE:
                return node

        raise ValueError("File node not found in file nodes")

    def _create_file_nodes(
        self, file: "File", parent_folder: "FolderNode", tree_sitter_helper: TreeSitterHelper
    ) -> List["Node"]:
        document_symbols = tree_sitter_helper.create_nodes_and_relationships_in_file(file, parent_folder=parent_folder)
        return document_symbols

    def _create_relationships_from_references_for_files(self) -> None:
        file_nodes = self.graph.get_nodes_by_label(NodeLabels.FILE)
        self._create_relationship_from_references(file_nodes)

    def _create_relationship_from_references(self, file_nodes: List["Node"]) -> None:
        references_relationships = []

        total_files = len(file_nodes)
        log_interval = max(1, total_files // 10)

        for index, file_node in enumerate(file_nodes):
            start_time = time.time()
            self._log_if_multiple_of_x(
                index=index,
                x=log_interval,
                text=f"Processing file {file_node.name}: {index + 1}/{total_files} -- {100 * index / total_files:.2f}%",
            )

            nodes = self.graph.get_nodes_by_path(file_node.path)
            for node in nodes:
                if node.label == NodeLabels.FILE:
                    continue

                logger.debug(f"Processing node {node.name}")

                tree_sitter_helper = self._get_tree_sitter_for_file_extension(node.extension)
                references_relationships.extend(
                    self._create_node_relationships(node=node, tree_sitter_helper=tree_sitter_helper)
                )
            end_time = time.time()

            execution_time = end_time - start_time
            self._log_if_multiple_of_x(
                index=index,
                x=log_interval,
                text=f"Execution time for {file_node.name}: {execution_time:.2f} seconds, relationship count: {len(references_relationships)}",
            )

        self.graph.add_references_relationships(references_relationships=references_relationships)

    def _log_if_multiple_of_x(self, index: int, x: int, text: str) -> None:
        if index % x == 0:
            Logger.log(text)

    def _create_node_relationships(
        self,
        node: "Node",
        tree_sitter_helper: TreeSitterHelper,
    ) -> List["Relationship"]:
        references = self.lsp_query_helper.get_paths_where_node_is_referenced(node)

        relationships = RelationshipCreator.create_relationships_from_paths_where_node_is_referenced(
            references=references, node=node, graph=self.graph, tree_sitter_helper=tree_sitter_helper
        )

        return relationships
    
    def _generate_llm_descriptions(self) -> None:
        """Generate LLM descriptions for nodes in the graph."""
        start_time = time.time()
        logger.info("Starting LLM description generation")
        
        try:
            description_nodes = self.description_generator.generate_descriptions_for_graph(self.graph)
            logger.info(f"Generated {len(description_nodes)} description nodes")
        except Exception as e:
            logger.error(f"Error generating LLM descriptions: {e}")
        
        end_time = time.time()
        execution_time = end_time - start_time
        logger.info(f"LLM description generation completed in {execution_time:.2f} seconds")
    
    def _generate_filesystem_nodes(self) -> None:
        """Generate filesystem nodes and relationships."""
        start_time = time.time()
        logger.info("Starting filesystem node generation")
        
        try:
            # Generate filesystem nodes
            self.filesystem_generator.generate_filesystem_nodes(self.graph)
            
            # Create IMPLEMENTS relationships
            implements_rels = self.filesystem_generator.create_implements_relationships(self.graph)
            self.graph.add_references_relationships(implements_rels)
            
            # Create description references if LLM descriptions are enabled
            if self.enable_llm_descriptions:
                desc_refs = self.filesystem_generator.create_description_references(self.graph)
                self.graph.add_references_relationships(desc_refs)
            
        except Exception as e:
            logger.error(f"Error generating filesystem nodes: {e}")
        
        end_time = time.time()
        execution_time = end_time - start_time
        logger.info(f"Filesystem node generation completed in {execution_time:.2f} seconds")
    
    def _generate_documentation_nodes(self) -> None:
        """Generate documentation nodes and relationships."""
        start_time = time.time()
        logger.info("Starting documentation node generation")
        
        try:
            # Generate documentation nodes
            self.documentation_generator.generate_documentation_nodes(self.graph)
            
        except Exception as e:
            logger.error(f"Error generating documentation nodes: {e}")
        
        end_time = time.time()
        execution_time = end_time - start_time
        logger.info(f"Documentation node generation completed in {execution_time:.2f} seconds")
