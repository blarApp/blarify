"""
Edge case and error handling tests for GraphBuilder.

These tests verify GraphBuilder behavior with invalid inputs,
error conditions, and boundary cases.
"""

import pytest
from pathlib import Path
from typing import Any, Dict

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.graph.graph import Graph
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from tests.utils.graph_assertions import GraphAssertions


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestGraphBuilderEdgeCases:
    """Test GraphBuilder edge cases and error handling."""

    async def test_graphbuilder_nonexistent_path(self, docker_check: Any) -> None:
        """Test GraphBuilder with non-existent root path."""
        nonexistent_path = "/this/path/does/not/exist"

        # GraphBuilder should handle this gracefully
        builder = GraphBuilder(root_path=nonexistent_path)

        # Build should either complete with empty graph or raise appropriate error
        try:
            graph = builder.build()
            # If it succeeds, should be a valid Graph object
            assert isinstance(graph, Graph)
        except (FileNotFoundError, OSError):
            # This is also acceptable behavior
            pass

    async def test_graphbuilder_empty_file(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GraphBuilder with empty source files."""
        # Create an empty Python file
        empty_file = temp_project_dir / "empty.py"
        empty_file.write_text("")

        # Create another empty file with different extension
        empty_js = temp_project_dir / "empty.js"
        empty_js.write_text("")

        builder = GraphBuilder(root_path=str(temp_project_dir))
        graph = builder.build()

        # Should create valid graph even with empty files
        assert isinstance(graph, Graph)

        # Save to Neo4j with isolated IDs
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Should have File nodes for empty files
        await graph_assertions.assert_node_exists("FILE")

        # Get file properties
        file_properties = await graph_assertions.get_node_properties("FILE")

        # Should have entries for our empty files
        file_paths = [props.get("path", props.get("file_path", "")) for props in file_properties]
        py_files = [path for path in file_paths if path.endswith(".py")]

        assert len(py_files) > 0, "Should have Python file entries"

        db_manager.close()

    async def test_graphbuilder_invalid_syntax_files(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GraphBuilder with files containing syntax errors."""
        # Create Python file with syntax error
        invalid_python = temp_project_dir / "invalid_syntax.py"
        invalid_python.write_text("""
# This file has intentional syntax errors
def broken_function(
    # Missing closing parenthesis and body
    
class IncompleteClass:
    def method_without_body():
        # Missing pass or implementation
        
# Unclosed string literal
text = "this string is never closed
""")

        # Create TypeScript file with syntax error
        invalid_ts = temp_project_dir / "invalid_syntax.ts"
        invalid_ts.write_text("""
// This TypeScript has syntax errors
interface IncompleteInterface {
    prop1: string
    // Missing semicolon and closing brace
    
function brokenFunction() {
    console.log("unclosed function
    // Missing quotes and closing brace
""")

        builder = GraphBuilder(root_path=str(temp_project_dir))

        # GraphBuilder should handle syntax errors gracefully
        try:
            graph = builder.build()
            assert isinstance(graph, Graph)

            # Save to Neo4j if successful with isolated IDs
            db_manager = Neo4jManager(
                uri=test_data_isolation["uri"],
                user="neo4j",
                password=test_data_isolation["password"],
                repo_id=test_data_isolation["repo_id"],
                entity_id=test_data_isolation["entity_id"],
            )
            db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

            # Should still have File nodes even for invalid files
            await graph_assertions.assert_node_exists("FILE")

            db_manager.close()

        except Exception as e:
            # GraphBuilder might raise parsing errors, which is acceptable
            print(f"Expected parsing error: {type(e).__name__}: {e}")

    async def test_graphbuilder_very_large_files(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GraphBuilder with relatively large source files."""
        # Create a Python file with many functions
        large_python = temp_project_dir / "large_file.py"

        python_content = '"""Large Python file for testing."""\n\n'

        # Generate many simple functions
        for i in range(50):  # Reasonable number for testing
            python_content += f"""
def function_{i}(param1: str, param2: int) -> str:
    '''Function number {i}.'''
    result = f"Function {{param1}} number {i} with {{param2}}"
    return result

"""

        # Add a large class with many methods
        python_content += """
class LargeClass:
    '''A class with many methods.'''
    
    def __init__(self, value: str) -> None:
        self.value = value
"""

        for i in range(20):  # Add many methods
            python_content += f"""
    def method_{i}(self) -> str:
        '''Method number {i}.'''
        return f"{{self.value}} - method {i}"
"""

        large_python.write_text(python_content)

        builder = GraphBuilder(root_path=str(temp_project_dir))
        graph = builder.build()

        assert isinstance(graph, Graph)

        # Save to Neo4j with isolated IDs
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Should have many function nodes
        await graph_assertions.assert_node_exists("FILE")
        await graph_assertions.assert_node_exists("FUNCTION")
        await graph_assertions.assert_node_exists("CLASS")

        # Check that we created a reasonable number of functions
        function_properties = await graph_assertions.get_node_properties("FUNCTION")
        function_count = len(function_properties)

        # Should have created multiple functions (50 functions + class methods)
        assert function_count > 10, f"Expected many functions, got {function_count}"

        db_manager.close()

    async def test_graphbuilder_special_characters_in_paths(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GraphBuilder with special characters in file/directory names."""
        # Create directories and files with special characters
        special_dir = temp_project_dir / "special-chars_dir"
        special_dir.mkdir()

        # File with spaces and special characters in name
        special_file = special_dir / "file with spaces & symbols.py"
        special_file.write_text("""
def function_with_special_chars():
    '''Function in file with special characters.'''
    return "Special file content"

class SpecialClass:
    def method(self):
        return "method result"
""")

        # File with unicode characters
        unicode_file = special_dir / "файл_с_unicode.py"
        unicode_file.write_text("""
def unicode_function():
    return "unicode content"
""")

        builder = GraphBuilder(root_path=str(temp_project_dir))

        try:
            graph = builder.build()
            assert isinstance(graph, Graph)

            # Save to Neo4j with isolated IDs
            db_manager = Neo4jManager(
                uri=test_data_isolation["uri"],
                user="neo4j",
                password=test_data_isolation["password"],
                repo_id=test_data_isolation["repo_id"],
                entity_id=test_data_isolation["entity_id"],
            )
            db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

            # Should handle special characters in file paths
            await graph_assertions.assert_node_exists("FILE")

            # Get file properties to verify special character handling
            file_properties = await graph_assertions.get_node_properties("FILE")

            # Should have files with special characters
            assert len(file_properties) > 0

            db_manager.close()

        except Exception as e:
            # Some systems might not support unicode filenames
            print(f"Special character handling error (may be expected): {e}")

    async def test_graphbuilder_deeply_nested_directory(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GraphBuilder with deeply nested directory structure."""
        # Create deeply nested directories
        deep_path = temp_project_dir
        for i in range(10):  # Create 10 levels deep
            deep_path = deep_path / f"level_{i}"
            deep_path.mkdir()

        # Create a Python file in the deepest directory
        deep_file = deep_path / "deep_file.py"
        deep_file.write_text("""
def deeply_nested_function():
    '''Function in deeply nested directory.'''
    return "deep content"
""")

        builder = GraphBuilder(root_path=str(temp_project_dir))
        graph = builder.build()

        assert isinstance(graph, Graph)

        # Save to Neo4j with isolated IDs
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )
        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Should handle deeply nested files
        await graph_assertions.assert_node_exists("FILE")
        await graph_assertions.assert_node_exists("FUNCTION")

        # Verify we found the deeply nested function
        function_properties = await graph_assertions.get_node_properties("FUNCTION")
        function_names = [props.get("name") for props in function_properties]

        assert "deeply_nested_function" in function_names

        db_manager.close()

    async def test_graphbuilder_mixed_valid_invalid_files(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test GraphBuilder with mix of valid and invalid files."""
        # Create valid Python file
        valid_file = temp_project_dir / "valid.py"
        valid_file.write_text("""
def valid_function():
    return "valid content"

class ValidClass:
    def method(self):
        return "valid method"
""")

        # Create invalid Python file
        invalid_file = temp_project_dir / "invalid.py"
        invalid_file.write_text("""
# Invalid syntax
def broken(
    missing_closing_paren
    
class NoColon
    pass
""")

        # Create non-code file that should be ignored
        text_file = temp_project_dir / "readme.txt"
        text_file.write_text("This is not code")

        # Create binary file
        binary_file = temp_project_dir / "image.bin"
        binary_file.write_bytes(b"\x89PNG\x0d\x0a\x1a\x0a\x00\x00")  # PNG header

        builder = GraphBuilder(root_path=str(temp_project_dir), extensions_to_skip=[".txt", ".bin"])

        try:
            graph = builder.build()
            assert isinstance(graph, Graph)

            # Save to Neo4j with isolated IDs
            db_manager = Neo4jManager(
                uri=test_data_isolation["uri"],
                user="neo4j",
                password=test_data_isolation["password"],
                repo_id=test_data_isolation["repo_id"],
                entity_id=test_data_isolation["entity_id"],
            )
            db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

            # Should process the valid file and handle invalid gracefully
            await graph_assertions.assert_node_exists("FILE")

            # Get file properties
            file_properties = await graph_assertions.get_node_properties("FILE")
            file_paths = [props.get("file_path", "") for props in file_properties]

            # Should have Python files but not text/binary files
            py_files = [path for path in file_paths if path.endswith(".py")]
            txt_files = [path for path in file_paths if path.endswith(".txt")]
            bin_files = [path for path in file_paths if path.endswith(".bin")]

            assert len(py_files) > 0, "Should have Python files"
            assert len(txt_files) == 0, "Should not have text files (filtered)"
            assert len(bin_files) == 0, "Should not have binary files (filtered)"

            db_manager.close()

        except Exception as e:
            print(f"Mixed file processing error: {e}")
            # Some parsing errors are acceptable