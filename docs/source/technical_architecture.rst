Technical Architecture
=====================

This document provides detailed technical explanations of Blarify's core algorithms, data structures, and implementation patterns.

Core Algorithm Overview
-----------------------

Blarify builds graphs through a multi-stage process:

1. **File Discovery**: Scan project directory structure
2. **Hierarchy Construction**: Use Tree-sitter to parse code structure  
3. **Semantic Analysis**: Use LSP to find references between nodes
4. **Relationship Detection**: Map LSP responses to relationship types
5. **Graph Assembly**: Combine hierarchy and relationships into final graph

Graph Construction Process
--------------------------

Folder and File Processing
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Stage 1: Directory Traversal**

.. code-block:: text

   ProjectFilesIterator
   ├── Scan root directory recursively
   ├── Apply extensions_to_skip filter
   ├── Apply names_to_skip filter  
   └── Generate file list for processing

**Stage 2: Hierarchy Creation**

.. code-block:: text

   For each folder:
   └── Create FOLDER node with path

   For each file:
   ├── Create FILE node with path  
   └── Process with Tree-sitter parser

Tree-sitter Analysis
~~~~~~~~~~~~~~~~~~~~

**Node Creation Process:**

.. code-block:: text

   Tree-sitter Parser
   ├── Parse file into syntax tree
   ├── Extract node information:
   │   ├── Node type (class, function, etc.)
   │   ├── Start line and end line  
   │   ├── Node name
   │   └── Source code text
   └── Create Blarify nodes with hierarchy

**Node Path Construction:**

.. code-block:: text

   Path Format: folder/file.py#class.method.nested_function
   
   Examples:
   ├── src/utils.py#validate_email → Function in file
   ├── src/models.py#User.save → Method in class
   └── src/core.py#Database.connect.retry → Nested function

**Node Types Created:**

- **FILE**: Source code files
- **FOLDER**: Directory structure
- **CLASS**: Class definitions from Tree-sitter class_definition nodes
- **FUNCTION**: Function/method definitions from function_definition nodes
- **DEFINITION**: Variables, imports, constants

LSP Integration Algorithm
-------------------------

Language Server Setup
~~~~~~~~~~~~~~~~~~~~~~

**Initialization Process:**

.. code-block:: text

   LspQueryHelper.start()
   ├── For each supported language:
   │   ├── Check if LSP server installed
   │   ├── Start LSP server process
   │   └── Establish JSON-RPC communication
   └── Ready for semantic analysis

**ensure_language_server_installed.py Logic:**

.. code-block:: text

   Purpose: Pre-download all LSP servers via multilspy
   
   Process:
   ├── Start all LSP servers once
   ├── Trigger multilspy auto-download
   ├── Download language-specific dependencies
   └── Cache servers for future use

Semantic Reference Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**LSP Query Process:**

.. code-block:: text

   For each file:
   ├── Send textDocument/references request to LSP
   ├── Receive array of reference locations
   ├── Each location contains:
   │   ├── File path
   │   ├── Line number  
   │   └── Character position
   └── Process each reference location

**Error Handling:**

.. code-block:: text

   LSP Request Failure:
   ├── Retry up to 3 times
   ├── If all retries fail:
   │   ├── Log warning
   │   ├── Skip references for this file
   │   └── Continue with next file
   └── No blocking failures

Relationship Detection Algorithm
--------------------------------

Core Detection Process
~~~~~~~~~~~~~~~~~~~~~~

**Step-by-Step Algorithm:**

.. code-block:: text

   1. LSP Response Processing:
      ├── LSP returns: file_path, line_number, character_position
      └── Target: Find relationship type

   2. Tree-sitter Node Lookup:
      ├── Parse target file with Tree-sitter
      ├── Find smallest node containing (line, character)
      └── Start traversal from this node

   3. Upward Traversal:
      ├── Check current node type against known patterns
      ├── If match found: assign relationship type
      ├── If no match: move to parent node
      ├── Continue until match or root reached
      └── If no match found: assign USES relationship

   4. Relationship Creation:
      ├── Source: Original node making reference
      ├── Target: Node found at LSP coordinates  
      ├── Type: Determined by Tree-sitter pattern
      └── Store in graph

**Example Traversal:**

.. code-block:: text

   LSP Response: line 42, char 15 → user.save()
   
   Tree-sitter Traversal:
   ├── identifier "save" (char 15)
   ├── ↑ attribute_access "user.save" 
   ├── ↑ call_expression "user.save()" ← MATCH!
   └── Result: CALLS relationship

Language-Specific Pattern Matching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Tree-sitter Node Type Mappings:**

Each language defines specific Tree-sitter patterns in ``blarify/code_hierarchy/languages/``:

**Python Patterns:**
.. code-block:: text

   call → CALLS relationship
   attribute → REFERENCES relationship  
   import_from_statement → USES relationship
   class_definition (inheritance) → INHERITS relationship

**JavaScript Patterns:**
.. code-block:: text

   call_expression → CALLS relationship
   member_expression → REFERENCES relationship
   import_statement → USES relationship
   class_declaration (extends) → INHERITS relationship

**Fallback Logic:**
.. code-block:: text

   If no pattern matches:
   └── Assign USES relationship type

Node Coordinate System
----------------------

Scope Detection Algorithm
~~~~~~~~~~~~~~~~~~~~~~~~~

**Finding Container Node:**

.. code-block:: text

   Given LSP coordinates (line, character):
   
   1. Get all nodes in target file
   2. Filter nodes where:
      ├── start_line ≤ line ≤ end_line
      └── Node contains the character position
   3. Select node with smallest scope:
      ├── Minimum (end_line - start_line)
      └── Most specific containing node
   4. Return container node

