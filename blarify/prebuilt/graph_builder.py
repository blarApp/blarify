from typing import Optional
from blarify.code_references.lsp_helper import LspQueryHelper
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
        # GitHub integration parameters
        enable_github_integration: bool = False,
        github_token: Optional[str] = None,
        github_repo_owner: Optional[str] = None,
        github_repo_name: Optional[str] = None,
        github_pr_limit: int = 50,
        github_since_date: Optional[str] = None,
    ):
        """
        A class responsible for constructing a graph representation of a project's codebase.

        Args:
            root_path: Root directory path of the project to analyze
            only_hierarchy: If True, only build the hierarchy without code references
            extensions_to_skip: File extensions to exclude from analysis (e.g., ['.md', '.txt'])
            names_to_skip: Filenames/directory names to exclude from analysis (e.g., ['venv', 'tests'])
            graph_environment: Optional graph environment to use
            enable_github_integration: Whether to enable GitHub integration
            github_token: GitHub personal access token (optional, uses env var if not provided)
            github_repo_owner: Repository owner/organization
            github_repo_name: Repository name
            github_pr_limit: Maximum number of PRs to fetch (default 50)
            github_since_date: ISO format date to fetch PRs since (optional)

        Example:
            builder = GraphBuilder(
                    "/path/to/project",
                    extensions_to_skip=[".json"],
                    names_to_skip=["__pycache__"],
                    enable_github_integration=True,
                    github_token="ghp_...",
                    github_repo_owner="blarApp",
                    github_repo_name="blarify"
                )
            project_graph = builder.build()

        """

        self.graph_environment = graph_environment or GraphEnvironment("blarify", "repo", root_path)

        self.root_path = root_path
        self.extensions_to_skip = extensions_to_skip or []
        self.names_to_skip = names_to_skip or []

        self.only_hierarchy = only_hierarchy
        
        # GitHub integration settings
        self.enable_github_integration = enable_github_integration
        self.github_token = github_token
        self.github_repo_owner = github_repo_owner
        self.github_repo_name = github_repo_name
        self.github_pr_limit = github_pr_limit
        self.github_since_date = github_since_date

    def build(
        self,
        db_manager=None,  # Optional database manager for GitHub integration
    ) -> Graph:
        """Build the code graph with optional GitHub integration.

        Args:
            db_manager: Database manager for persisting GitHub integration data (optional)

        Returns:
            Graph object containing code nodes (and GitHub integration if enabled)
        """
        lsp_query_helper = self._get_started_lsp_query_helper()
        project_files_iterator = self._get_project_files_iterator()

        graph_creator = ProjectGraphCreator(
            self.root_path, lsp_query_helper, project_files_iterator, graph_environment=self.graph_environment
        )

        if self.only_hierarchy:
            graph = graph_creator.build_hierarchy_only()
        else:
            graph = graph_creator.build()

        lsp_query_helper.shutdown_exit_close()
        
        # Add GitHub integration if enabled
        if self.enable_github_integration and db_manager:
            self._build_github_integration(db_manager)

        return graph
    
    def _build_github_integration(self, db_manager):
        """Build GitHub integration layer."""
        from blarify.integrations.github_creator import GitHubCreator
        
        github_creator = GitHubCreator(
            db_manager=db_manager,
            graph_environment=self.graph_environment,
            github_token=self.github_token,
            repo_owner=self.github_repo_owner,
            repo_name=self.github_repo_name,
        )
        
        result = github_creator.create_github_integration(
            pr_limit=self.github_pr_limit,
            since_date=self.github_since_date,
            save_to_database=True,
        )
        
        return result

    def _get_project_files_iterator(self):
        return ProjectFilesIterator(
            root_path=self.root_path, extensions_to_skip=self.extensions_to_skip, names_to_skip=self.names_to_skip
        )

    def _get_started_lsp_query_helper(self):
        lsp_query_helper = LspQueryHelper(root_uri=self.root_path)
        lsp_query_helper.start()
        return lsp_query_helper
