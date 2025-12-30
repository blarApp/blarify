"""
Integration tests for GraphBuilder incremental_update functionality.

These tests verify that incremental_update correctly updates only the specified files
without rebuilding the entire graph.
"""

import pytest
from pathlib import Path
from typing import Any, Dict, Optional, Callable, Union, Type
from unittest.mock import Mock, patch

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.project_graph_updater import UpdatedFile
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.agents.llm_provider import LLMProvider
from tests.utils.graph_assertions import GraphAssertions
from pydantic import BaseModel


def make_llm_mock(
    dumb_response: Union[str, Callable[[Dict[str, Any]], str]],
) -> Mock:
    """Create a Mock that only mocks LLMProvider.call_dumb_agent.

    - call_dumb_agent returns the provided static string or the result of the callable with input_dict.
    """
    m = Mock(spec=LLMProvider)

    if callable(dumb_response):

        def _side_effect(
            system_prompt: str,
            input_dict: Dict[str, Any],
            output_schema: Optional[Type[BaseModel]] = None,
            ai_model: Optional[str] = None,
            input_prompt: str = "Start",
            config: Optional[Dict[str, Any]] = None,
            timeout: Optional[int] = None,
        ) -> Any:
            return dumb_response(input_dict)

        m.call_dumb_agent.side_effect = _side_effect
    else:
        m.call_dumb_agent.return_value = dumb_response

    return m