**Hierarchy Levels:**

.. code-block:: text

   Level Assignment:
   ├── 0: FILE nodes (top level)
   ├── 1: Top-level classes/functions
   ├── 2: Methods inside classes  
   ├── 3: Nested functions
   └── N: Unlimited nesting depth

Graph Data Structure
--------------------

Node Structure
~~~~~~~~~~~~~~

**Node Attributes:**

.. code-block:: python

   Node Properties:
   {
       "type": "FUNCTION|CLASS|FILE|FOLDER|DEFINITION",
       "path": "folder/file.py#class.method", 
       "node_id": "hashed_path_identifier",
       "name": "method",
       "level": 2,
       "start_line": 15,
       "end_line": 25, 
       "text": "def method(self):\n    return True"
   }

**Node ID Generation:**

.. code-block:: text

   Process:
   ├── Take full node path: "src/models.py#User.save" 
   ├── Apply hash function (implementation in IdCalculator)
   └── Generate unique identifier for database storage

Relationship Structure
~~~~~~~~~~~~~~~~~~~~~~

**Relationship Types:**

.. code-block:: text

   CONTAINS: Hierarchical containment
   ├── Folder CONTAINS file
   ├── File CONTAINS class
   └── Class CONTAINS method

   CALLS: Function invocation
   ├── Function calls another function
   └── Method calls another method

   REFERENCES: Variable/attribute access
   ├── Variable references
   └── Attribute access

   INHERITS: Class inheritance
   └── Class inherits from parent class

   USES: Generic relationship (fallback)
   └── Any reference not matching specific patterns

**Relationship Attributes:**

.. code-block:: python

   Relationship Properties:
   {
       "sourceId": "source_node_hashed_id",
       "targetId": "target_node_hashed_id", 
       "type": "CALLS|REFERENCES|INHERITS|CONTAINS|USES",
       "scopeText": "surrounding_code_context"
   }

Multi-Language Support
----------------------

Language Server Protocol Servers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**LSP Server Mapping:**

.. code-block:: text

   Python: Jedi Language Server
   JavaScript/TypeScript: TypeScript Language Server  
   Ruby: Solargraph
   Go: gopls
   C#: OmniSharp
   Java: Eclipse JDT Language Server
   PHP: Intelephense

**Tree-sitter Parser Mapping:**

.. code-block:: text

   .py → tree-sitter-python + PythonDefinitions
   .js/.jsx → tree-sitter-javascript + JavascriptDefinitions
   .ts/.tsx → tree-sitter-typescript + TypescriptDefinitions
   .rb → tree-sitter-ruby + RubyDefinitions
   .go → tree-sitter-go + GoDefinitions
   .cs → tree-sitter-csharp + CsharpDefinitions
   .java → tree-sitter-java + JavaDefinitions
   .php → tree-sitter-php + PhpDefinitions

Language-Specific Implementation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Definition Classes:**

Each language implements specific logic in ``blarify/code_hierarchy/languages/``:

.. code-block:: text

   LanguageDefinitions (Base Class)
   ├── PythonDefinitions
   ├── JavascriptDefinitions  
   ├── TypescriptDefinitions
   ├── RubyDefinitions
   ├── GoDefinitions
   ├── CsharpDefinitions
   ├── JavaDefinitions
   └── PhpDefinitions

**Language-Specific Patterns:**

Each class defines:

- Tree-sitter node type mappings
- Relationship detection patterns  
- Language-specific syntax handling
- Import/export statement processing

Performance Characteristics
---------------------------

Algorithmic Complexity
~~~~~~~~~~~~~~~~~~~~~~

**Time Complexity:**

.. code-block:: text

   Graph Construction: O(n × m)
   ├── n = number of files
   ├── m = average references per file
   └── LSP queries dominate processing time

   Tree-sitter Parsing: O(n × k)  
   ├── n = number of files
   ├── k = average file size
   └── Linear parsing per file

   Node Lookup: O(log n)
   ├── Binary search on line ranges
   └── Efficient coordinate-to-node mapping

**Space Complexity:**

.. code-block:: text

   Memory Usage: O(n + r)
   ├── n = total nodes created
   ├── r = total relationships found
   └── Graph stored in memory during construction

**Scaling Characteristics:**

.. code-block:: text

   LSP Communication:
   ├── Bottle­neck for large files
   ├── Network-like latency per request
   └── Benefits from LSP server caching

   Tree-sitter Parsing:
   ├── Fast and predictable
   ├── Scales linearly with file size
   └── Memory efficient

Error Handling Patterns
-----------------------

LSP Error Recovery
~~~~~~~~~~~~~~~~~~

**Failure Scenarios:**

.. code-block:: text

   LSP Server Startup Failure:
   ├── Log error message
   ├── Continue without LSP for that language
   └── Only Tree-sitter hierarchy created

   LSP Request Timeout:
   ├── Retry request up to 3 times
   ├── If still failing: skip file references
   └── Continue processing other files

   LSP Response Malformed:
   ├── Log warning with details
   ├── Skip malformed references
   └── Process remaining valid references

Tree-sitter Error Recovery
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Parsing Failures:**

.. code-block:: text

   Syntax Errors in Source:
   ├── Tree-sitter creates partial tree
   ├── Extract what nodes possible
   └── Continue with partial hierarchy

   Unsupported Language Features:
   ├── Use FallbackDefinitions class
   ├── Basic node detection only
   └── Limited relationship detection

**Graceful Degradation:**

.. code-block:: text

   Progressive Fallback:
   ├── Full analysis (Tree-sitter + LSP)
   ├── ↓ Hierarchy only (Tree-sitter)  
   ├── ↓ Basic file structure
   └── ↓ Minimal folder/file nodes