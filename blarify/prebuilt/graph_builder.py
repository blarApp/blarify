from blarify.code_references.lsp_helper import LspQueryHelper
from blarify.graph.graph import Graph
from blarify.graph.graph_environment import GraphEnvironment
from blarify.project_file_explorer.project_files_iterator import ProjectFilesIterator
from blarify.project_graph_creator import ProjectGraphCreator


class GraphBuilder:
    def __init__(
        self,
        root_path: str,
        extensions_to_skip: list[str] = None,
        names_to_skip: list[str] = None,
        only_hierarchy: bool = False,
        graph_environment: GraphEnvironment = None,
    ):
        """
        Builds complete project graphs using Tree-sitter and Language Server Protocol.

        Uses ProjectGraphCreator to analyze source code and create comprehensive graphs
        containing file hierarchy, classes, functions, and their relationships.

        Args:
            root_path: Root directory path of the project to analyze
            extensions_to_skip: File extensions to exclude (e.g., ['.json', '.md'])
            names_to_skip: Files/directories to exclude (e.g., ['node_modules', '__pycache__'])
            only_hierarchy: If True, build only structure without semantic relationships
            graph_environment: Custom environment configuration

        Example:
            builder = GraphBuilder("/path/to/project")
            graph = builder.build()
            nodes = graph.get_nodes_as_objects()
            relationships = graph.get_relationships_as_objects()
        """

        self.graph_environment = graph_environment or GraphEnvironment("blarify", "repo", root_path)

        self.root_path = root_path
        self.extensions_to_skip = extensions_to_skip or []
        self.names_to_skip = names_to_skip or []

        self.only_hierarchy = only_hierarchy

    def build(self) -> Graph:
        lsp_query_helper = self._get_started_lsp_query_helper()
        project_files_iterator = self._get_project_files_iterator()

        graph_creator = ProjectGraphCreator(self.root_path, lsp_query_helper, project_files_iterator, 
                                            graph_environment=self.graph_environment)

        if self.only_hierarchy:
            graph = graph_creator.build_hierarchy_only()
        else:
            graph = graph_creator.build()

        lsp_query_helper.shutdown_exit_close()

        return graph

    def _get_project_files_iterator(self):
        return ProjectFilesIterator(
            root_path=self.root_path, extensions_to_skip=self.extensions_to_skip, names_to_skip=self.names_to_skip
        )

    def _get_started_lsp_query_helper(self):
        lsp_query_helper = LspQueryHelper(root_uri=self.root_path)
        lsp_query_helper.start()
        return lsp_query_helper
