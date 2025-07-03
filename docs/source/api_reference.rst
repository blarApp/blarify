API Reference
=============

This section provides detailed API documentation for all public classes and methods in Blarify.

Prebuilt Classes
----------------

These are the main entry points for using Blarify in your applications.

GraphBuilder
~~~~~~~~~~~~

.. autoclass:: blarify.prebuilt.graph_builder.GraphBuilder
   :members:
   :show-inheritance:

**Constructor Parameters:**

- ``root_path`` (str): Path to the project directory to analyze
- ``extensions_to_skip`` (List[str], optional): File extensions to ignore (e.g., ``[".json", ".md"]``)
- ``names_to_skip`` (List[str], optional): Files/directories to ignore (e.g., ``["node_modules", "__pycache__"]``)
- ``only_hierarchy`` (bool, optional): If True, skip semantic analysis and only build structure
- ``graph_environment`` (GraphEnvironment, optional): Custom environment configuration

**Example:**

.. code-block:: python

   from blarify.prebuilt.graph_builder import GraphBuilder

   builder = GraphBuilder(
       root_path="/path/to/project",
       extensions_to_skip=[".json", ".md"],
       names_to_skip=["node_modules", "__pycache__"]
   )
   graph = builder.build()

GraphDiffBuilder
~~~~~~~~~~~~~~~~

.. autoclass:: blarify.prebuilt.graph_diff_builder.GraphDiffBuilder
   :members:
   :show-inheritance:

**Constructor Parameters:**

- ``root_path`` (str): Path to the project directory
- ``file_diffs`` (List[FileDiff]): List of file changes to analyze
- ``previous_node_states`` (List[PreviousNodeState], optional): Previous versions of nodes for comparison
- ``extensions_to_skip`` (List[str], optional): File extensions to ignore
- ``names_to_skip`` (List[str], optional): Files/directories to ignore
- ``graph_environment`` (GraphEnvironment, optional): Environment for main graph
- ``pr_environment`` (GraphEnvironment, optional): Environment for PR-specific nodes

**Example:**

.. code-block:: python

   from blarify.prebuilt.graph_diff_builder import GraphDiffBuilder
   from blarify.project_graph_diff_creator import FileDiff, ChangeType

   diffs = [
       FileDiff(
           path="file://path/to/file.py",
           diff_text="@@ -1,3 +1,4 @@\n def func():\n+    print('hello')\n     pass",
           change_type=ChangeType.MODIFIED
       )
   ]

   builder = GraphDiffBuilder(
       root_path="/path/to/project",
       file_diffs=diffs
   )
   graph_update = builder.build()

Data Classes
------------

FileDiff
~~~~~~~~

.. autoclass:: blarify.project_graph_diff_creator.FileDiff
   :members:
   :show-inheritance:

**Attributes:**

- ``path`` (str): File path in URI format (e.g., ``"file://path/to/file.py"``)
- ``diff_text`` (str): Git diff text showing changes
- ``change_type`` (ChangeType): Type of change (ADDED, MODIFIED, DELETED)

PreviousNodeState
~~~~~~~~~~~~~~~~~

.. autoclass:: blarify.project_graph_diff_creator.PreviousNodeState
   :members:
   :show-inheritance:

**Attributes:**

- ``node_path`` (str): Path to the node (e.g., ``"/path/to/file.py.function_name"``)
- ``code_text`` (str): Previous code content

ChangeType
~~~~~~~~~~

.. autoclass:: blarify.project_graph_diff_creator.ChangeType
   :members:
   :show-inheritance:

**Values:**

- ``ADDED``: File was added
- ``MODIFIED``: File was modified
- ``DELETED``: File was deleted

Graph Classes
-------------

Graph
~~~~~

.. autoclass:: blarify.graph.graph.Graph
   :members:
   :show-inheritance:

**Key Methods:**

