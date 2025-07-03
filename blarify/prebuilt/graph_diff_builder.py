from blarify.code_references.lsp_helper import LspQueryHelper
from blarify.graph.graph import Graph
from blarify.graph.graph_environment import GraphEnvironment
from blarify.project_file_explorer.project_files_iterator import ProjectFilesIterator
from blarify.project_graph_diff_creator import FileDiff, PreviousNodeState, ProjectGraphDiffCreator


class GraphDiffBuilder:
    def __init__(
        self,
        root_path: str,
        file_diffs: list[FileDiff],
        previous_node_states: list[PreviousNodeState] = None,
        extensions_to_skip: list[str] = None,
        names_to_skip: list[str] = None,
        only_hierarchy: bool = False,
        graph_environment: GraphEnvironment = None,
        pr_environment: GraphEnvironment = None,
    ):
        """
        A class responsible for constructing a graph representation of a project's codebase.

        Args:
            root_path: Root directory path of the project to analyze
            extensions_to_skip: File extensions to exclude from analysis (e.g., ['.md', '.txt'])
            names_to_skip: Filenames/directory names to exclude from analysis (e.g., ['venv', 'tests'])

        Example:
            builder = GraphBuilder(
                    "/path/to/project",
                    extensions_to_skip=[".json"],
                    names_to_skip=["__pycache__"]
                )
            project_graph = builder.build()

        """

        self.graph_environment = graph_environment or GraphEnvironment("blarify", "repo", root_path)
        self.pr_environment = pr_environment or GraphEnvironment("blarify", "pull_request", root_path)

        self.previous_node_states = previous_node_states or []

        self.file_diffs = file_diffs

        self.root_path = root_path
        self.extensions_to_skip = extensions_to_skip or []
        self.names_to_skip = names_to_skip or []

        self.only_hierarchy = only_hierarchy

    def build(self) -> Graph:
        lsp_query_helper = self._get_started_lsp_query_helper()
        project_files_iterator = self._get_project_files_iterator()

        graph_diff_creator = ProjectGraphDiffCreator(
            root_path=self.root_path,
            lsp_query_helper=lsp_query_helper,
            project_files_iterator=project_files_iterator,
            graph_environment=self.graph_environment,
            pr_environment=self.pr_environment,
            file_diffs=self.file_diffs,
        )

        if self.previous_node_states:
            graph = graph_diff_creator.build_with_previous_node_states(
                previous_node_states=self.previous_node_states,
            )
        else:
            graph = graph_diff_creator.build()

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
