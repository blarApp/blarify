Installation & Configuration
============================

Requirements
------------

- Python 3.10 - 3.14
- Linux or macOS

Installation
------------

From PyPI:

.. code-block:: bash

   pip install blarify

From Source:

.. code-block:: bash

   git clone https://github.com/blarApp/blarify.git
   cd blarify
   poetry install

Configuration
-------------

Create a `.env` file:

.. code-block:: bash

   ROOT_PATH=/path/to/your/project

Usage
-----

.. code-block:: python

   from blarify.prebuilt.graph_builder import GraphBuilder
   from blarify.db_managers.neo4j_manager import Neo4jManager

   builder = GraphBuilder("/path/to/project")
   graph = builder.build()

   db = Neo4jManager(repo_id="project", entity_id="org")
   db.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())
   db.close()

Development
-----------

.. code-block:: bash

   git clone https://github.com/blarApp/blarify.git
   cd blarify
   poetry install
   poetry run python -m blarify.main