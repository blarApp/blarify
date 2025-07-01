Blarify Documentation
=====================

A simple graph builder based on LSP calls that represents local code repositories as graph structures.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   quickstart
   core_components
   visual_examples

Quick Start
-----------

.. code-block:: python

   from blarify.prebuilt.graph_builder import GraphBuilder

   builder = GraphBuilder("/path/to/your/project")
   graph = builder.build()
   
   nodes = graph.get_nodes_as_objects()
   relationships = graph.get_relationships_as_objects()

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
