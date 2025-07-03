Language Implementations
========================

This document details how each supported language is parsed and analyzed within Blarify. Each language has specific Tree-sitter patterns and relationship detection logic.

Base Language Interface
-----------------------

LanguageDefinitions Abstract Class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All language implementations extend the ``LanguageDefinitions`` abstract base class:

**Core Methods:**

.. code-block:: python

   class LanguageDefinitions(ABC):
       @abstractmethod
       def get_language_name() -> str
           # Returns LSP language identifier
           
       @abstractmethod  
       def should_create_node(node: Node) -> bool
           # Determines if Tree-sitter node becomes graph node
           
       @abstractmethod
       def get_identifier_node(node: Node) -> Node
           # Extracts name/identifier from Tree-sitter node
           
       @abstractmethod
       def get_body_node(node: Node) -> Node
           # Extracts code body without signatures
           
       @abstractmethod
       def get_relationship_type(node, reference_node: Node) -> FoundRelationshipScope
           # Maps Tree-sitter patterns to relationship types
           
       @abstractmethod
       def get_node_label_from_type(type: str) -> NodeLabels
           # Converts Tree-sitter types to Blarify node labels

**Relationship Detection Algorithm:**

.. code-block:: text

   For each LSP reference:
   ├── Find Tree-sitter node at coordinates
   ├── Call get_relationship_type()
   ├── Traverse up AST until pattern match
   ├── Return relationship type and scope
   └── Fallback to USES if no match

Language-Specific Implementations
---------------------------------

