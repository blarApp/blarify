"""
Integration tests for GraphBuilder incremental_update functionality.

These tests verify that incremental_update correctly updates only the specified files
without rebuilding the entire graph.
"""

import pytest
from pathlib import Path
from typing import Any, Dict

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.project_graph_updater import UpdatedFile
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from tests.utils.graph_assertions import GraphAssertions


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestGraphBuilderIncrementalUpdate:
    """Test incremental update functionality with realistic scenarios."""

    async def test_incremental_update_adds_new_file(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that incremental_update correctly adds a new file to existing graph."""
        # Create initial file
        initial_file = temp_project_dir / "initial.py"
        initial_file.write_text(
            "def initial_function():\n"
            "    return 'initial'\n"
        )

        # Initialize database manager
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        # Build initial graph
        builder = GraphBuilder(
            root_path=str(temp_project_dir),
            db_manager=db_manager,
        )
        builder.build(save_to_db=True)

        # Verify initial state
        initial_functions = await graph_assertions.get_node_properties("FUNCTION")
        assert len(initial_functions) == 1
        assert initial_functions[0]["name"] == "initial_function"
        initial_function_count = len(initial_functions)

        # Add NEW file
        new_file = temp_project_dir / "added.py"
        new_file.write_text(
            "def added_function():\n"
            "    return 'added'\n"
        )

        # Run incremental update for new file only
        updated_files = [UpdatedFile(path=str(new_file))]
        builder.incremental_update(updated_files, save_to_db=True)

        # Verify new file was added
        final_functions = await graph_assertions.get_node_properties("FUNCTION")

        assert len(final_functions) == initial_function_count + 1, f"Should have {initial_function_count + 1} functions after adding new file"

        function_names = {f["name"] for f in final_functions}
        assert "initial_function" in function_names, "Original function should still exist"
        assert "added_function" in function_names, "New function should be added"

        db_manager.close()

    async def test_incremental_update_modifies_existing_file(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that incremental_update correctly updates a modified file."""
        # Create initial file
        target_file = temp_project_dir / "target.py"
        target_file.write_text(
            "def original_function():\n"
            "    return 'original'\n"
        )

        # Initialize database manager
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        # Build initial graph
        builder = GraphBuilder(
            root_path=str(temp_project_dir),
            db_manager=db_manager,
        )
        builder.build(save_to_db=True)

        # Verify initial state
        initial_functions = await graph_assertions.get_node_properties("FUNCTION")
        assert len(initial_functions) == 1
        assert initial_functions[0]["name"] == "original_function"

        # Modify file - add a new function
        target_file.write_text(
            "def original_function():\n"
            "    return 'original'\n"
            "\n"
            "def new_function():\n"
            "    return 'new'\n"
        )

        # Run incremental update for modified file
        updated_files = [UpdatedFile(path=str(target_file))]
        builder.incremental_update(updated_files, save_to_db=True)

        # Verify updated state
        final_functions = await graph_assertions.get_node_properties("FUNCTION")
        assert len(final_functions) == 2, "Should have 2 functions after modification"

        function_names = {f["name"] for f in final_functions}
        assert "original_function" in function_names
        assert "new_function" in function_names

        db_manager.close()

    async def test_incremental_update_multiple_files_mixed_changes(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test incremental update with multiple files: one modified, one new."""
        # Create initial files
        file1 = temp_project_dir / "file1.py"
        file1.write_text("def func1():\n    pass\n")

        file2 = temp_project_dir / "file2.py"
        file2.write_text("def func2():\n    pass\n")

        # Initialize database manager
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        # Build initial graph
        builder = GraphBuilder(
            root_path=str(temp_project_dir),
            db_manager=db_manager,
        )
        builder.build(save_to_db=True)

        # Verify initial state
        initial_functions = await graph_assertions.get_node_properties("FUNCTION")
        assert len(initial_functions) == 2
        initial_function_names = {f["name"] for f in initial_functions}
        assert initial_function_names == {"func1", "func2"}

        # Modify file1
        file1.write_text("def func1():\n    pass\n\ndef func1_new():\n    pass\n")

        # Add file3 (new)
        file3 = temp_project_dir / "file3.py"
        file3.write_text("def func3():\n    pass\n")

        # Run incremental update for both changes
        updated_files = [
            UpdatedFile(path=str(file1)),
            UpdatedFile(path=str(file3)),
        ]
        builder.incremental_update(updated_files, save_to_db=True)

        # Verify final state
        final_functions = await graph_assertions.get_node_properties("FUNCTION")

        function_names = {f["name"] for f in final_functions}
        # Check all expected functions exist
        assert "func1" in function_names
        assert "func1_new" in function_names
        assert "func2" in function_names, "func2 should still exist (wasn't modified)"
        assert "func3" in function_names

        db_manager.close()

    async def test_incremental_update_only_affects_specified_files(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that incremental_update only updates specified files, not others."""
        # Create initial files
        file1 = temp_project_dir / "file1.py"
        file1.write_text("def func1():\n    return 1\n")

        file2 = temp_project_dir / "file2.py"
        file2.write_text("def func2():\n    return 2\n")

        # Initialize database manager
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        # Build initial graph
        builder = GraphBuilder(
            root_path=str(temp_project_dir),
            db_manager=db_manager,
        )
        builder.build(save_to_db=True)

        # Modify BOTH files
        file1.write_text("def func1():\n    return 1\n\ndef func1_extra():\n    pass\n")
        file2.write_text("def func2():\n    return 2\n\ndef func2_extra():\n    pass\n")

        # Run incremental update for ONLY file2 (not file1)
        updated_files = [UpdatedFile(path=str(file2))]
        builder.incremental_update(updated_files, save_to_db=True)

        # Verify: file2 updated, file1 NOT updated
        final_functions = await graph_assertions.get_node_properties("FUNCTION")
        function_names = {f["name"] for f in final_functions}

        # file2 should be updated (has func2_extra)
        assert "func2_extra" in function_names, "file2 should be updated with new function"

        # file1 should NOT be updated (no func1_extra)
        assert "func1_extra" not in function_names, "file1 should NOT be updated since it wasn't specified"

        # Original functions should still exist
        assert "func1" in function_names
        assert "func2" in function_names

        db_manager.close()

    async def test_incremental_update_with_relationships(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that incremental_update correctly handles relationships between nodes."""
        # Create initial files with import relationship
        file1 = temp_project_dir / "module1.py"
        file1.write_text("def helper():\n    return 'help'\n")

        file2 = temp_project_dir / "module2.py"
        file2.write_text(
            "from module1 import helper\n\n"
            "def main():\n"
            "    return helper()\n"
        )

        # Initialize database manager
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        # Build initial graph
        builder = GraphBuilder(
            root_path=str(temp_project_dir),
            db_manager=db_manager,
        )
        builder.build(save_to_db=True)

        # Verify initial import relationship exists
        relationships = await graph_assertions.get_relationship_types()
        assert "IMPORTS" in relationships or "CALLS" in relationships

        # Add new file that imports from module1
        file3 = temp_project_dir / "module3.py"
        file3.write_text(
            "from module1 import helper\n\n"
            "def use_helper():\n"
            "    return helper()\n"
        )

        # Run incremental update for new file
        updated_files = [UpdatedFile(path=str(file3))]
        builder.incremental_update(updated_files, save_to_db=True)

        # Verify new file and its relationships
        final_functions = await graph_assertions.get_node_properties("FUNCTION")
        function_names = {f["name"] for f in final_functions}

        assert "use_helper" in function_names, "New function should be added"
        assert "helper" in function_names, "Original helper function should still exist"
        assert "main" in function_names, "Original main function should still exist"

        db_manager.close()

    async def test_incremental_update_does_not_duplicate_workflows_and_docs(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that incremental_update doesn't duplicate workflow and documentation nodes."""
        # Create initial files with function calls
        file1 = temp_project_dir / "service.py"
        file1.write_text(
            "def helper():\n"
            "    return 'help'\n"
            "\n"
            "def process():\n"
            "    return helper()\n"
        )

        # Initialize database manager
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        # Build initial graph WITH workflows and documentation
        builder = GraphBuilder(
            root_path=str(temp_project_dir),
            db_manager=db_manager,
            generate_embeddings=False,
        )
        builder.build(
            save_to_db=True,
            create_workflows=True,
            create_documentation=True,
        )

        # Get initial counts of workflow and documentation nodes
        initial_workflows = await graph_assertions.get_node_properties("WORKFLOW")
        initial_docs = await graph_assertions.get_node_properties("DOCUMENTATION")

        initial_workflow_count = len(initial_workflows)
        initial_doc_count = len(initial_docs)

        # Modify file - add a new function
        file1.write_text(
            "def helper():\n"
            "    return 'help'\n"
            "\n"
            "def process():\n"
            "    return helper()\n"
            "\n"
            "def new_function():\n"
            "    return 'new'\n"
        )

        # Run incremental update WITH workflows and documentation
        updated_files = [UpdatedFile(path=str(file1))]
        builder.incremental_update(
            updated_files,
            save_to_db=True,
            create_workflows=True,
            create_documentation=True,
        )

        # Verify workflows and docs are NOT duplicated
        final_workflows = await graph_assertions.get_node_properties("WORKFLOW")
        final_docs = await graph_assertions.get_node_properties("DOCUMENTATION")

        assert len(final_workflows) == initial_workflow_count, (
            f"Workflows should not duplicate. Expected {initial_workflow_count}, "
            f"got {len(final_workflows)}"
        )

        assert len(final_docs) == initial_doc_count + 1, (
            f"Documentation should increase by 1 (for new_function). "
            f"Expected {initial_doc_count + 1}, got {len(final_docs)}"
        )

        # Verify the new function was added
        final_functions = await graph_assertions.get_node_properties("FUNCTION")
        function_names = {f["name"] for f in final_functions}
        assert "new_function" in function_names, "New function should be added"

        db_manager.close()