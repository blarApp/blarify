GraphDiffBuilder Modes
======================

GraphDiffBuilder has two modes for analyzing pull request changes.

Mode 1: Without Previous Node States
-------------------------------------

**Method:** ``build()``

**What gets tagged:**
- Entire files marked as ADDED/MODIFIED/DELETED
- All functions and classes in changed files get the same tag

**Example:**
If you modify one function in a file with 10 functions, all 10 functions are tagged as MODIFIED.

.. code-block:: python

   builder = GraphDiffBuilder(root_path="/project", file_diffs=diffs)
   result = builder.build()

Mode 2: With Previous Node States  
----------------------------------

**Method:** ``build_with_previous_node_states()``

**What gets tagged:**
- Only specific functions/classes that actually changed
- Minimal scope tagging based on code comparison

**Example:**
If you modify one function in a file with 10 functions, only that 1 function is tagged as MODIFIED.

.. code-block:: python

   previous_states = [
       PreviousNodeState(
           node_path="/project/src/file.py.function_name",
           code_text="previous function code"
       )
   ]

   builder = GraphDiffBuilder(root_path="/project", file_diffs=diffs, previous_node_states=previous_states)
   result = builder.build_with_previous_node_states(previous_states)

Node Path Format
----------------

Previous node states use hierarchical paths:

.. code-block:: text

   /project/src/file.py                    # File
   /project/src/file.py.function_name      # Function
   /project/src/file.py.ClassName          # Class
   /project/src/file.py.ClassName.method   # Method

Comparison
----------

+------------------+----------------------+------------------------+
| Mode             | File-Level           | Function-Level         |
+==================+======================+========================+
| Scope            | Entire files         | Specific functions     |
| Performance      | Faster               | Slower                 |
| Precision        | Lower                | Higher                 |
+------------------+----------------------+------------------------+

Use file-level mode for broad analysis. Use function-level mode when you need to know exactly which functions changed.