``get_nodes_as_objects() -> List[Dict]``
  Returns all nodes as dictionary objects for database storage.

  **Node Structure:**

  .. code-block:: python

     {
         "type": "node_type",
         "extra_labels": [],
         "attributes": {
             "label": "node_type",
             "path": "file://path/to/file",
             "node_id": "hashed_id",
             "name": "node_name",
             "level": "hierarchy_level",
             "start_line": 10,      # Optional
             "end_line": 20,        # Optional
             "text": "code_text"    # Optional
         }
     }

``get_relationships_as_objects() -> List[Dict]``
  Returns all relationships as dictionary objects.

  **Relationship Structure:**

  .. code-block:: python

     {
         "sourceId": "source_node_id",
         "targetId": "target_node_id", 
         "type": "relationship_type",
         "scopeText": "context_text"
     }

GraphUpdate
~~~~~~~~~~~

.. autoclass:: blarify.graph.graph_update.GraphUpdate
   :members:
   :show-inheritance:

**Attributes:**

- ``graph`` (Graph): The updated graph with changes
- ``external_relationships`` (List): Relationships to external nodes

Database Managers
-----------------

Neo4jManager
~~~~~~~~~~~~

.. autoclass:: blarify.db_managers.neo4j_manager.Neo4jManager
   :members:
   :show-inheritance:

**Constructor Parameters:**

- ``repo_id`` (str): Repository identifier
- ``entity_id`` (str): Organization/entity identifier
- ``uri`` (str, optional): Neo4j URI (default from NEO4J_URI env var)
- ``username`` (str, optional): Neo4j username (default from NEO4J_USERNAME env var)
- ``password`` (str, optional): Neo4j password (default from NEO4J_PASSWORD env var)

**Example:**

.. code-block:: python

   from blarify.db_managers.neo4j_manager import Neo4jManager

   db = Neo4jManager(repo_id="my-project", entity_id="my-org")
   db.save_graph(nodes, relationships)
   db.close()

FalkorDBManager
~~~~~~~~~~~~~~~

.. autoclass:: blarify.db_managers.falkordb_manager.FalkorDBManager
   :members:
   :show-inheritance:

**Constructor Parameters:**

- ``repo_id`` (str): Repository identifier
- ``entity_id`` (str): Organization/entity identifier
- ``uri`` (str, optional): FalkorDB URI (default from FALKORDB_URI env var)
- ``port`` (int, optional): FalkorDB port (default from FALKORDB_PORT env var)
- ``username`` (str, optional): FalkorDB username
- ``password`` (str, optional): FalkorDB password

**Example:**

.. code-block:: python

   from blarify.db_managers.falkordb_manager import FalkorDBManager

   db = FalkorDBManager(repo_id="my-project", entity_id="my-org")
   db.save_graph(nodes, relationships)
   db.close()

Node Types
----------

The following node types are created by Blarify:

FILE
~~~~
Represents source code files.

**Attributes:**
- ``path``: File path
- ``name``: File name
- ``level``: Hierarchy level (0 for root files)

FOLDER
~~~~~~
Represents directory structure.

**Attributes:**
- ``path``: Directory path
- ``name``: Directory name
- ``level``: Hierarchy level

CLASS
~~~~~
Represents class definitions.

**Attributes:**
- ``path``: File path containing the class
- ``name``: Class name
- ``level``: Hierarchy level within file
- ``start_line``: Starting line number
- ``end_line``: Ending line number
- ``text``: Class source code

FUNCTION
~~~~~~~~
Represents function/method definitions.

**Attributes:**
- ``path``: File path containing the function
- ``name``: Function name
- ``level``: Hierarchy level within file
- ``start_line``: Starting line number
- ``end_line``: Ending line number
- ``text``: Function source code

DEFINITION
~~~~~~~~~~
Represents variables, imports, and constants.

**Attributes:**
- ``path``: File path containing the definition
- ``name``: Definition name
- ``level``: Hierarchy level within file
- ``start_line``: Starting line number
- ``end_line``: Ending line number
- ``text``: Definition source code