Python (python_definitions.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**LSP Language:** ``python``

**File Extensions:** ``.py``

**Tree-sitter Mappings:**

.. code-block:: text

   class_definition → NodeLabels.CLASS
   function_definition → NodeLabels.FUNCTION

**Relationship Patterns:**

.. code-block:: text

   CLASS relationships:
   ├── import_from_statement → RelationshipType.IMPORTS
   ├── superclasses → RelationshipType.INHERITS  
   ├── call → RelationshipType.INSTANTIATES
   ├── typing → RelationshipType.TYPES
   └── assignment → RelationshipType.TYPES

   FUNCTION relationships:
   ├── call → RelationshipType.CALLS
   ├── interpolation → RelationshipType.CALLS (f-strings)
   ├── import_from_statement → RelationshipType.IMPORTS
   └── assignment → RelationshipType.ASSIGNS

**Python-Specific Features:**

- **String Interpolation**: ``f"Hello {name}"`` creates CALLS relationship
- **Type Hints**: ``def func(x: int)`` creates TYPES relationship
- **From Imports**: ``from module import func`` creates IMPORTS relationship

JavaScript (javascript_definitions.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**LSP Language:** ``javascript``

**File Extensions:** ``.js``, ``.jsx``

**Tree-sitter Mappings:**

.. code-block:: text

   class_declaration → NodeLabels.CLASS
   function_declaration → NodeLabels.FUNCTION
   method_definition → NodeLabels.FUNCTION
   interface_declaration → NodeLabels.CLASS
   variable_declarator → NodeLabels.FUNCTION (arrow functions)

**Special Arrow Function Detection:**

.. code-block:: text

   Pattern: variable_declarator with arrow_function value
   Example: const func = () => {}
   Result: Creates FUNCTION node

**Relationship Patterns:**

.. code-block:: text

   CLASS relationships:
   ├── import_specifier/import_clause → RelationshipType.IMPORTS
   ├── new_expression → RelationshipType.INSTANTIATES
   ├── class_heritage → RelationshipType.INHERITS
   ├── variable_declarator → RelationshipType.ASSIGNS
   └── type_annotation → RelationshipType.TYPES

   FUNCTION relationships:
   ├── import_specifier/import_clause → RelationshipType.IMPORTS
   ├── call_expression → RelationshipType.CALLS
   └── variable_declarator → RelationshipType.ASSIGNS

**JavaScript-Specific Features:**

- **ES6 Imports**: ``import {func} from 'module'`` creates IMPORTS
- **Arrow Functions**: ``const f = () => {}`` detected as functions
- **Class Inheritance**: ``class Child extends Parent`` creates INHERITS
- **Object Creation**: ``new Class()`` creates INSTANTIATES

TypeScript (typescript_definitions.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**LSP Language:** ``typescript``

**File Extensions:** ``.ts``, ``.tsx``, ``.js``, ``.jsx``

**Implementation:** Extends ``JavascriptDefinitions``

**Additional Features:**

- **TypeScript Parser**: Uses ``tree_sitter_typescript.language_typescript()``
- **TSX Support**: Uses ``tree_sitter_typescript.language_tsx()`` for React
- **Type Annotations**: Enhanced type relationship detection
- **Interface Support**: ``interface`` declarations treated as classes

Ruby (ruby_definitions.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~

**LSP Language:** ``ruby``

**File Extensions:** ``.rb``

**Tree-sitter Mappings:**

.. code-block:: text

   class → NodeLabels.CLASS
   method → NodeLabels.FUNCTION
   singleton_method → NodeLabels.FUNCTION

**Relationship Patterns:**

.. code-block:: text

   CLASS relationships:
   ├── superclass → RelationshipType.INHERITS
   └── call with method "new" → RelationshipType.INSTANTIATES

   FUNCTION relationships:
   └── call → RelationshipType.CALLS

   General:
   └── assignment → RelationshipType.ASSIGNS

**Ruby-Specific Features:**

- **Class Inheritance**: ``class Child < Parent`` creates INHERITS
- **Constructor Detection**: ``Class.new`` creates INSTANTIATES
- **Singleton Methods**: ``def self.method`` treated as functions

Go (go_definitions.py)
~~~~~~~~~~~~~~~~~~~~~

**LSP Language:** ``go``

**File Extensions:** ``.go``

**Tree-sitter Mappings:**

.. code-block:: text

   type_spec → NodeLabels.CLASS
   type_alias → NodeLabels.CLASS
   method_declaration → NodeLabels.FUNCTION
   function_declaration → NodeLabels.FUNCTION

**Relationship Patterns:**

.. code-block:: text

   CLASS relationships:
   ├── import_declaration → RelationshipType.IMPORTS
   ├── field_declaration → RelationshipType.TYPES
   └── composite_literal → RelationshipType.INSTANTIATES

   FUNCTION relationships:
   ├── import_declaration → RelationshipType.IMPORTS
   └── call_expression → RelationshipType.CALLS

**Go-Specific Features:**

- **Type Definitions**: ``type User struct{}`` creates CLASS nodes
- **Type Aliases**: ``type UserID int`` creates CLASS nodes  
- **Composite Literals**: ``User{}`` creates INSTANTIATES
- **Package Imports**: ``import "package"`` creates IMPORTS

C# (csharp_definitions.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~

**LSP Language:** ``csharp``

**File Extensions:** ``.cs``

**Tree-sitter Mappings:**

.. code-block:: text

   class_declaration → NodeLabels.CLASS
   interface_declaration → NodeLabels.CLASS
   record_declaration → NodeLabels.CLASS
   method_declaration → NodeLabels.FUNCTION
   constructor_declaration → NodeLabels.FUNCTION

**Relationship Patterns:**

.. code-block:: text

   CLASS relationships:
   ├── object_creation_expression → RelationshipType.INSTANTIATES
   ├── using_directive → RelationshipType.IMPORTS
   ├── variable_declaration → RelationshipType.TYPES
   ├── parameter → RelationshipType.TYPES
   └── base_list → RelationshipType.INHERITS

   FUNCTION relationships:
   └── invocation_expression → RelationshipType.CALLS

**C#-Specific Features:**

- **Records**: ``record User(string Name)`` creates CLASS nodes
- **Using Directives**: ``using System`` creates IMPORTS
- **Object Creation**: ``new Class()`` creates INSTANTIATES
- **Inheritance**: ``class Child : Parent`` creates INHERITS

Java (java_definitions.py)
~~~~~~~~~~~~~~~~~~~~~~~~~~

**LSP Language:** ``java``

**File Extensions:** ``.java``

**Tree-sitter Mappings:**

.. code-block:: text

   class_declaration → NodeLabels.CLASS
   interface_declaration → NodeLabels.CLASS
   record_declaration → NodeLabels.CLASS
   method_declaration → NodeLabels.FUNCTION
   constructor_declaration → NodeLabels.FUNCTION

**Relationship Patterns:**

.. code-block:: text

   CLASS relationships:
   ├── object_creation_expression → RelationshipType.INSTANTIATES
   ├── import_declaration → RelationshipType.IMPORTS
   ├── variable_declarator → RelationshipType.ASSIGNS
   ├── formal_parameter → RelationshipType.TYPES
   ├── class_heritage → RelationshipType.INHERITS
   └── field_declaration → RelationshipType.TYPES

   FUNCTION relationships:
   └── method_invocation → RelationshipType.CALLS

**Java-Specific Features:**

- **Records**: ``record User(String name)`` creates CLASS nodes
- **Package Imports**: ``import java.util.List`` creates IMPORTS
- **Method Invocation**: ``object.method()`` creates CALLS
- **Inheritance**: ``class Child extends Parent`` creates INHERITS

PHP (php_definitions.py)
~~~~~~~~~~~~~~~~~~~~~~~~

**LSP Language:** ``php``

**File Extensions:** ``.php``

**Tree-sitter Mappings:**

.. code-block:: text

   class_declaration → NodeLabels.CLASS
   function_definition → NodeLabels.FUNCTION
   method_declaration → NodeLabels.FUNCTION

**Relationship Patterns:**

.. code-block:: text

   CLASS relationships:
   ├── namespace_use_declaration → RelationshipType.IMPORTS
   ├── base_clause → RelationshipType.INHERITS
   ├── object_creation_expression → RelationshipType.INSTANTIATES
   └── simple_parameter → RelationshipType.TYPES

   FUNCTION relationships:
   ├── function_call_expression → RelationshipType.CALLS
   ├── member_call_expression → RelationshipType.CALLS
   ├── namespace_use_declaration → RelationshipType.IMPORTS
   └── assignment_expression → RelationshipType.ASSIGNS

**PHP-Specific Features:**

- **Namespaces**: ``use App\\User`` creates IMPORTS
- **Class Inheritance**: ``class Child extends Parent`` creates INHERITS
- **Object Creation**: ``new Class()`` creates INSTANTIATES
- **Member Calls**: ``$object->method()`` creates CALLS

Relationship Detection Patterns
-------------------------------

Common Relationship Types
~~~~~~~~~~~~~~~~~~~~~~~~~

**CALLS vs REFERENCES:**

.. code-block:: text

   CALLS: Function/method invocations
   ├── Python: call
   ├── JavaScript: call_expression
   ├── Ruby: call
   ├── Go: call_expression
   ├── C#: invocation_expression
   ├── Java: method_invocation
   └── PHP: function_call_expression, member_call_expression

   REFERENCES: Variable/identifier usage
   └── Determined by context and lack of call patterns

**INHERITS vs INSTANTIATES:**

.. code-block:: text

   INHERITS: Class inheritance
   ├── Python: superclasses
   ├── JavaScript: class_heritage
   ├── Ruby: superclass
   ├── C#: base_list
   ├── Java: class_heritage
   └── PHP: base_clause

   INSTANTIATES: Object creation
   ├── JavaScript: new_expression
   ├── Ruby: call with method "new"
   ├── Go: composite_literal
   ├── C#: object_creation_expression
   ├── Java: object_creation_expression
   └── PHP: object_creation_expression

**IMPORTS vs TYPES:**

.. code-block:: text

   IMPORTS: Module/package imports
   ├── Python: import_from_statement
   ├── JavaScript: import_specifier, import_clause
   ├── Go: import_declaration
   ├── C#: using_directive
   ├── Java: import_declaration
   └── PHP: namespace_use_declaration

   TYPES: Type annotations and declarations
   ├── Python: typing
   ├── JavaScript: type_annotation
   ├── Go: field_declaration
   ├── C#: variable_declaration, parameter
   ├── Java: formal_parameter, field_declaration
   └── PHP: simple_parameter

Tree-sitter Integration Patterns
---------------------------------

Parser Configuration
~~~~~~~~~~~~~~~~~~~~

**Parser Mapping:**

.. code-block:: python

   language_parsers = {
       ".py": tree_sitter_python.language(),
       ".js": tree_sitter_javascript.language(),
       ".jsx": tree_sitter_javascript.language(),
       ".ts": tree_sitter_typescript.language_typescript(),
       ".tsx": tree_sitter_typescript.language_tsx(),
       ".rb": tree_sitter_ruby.language(),
       ".go": tree_sitter_go.language(),
       ".cs": tree_sitter_c_sharp.language(),
       ".java": tree_sitter_java.language(),
       ".php": tree_sitter_php.language()
   }

**Node Processing:**

.. code-block:: text

   For each Tree-sitter node:
   ├── Check should_create_node() - filter significant nodes
   ├── Extract identifier with get_identifier_node()
   ├── Extract body with get_body_node()
   ├── Map type with get_node_label_from_type()
   └── Create Blarify node with path, lines, text

Language Server Integration
---------------------------

LSP Server Mapping
~~~~~~~~~~~~~~~~~~

**Server Assignment:**

.. code-block:: text

   Python → Jedi Language Server
   JavaScript/TypeScript → TypeScript Language Server
   Ruby → Solargraph
   Go → gopls
   C# → OmniSharp
   Java → Eclipse JDT Language Server
   PHP → Intelephense

**LSP Request Processing:**

.. code-block:: text

   For each file:
   ├── Send textDocument/references request
   ├── Receive location array (file, line, character)
   ├── Map each location to Tree-sitter node
   ├── Apply language-specific relationship detection
   └── Create relationships in graph

Error Handling by Language
---------------------------

**Graceful Degradation:**

.. code-block:: text

   LSP Server Unavailable:
   ├── Log warning for language
   ├── Continue with Tree-sitter only
   └── Create hierarchy without references

   Tree-sitter Parse Error:
   ├── Extract partial syntax tree
   ├── Create nodes from parseable sections
   └── Skip malformed code sections

   Unknown Node Types:
   ├── Use FallbackDefinitions
   ├── Basic node detection only
   └── Limited relationship detection

Extending Language Support
--------------------------

Adding New Languages
~~~~~~~~~~~~~~~~~~~

**Implementation Steps:**

1. **Create Language Definition Class:**

.. code-block:: python

   class NewLanguageDefinitions(LanguageDefinitions):
       def get_language_name(self) -> str:
           return "newlang"
           
       def get_language_file_extensions(self) -> Set[str]:
           return {".newext"}
           
       # Implement all abstract methods...

2. **Define Tree-sitter Mappings:**

.. code-block:: python

   def get_node_label_from_type(self, type: str) -> NodeLabels:
       mappings = {
           "class_def": NodeLabels.CLASS,
           "func_def": NodeLabels.FUNCTION,
           # Language-specific mappings...
       }
       return mappings.get(type, NodeLabels.DEFINITION)

3. **Configure Relationship Detection:**

.. code-block:: python

   def get_relationship_type(self, node, reference_node):
       # Define language-specific patterns
       if node.type == "call_expr":
           return FoundRelationshipScope(node, RelationshipType.CALLS)
       # Additional patterns...

4. **Register in Language Map:**

.. code-block:: python

   languages = {
       ".newext": NewLanguageDefinitions,
       # Other languages...
   }

**Requirements:**

- Tree-sitter parser for the language
- LSP server supporting the language
- Understanding of language-specific syntax patterns
- Relationship detection logic appropriate for the language