"""
Integration tests for bridge edge creation with WorkflowCreator.

This module tests that bridge edges work correctly with the complete
workflow discovery system, ensuring LLM agents receive continuous
execution traces.
"""

from unittest.mock import Mock
from typing import List, Dict, Any

from blarify.db_managers.queries import find_code_workflows


class TestWorkflowBridgeIntegration:
    """Integration tests for bridge edges with workflow discovery."""

    def create_mock_db_manager(self, query_result: List[Dict[str, Any]]) -> Mock:
        """Create a mock database manager that returns specified query results."""
        mock_db = Mock()
        mock_db.query.return_value = query_result
        return mock_db

    def test_find_code_workflows_creates_continuous_traces(self) -> None:
        """Test that find_code_workflows creates continuous execution traces with bridge edges."""
        # Mock database result representing two DFS paths
        mock_result = [{
            "executionNodes": [
                {"id": "main", "name": "main", "path": "/main.py", "depth": 0, "start_line": 1, "end_line": 10},
                {"id": "process", "name": "process_data", "path": "/process.py", "depth": 1, "start_line": 5, "end_line": 15},
                {"id": "validate", "name": "validate", "path": "/validate.py", "depth": 2, "start_line": 8, "end_line": 12},
                {"id": "main", "name": "main", "path": "/main.py", "depth": 0, "start_line": 1, "end_line": 10},  # Path 2
                {"id": "cleanup", "name": "cleanup", "path": "/cleanup.py", "depth": 1, "start_line": 3, "end_line": 8}
            ],
            "executionEdges": [
                {
                    "caller_id": "main", "caller": "main", "caller_path": "/main.py",
                    "callee_id": "process", "callee": "process_data", "callee_path": "/process.py",
                    "call_line": 20, "call_character": 4, "depth": 1
                },
                {
                    "caller_id": "process", "caller": "process_data", "caller_path": "/process.py", 
                    "callee_id": "validate", "callee": "validate", "callee_path": "/validate.py",
                    "call_line": 12, "call_character": 8, "depth": 2
                },
                {
                    "caller_id": "main", "caller": "main", "caller_path": "/main.py",
                    "callee_id": "cleanup", "callee": "cleanup", "callee_path": "/cleanup.py",
                    "call_line": 25, "call_character": 4, "depth": 1
                }
            ]
        }]

        mock_db = self.create_mock_db_manager(mock_result)
        
        # Call the function
        workflows = find_code_workflows(
            db_manager=mock_db,
            entity_id="test_entity",
            repo_id="test_repo", 
            entry_point_id="main",
            max_depth=10
        )

        # Verify workflow structure
        assert len(workflows) == 1
        workflow = workflows[0]
        
        # Check workflow metadata
        assert workflow["entryPointId"] == "main"
        assert workflow["entryPointName"] == "main"
        assert workflow["entryPointPath"] == "/main.py"
        assert workflow["workflowType"] == "dfs_execution_trace_with_edges"

        # Check that bridge edges were created
        workflow_edges = workflow["workflowEdges"]
        
        # Should have 3 original edges + 1 bridge edge
        assert len(workflow_edges) == 4

        # Find bridge edges
        bridge_edges = [edge for edge in workflow_edges if edge.get("is_bridge_edge", False)]
        assert len(bridge_edges) == 1

        # Verify bridge edge connects paths correctly
        bridge_edge = bridge_edges[0]
        assert bridge_edge["caller_id"] == "validate"  # Last node of path 1
        assert bridge_edge["callee_id"] == "cleanup"   # First node of path 2

        # Verify continuous step ordering
        workflow_edges.sort(key=lambda e: e["step_order"])  # type: ignore 
        step_orders = [edge["step_order"] for edge in workflow_edges]
        assert step_orders == [0, 1, 2, 3]  # Continuous sequence

    def test_empty_result_handling(self) -> None:
        """Test that empty database results are handled gracefully."""
        mock_db = self.create_mock_db_manager([])
        
        workflows = find_code_workflows(
            db_manager=mock_db,
            entity_id="test_entity", 
            repo_id="test_repo",
            entry_point_id="main",
            max_depth=10
        )
        
        assert workflows == []

    def test_single_path_no_bridge_edges(self) -> None:
        """Test that single-path workflows don't create unnecessary bridge edges."""
        mock_result = [{
            "executionNodes": [
                {"id": "main", "name": "main", "path": "/main.py", "depth": 0},
                {"id": "helper", "name": "helper", "path": "/helper.py", "depth": 1}
            ],
            "executionEdges": [
                {
                    "caller_id": "main", "caller": "main", "caller_path": "/main.py",
                    "callee_id": "helper", "callee": "helper", "callee_path": "/helper.py", 
                    "call_line": 10, "call_character": 4, "depth": 1
                }
            ]
        }]

        mock_db = self.create_mock_db_manager(mock_result)
        
        workflows = find_code_workflows(
            db_manager=mock_db,
            entity_id="test_entity",
            repo_id="test_repo",
            entry_point_id="main",
            max_depth=10
        )

        assert len(workflows) == 1
        workflow_edges = workflows[0]["workflowEdges"]
        
        # Should have only the original edge, no bridge edges
        assert len(workflow_edges) == 1
        bridge_edges = [edge for edge in workflow_edges if edge.get("is_bridge_edge", False)]
        assert len(bridge_edges) == 0

    def test_multiple_paths_multiple_bridges(self) -> None:
        """Test that multiple paths create appropriate bridge edges."""
        mock_result = [{
            "executionNodes": [
                # Path 1: main → service → database
                {"id": "main", "name": "main", "path": "/main.py", "depth": 0},
                {"id": "service", "name": "service", "path": "/service.py", "depth": 1},
                {"id": "database", "name": "database", "path": "/db.py", "depth": 2},
                # Path 2: main → logger  
                {"id": "main", "name": "main", "path": "/main.py", "depth": 0},
                {"id": "logger", "name": "logger", "path": "/log.py", "depth": 1},
                # Path 3: main → metrics → reporter
                {"id": "main", "name": "main", "path": "/main.py", "depth": 0},
                {"id": "metrics", "name": "metrics", "path": "/metrics.py", "depth": 1},
                {"id": "reporter", "name": "reporter", "path": "/report.py", "depth": 2}
            ],
            "executionEdges": [
                {"caller_id": "main", "callee_id": "service", "depth": 1},
                {"caller_id": "service", "callee_id": "database", "depth": 2},
                {"caller_id": "main", "callee_id": "logger", "depth": 1},
                {"caller_id": "main", "callee_id": "metrics", "depth": 1},
                {"caller_id": "metrics", "callee_id": "reporter", "depth": 2}
            ]
        }]

        mock_db = self.create_mock_db_manager(mock_result)
        
        workflows = find_code_workflows(
            db_manager=mock_db,
            entity_id="test_entity",
            repo_id="test_repo",
            entry_point_id="main",
            max_depth=10
        )

        workflow_edges = workflows[0]["workflowEdges"]
        
        # Should have 5 original edges + 2 bridge edges
        assert len(workflow_edges) == 7
        
        bridge_edges = [edge for edge in workflow_edges if edge.get("is_bridge_edge", False)]
        assert len(bridge_edges) == 2

        # Verify bridge connections create continuous flow
        bridge_edges.sort(key=lambda e: e["step_order"])
        
        # First bridge: database → logger (end of path 1 → start of path 2)
        assert bridge_edges[0]["caller_id"] == "database"
        assert bridge_edges[0]["callee_id"] == "logger"
        
        # Second bridge: logger → metrics (end of path 2 → start of path 3)  
        assert bridge_edges[1]["caller_id"] == "logger"
        assert bridge_edges[1]["callee_id"] == "metrics"

    def test_workflow_result_structure_compatibility(self) -> None:
        """Test that results maintain compatibility with WorkflowResult structure."""
        mock_result = [{
            "executionNodes": [
                {"id": "entry", "name": "entry_func", "path": "/entry.py", "depth": 0, "start_line": 1, "end_line": 20},
                {"id": "worker", "name": "worker_func", "path": "/worker.py", "depth": 1, "start_line": 5, "end_line": 15}
            ],
            "executionEdges": [
                {
                    "caller_id": "entry", "caller": "entry_func", "caller_path": "/entry.py",
                    "callee_id": "worker", "callee": "worker_func", "callee_path": "/worker.py",
                    "call_line": 10, "call_character": 8, "depth": 1
                }
            ]
        }]

        mock_db = self.create_mock_db_manager(mock_result)
        
        workflows = find_code_workflows(
            db_manager=mock_db,
            entity_id="test_entity",
            repo_id="test_repo",
            entry_point_id="entry",
            max_depth=5
        )

        workflow = workflows[0]
        
        # Verify all required fields are present for WorkflowResult compatibility
        required_fields = [
            "entryPointId", "entryPointName", "entryPointPath",
            "endPointId", "endPointName", "endPointPath", 
            "workflowNodes", "workflowEdges", "pathLength",
            "totalExecutionSteps", "workflowType", "discoveredBy"
        ]
        
        for field in required_fields:
            assert field in workflow, f"Missing required field: {field}"

        # Verify field types and values
        assert isinstance(workflow["workflowNodes"], list)
        assert isinstance(workflow["workflowEdges"], list) 
        assert isinstance(workflow["pathLength"], int)
        assert isinstance(workflow["totalExecutionSteps"], int)
        assert workflow["workflowType"] == "dfs_execution_trace_with_edges"
        assert workflow["discoveredBy"] == "apoc_dfs_traversal"

        # Verify end point is correctly identified
        assert workflow["endPointId"] == "worker"
        assert workflow["endPointName"] == "worker_func"
        assert workflow["endPointPath"] == "/worker.py"

    def test_error_handling_preserves_original_behavior(self) -> None:
        """Test that bridge edge creation doesn't interfere with error handling."""
        # Mock database manager that raises an exception
        mock_db = Mock()
        mock_db.query.side_effect = Exception("Database connection failed")
        
        workflows = find_code_workflows(
            db_manager=mock_db,
            entity_id="test_entity",
            repo_id="test_repo", 
            entry_point_id="entry",
            max_depth=5
        )
        
        # Should return empty list on error, just like original behavior
        assert workflows == []

    def test_bridge_edge_field_completeness(self) -> None:
        """Test that bridge edges have all required fields for downstream processing."""
        mock_result = [{
            "executionNodes": [
                {"id": "a", "name": "func_a", "path": "/a.py", "depth": 0},
                {"id": "b", "name": "func_b", "path": "/b.py", "depth": 1},
                {"id": "a", "name": "func_a", "path": "/a.py", "depth": 0},
                {"id": "c", "name": "func_c", "path": "/c.py", "depth": 1}
            ],
            "executionEdges": [
                {
                    "caller_id": "a", "caller": "func_a", "caller_path": "/a.py",
                    "callee_id": "b", "callee": "func_b", "callee_path": "/b.py",
                    "call_line": 5, "call_character": 2, "depth": 1
                },
                {
                    "caller_id": "a", "caller": "func_a", "caller_path": "/a.py", 
                    "callee_id": "c", "callee": "func_c", "callee_path": "/c.py",
                    "call_line": 8, "call_character": 2, "depth": 1
                }
            ]
        }]

        mock_db = self.create_mock_db_manager(mock_result)
        
        workflows = find_code_workflows(
            db_manager=mock_db,
            entity_id="test_entity",
            repo_id="test_repo",
            entry_point_id="a",
            max_depth=10
        )

        workflow_edges = workflows[0]["workflowEdges"]
        bridge_edges = [edge for edge in workflow_edges if edge.get("is_bridge_edge", False)]
        
        assert len(bridge_edges) == 1
        bridge_edge = bridge_edges[0]

        # Verify all fields that regular CALLS edges have
        required_fields = [
            "caller_id", "caller", "caller_path",
            "callee_id", "callee", "callee_path",
            "call_line", "call_character", "depth", "step_order"
        ]
        
        for field in required_fields:
            assert field in bridge_edge, f"Bridge edge missing field: {field}"

        # Verify special bridge edge fields
        assert bridge_edge["is_bridge_edge"] is True
        assert bridge_edge["call_line"] is None  # Bridge edges have no source location
        assert bridge_edge["call_character"] is None
        assert isinstance(bridge_edge["step_order"], int)