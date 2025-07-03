Core Components
===============

The three most important classes in Blarify for graph creation and management.

.. note::
   For visual examples of what these components generate, see :doc:`visual_examples`.

ProjectGraphCreator
-------------------

The foundational class that creates graphs from source code by analyzing project files and building the complete graph structure.

**Purpose:**
  Creates complete project graphs from scratch by scanning project files, parsing code with Tree-sitter, and extracting relationships using Language Server Protocol (LSP).

**Key Features:**
  - Scans project directories and files
  - Builds code hierarchy (folders, files, classes, functions)
  - Extracts relationships between code elements (calls, imports, contains)
  - Supports multiple programming languages.
  - Uses Tree-sitter for syntax parsing
  - Uses LSP for extracting relationships

**Main Methods:**

``build()``
  Creates a complete graph with both hierarchy and relationships

.. code-block:: python

   from blarify.project_graph_creator import ProjectGraphCreator
   from blarify.code_references.lsp_helper import LspQueryHelper
   from blarify.project_file_explorer import ProjectFilesIterator

   # Setup components
   lsp_helper = LspQueryHelper(root_uri="/path/to/project")
   lsp_helper.start()

   files_iterator = ProjectFilesIterator(
       root_path="/path/to/project",
       extensions_to_skip=[".json"],
       names_to_skip=["__pycache__"]
   )

   # Create graph
   creator = ProjectGraphCreator(
       root_path="/path/to/project",
       lsp_query_helper=lsp_helper,
       project_files_iterator=files_iterator
   )

   graph = creator.build()
   lsp_helper.shutdown_exit_close()

``build_hierarchy_only()``
  Creates only the code structure without relationships (faster for large projects)

.. code-block:: python

   # For faster analysis of large projects
   graph = creator.build_hierarchy_only()

**Constructor Parameters:**
  - ``root_path``: Project root directory path
  - ``lsp_query_helper``: LSP helper for semantic analysis
  - ``project_files_iterator``: Iterator for project files
  - ``graph_environment``: Optional graph environment context

ProjectGraphDiffCreator
-----------------------

Extends ProjectGraphCreator to handle incremental graph updates by processing file diffs and creating graphs for only changed code.

**Purpose:**
  Creates graphs for only the parts of a project that have changed.

**Key Features:**
  - Processes file diffs (added, modified, deleted)
  - Creates graphs for only changed files
  - Handles external relationships to unchanged code
  - Tracks previous node states for comparison
  - Supports pull request environments

**Main Methods:**

``build()``
  Creates a GraphUpdate with changes and external relationships

.. code-block:: python

   from blarify.project_graph_diff_creator import ProjectGraphDiffCreator, FileDiff, ChangeType

   # Define file changes
   file_diffs = [
       FileDiff(
           path="src/example.py",
           diff_text="def new_function():\n    pass",
           change_type=ChangeType.MODIFIED
       )
   ]

   # Create diff creator
   diff_creator = ProjectGraphDiffCreator(
       root_path="/path/to/project",
       lsp_query_helper=lsp_helper,
       project_files_iterator=files_iterator,
       file_diffs=file_diffs,
       graph_environment=graph_environment,
       pr_environment=pr_environment
   )

   graph_update = diff_creator.build()

``build_with_previous_node_states()``
  Creates updates with knowledge of previous code states, this allows for more accurate diffs, like specific function changes or class modifications.

.. code-block:: python

   from blarify.project_graph_diff_creator import PreviousNodeState

   previous_states = [
       PreviousNodeState(
           node_path="src/example.py#ClassName.method_name",
           code_text="def old_method(self):\n    return 'old'"
       )
   ]

   graph_update = diff_creator.build_with_previous_node_states(previous_states)

**Constructor Parameters:**
  - All parameters from ProjectGraphCreator, plus:
  - ``file_diffs``: List of FileDiff objects describing changes
  - ``pr_environment``: Environment context of pull request, used to label nodes that are part of the PR

**File Diff Structure:**

.. code-block:: python

   @dataclass
   class FileDiff:
       path: str              # File path relative to project root
       diff_text: str         # The actual diff content
       change_type: ChangeType # ADDED, MODIFIED, or DELETED

ProjectGraphUpdater
-------------------

A simplified wrapper around ProjectGraphDiffCreator specifically designed for updating graphs when files have been modified.

**Purpose:**
  Provides a simple interface for updating existing graphs when you have a list of files that have been changed, without needing to rebuild the entire graph.

**Key Features:**
  - Allows incremental updates of graph
  - Uses same logic as ProjectGraphDiffCreator but simplifies the interface

**Main Methods:**

``build()``
  Creates a GraphUpdate for all specified updated files

.. code-block:: python

   from blarify.project_graph_updater import ProjectGraphUpdater, UpdatedFile

   # List of files that have been changed
   updated_files = [
       UpdatedFile(path="src/file1.py"),
       UpdatedFile(path="src/file2.py")
   ]

   # Create updater
   updater = ProjectGraphUpdater(
       updated_files=updated_files,
       graph_environment=graph_environment,
       root_path="/path/to/project",
       lsp_query_helper=lsp_helper,
       project_files_iterator=files_iterator
   )

   graph_update = updater.build()

``build_hierarchy_only()``
  Updates only the code structure without relationships

.. code-block:: python

   # Faster update for large projects
   graph_update = updater.build_hierarchy_only()

**Constructor Parameters:**
  - ``updated_files``: List of UpdatedFile objects
  - ``graph_environment``: Environment context (used for both graph and PR)
  - All other parameters from ProjectGraphCreator

**Updated File Structure:**

.. code-block:: python

   @dataclass
   class UpdatedFile:
       path: str  # File path relative to project root

Usage Patterns
--------------

**Full Project Analysis (Initial Setup):**

.. code-block:: python

   # Use ProjectGraphCreator for complete analysis
   creator = ProjectGraphCreator(root_path, lsp_helper, files_iterator)
   graph = creator.build()

**Incremental Updates (CI/CD):**

.. code-block:: python

   # Use ProjectGraphUpdater for simple file updates
   updater = ProjectGraphUpdater(updated_files, graph_environment, ...)
   graph_update = updater.build()

**Pull Request Analysis:**

.. code-block:: python

   # Use ProjectGraphDiffCreator for detailed diff analysis
   diff_creator = ProjectGraphDiffCreator(
       file_diffs=pr_diffs,
       graph_environment=main_env,
       pr_environment=pr_env,
       ...
   )
   graph_update = diff_creator.build()

**Performance Considerations:**

- Use ``build_hierarchy_only()`` for faster analysis when relationships aren't needed

Implementation Notes
--------------------

- ProjectGraphUpdater and ProjectGraphDiffCreator outputs are designed to be merged to the original graph with a MERGE cypher query.
- See :class:`blarify.db_managers.neo4j_manager.Neo4jManager` for graph merging operations using ``create_nodes()`` and ``create_edges()`` methods which implement MERGE functionality via ``apoc.merge.node`` and ``apoc.merge.relationship``

.. autoclass:: blarify.project_graph_creator.ProjectGraphCreator
   :members:
   :show-inheritance:

.. autoclass:: blarify.project_graph_diff_creator.ProjectGraphDiffCreator
   :members:
   :show-inheritance:

.. autoclass:: blarify.project_graph_updater.ProjectGraphUpdater
   :members:
   :show-inheritance:
