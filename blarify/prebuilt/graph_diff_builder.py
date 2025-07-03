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
        Adds pull request changes to graphs for AI analysis using Tree-sitter and LSP.

        Uses ProjectGraphDiffCreator to analyze file changes and create graph representations
        of pull requests. Operates in two modes based on available previous node states.

        Two modes:
        - Without previous_node_states: Tags entire files as changed
        - With previous_node_states: Tags only specific functions that changed

        Args:
            root_path: Root directory path of the project
            file_diffs: List of FileDiff objects with git diff information
            previous_node_states: Previous versions of nodes for precise change detection
            extensions_to_skip: File extensions to exclude (e.g., ['.json', '.md'])
            names_to_skip: Files/directories to exclude (e.g., ['node_modules', '__pycache__'])
            only_hierarchy: If True, build only structure without semantic relationships
            graph_environment: Environment for main graph
            pr_environment: Environment for PR-specific nodes

        Example:
            diffs = [FileDiff(path="file://src/file.py", diff_text="...", change_type=ChangeType.MODIFIED)]
            builder = GraphDiffBuilder(root_path="/project", file_diffs=diffs)
            graph_update = builder.build()
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
