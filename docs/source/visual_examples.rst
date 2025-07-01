Visual Examples
===============

This section showcases what the generated graphs look like when visualized in Neo4j Browser, demonstrating the output of the core Blarify components.

ProjectGraphCreator Output
--------------------------

The **ProjectGraphCreator** generates comprehensive graphs showing the complete structure and relationships of your codebase.

**Complete Project Graph:**

.. image:: _static/images/graph.png
   :alt: Complete project graph showing files, classes, functions and their relationships
   :width: 100%
   :align: center


**Detailed View - Code Relationships:**

.. image:: _static/images/graph_zoomed_in.png
   :alt: Zoomed in view showing detailed relationships between code elements
   :width: 100%
   :align: center


**Relationship Types:**

- **CONTAINS** - Folders contain files
- **DEFINES** - Files define classes and functions, classes define functions
- **CALLS** - Functions calling other functions
- **IMPORTS** - Classes or functions importing from other files