@pytest.mark.asyncio  # type: ignore[misc]
@pytest.mark.neo4j_integration  # type: ignore[misc]
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
        initial_file.write_text("def initial_function():\n    return 'initial'\n")

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
        new_file.write_text("def added_function():\n    return 'added'\n")

        # Run incremental update for new file only
        updated_files = [UpdatedFile(path=str(new_file))]
        builder.incremental_update(updated_files, save_to_db=True)

        # Verify new file was added
        final_functions = await graph_assertions.get_node_properties("FUNCTION")

        assert (
            len(final_functions) == initial_function_count + 1
        ), f"Should have {initial_function_count + 1} functions after adding new file"

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
        target_file.write_text("def original_function():\n    return 'original'\n")

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
            "def original_function():\n    return 'original'\n\ndef new_function():\n    return 'new'\n"
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
        file2.write_text("from module1 import helper\n\ndef main():\n    return helper()\n")

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
        file3.write_text("from module1 import helper\n\ndef use_helper():\n    return helper()\n")

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
        file1.write_text("def helper():\n    return 'help'\n\ndef process():\n    return helper()\n")

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
            "def helper():\n    print(\"Helping\")\n    return 'help'\n\ndef process():\n    return helper()\n\n"
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

        assert (
            len(final_workflows) == initial_workflow_count
        ), f"Workflows should not duplicate. Expected {initial_workflow_count}, got {len(final_workflows)}"

        assert (
            len(final_docs) == initial_doc_count
        ), f"Documentation should not duplicate. Expected {initial_doc_count}, got {len(final_docs)}"

        # Verify the new code was added
        final_functions = await graph_assertions.get_node_properties("FUNCTION")
        function_contents = {f["text"] for f in final_functions}
        assert any('print("Helping")' in content for content in function_contents), "Modified code should be present"

        db_manager.close()

    async def test_incremental_update_updates_workflows_on_relationship_changes(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that incremental_update properly updates workflows when function relationships change."""
        # Create initial files with function calls
        file1 = temp_project_dir / "helpers.py"
        file1.write_text("def helper_a():\n    return 'a'\n\ndef helper_b():\n    return 'b'\n")

        file2 = temp_project_dir / "main.py"
        file2.write_text("from helpers import helper_a\n\ndef main():\n    return helper_a()\n")

        # Initialize database manager
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        # Build initial graph with workflows and documentation
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

        # Get initial workflow and documentation counts
        initial_workflows = await graph_assertions.get_node_properties("WORKFLOW")
        initial_docs = await graph_assertions.get_node_properties("DOCUMENTATION")
        initial_workflow_count = len(initial_workflows)
        initial_doc_count = len(initial_docs)

        # Verify initial state has functions
        initial_functions = await graph_assertions.get_node_properties("FUNCTION")
        initial_function_names = {f["name"] for f in initial_functions}
        assert "main" in initial_function_names
        assert "helper_a" in initial_function_names
        assert "helper_b" in initial_function_names

        # Modify main.py to call helper_b instead of helper_a
        file2.write_text("from helpers import helper_b\n\ndef main():\n    return helper_b()\n")

        # Run incremental update with workflows and documentation
        updated_files = [UpdatedFile(path=str(file2))]
        builder.incremental_update(
            updated_files,
            save_to_db=True,
            create_workflows=True,
            create_documentation=True,
        )

        # Verify workflows were updated (count should remain same, content should change)
        final_workflows = await graph_assertions.get_node_properties("WORKFLOW")
        assert (
            len(final_workflows) == initial_workflow_count
        ), f"Workflow count should remain the same. Expected {initial_workflow_count}, got {len(final_workflows)}"

        # Verify documentation for main function was updated (count should remain same)
        final_docs = await graph_assertions.get_node_properties("DOCUMENTATION")
        assert len(final_docs) == initial_doc_count, (
            f"Documentation count should remain the same since no functions were added/removed. "
            f"Expected {initial_doc_count}, got {len(final_docs)}"
        )

        # Verify the function still exists
        final_functions = await graph_assertions.get_node_properties("FUNCTION")
        final_function_names = {f["name"] for f in final_functions}
        assert "main" in final_function_names, "main function should still exist"
        assert "helper_a" in final_function_names, "helper_a should still exist"
        assert "helper_b" in final_function_names, "helper_b should still exist"

        db_manager.close()

    async def test_incremental_update_updates_caller_workflows_when_file_changes(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that incremental_update updates workflows for both modified file AND its callers."""
        # Create file A with helper function
        file_a = temp_project_dir / "helpers.py"
        file_a.write_text("def helper_a():\n    '''Original helper function'''\n    return 'a'\n")

        # Create file B with main that calls helper_a
        file_b = temp_project_dir / "main.py"
        file_b.write_text(
            "from helpers import helper_a\n"
            "\n"
            "def main():\n"
            "    '''Main function that calls helper_a'''\n"
            "    return helper_a()\n"
        )

        # Initialize database manager
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        # Build initial graph with workflows
        builder = GraphBuilder(
            root_path=str(temp_project_dir),
            db_manager=db_manager,
            generate_embeddings=False,
        )
        builder.build(
            save_to_db=True,
            create_workflows=True,
            create_documentation=False,
        )

        # Verify initial state
        initial_workflows = await graph_assertions.get_node_properties("WORKFLOW")
        initial_workflow_count = len(initial_workflows)
        initial_functions = await graph_assertions.get_node_properties("FUNCTION")
        initial_function_names = {f["name"] for f in initial_functions}

        assert "main" in initial_function_names, "main should exist initially"
        assert "helper_a" in initial_function_names, "helper_a should exist initially"

        # Modify file A: change helper_a implementation
        file_a.write_text(
            "def helper_a():\n    '''Modified helper function with new implementation'''\n    return 'a_modified'\n"
        )

        # Run incremental update for file A with workflows
        updated_files = [UpdatedFile(path=str(file_a))]
        builder.incremental_update(
            updated_files,
            save_to_db=True,
            create_workflows=True,
            create_documentation=False,
        )

        # Verify final state
        final_workflows = await graph_assertions.get_node_properties("WORKFLOW")
        final_functions = await graph_assertions.get_node_properties("FUNCTION")
        final_function_names = {f["name"] for f in final_functions}

        # Check both functions still exist
        assert "helper_a" in final_function_names, "helper_a should exist after update"
        assert "main" in final_function_names, "main should still exist after update"

        # KEY ASSERTION: Verify workflows were created for both the modified function AND its caller
        assert (
            len(final_workflows) >= initial_workflow_count
        ), f"Should have at least {initial_workflow_count} workflows after update, got {len(final_workflows)}"

        # Get final node IDs to verify workflows reference them
        final_helper_a = [f for f in final_functions if f["name"] == "helper_a"][0]
        final_main = [f for f in final_functions if f["name"] == "main"][0]

        # Verify workflows exist for both functions
        workflow_contains_helper_a = False
        workflow_contains_main = False

        for workflow in final_workflows:
            workflow_scope = "workflow_id:" + workflow["node_id"]

            step_records = await test_data_isolation["container"].execute_cypher(
                """
                MATCH (source:NODE)-[r:WORKFLOW_STEP]->(target:NODE)
                WHERE r.scopeText CONTAINS $workflow_scope
                RETURN source.node_id AS source_id,
                       target.node_id AS target_id,
                       coalesce(r.step_order, r.depth, 0) AS order
                ORDER BY order
                """,
                parameters={"workflow_scope": workflow_scope},
            )

            node_ids: list[str] = []

            for record in step_records:
                source_id = record.get("source_id")
                target_id = record.get("target_id")

                if source_id and source_id not in node_ids:
                    node_ids.append(source_id)
                if target_id and target_id not in node_ids:
                    node_ids.append(target_id)

            if final_helper_a["node_id"] in node_ids:
                workflow_contains_helper_a = True
            if final_main["node_id"] in node_ids:
                workflow_contains_main = True

        assert workflow_contains_helper_a, "Workflows should include helper_a (modified function)"
        assert workflow_contains_main, "Workflows should include main (caller of modified function)"

        db_manager.close()

    async def test_incremental_update_documents_complete_hierarchy_when_file_changes(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """
        Test that incremental_update documents the COMPLETE hierarchical context.

        When updating a file, should document:
        - The modified file itself
        - All classes in the file (even if not all are called)
        - All methods in those classes (even if not all are called)

        This ensures complete hierarchical context, not just execution path.
        """
        # Create helpers.py with Helper class containing TWO methods
        helpers_file = temp_project_dir / "helpers.py"
        helpers_file.write_text(
            "class Helper:\n"
            "    def validate(self, data):\n"
            "        '''Validates data'''\n"
            "        return True\n"
            "\n"
            "    def format(self, data):\n"
            "        '''Formats data'''\n"
            "        return str(data)\n"
        )

        # Create main.py that ONLY calls validate() - NOT format()
        main_file = temp_project_dir / "main.py"
        main_file.write_text(
            "from helpers import Helper\n"
            "\n"
            "def main():\n"
            "    '''Main function that uses Helper'''\n"
            "    helper = Helper()\n"
            "    return helper.validate({})\n"
        )

        # Create an unrelated file that should not be part of the documentation refresh
        unrelated_file = temp_project_dir / "standalone.py"
        unrelated_file.write_text("def standalone():\n    return 'detached'\n")

        # Initialize database manager
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        response_prefix: Dict[str, str] = {"value": "Initial"}

        def node_specific_doc(input_dict: Dict[str, Any]) -> str:
            node_name = input_dict.get("node_name") or input_dict.get("node_path") or "unknown"
            return f"{response_prefix['value']} documentation for {node_name}"

        llm_provider = make_llm_mock(dumb_response=node_specific_doc)

        try:
            with (
                patch("blarify.prebuilt.graph_builder.LLMProvider", return_value=llm_provider),
                patch(
                    "blarify.documentation.documentation_creator.LLMProvider",
                    return_value=llm_provider,
                ),
            ):
                builder = GraphBuilder(
                    root_path=str(temp_project_dir),
                    db_manager=db_manager,
                    generate_embeddings=False,
                )

                builder.build(
                    save_to_db=True,
                    create_workflows=False,
                    create_documentation=True,
                )

                # Clear any documentation calls recorded during the initial build
                llm_provider.call_dumb_agent.reset_mock()

                # Modify helpers.py: change validate() implementation
                helpers_file.write_text(
                    "class Helper:\n"
                    "    def validate(self, data):\n"
                    "        '''Modified validation with enhanced checks'''\n"
                    "        if not data:\n"
                    "            return False\n"
                    "        return True\n"
                    "\n"
                    "    def format(self, data):\n"
                    "        '''Formats data'''\n"
                    "        return str(data)\n"
                )

                # Record that subsequent documentation should be marked as updated
                response_prefix["value"] = "Updated"

                # Run incremental update targeting ONLY helpers.py
                updated_files = [UpdatedFile(path=str(helpers_file))]
                builder.incremental_update(
                    updated_files,
                    save_to_db=True,
                    create_workflows=False,
                    create_documentation=True,
                )

                # Fetch nodes for verification
                final_functions = await graph_assertions.get_node_properties("FUNCTION")
                function_nodes = {f["name"]: f for f in final_functions}

                validate_node = function_nodes.get("validate")
                format_node = function_nodes.get("format")
                main_node = function_nodes.get("main")

                assert validate_node is not None, "validate function missing after update"
                assert format_node is not None, "format function missing after update"
                assert main_node is not None, "main function missing after update"

                final_classes = await graph_assertions.get_node_properties("CLASS")
                helper_class = next((c for c in final_classes if c["name"] == "Helper"), None)
                assert helper_class is not None, "Helper class missing after update"

                final_files = await graph_assertions.get_node_properties("FILE")
                helpers_file_node = next(
                    (f for f in final_files if f.get("name") == "helpers.py" or "helpers.py" in f.get("path", "")),
                    None,
                )
                assert helpers_file_node is not None, "helpers.py file node missing after update"

                # Confirm documentation requests were issued for the execution chain and hierarchy nodes
                documented_nodes: list[str] = []
                documented_payloads: list[dict[str, Any]] = []
                for call in llm_provider.call_dumb_agent.call_args_list:
                    input_dict = call.kwargs.get("input_dict") if call.kwargs else None
                    if input_dict is None and len(call.args) > 1:
                        input_dict = call.args[1]
                    if not isinstance(input_dict, dict):
                        continue
                    node_name = input_dict.get("node_name") or input_dict.get("node_path")
                    if node_name:
                        documented_nodes.append(str(node_name))
                    documented_payloads.append(
                        {
                            "node_name": input_dict.get("node_name"),
                            "node_path": input_dict.get("node_path"),
                            "node_labels": input_dict.get("node_labels"),
                        }
                    )

                expected_node_labels = ["helpers.py", "Helper", "validate", "format", "main"]
                documented_summary = ", ".join(documented_nodes)
                for label in expected_node_labels:
                    assert label in documented_nodes, (
                        f"Expected documentation request for '{label}', got calls for: {documented_summary}."
                        f" Payloads: {documented_payloads}"
                    )

                unexpected_node_tokens = ["standalone", "standalone.py"]
                for token in unexpected_node_tokens:
                    assert not any(
                        token in node for node in documented_nodes
                    ), f"Documentation should not run for '{token}', but calls included: {documented_summary}"

                async def assert_documentation_exists(node_id: str, expected_label: str) -> None:
                    docs = await test_data_isolation["container"].execute_cypher(
                        """
                        MATCH (doc:DOCUMENTATION)-[:DESCRIBES]->(n:NODE {node_id: $node_id})
                        RETURN doc.content as content
                        """,
                        parameters={"node_id": node_id},
                    )
                    assert docs, f"Expected documentation records for {expected_label}"

                await assert_documentation_exists(validate_node["node_id"], "validate")
                await assert_documentation_exists(format_node["node_id"], "format")
                await assert_documentation_exists(helper_class["node_id"], "Helper")
                await assert_documentation_exists(helpers_file_node["node_id"], "helpers.py")
                await assert_documentation_exists(main_node["node_id"], "main")

        finally:
            db_manager.close()

    async def test_incremental_update_deletes_old_workflows_and_edges(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that incremental_update deletes old workflow nodes and WORKFLOW_STEP edges."""
        # Create initial files with function calls
        file1 = temp_project_dir / "helpers.py"
        file1.write_text("def helper_a():\n    return 'a'\n\ndef helper_b():\n    return 'b'\n")

        file2 = temp_project_dir / "main.py"
        file2.write_text("from helpers import helper_a\n\ndef main():\n    return helper_a()\n")

        # Initialize database manager
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        # Build initial graph with workflows
        builder = GraphBuilder(
            root_path=str(temp_project_dir),
            db_manager=db_manager,
            generate_embeddings=False,
        )
        builder.build(
            save_to_db=True,
            create_workflows=True,
            create_documentation=False,
        )

        # Get initial workflow nodes
        initial_workflows = await graph_assertions.get_node_properties("WORKFLOW")
        assert len(initial_workflows) > 0, "Should have workflows after initial build"

        # Find workflows related to main.py (entry point for main function)
        # These are the ones that should be deleted on incremental update
        main_related_workflows = [w for w in initial_workflows if "main" in w.get("entry_point_name", "").lower()]
        assert len(main_related_workflows) > 0, "Should have at least one workflow for main entry point"

        main_workflow_ids = {w["node_id"] for w in main_related_workflows}

        # Get initial WORKFLOW_STEP relationships for main's workflows
        initial_main_workflow_steps = await test_data_isolation["container"].execute_cypher(
            """
            MATCH (w:NODE {layer: 'workflows'})
            WHERE w.node_id IN $workflow_ids
            MATCH ()-[r:WORKFLOW_STEP]->()
            WHERE r.scopeText CONTAINS ('workflow_id:' + w.node_id)
            RETURN r.scopeText as scope_text, elementId(r) as edge_id, w.node_id as workflow_id
            """,
            parameters={"workflow_ids": list(main_workflow_ids)},
        )
        initial_main_step_edge_ids = {step["edge_id"] for step in initial_main_workflow_steps}
        assert len(initial_main_step_edge_ids) > 0, "Should have WORKFLOW_STEP relationships for main"

        # Modify main.py to change the call pattern (call helper_b instead)
        file2.write_text("from helpers import helper_b\n\ndef main():\n    return helper_b()\n")

        # Run incremental update with workflows
        updated_files = [UpdatedFile(path=str(file2))]
        builder.incremental_update(
            updated_files,
            save_to_db=True,
            create_workflows=True,
            create_documentation=False,
        )

        # Verify old main-related workflow nodes were deleted
        final_workflows = await graph_assertions.get_node_properties("WORKFLOW")
        final_workflow_ids = {w["node_id"] for w in final_workflows}

        # Check that old main workflow IDs are not present
        for old_id in main_workflow_ids:
            assert old_id not in final_workflow_ids, f"Old workflow node {old_id} for main should have been deleted"

        # Verify new workflows were created (should have at least one for the updated main)
        new_main_workflows = [w for w in final_workflows if "main" in w.get("entry_point_name", "").lower()]
        assert len(new_main_workflows) > 0, "Should have new workflow for main after update"

        # Verify old WORKFLOW_STEP relationships for main were deleted
        final_all_workflow_steps = await test_data_isolation["container"].execute_cypher(
            """
            MATCH ()-[r:WORKFLOW_STEP]->()
            RETURN r.scopeText as scope_text, elementId(r) as edge_id
            """,
            parameters={},
        )
        final_all_edge_ids = {step["edge_id"] for step in final_all_workflow_steps}

        # Check that old main-related edge IDs are not present
        for old_edge_id in initial_main_step_edge_ids:
            assert (
                old_edge_id not in final_all_edge_ids
            ), f"Old WORKFLOW_STEP edge {old_edge_id} for main should have been deleted"

        db_manager.close()

    async def test_incremental_update_cleans_up_orphaned_documentation(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """Test that incremental_update deletes orphaned documentation after code changes."""
        # Create initial file
        file1 = temp_project_dir / "module.py"
        file1.write_text("def old_function():\n    return 'old'\n")

        # Initialize database manager
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        # Build initial graph with documentation
        builder = GraphBuilder(
            root_path=str(temp_project_dir),
            db_manager=db_manager,
            generate_embeddings=False,
        )
        builder.build(
            save_to_db=True,
            create_workflows=False,
            create_documentation=True,
        )

        # Get initial documentation count
        initial_docs = await graph_assertions.get_node_properties("DOCUMENTATION")
        initial_doc_count = len(initial_docs)
        assert initial_doc_count > 0, "Should have documentation after initial build"

        # Verify documentation has DESCRIBES relationship
        docs_with_describes = await test_data_isolation["container"].execute_cypher(
            """
            MATCH (doc:DOCUMENTATION)-[:DESCRIBES]->()
            RETURN count(doc) as count
            """,
            parameters={},
        )
        assert docs_with_describes[0]["count"] == initial_doc_count, "All docs should have DESCRIBES"

        # Completely replace file content (deletes old_function, adds new_function)
        file1.write_text("def new_function():\n    return 'new'\n")

        # Run incremental update with documentation
        updated_files = [UpdatedFile(path=str(file1))]
        builder.incremental_update(
            updated_files,
            save_to_db=True,
            create_workflows=False,
            create_documentation=True,
        )

        # Verify orphaned documentation was cleaned up
        orphaned_docs = await test_data_isolation["container"].execute_cypher(
            """
            MATCH (doc:DOCUMENTATION)
            WHERE NOT (doc)-[:DESCRIBES]->()
            RETURN count(doc) as orphan_count
            """,
            parameters={},
        )
        assert orphaned_docs[0]["orphan_count"] == 0, "Should have no orphaned documentation nodes"

        # Verify new documentation exists
        final_docs = await graph_assertions.get_node_properties("DOCUMENTATION")
        assert len(final_docs) > 0, "Should have documentation after update"

        # Verify all documentation has DESCRIBES relationship
        docs_with_describes_final = await test_data_isolation["container"].execute_cypher(
            """
            MATCH (doc:DOCUMENTATION)-[:DESCRIBES]->()
            RETURN count(doc) as count
            """,
            parameters={},
        )
        assert docs_with_describes_final[0]["count"] == len(final_docs), "All docs should have DESCRIBES after cleanup"

        db_manager.close()

    async def test_incremental_update_redocuments_affected_nodes(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """
        Test that incremental_update re-documents affected nodes:
        - All nodes inside changed file (hierarchy)
        - Direct callers of changed nodes (1 level only)
        - Parent folders

        And does NOT re-document nodes 2+ levels away.

        Uses simple_linear workflow: main() → process_data() → transform_value()
        """
        import shutil

        # Copy simple_linear workflow to temp dir
        src_dir = test_code_examples_path / "workflows" / "simple_linear"
        for file_name in ["main.py", "processor.py", "utils.py", "__init__.py"]:
            shutil.copy(src_dir / file_name, temp_project_dir / file_name)

        response_prefix: Dict[str, str] = {"value": "Initial"}

        def node_specific_doc(input_dict: Dict[str, Any]) -> str:
            node_name = input_dict.get("node_name") or input_dict.get("node_path") or "unknown"
            return f"{response_prefix['value']} doc for {node_name}"

        llm_provider = make_llm_mock(dumb_response=node_specific_doc)

        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            repo_id=test_data_isolation["repo_id"],
            entity_id=test_data_isolation["entity_id"],
        )

        try:
            with (
                patch("blarify.prebuilt.graph_builder.LLMProvider", return_value=llm_provider),
                patch(
                    "blarify.documentation.documentation_creator.LLMProvider",
                    return_value=llm_provider,
                ),
            ):
                builder = GraphBuilder(
                    root_path=str(temp_project_dir),
                    db_manager=db_manager,
                    generate_embeddings=False,
                )

                builder.build(
                    save_to_db=True,
                    create_workflows=False,
                    create_documentation=True,
                )

                # Verify initial docs were created for all nodes
                async def get_doc_content(node_name: str) -> str:
                    docs = await test_data_isolation["container"].execute_cypher(
                        """
                        MATCH (doc:DOCUMENTATION)-[:DESCRIBES]->(n:NODE)
                        WHERE n.name = $name
                        RETURN doc.content as content
                        """,
                        parameters={"name": node_name},
                    )
                    return docs[0]["content"] if docs else ""

                # Verify initial state - all should have "Initial"
                for node_name in ["transform_value", "process_data", "main"]:
                    content = await get_doc_content(node_name)
                    assert "Initial" in content, f"{node_name} should have Initial doc before update"

                # Change mock to return "Updated"
                response_prefix["value"] = "Updated"

                # Modify utils.py (leaf node in call chain)
                utils_file = temp_project_dir / "utils.py"
                utils_file.write_text(
                    '"""Utility functions for the workflow."""\n\n'
                    "def transform_value(value: int) -> int:\n"
                    '    """Transform a value by tripling it."""\n'
                    "    return value * 3\n"
                )

                # Run incremental update targeting utils.py
                updated_files = [UpdatedFile(path=str(utils_file))]
                builder.incremental_update(
                    updated_files,
                    save_to_db=True,
                    create_workflows=False,
                    create_documentation=True,
                )

                # ASSERT: Changed file nodes → "Updated"
                transform_content = await get_doc_content("transform_value")
                assert "Updated" in transform_content, "transform_value (changed file) should have Updated doc"

                # ASSERT: Direct caller (1 level) → "Updated"
                process_data_content = await get_doc_content("process_data")
                assert "Updated" in process_data_content, "process_data (direct caller) should have Updated doc"

                # ASSERT: 2 levels away → still "Initial" (NOT updated)
                main_content = await get_doc_content("main")
                assert "Initial" in main_content, (
                    "main() (2 levels away) should NOT be re-documented. " f"Got: {main_content}"
                )

        finally:
            db_manager.close()
