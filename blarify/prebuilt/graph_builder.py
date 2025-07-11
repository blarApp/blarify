from typing import Optional, Dict, Any

from blarify.code_references.lsp_helper import LspQueryHelper
from blarify.graph.graph import Graph
from blarify.graph.graph_environment import GraphEnvironment
from blarify.project_file_explorer.project_files_iterator import ProjectFilesIterator
from blarify.project_graph_creator import ProjectGraphCreator
from blarify.documentation.semantic_analyzer import LLMProvider
from blarify.documentation.post_processor import DocumentationPostProcessor
from blarify.db_managers.abstract_db_manager import AbstractDbManager


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

    def build(self, include_documentation: bool = False, llm_provider: Optional[LLMProvider] = None, 
              db_manager: Optional[AbstractDbManager] = None) -> Graph:
        """Build the code graph with optional documentation layer.
        
        Args:
            include_documentation: Whether to generate documentation layer
            llm_provider: LLM provider for documentation analysis (required if include_documentation=True)
            db_manager: Database manager for persisting documentation (required if include_documentation=True)
            
        Returns:
            Graph object containing code nodes (and documentation nodes if requested)
        """
        lsp_query_helper = self._get_started_lsp_query_helper()
        project_files_iterator = self._get_project_files_iterator()

        graph_creator = ProjectGraphCreator(self.root_path, lsp_query_helper, project_files_iterator, 
                                            graph_environment=self.graph_environment)

        if self.only_hierarchy:
            graph = graph_creator.build_hierarchy_only()
        else:
            graph = graph_creator.build()

        lsp_query_helper.shutdown_exit_close()
        
        # Add documentation layer if requested
        if include_documentation:
            if not llm_provider or not db_manager:
                raise ValueError("llm_provider and db_manager are required when include_documentation=True")
            
            doc_processor = DocumentationPostProcessor(
                graph=graph,
                db_manager=db_manager,
                llm_provider=llm_provider,
                process_mode="full"
            )
            doc_stats = doc_processor.process()
            
            # Add documentation nodes to the graph
            # Note: The documentation nodes are already persisted to DB by the processor
            # but we might want to add them to the in-memory graph as well
            for info_node in doc_processor.information_nodes:
                graph.add_node(info_node)
            
            # Add documentation relationships
            if doc_processor.documentation_relationships:
                graph.add_references_relationships(doc_processor.documentation_relationships)

        return graph

    def _get_project_files_iterator(self):
        return ProjectFilesIterator(
            root_path=self.root_path, extensions_to_skip=self.extensions_to_skip, names_to_skip=self.names_to_skip
        )

    def _get_started_lsp_query_helper(self):
        lsp_query_helper = LspQueryHelper(root_uri=self.root_path)
        lsp_query_helper.start()
        return lsp_query_helper