Relationship Types
------------------

The following relationship types are created by Blarify:

CONTAINS
~~~~~~~~
Hierarchical containment relationships.

**Examples:**
- Folder contains file
- File contains class
- Class contains method

CALLS
~~~~~
Function call relationships.

**Examples:**
- Function A calls function B
- Method calls external function

REFERENCES
~~~~~~~~~~
Code reference relationships.

**Examples:**
- Variable references
- Import usage
- Type references

INHERITS
~~~~~~~~
Class inheritance relationships.

**Examples:**
- Class A inherits from class B
- Interface implementation

MODIFIED
~~~~~~~~
Node was modified in a pull request.

ADDED
~~~~~
Node was added in a pull request.

DELETED
~~~~~~~
Node was deleted in a pull request.

Environment Variables
---------------------

Required environment variables for Blarify:

Project Configuration
~~~~~~~~~~~~~~~~~~~~~

``ROOT_PATH``
  Path to the project to analyze.

``BLARIGNORE_PATH`` (optional)
  Path to a file containing ignore patterns.

Neo4j Configuration
~~~~~~~~~~~~~~~~~~~

``NEO4J_URI``
  Neo4j connection URI (e.g., ``bolt://localhost:7687``)

``NEO4J_USERNAME``
  Neo4j username

``NEO4J_PASSWORD``
  Neo4j password

FalkorDB Configuration
~~~~~~~~~~~~~~~~~~~~~~

``FALKORDB_URI``
  FalkorDB host (e.g., ``127.0.0.1``)

``FALKORDB_PORT``
  FalkorDB port (e.g., ``6379``)

``FALKORDB_USERNAME``
  FalkorDB username

``FALKORDB_PASSWORD``
  FalkorDB password

Supported Languages
-------------------

Blarify supports the following programming languages:

- **Python**: Full support with Tree-sitter and Jedi LSP
- **JavaScript**: Full support with Tree-sitter and TypeScript LSP
- **TypeScript**: Full support with Tree-sitter and TypeScript LSP
- **Ruby**: Full support with Tree-sitter and Solargraph LSP
- **Go**: Full support with Tree-sitter and gopls LSP
- **C#**: Full support with Tree-sitter and OmniSharp LSP
- **Java**: Full support with Tree-sitter and Eclipse JDT LSP
- **PHP**: Full support with Tree-sitter and Intelephense LSP

Each language has its own parser and LSP integration for accurate semantic analysis.

Usage Examples
--------------

Complete Project Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from blarify.prebuilt.graph_builder import GraphBuilder
   from blarify.db_managers.neo4j_manager import Neo4jManager
   
   # Build complete project graph
   builder = GraphBuilder("/path/to/project")
   graph = builder.build()
   
   # Save to database
   db = Neo4jManager(repo_id="project", entity_id="org")
   db.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
   db.close()

Pull Request Analysis
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from blarify.prebuilt.graph_diff_builder import GraphDiffBuilder
   from blarify.project_graph_diff_creator import FileDiff, ChangeType
   
   # Define changes
   diffs = [
       FileDiff(
           path="file://src/service.py",
           diff_text="@@ -10,4 +10,6 @@\n def process():\n+    validate_input()\n     return result",
           change_type=ChangeType.MODIFIED
       )
   ]
   
   # Build graph with PR changes
   builder = GraphDiffBuilder(root_path="/path/to/project", file_diffs=diffs)
   graph_update = builder.build()
   
   # Save to database
   db = Neo4jManager(repo_id="project", entity_id="org")
   db.save_graph(
       graph_update.graph.get_nodes_as_objects(),
       graph_update.graph.get_relationships_as_objects()
   )
   db.close()

Hierarchy Only (Fast)
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from blarify.prebuilt.graph_builder import GraphBuilder
   
   # Build only structure without semantic relationships
   builder = GraphBuilder("/path/to/project", only_hierarchy=True)
   graph = builder.build()  # Much faster for large projects