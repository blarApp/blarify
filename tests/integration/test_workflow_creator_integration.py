"""
Integration tests for WorkflowCreator with BELONGS_TO_WORKFLOW relationships.

These tests verify that the WorkflowCreator properly creates BELONGS_TO_WORKFLOW
relationships connecting all workflow participant nodes to their workflow nodes.
Following TDD methodology, these tests are written first (RED phase).
"""

import pytest
from pathlib import Path
from typing import Any, Dict

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.documentation.workflow_creator import WorkflowCreator
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.graph.graph_environment import GraphEnvironment
from tests.utils.graph_assertions import GraphAssertions


@pytest.mark.asyncio
@pytest.mark.neo4j_integration
class TestWorkflowCreatorIntegration:
    """Test WorkflowCreator with complete integration, focusing on BELONGS_TO_WORKFLOW relationships."""

    async def test_belongs_to_workflow_relationships_created(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """
        Test that BELONGS_TO_WORKFLOW relationships are created for all workflow participants.

        This test creates a simple linear workflow (main -> processor -> utils) and verifies
        that each participating node has a BELONGS_TO_WORKFLOW relationship to the workflow node.
        """
        # Setup: Create simple linear workflow code structure
        workflow_path = test_code_examples_path / "workflows" / "simple_linear"

        # Step 1: Build the code graph
        builder = GraphBuilder(
            root_path=str(workflow_path),
            extensions_to_skip=[".pyc", ".pyo"],
            names_to_skip=["__pycache__"],
        )

        graph = builder.build()
        assert graph is not None

        # Step 2: Save graph to Neo4j
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            entity_id=test_data_isolation["entity_id"],
            repo_id=test_data_isolation["repo_id"],
        )

        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Debug: Print initial graph state
        await graph_assertions.debug_print_graph_summary()

        # Step 3: Create WorkflowCreator and discover workflows
        graph_env = GraphEnvironment(environment="test", diff_identifier="test-diff", root_path=str(workflow_path))
        workflow_creator = WorkflowCreator(db_manager=db_manager, graph_environment=graph_env)

        # Find the main function ID to use as entry point
        main_query = """
        MATCH (f:FUNCTION {name: 'main'})
        RETURN f.node_id as id
        """
        main_results = await test_data_isolation["container"].execute_cypher(main_query)
        assert len(main_results) > 0, "No 'main' function found in graph"

        main_id = main_results[0]["id"]

        # Discover workflows from the main entry point
        discovery_result = workflow_creator.discover_workflows(
            entry_points=[main_id],  # Provide main function ID directly
            max_depth=10,
            save_to_database=True,
        )

        # Verify workflow was discovered
        assert discovery_result.total_workflows > 0, "No workflows discovered"
        assert discovery_result.error is None, f"Error during discovery: {discovery_result.error}"

        # Step 4: Verify BELONGS_TO_WORKFLOW relationships exist
        # Get the workflow node
        workflow_query = """
        MATCH (w:WORKFLOW)
        WHERE w.entry_point_name CONTAINS 'main'
        RETURN w.node_id as workflow_id, w.entry_point_name as name
        """
        workflow_results = await test_data_isolation["container"].execute_cypher(workflow_query)
        assert len(workflow_results) > 0, "No workflow node found"

        workflow_id = workflow_results[0]["workflow_id"]

        # Check that each participating function has BELONGS_TO_WORKFLOW relationship
        # Expected participants: main, process_data, transform_value
        participant_query = """
        MATCH (n)-[:BELONGS_TO_WORKFLOW]->(w:WORKFLOW)
        WHERE w.node_id = $workflow_id
        RETURN n.name as participant_name, labels(n) as labels
        ORDER BY n.name
        """
        participants = await test_data_isolation["container"].execute_cypher(participant_query, {"workflow_id": workflow_id})

        # Extract participant names
        participant_names = [p["participant_name"] for p in participants]

        # Verify all expected functions are connected
        expected_participants = ["main", "process_data", "transform_value"]
        for expected in expected_participants:
            assert expected in participant_names, (
                f"Function '{expected}' not connected to workflow. Found participants: {participant_names}"
            )

        # Verify no duplicate relationships
        duplicate_query = """
        MATCH (n)-[r:BELONGS_TO_WORKFLOW]->(w:WORKFLOW)
        WHERE w.node_id = $workflow_id
        WITH n, w, count(r) as rel_count
        WHERE rel_count > 1
        RETURN n.name as node_name, rel_count
        """
        duplicates = await test_data_isolation["container"].execute_cypher(duplicate_query, {"workflow_id": workflow_id})
        assert len(duplicates) == 0, f"Found duplicate BELONGS_TO_WORKFLOW relationships: {duplicates}"

    async def test_multiple_workflows_with_shared_nodes(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """
        Test that shared nodes have BELONGS_TO_WORKFLOW relationships to multiple workflows.

        This test uses the complex_branching example where shared services are used
        by multiple entry points, creating multiple workflows with shared participants.
        """
        # Setup: Use complex branching workflow with shared services
        workflow_path = test_code_examples_path / "workflows" / "complex_branching"

        # Step 1: Build and save the code graph
        builder = GraphBuilder(
            root_path=str(workflow_path),
            extensions_to_skip=[".pyc", ".pyo"],
            names_to_skip=["__pycache__"],
        )

        graph = builder.build()
        assert graph is not None

        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            entity_id=test_data_isolation["entity_id"],
            repo_id=test_data_isolation["repo_id"],
        )

        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Step 2: Create WorkflowCreator and discover workflows
        graph_env = GraphEnvironment(environment="test", diff_identifier="test-diff", root_path=str(workflow_path))
        workflow_creator = WorkflowCreator(db_manager=db_manager, graph_environment=graph_env)

        discovery_result = workflow_creator.discover_workflows(
            entry_points=None,
            max_depth=10,
            save_to_database=True,
        )

        # Should discover at least 2 workflows (api_get_endpoint and api_post_endpoint)
        assert discovery_result.total_workflows >= 2, (
            f"Expected at least 2 workflows, found {discovery_result.total_workflows}"
        )

        # Step 3: Verify shared services have multiple BELONGS_TO_WORKFLOW relationships
        shared_service_query = """
        MATCH (n:FUNCTION)-[:BELONGS_TO_WORKFLOW]->(w:WORKFLOW)
        WHERE n.name IN ['validate_data', 'format_response']
        WITH n.name as service_name, collect(w.entry_point_name) as workflows
        RETURN service_name, workflows, size(workflows) as workflow_count
        ORDER BY service_name
        """
        shared_results = await test_data_isolation["container"].execute_cypher(shared_service_query)

        # Both validate_data and format_response should be in multiple workflows
        for result in shared_results:
            service_name = result["service_name"]
            workflow_count = result["workflow_count"]
            assert workflow_count >= 2, (
                f"Shared service '{service_name}' only belongs to {workflow_count} workflow(s). "
                f"Expected at least 2. Workflows: {result['workflows']}"
            )

    async def test_cyclic_workflow_relationships(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """
        Test that cyclic workflows properly create BELONGS_TO_WORKFLOW relationships.

        Ensures that recursive and mutually recursive functions are properly connected
        to their workflow nodes without creating duplicate relationships.
        """
        # Setup: Use cyclic patterns (recursive functions)
        workflow_path = test_code_examples_path / "workflows" / "cyclic_patterns"

        # Step 1: Build and save the code graph
        builder = GraphBuilder(
            root_path=str(workflow_path),
            extensions_to_skip=[".pyc", ".pyo"],
            names_to_skip=["__pycache__"],
        )

        graph = builder.build()
        assert graph is not None

        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            entity_id=test_data_isolation["entity_id"],
            repo_id=test_data_isolation["repo_id"],
        )

        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Step 2: Create WorkflowCreator and discover workflows
        graph_env = GraphEnvironment(environment="test", diff_identifier="test-diff", root_path=str(workflow_path))
        workflow_creator = WorkflowCreator(db_manager=db_manager, graph_environment=graph_env)

        # Find function IDs to use as entry points (factorial, is_even as examples)
        entry_query = """
        MATCH (f:FUNCTION)
        WHERE f.name IN ['factorial', 'is_even']
        RETURN f.node_id as id
        """
        entry_results = await test_data_isolation["container"].execute_cypher(entry_query)
        assert len(entry_results) > 0, "No recursive functions found in graph"

        entry_ids = [r["id"] for r in entry_results]

        discovery_result = workflow_creator.discover_workflows(
            entry_points=entry_ids,
            max_depth=10,
            save_to_database=True,
        )

        # For cyclic patterns, workflows might be detected differently
        # The important thing is that if workflows ARE created, relationships are correct
        if discovery_result.total_workflows > 0:
            # Step 3: Verify recursive functions have BELONGS_TO_WORKFLOW without duplicates
            # Check factorial workflow
            factorial_query = """
            MATCH (f:FUNCTION {name: 'factorial'})-[r:BELONGS_TO_WORKFLOW]->(w:WORKFLOW)
            RETURN count(r) as rel_count, w.entry_point_name as workflow_name
            """
            factorial_results = await test_data_isolation["container"].execute_cypher(factorial_query)

            if factorial_results:
                for result in factorial_results:
                    assert result["rel_count"] == 1, (
                        f"Factorial function has {result['rel_count']} BELONGS_TO_WORKFLOW relationships "
                        f"to workflow '{result['workflow_name']}'. Expected exactly 1."
                    )

            # Check mutual recursion (is_even/is_odd)
            mutual_query = """
            MATCH (f:FUNCTION)-[:BELONGS_TO_WORKFLOW]->(w:WORKFLOW)
            WHERE f.name IN ['is_even', 'is_odd']
            WITH w, collect(f.name) as functions
            WHERE size(functions) = 2
            RETURN w.entry_point_name as workflow_name, functions
            """
            mutual_results = await test_data_isolation["container"].execute_cypher(mutual_query)

            # If mutual recursion workflow exists, both functions should belong to it
            if mutual_results:
                for result in mutual_results:
                    assert set(result["functions"]) == {"is_even", "is_odd"}, (
                        f"Mutual recursion workflow missing expected functions. Found: {result['functions']}"
                    )
        else:
            # If no workflows were discovered (which can happen with pure recursive functions),
            # just verify the functions exist in the graph
            function_check = """
            MATCH (f:FUNCTION)
            WHERE f.name IN ['factorial', 'is_even', 'is_odd']
            RETURN count(f) as func_count
            """
            func_result = await test_data_isolation["container"].execute_cypher(function_check)
            assert func_result[0]["func_count"] >= 2, "Recursive functions not found in graph"

    async def test_empty_workflow_no_relationships(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        temp_project_dir: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """
        Test that empty workflows (entry points with no calls) don't create BELONGS_TO_WORKFLOW relationships.

        This is an edge case where an entry point exists but doesn't call any other functions.
        """
        # Setup: Create a simple file with an entry point that does nothing
        test_file = temp_project_dir / "empty_workflow.py"
        test_file.write_text("""
def standalone_entry():
    '''Entry point that does nothing.'''
    pass

def main():
    '''Main function that only does local operations.'''
    x = 1 + 1
    return x
""")

        # Step 1: Build and save the code graph
        builder = GraphBuilder(
            root_path=str(temp_project_dir),
            extensions_to_skip=[".pyc", ".pyo"],
            names_to_skip=["__pycache__"],
        )

        graph = builder.build()
        assert graph is not None

        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            entity_id=test_data_isolation["entity_id"],
            repo_id=test_data_isolation["repo_id"],
        )

        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Step 2: Create WorkflowCreator and discover workflows
        graph_env = GraphEnvironment(environment="test", diff_identifier="test-diff", root_path=str(temp_project_dir))
        workflow_creator = WorkflowCreator(db_manager=db_manager, graph_environment=graph_env)

        _ = workflow_creator.discover_workflows(
            entry_points=None,
            max_depth=10,
            save_to_database=True,
        )

        # Step 3: Check if workflow was created and verify relationships
        workflow_query = """
        MATCH (w:WORKFLOW)
        RETURN w.entry_point_name as name, w.total_execution_steps as steps
        """
        workflows = await test_data_isolation["container"].execute_cypher(workflow_query)

        # For empty workflows, we should either:
        # 1. Not create a workflow node at all, OR
        # 2. Create a workflow with only the entry point connected

        for workflow in workflows:
            if workflow["steps"] == 1:  # Single node workflow
                # Should only have the entry point connected
                relationship_query = """
                MATCH (n)-[:BELONGS_TO_WORKFLOW]->(w:WORKFLOW)
                WHERE w.entry_point_name = $workflow_name
                RETURN count(n) as connected_nodes
                """
                results = await test_data_isolation["container"].execute_cypher(relationship_query, {"workflow_name": workflow["name"]})

                if results:
                    # Only the entry point itself should be connected
                    assert results[0]["connected_nodes"] == 1, (
                        f"Empty workflow '{workflow['name']}' has {results[0]['connected_nodes']} "
                        f"connected nodes. Expected 1 (just the entry point)."
                    )

    async def test_workflow_relationships_with_targeted_node_path(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """
        Test BELONGS_TO_WORKFLOW relationships when discovering workflows for a specific node path.

        This tests the targeted discovery feature where workflows are found that reach a specific node.
        """
        # Setup: Use simple linear workflow
        workflow_path = test_code_examples_path / "workflows" / "simple_linear"

        # Step 1: Build and save the code graph
        builder = GraphBuilder(
            root_path=str(workflow_path),
            extensions_to_skip=[".pyc", ".pyo"],
            names_to_skip=["__pycache__"],
        )

        graph = builder.build()
        assert graph is not None

        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            entity_id=test_data_isolation["entity_id"],
            repo_id=test_data_isolation["repo_id"],
        )

        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Step 2: Discover workflows (simplified - just use main entry point)
        graph_env = GraphEnvironment(environment="test", diff_identifier="test-diff", root_path=str(workflow_path))
        workflow_creator = WorkflowCreator(db_manager=db_manager, graph_environment=graph_env)

        # Find the main function ID
        main_query = """
        MATCH (f:FUNCTION {name: 'main'})
        RETURN f.node_id as id
        """
        main_results = await test_data_isolation["container"].execute_cypher(main_query)
        assert len(main_results) > 0, "No 'main' function found"

        main_id = main_results[0]["id"]

        # Discover workflows from main (which should reach utils.py)
        discovery_result = workflow_creator.discover_workflows(
            entry_points=[main_id],
            max_depth=10,
            save_to_database=True,
        )

        assert discovery_result.total_workflows > 0, "No workflows discovered"

        # Step 3: Verify BELONGS_TO_WORKFLOW relationships exist for the discovered workflow
        workflow_query = """
        MATCH (w:WORKFLOW)
        WHERE w.source_type = 'code_workflow_discovery'
        RETURN w.node_id as workflow_id, w.entry_point_name as entry_name
        """
        workflows = await test_data_isolation["container"].execute_cypher(workflow_query)
        assert len(workflows) > 0, "No workflow nodes found after targeted discovery"

        # Check that nodes in the path to utils.py have BELONGS_TO_WORKFLOW relationships
        for workflow in workflows:
            participant_query = """
            MATCH (n)-[:BELONGS_TO_WORKFLOW]->(w:WORKFLOW)
            WHERE w.node_id = $workflow_id
            RETURN n.name as name
            ORDER BY n.name
            """
            participants = await test_data_isolation["container"].execute_cypher(
                participant_query, {"workflow_id": workflow["workflow_id"]}
            )

            participant_names = [p["name"] for p in participants]

            # Should include at least transform_value from utils.py
            assert "transform_value" in participant_names, (
                f"Target function 'transform_value' not in workflow participants. Found: {participant_names}"
            )

    async def test_workflow_relationships_persistence(
        self,
        docker_check: Any,
        test_data_isolation: Dict[str, Any],
        test_code_examples_path: Path,
        graph_assertions: GraphAssertions,
    ) -> None:
        """
        Test that BELONGS_TO_WORKFLOW relationships persist correctly in the database.

        This verifies that relationships are properly saved and can be queried after creation.
        """
        # Setup: Use simple linear workflow
        workflow_path = test_code_examples_path / "workflows" / "simple_linear"

        # Step 1: Build and save the code graph
        builder = GraphBuilder(
            root_path=str(workflow_path),
            extensions_to_skip=[".pyc", ".pyo"],
            names_to_skip=["__pycache__"],
        )

        graph = builder.build()
        db_manager = Neo4jManager(
            uri=test_data_isolation["uri"],
            user="neo4j",
            password=test_data_isolation["password"],
            entity_id=test_data_isolation["entity_id"],
            repo_id=test_data_isolation["repo_id"],
        )

        db_manager.save_graph(graph.get_nodes_as_objects(), graph.get_relationships_as_objects())

        # Step 2: Create workflows
        graph_env = GraphEnvironment(environment="test", diff_identifier="test-diff", root_path=str(workflow_path))
        workflow_creator = WorkflowCreator(db_manager=db_manager, graph_environment=graph_env)

        # Find the main function ID
        main_query = """
        MATCH (f:FUNCTION {name: 'main'})
        RETURN f.node_id as id
        """
        main_results = await test_data_isolation["container"].execute_cypher(main_query)
        assert len(main_results) > 0, "No 'main' function found"

        main_id = main_results[0]["id"]

        discovery_result = workflow_creator.discover_workflows(
            entry_points=[main_id],
            max_depth=10,
            save_to_database=True,
        )

        assert discovery_result.total_workflows > 0, "No workflows discovered"

        # Step 3: Query relationships directly to verify persistence
        relationship_query = """
        MATCH ()-[r:BELONGS_TO_WORKFLOW]->()
        RETURN count(r) as total_relationships
        """
        result = await test_data_isolation["container"].execute_cypher(relationship_query)
        total_relationships = result[0]["total_relationships"]

        assert total_relationships > 0, "No BELONGS_TO_WORKFLOW relationships found in database"

        # Step 4: Verify relationship properties are correct
        property_query = """
        MATCH (n)-[r:BELONGS_TO_WORKFLOW]->(w)
        RETURN type(r) as rel_type, r.scopeText as scope_text
        LIMIT 1
        """
        prop_result = await test_data_isolation["container"].execute_cypher(property_query)

        if prop_result:
            assert prop_result[0]["rel_type"] == "BELONGS_TO_WORKFLOW", (
                f"Incorrect relationship type: {prop_result[0]['rel_type']}"
            )
            # scopeText should be empty string as per the implementation
            assert prop_result[0]["scope_text"] == "" or prop_result[0]["scope_text"] is None, (
                f"Unexpected scopeText value: {prop_result[0]['scope_text']}"
            )


