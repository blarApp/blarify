from typing import Optional
from blarify.code_references.hybrid_resolver import HybridReferenceResolver, ResolverMode
from blarify.graph.graph import Graph
from blarify.graph.graph_environment import GraphEnvironment
from blarify.project_file_explorer.project_files_iterator import ProjectFilesIterator
from blarify.project_graph_creator import ProjectGraphCreator
from blarify.project_graph_updater import ProjectGraphUpdater, UpdatedFile
from blarify.documentation.workflow_creator import WorkflowCreator
from blarify.documentation.documentation_creator import DocumentationCreator
from blarify.agents.llm_provider import LLMProvider
from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager
from blarify.utils.path_calculator import PathCalculator
from blarify.graph.node.utils.id_calculator import IdCalculator
from ..repositories.graph_db_manager.graph_queries import (
    detach_delete_nodes_by_paths_query,
    match_empty_folders_query,
    detach_delete_nodes_by_node_ids_query,
)


class GraphBuilder:
    def __init__(
        self,
        root_path: str,
        db_manager: AbstractDbManager,
        only_hierarchy: bool = False,
        extensions_to_skip: Optional[list[str]] = None,
        names_to_skip: Optional[list[str]] = None,
        graph_environment: Optional[GraphEnvironment] = None,
        generate_embeddings: bool = False,
    ):
        """
        A class responsible for constructing a graph representation of a project's codebase.

        Args:
            root_path: Root directory path of the project to analyze
            extensions_to_skip: File extensions to exclude from analysis (e.g., ['.md', '.txt'])
            names_to_skip: Filenames/directory names to exclude from analysis (e.g., ['venv', 'tests'])
            db_manager: Optional database manager for saving graph and creating workflows/documentation
            generate_embeddings: Whether to generate embeddings for documentation nodes

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
        self.db_manager = db_manager
        self.generate_embeddings = generate_embeddings

        self.only_hierarchy = only_hierarchy

    def build(
        self,
        save_to_db: bool = True,
        create_workflows: bool = False,
        create_documentation: bool = False,
        max_workers: int = 75,
    ) -> Graph:
        """Build the code graph with optional persistence and documentation/workflow generation.

        Args:
            save_to_db: Whether to save the graph to database (requires db_manager)
            create_workflows: Whether to discover and create workflows (requires db_manager and save_to_db)
            create_documentation: Whether to generate documentation (requires db_manager and save_to_db)

        Returns:
            Graph object containing code nodes

        Example:
            # Simple build without persistence
            graph = builder.build(save_to_db=False)

            # Build with workflows
            graph = builder.build(create_workflows=True)

            # Full pipeline with documentation
            graph = builder.build(
                create_workflows=True,
                create_documentation=True
            )
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

        # Optionally save and create workflows/documentation
        if self.db_manager and save_to_db:
            nodes = graph.get_nodes_as_objects()
            relationships = graph.get_relationships_as_objects()
            self.db_manager.save_graph(nodes, relationships)

            # Create workflows if requested
            if create_workflows:
                workflow_creator = WorkflowCreator(
                    db_manager=self.db_manager,
                    graph_environment=self.graph_environment,
                )
                workflow_creator.discover_workflows(save_to_database=True)

            # Create documentation if requested
            if create_documentation:
                agent_caller = LLMProvider()
                doc_creator = DocumentationCreator(
                    db_manager=self.db_manager,
                    agent_caller=agent_caller,
                    graph_environment=self.graph_environment,
                    max_workers=max_workers,
                )
                doc_creator.create_documentation(generate_embeddings=self.generate_embeddings)

        return graph

    def incremental_update(
        self,
        updated_files: list[UpdatedFile],
        save_to_db: bool = True,
        create_workflows: bool = False,
        create_documentation: bool = False,
    ) -> Graph:
        """Incrementally update the code graph for specific files with optional persistence and documentation/workflow generation.

        This method is optimized for updating only the files that have changed, rather than rebuilding
        the entire graph. It uses the same workflow as the full build but only processes specified files.

        Args:
            updated_files: List of UpdatedFile objects indicating which files to update
            save_to_db: Whether to save the graph to database (requires db_manager)
            create_workflows: Whether to discover and create workflows (requires db_manager and save_to_db)
            create_documentation: Whether to generate documentation (requires db_manager and save_to_db)

        Returns:
            Graph object containing updated code nodes

        Example:
            # Simple incremental update without persistence
            updated_files = [UpdatedFile(path="/path/to/changed_file.py")]
            graph = builder.incremental_update(updated_files, save_to_db=False)

            # Incremental update with workflows
            graph = builder.incremental_update(updated_files, create_workflows=True)

            # Full pipeline with documentation
            graph = builder.incremental_update(
                updated_files,
                create_workflows=True,
                create_documentation=True
            )
        """
        reference_query_helper = self._get_started_reference_query_helper()
        project_files_iterator = self._get_project_files_iterator()
        file_paths = [file.path for file in updated_files]
        node_paths = [self._convert_file_path_to_node_path(path) for path in file_paths]

        self._detatch_delete_nodes_by_paths(file_paths=file_paths)

        graph_updater = ProjectGraphUpdater(
            updated_files=updated_files,
            root_path=self.root_path,
            reference_query_helper=reference_query_helper,
            project_files_iterator=project_files_iterator,
            graph_environment=self.graph_environment,
        )

        if self.only_hierarchy:
            graph = graph_updater.build_hierarchy_only()
        else:
            graph = graph_updater.build()

        reference_query_helper.shutdown()

        self._detatch_empty_folder_nodes_iteratively()

        # Optionally save and create workflows/documentation
        if save_to_db:
            nodes = graph.get_nodes_as_objects()
            relationships = graph.get_relationships_as_objects()
            self.db_manager.save_graph(nodes, relationships)

            # Create workflows if requested
            if create_workflows:
                workflow_creator = WorkflowCreator(
                    db_manager=self.db_manager,
                    graph_environment=self.graph_environment,
                )
                workflow_creator.discover_workflows(file_paths=node_paths, save_to_database=True)

            # Create documentation if requested
            if create_documentation:
                agent_caller = LLMProvider()
                doc_creator = DocumentationCreator(
                    db_manager=self.db_manager,
                    agent_caller=agent_caller,
                    graph_environment=self.graph_environment,
                )
                doc_creator.create_documentation(target_paths=node_paths, generate_embeddings=self.generate_embeddings)

        return graph

    def _detatch_delete_nodes_by_paths(self, file_paths: list[str]):
        query = detach_delete_nodes_by_paths_query()
        self.db_manager.query(
            query,
            parameters={
                "file_paths": file_paths,
            },
            transaction=True,
        )

    def __detatch_delete_nodes_by_node_ids(self, node_ids: list[str]):
        query = detach_delete_nodes_by_node_ids_query()
        self.db_manager.query(
            query,
            parameters={
                "node_ids": node_ids,
            },
            transaction=True,
        )

    def __match_empty_folders(self):
        query = match_empty_folders_query()
        result = self.db_manager.query(
            query,
            parameters={},
        )

        return result

    def _detatch_empty_folder_nodes_iteratively(self):
        while empty_folders := self.__match_empty_folders():
            empty_nodes_ids = [folder["folder"]["node_id"] for folder in empty_folders]
            self.__detatch_delete_nodes_by_node_ids(empty_nodes_ids)

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

    def _convert_file_path_to_node_path(self, file_path: str) -> str:
        """
        Convert a file URI path to a node_path.

        Args:
            file_path: File URI (e.g., "file:///path/to/file.py")

        Returns:
            Node path (e.g., "/environment/diff_identifier/relative/path")
        """
        pure_path = PathCalculator.uri_to_path(file_path)
        relative_path = PathCalculator.compute_relative_path_with_prefix(pure_path, self.graph_environment.root_path)
        node_path = IdCalculator.generate_file_id(
            self.graph_environment.environment, self.graph_environment.diff_identifier, relative_path
        )
        return node_path
