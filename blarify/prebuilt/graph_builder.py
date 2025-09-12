from typing import Optional
from blarify.code_references.hybrid_resolver import HybridReferenceResolver, ResolverMode
from blarify.graph.graph import Graph
from blarify.graph.graph_environment import GraphEnvironment
from blarify.project_file_explorer.project_files_iterator import ProjectFilesIterator
from blarify.project_graph_creator import ProjectGraphCreator


class GraphBuilder:
    def __init__(
        self,
        root_path: str,
        only_hierarchy: bool = False,
        extensions_to_skip: Optional[list[str]] = None,
        names_to_skip: Optional[list[str]] = None,
        graph_environment: Optional[GraphEnvironment] = None,
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

        self.root_path = root_path
        self.extensions_to_skip = extensions_to_skip or []
        self.names_to_skip = names_to_skip or []

        self.only_hierarchy = only_hierarchy

    def build(
        self,
    ) -> Graph:
        """Build the code graph with optional documentation layer.

        Args:
            include_documentation: Whether to generate documentation layer
            llm_provider: LLM provider for documentation analysis (required if include_documentation=True)
            db_manager: Database manager for persisting documentation (required if include_documentation=True)

        Returns:
            Graph object containing code nodes (and documentation nodes if requested)
        """
        reference_query_helper = self._get_started_reference_query_helper()
        project_files_iterator = self._get_project_files_iterator()

        graph_creator = ProjectGraphCreator(
            root_path=self.root_path,
            reference_query_helper=reference_query_helper,
            project_files_iterator=project_files_iterator,
            graph_environment=self.graph_environment,
        )

        if self.only_hierarchy:
            graph = graph_creator.build_hierarchy_only()
        else:
            graph = graph_creator.build()

        reference_query_helper.shutdown()

        return graph

    def _get_project_files_iterator(self):
        return ProjectFilesIterator(
            root_path=self.root_path,
            extensions_to_skip=self.extensions_to_skip,
            names_to_skip=self.names_to_skip,
            blarignore_path=self.root_path + "/.blarignore",
        )

    def _get_started_reference_query_helper(self):
        reference_query_helper = HybridReferenceResolver(root_uri=self.root_path, mode=ResolverMode.AUTO)
        return reference_query_helper