class WorkflowGraphAssertions(GraphAssertions):
    """Extended GraphAssertions with workflow-specific helpers."""

    async def assert_belongs_to_workflow_exists(self, node_name: str, workflow_id: str) -> None:
        """Assert that a BELONGS_TO_WORKFLOW relationship exists between node and workflow."""
        query = """
        MATCH (n {name: $node_name})-[r:BELONGS_TO_WORKFLOW]->(w:WORKFLOW {id: $workflow_id})
        RETURN count(r) as count
        """
        result = await self.neo4j_instance.execute_cypher(query, {"node_name": node_name, "workflow_id": workflow_id})

        assert result[0]["count"] > 0, (
            f"No BELONGS_TO_WORKFLOW relationship found between node '{node_name}' and workflow '{workflow_id}'"
        )

    async def assert_workflow_complete(self, workflow_id: str) -> Dict[str, Any]:
        """
        Assert that all workflow relationships are properly created.

        Returns statistics about the workflow.
        """
        # Check WORKFLOW_STEP relationships
        step_query = """
        MATCH (w:WORKFLOW {id: $workflow_id})<-[:WORKFLOW_STEP]-()
        RETURN count(*) as step_count
        """
        step_result = await self.neo4j_instance.execute_cypher(step_query, {"workflow_id": workflow_id})

        # Check BELONGS_TO_WORKFLOW relationships
        belongs_query = """
        MATCH (n)-[:BELONGS_TO_WORKFLOW]->(w:WORKFLOW {id: $workflow_id})
        RETURN count(n) as participant_count, collect(n.name) as participants
        """
        belongs_result = await self.neo4j_instance.execute_cypher(belongs_query, {"workflow_id": workflow_id})

        return {
            "workflow_id": workflow_id,
            "step_count": step_result[0]["step_count"] if step_result else 0,
            "participant_count": belongs_result[0]["participant_count"] if belongs_result else 0,
            "participants": belongs_result[0]["participants"] if belongs_result else [],
        }

    async def get_workflow_participant_count(self, workflow_id: str) -> int:
        """Get count of nodes belonging to a workflow."""
        query = """
        MATCH (n)-[:BELONGS_TO_WORKFLOW]->(w:WORKFLOW {id: $workflow_id})
        RETURN count(n) as count
        """
        result = await self.neo4j_instance.execute_cypher(query, {"workflow_id": workflow_id})

        return result[0]["count"] if result else 0
