Installation & Configuration
============================

Requirements
------------

- Python 3.10 - 3.14
- Neo4j or FalkorDB database
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

Database Setup
--------------

Neo4j
~~~~~

.. code-block:: bash

   # Docker
   docker run -p 7474:7474 -p 7687:7687 \
       -e NEO4J_AUTH=neo4j/your_password \
       neo4j:latest

   # Ubuntu/Debian
   sudo apt-get install neo4j

   # macOS
   brew install neo4j

FalkorDB
~~~~~~~~

.. code-block:: bash

   # Docker
   docker run -p 6379:6379 falkordb/falkordb:latest

Configuration
-------------

Create a `.env` file:

.. code-block:: bash

   ROOT_PATH=/path/to/your/project
   
   # Neo4j
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your_password
   
   # Or FalkorDB
   FALKORDB_URI=127.0.0.1
   FALKORDB_PORT=6379

Ignore Files
------------

Create `.blarignore`:

.. code-block:: text

   node_modules/
   .venv/
   __pycache__/
   .git/
   *.json
   *.md
   docs/

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