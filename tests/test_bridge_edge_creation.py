"""
Unit tests for bridge edge creation in DFS path sequencing.

This module tests the _create_bridge_edges function that addresses gaps
between consecutive DFS paths in workflow discovery, enabling continuous
execution traces for LLM agent analysis.
"""

import pytest
from typing import List, Dict, Any

from blarify.db_managers.queries import _create_bridge_edges


class TestBridgeEdgeCreation:
    """Test suite for bridge edge creation functionality."""

    def test_empty_inputs_return_original_edges(self) -> None:
        """Test that empty inputs return the original edges unchanged."""
        # Test empty execution_nodes
        result = _create_bridge_edges([], [])
        assert result == []
        
        # Test empty execution_edges with nodes
        nodes = [{"id": "node1", "name": "func1", "path": "/test.py", "depth": 0}]
        result = _create_bridge_edges(nodes, [])
        assert result == []
        
        # Test empty execution_nodes with edges  
        edges = [{"caller_id": "node1", "callee_id": "node2", "step_order": 0}]
        result = _create_bridge_edges([], edges)
        assert result == edges

    def test_single_node_no_bridge_edges(self) -> None:
        """Test that single node workflows don't create bridge edges."""
        nodes = [{"id": "node1", "name": "func1", "path": "/test.py", "depth": 0}]
        edges: List[Dict[str, Any]] = []
        
        result = _create_bridge_edges(nodes, edges)
        assert result == edges
        assert len(result) == 0

    def test_linear_path_no_bridge_edges(self) -> None:
        """Test that linear paths (single DFS path) don't create bridge edges."""
        nodes = [
            {"id": "a", "name": "func_a", "path": "/test.py", "depth": 0},
            {"id": "b", "name": "func_b", "path": "/test.py", "depth": 1},
            {"id": "c", "name": "func_c", "path": "/test.py", "depth": 2}
        ]
        edges = [
            {"caller_id": "a", "callee_id": "b", "step_order": 0},
            {"caller_id": "b", "callee_id": "c", "step_order": 1}
        ]
        
        result = _create_bridge_edges(nodes, edges)
        assert len(result) == 2  # Only original edges
        assert result == edges

    def test_two_paths_creates_bridge_edge(self) -> None:
        """Test that two consecutive DFS suffix paths create exactly one bridge edge."""
        # DFS suffix representation (entry point appears only once):
        # Path 1 suffix: b → x (depth 0 → 1)  
        # Path 2 suffix: c (depth 0, indicating new path from common prefix)
        # Expected bridge: x → c
        nodes = [
            {"id": "a", "name": "func_a", "path": "/test.py", "depth": 0},  # Entry point (once only)
            {"id": "b", "name": "func_b", "path": "/test.py", "depth": 0}, 
            {"id": "x", "name": "func_x", "path": "/test.py", "depth": 1},
            {"id": "c", "name": "func_c", "path": "/test.py", "depth": 0}  # Depth decrease = new path
        ]
        edges = [
            {"caller_id": "a", "callee_id": "b", "step_order": 0},
            {"caller_id": "b", "callee_id": "x", "step_order": 1},
            {"caller_id": "a", "callee_id": "c", "step_order": 2}
        ]
        
        result = _create_bridge_edges(nodes, edges)
        
        # Should have 3 original edges + 1 bridge edge
        assert len(result) == 4
        
        # Find the bridge edge
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        assert len(bridge_edges) == 1
        
        bridge_edge = bridge_edges[0]
        assert bridge_edge["caller_id"] == "x"  # Last node of path 1
        assert bridge_edge["callee_id"] == "c"  # First node of path 2 (after entry)
        assert bridge_edge["is_bridge_edge"] is True
        assert bridge_edge["call_line"] is None
        assert bridge_edge["call_character"] is None
        assert bridge_edge["depth"] == 1

    def test_multiple_paths_create_multiple_bridges(self) -> None:
        """Test that multiple consecutive DFS suffix paths create appropriate bridge edges."""
        # DFS suffix representation:
        # Path 1 suffix: b → x (depth 0 → 1)
        # Path 2 suffix: c → y (depth 0 → 1, then new path starts at depth 0)  
        # Path 3 suffix: d (depth 0)
        # Expected bridges: x → c, y → d
        nodes = [
            {"id": "a", "name": "func_a", "path": "/test.py", "depth": 0},  # Entry point (once only)
            {"id": "b", "name": "func_b", "path": "/test.py", "depth": 0},
            {"id": "x", "name": "func_x", "path": "/test.py", "depth": 1},
            {"id": "c", "name": "func_c", "path": "/test.py", "depth": 0},  # Path 2 starts (depth decrease)
            {"id": "y", "name": "func_y", "path": "/test.py", "depth": 1},
            {"id": "d", "name": "func_d", "path": "/test.py", "depth": 0}   # Path 3 starts (depth decrease)
        ]
        edges = [
            {"caller_id": "a", "callee_id": "b", "step_order": 0},
            {"caller_id": "b", "callee_id": "x", "step_order": 1},
            {"caller_id": "a", "callee_id": "c", "step_order": 2},
            {"caller_id": "c", "callee_id": "y", "step_order": 3},
            {"caller_id": "a", "callee_id": "d", "step_order": 4}
        ]
        
        result = _create_bridge_edges(nodes, edges)
        
        # Should have 5 original edges + 2 bridge edges
        assert len(result) == 7
        
        # Find bridge edges
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        assert len(bridge_edges) == 2
        
        # Sort bridge edges by step_order to verify correct sequence
        bridge_edges.sort(key=lambda e: e["step_order"])
        
        # First bridge: x → c
        assert bridge_edges[0]["caller_id"] == "x"
        assert bridge_edges[0]["callee_id"] == "c"
        
        # Second bridge: y → d  
        assert bridge_edges[1]["caller_id"] == "y"
        assert bridge_edges[1]["callee_id"] == "d"

    def test_bridge_edge_structure_matches_calls_edges(self) -> None:
        """Test that bridge edges have identical structure to CALLS edges."""
        nodes = [
            {"id": "a", "name": "func_a", "path": "/src/main.py", "depth": 0},
            {"id": "b", "name": "func_b", "path": "/src/utils.py", "depth": 1},
            {"id": "c", "name": "func_c", "path": "/src/helpers.py", "depth": 0}  # Depth decrease 1→0 = new path
        ]
        edges = [
            {
                "caller_id": "a", "caller": "func_a", "caller_path": "/src/main.py",
                "callee_id": "b", "callee": "func_b", "callee_path": "/src/utils.py", 
                "call_line": 10, "call_character": 5, "depth": 1, "step_order": 0
            },
            {
                "caller_id": "a", "caller": "func_a", "caller_path": "/src/main.py",
                "callee_id": "c", "callee": "func_c", "callee_path": "/src/helpers.py",
                "call_line": 15, "call_character": 8, "depth": 1, "step_order": 1
            }
        ]
        
        result = _create_bridge_edges(nodes, edges)
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        
        assert len(bridge_edges) == 1
        bridge_edge = bridge_edges[0]
        
        # Verify all required fields are present and correctly typed
        required_fields = [
            "caller_id", "caller", "caller_path",
            "callee_id", "callee", "callee_path", 
            "call_line", "call_character", "depth", "step_order"
        ]
        
        for field in required_fields:
            assert field in bridge_edge, f"Missing required field: {field}"
        
        # Verify field values
        assert bridge_edge["caller_id"] == "b"
        assert bridge_edge["caller"] == "func_b"  
        assert bridge_edge["caller_path"] == "/src/utils.py"
        assert bridge_edge["callee_id"] == "c"
        assert bridge_edge["callee"] == "func_c"
        assert bridge_edge["callee_path"] == "/src/helpers.py"
        assert bridge_edge["call_line"] is None  # Bridge edges have no source location
        assert bridge_edge["call_character"] is None
        assert bridge_edge["depth"] == 1
        assert isinstance(bridge_edge["step_order"], int)

    def test_step_order_continuity_maintained(self) -> None:
        """Test that bridge edges maintain continuous step ordering."""
        nodes = [
            {"id": "a", "name": "func_a", "path": "/test.py", "depth": 0},
            {"id": "b", "name": "func_b", "path": "/test.py", "depth": 1},
            {"id": "c", "name": "func_c", "path": "/test.py", "depth": 0}  # Depth decrease = new path
        ]
        edges = [
            {"caller_id": "a", "callee_id": "b", "step_order": 0},
            {"caller_id": "a", "callee_id": "c", "step_order": 1}
        ]
        
        result = _create_bridge_edges(nodes, edges)
        
        # Sort by step_order to verify continuity
        result.sort(key=lambda e: e["step_order"])
        
        # Verify step orders are continuous
        expected_orders = [0, 1, 2]  # Original edges + 1 bridge edge
        actual_orders = [edge["step_order"] for edge in result]
        assert actual_orders == expected_orders

    def test_path_boundary_detection_accuracy(self) -> None:
        """Test accurate detection of path boundaries based on depth changes."""
        # Complex scenario with nested calls and multiple path transitions
        nodes = [
            {"id": "a", "name": "func_a", "path": "/test.py", "depth": 0},
            {"id": "b", "name": "func_b", "path": "/test.py", "depth": 0},
            {"id": "x", "name": "func_x", "path": "/test.py", "depth": 1},
            {"id": "y", "name": "func_y", "path": "/test.py", "depth": 2},
            {"id": "c", "name": "func_c", "path": "/test.py", "depth": 0},  # New path (depth decrease 2→0)
            {"id": "d", "name": "func_d", "path": "/test.py", "depth": 0},  # Another path
            {"id": "z", "name": "func_z", "path": "/test.py", "depth": 1}
        ]
        edges = [
            {"caller_id": "a", "callee_id": "b", "step_order": 0},
            {"caller_id": "b", "callee_id": "x", "step_order": 1},
            {"caller_id": "x", "callee_id": "y", "step_order": 2},
            {"caller_id": "a", "callee_id": "c", "step_order": 3},
            {"caller_id": "a", "callee_id": "d", "step_order": 4},
            {"caller_id": "d", "callee_id": "z", "step_order": 5}
        ]
        
        result = _create_bridge_edges(nodes, edges)
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        
        # Should detect 2 path boundaries and create 2 bridge edges
        assert len(bridge_edges) == 2
        
        # Verify bridge connections
        bridge_edges.sort(key=lambda e: e["step_order"])
        
        # First bridge: y (end of path 1) → c (start of path 2)
        assert bridge_edges[0]["caller_id"] == "y"
        assert bridge_edges[0]["callee_id"] == "c"
        
        # Second bridge: c (end of path 2) → d (start of path 3) 
        assert bridge_edges[1]["caller_id"] == "c"
        assert bridge_edges[1]["callee_id"] == "d"

    def test_original_edges_preserved(self) -> None:
        """Test that original edges are preserved unchanged except for sorting."""
        nodes = [
            {"id": "a", "name": "func_a", "path": "/test.py", "depth": 0},
            {"id": "b", "name": "func_b", "path": "/test.py", "depth": 1},
            {"id": "c", "name": "func_c", "path": "/test.py", "depth": 0}  # Depth decrease = new path
        ]
        original_edges = [
            {"caller_id": "a", "callee_id": "b", "step_order": 0, "call_line": 5},
            {"caller_id": "a", "callee_id": "c", "step_order": 1, "call_line": 10}
        ]
        
        result = _create_bridge_edges(nodes, original_edges.copy())
        
        # Filter out bridge edges to check original edges
        non_bridge_edges = [edge for edge in result if not edge.get("is_bridge_edge", False)]
        
        assert len(non_bridge_edges) == 2
        
        # Verify original edges are intact
        for original_edge in original_edges:
            matching_edges = [
                edge for edge in non_bridge_edges 
                if (edge["caller_id"] == original_edge["caller_id"] and 
                    edge["callee_id"] == original_edge["callee_id"])
            ]
            assert len(matching_edges) == 1
            
            matching_edge = matching_edges[0]
            assert matching_edge["call_line"] == original_edge["call_line"]
            assert matching_edge["step_order"] == original_edge["step_order"]

    def test_complex_workflow_integration(self) -> None:
        """Test bridge edge creation in complex multi-path workflow scenarios."""
        # DFS suffix representation of realistic workflow:
        # Path 1 suffix: process_data → validate → save (depth 0→1→2)
        # Path 2 suffix: cleanup (depth 0, regression from 2→0)
        # Path 3 suffix: log_stats → format (depth 0→1)
        nodes = [
            {"id": "main", "name": "main", "path": "/main.py", "depth": 0},  # Entry point (once only)
            {"id": "process", "name": "process_data", "path": "/processor.py", "depth": 0},
            {"id": "validate", "name": "validate", "path": "/validator.py", "depth": 1},
            {"id": "save", "name": "save", "path": "/storage.py", "depth": 2},
            {"id": "cleanup", "name": "cleanup", "path": "/cleaner.py", "depth": 0},  # Path 2 (depth decrease 2→0)
            {"id": "log_stats", "name": "log_stats", "path": "/logger.py", "depth": 0},  # Path 3 (depth stable 0→0)
            {"id": "format", "name": "format", "path": "/formatter.py", "depth": 1}
        ]
        
        edges = [
            {"caller_id": "main", "callee_id": "process", "step_order": 0},
            {"caller_id": "process", "callee_id": "validate", "step_order": 1},
            {"caller_id": "validate", "callee_id": "save", "step_order": 2},
            {"caller_id": "main", "callee_id": "cleanup", "step_order": 3},
            {"caller_id": "main", "callee_id": "log_stats", "step_order": 4},
            {"caller_id": "log_stats", "callee_id": "format", "step_order": 5}
        ]
        
        result = _create_bridge_edges(nodes, edges)
        
        # Should have original 6 edges + 2 bridge edges
        assert len(result) == 8
        
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        assert len(bridge_edges) == 2
        
        # Verify continuous flow through bridge edges
        all_edges_sorted = sorted(result, key=lambda e: e["step_order"])
        
        # Check that workflow creates continuous execution trace
        execution_sequence = []
        for edge in all_edges_sorted:
            if not execution_sequence:
                execution_sequence.append(edge["caller_id"])
            execution_sequence.append(edge["callee_id"])
        
        # Should have continuous execution without gaps
        assert len(execution_sequence) == len(all_edges_sorted) + 1
        
        # Verify bridge edges connect the right functions
        bridge_edges.sort(key=lambda e: e["step_order"])
        assert bridge_edges[0]["caller_id"] == "save"  # End of path 1
        assert bridge_edges[0]["callee_id"] == "cleanup"  # Start of path 2
        assert bridge_edges[1]["caller_id"] == "cleanup"  # End of path 2  
        assert bridge_edges[1]["callee_id"] == "log_stats"  # Start of path 3