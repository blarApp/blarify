"""
Test cases for the new same-depth bridge edge creation logic.

This tests the enhancement to _create_bridge_edges that connects nodes
at the same depth level when they aren't already connected, addressing
the case where LCP filtering removes some edges from the DFS paths.
"""

import pytest
from typing import List, Dict, Any

from blarify.db_managers.queries import _create_bridge_edges


class TestSameDepthBridgeEdges:
    """Test suite for same-depth node bridge edge creation."""

    def test_connects_same_depth_nodes_without_edge(self) -> None:
        """Test that nodes at the same depth get connected when there's no existing edge."""
        # Scenario: main_diff calls both start and build at depth 1
        # Due to LCP, we might not have the main_diff→build edge
        nodes = [
            {"id": "main_diff", "name": "main_diff", "path": "/main.py", "depth": 0},
            {"id": "start", "name": "start", "path": "/start.py", "depth": 1},
            {"id": "build", "name": "build", "path": "/build.py", "depth": 1},
            {"id": "create_hierarchy", "name": "_create_code_hierarchy", "path": "/creator.py", "depth": 2}
        ]
        
        # Edges missing main_diff→build due to LCP filtering
        edges = [
            {"caller_id": "main_diff", "callee_id": "start", "depth": 1, "step_order": 0},
            {"caller_id": "build", "callee_id": "create_hierarchy", "depth": 2, "step_order": 1}
        ]
        
        result = _create_bridge_edges(nodes, edges)
        
        # Should create a bridge edge between start and build (same depth 1)
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        assert len(bridge_edges) == 1
        
        bridge = bridge_edges[0]
        assert bridge["caller_id"] == "start"
        assert bridge["callee_id"] == "build"
        assert bridge["depth"] == 2  # Edge depth is nodes' depth + 1
        
    def test_preserves_existing_edges_between_same_depth_nodes(self) -> None:
        """Test that existing edges between same-depth nodes are not duplicated."""
        nodes = [
            {"id": "main", "name": "main", "path": "/main.py", "depth": 0},
            {"id": "func_a", "name": "func_a", "path": "/a.py", "depth": 1},
            {"id": "func_b", "name": "func_b", "path": "/b.py", "depth": 1}
        ]
        
        # Edge already exists between func_a and func_b
        edges = [
            {"caller_id": "main", "callee_id": "func_a", "depth": 1, "step_order": 0},
            {"caller_id": "func_a", "callee_id": "func_b", "depth": 1, "step_order": 1}
        ]
        
        result = _create_bridge_edges(nodes, edges)
        
        # Should not create any bridge edges since edge already exists
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        assert len(bridge_edges) == 0
        assert len(result) == 2  # Only original edges
        
    def test_multiple_nodes_at_same_depth(self) -> None:
        """Test connecting multiple nodes at the same depth level."""
        nodes = [
            {"id": "entry", "name": "entry", "path": "/entry.py", "depth": 0},
            {"id": "service1", "name": "service1", "path": "/s1.py", "depth": 1},
            {"id": "service2", "name": "service2", "path": "/s2.py", "depth": 1},
            {"id": "service3", "name": "service3", "path": "/s3.py", "depth": 1},
            {"id": "util", "name": "util", "path": "/util.py", "depth": 2}
        ]
        
        # Missing edges between services at depth 1
        edges = [
            {"caller_id": "entry", "callee_id": "service1", "depth": 1, "step_order": 0},
            {"caller_id": "entry", "callee_id": "service3", "depth": 1, "step_order": 1},
            {"caller_id": "service2", "callee_id": "util", "depth": 2, "step_order": 2}
        ]
        
        result = _create_bridge_edges(nodes, edges)
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        
        # Should create bridges: service1→service2 and service2→service3
        assert len(bridge_edges) == 2
        
        # Verify the bridges connect in order
        bridges_sorted = sorted(bridge_edges, key=lambda e: (e["caller_id"], e["callee_id"]))
        assert bridges_sorted[0]["caller_id"] == "service1"
        assert bridges_sorted[0]["callee_id"] == "service2"
        assert bridges_sorted[1]["caller_id"] == "service2"
        assert bridges_sorted[1]["callee_id"] == "service3"
        
    def test_mixed_depth_levels(self) -> None:
        """Test bridge creation across multiple depth levels."""
        nodes = [
            {"id": "main", "name": "main", "path": "/main.py", "depth": 0},
            {"id": "level1_a", "name": "level1_a", "path": "/l1a.py", "depth": 1},
            {"id": "level1_b", "name": "level1_b", "path": "/l1b.py", "depth": 1},
            {"id": "level2_a", "name": "level2_a", "path": "/l2a.py", "depth": 2},
            {"id": "level2_b", "name": "level2_b", "path": "/l2b.py", "depth": 2},
            {"id": "level3", "name": "level3", "path": "/l3.py", "depth": 3}
        ]
        
        # Sparse edges across levels
        edges = [
            {"caller_id": "main", "callee_id": "level1_a", "depth": 1, "step_order": 0},
            {"caller_id": "level1_b", "callee_id": "level2_a", "depth": 2, "step_order": 1},
            {"caller_id": "level2_b", "callee_id": "level3", "depth": 3, "step_order": 2}
        ]
        
        result = _create_bridge_edges(nodes, edges)
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        
        # Should create bridges at each depth level
        expected_bridges = [
            ("level1_a", "level1_b", 2),  # depth 1 nodes
            ("level2_a", "level2_b", 3),  # depth 2 nodes
        ]
        
        assert len(bridge_edges) == len(expected_bridges)
        
        for bridge in bridge_edges:
            found = False
            for expected_caller, expected_callee, expected_depth in expected_bridges:
                if (bridge["caller_id"] == expected_caller and 
                    bridge["callee_id"] == expected_callee and
                    bridge["depth"] == expected_depth):
                    found = True
                    break
            assert found, f"Unexpected bridge: {bridge}"
            
    def test_single_node_at_depth(self) -> None:
        """Test that single nodes at a depth level don't create bridges."""
        nodes = [
            {"id": "main", "name": "main", "path": "/main.py", "depth": 0},
            {"id": "single", "name": "single", "path": "/single.py", "depth": 1},
            {"id": "deep", "name": "deep", "path": "/deep.py", "depth": 2}
        ]
        
        edges = [
            {"caller_id": "main", "callee_id": "single", "depth": 1, "step_order": 0},
            {"caller_id": "single", "callee_id": "deep", "depth": 2, "step_order": 1}
        ]
        
        result = _create_bridge_edges(nodes, edges)
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        
        # No bridges needed - only one node at each depth
        assert len(bridge_edges) == 0
        
    def test_maintains_execution_order(self) -> None:
        """Test that bridge edges respect the execution order of nodes."""
        nodes = [
            {"id": "main", "name": "main", "path": "/main.py", "depth": 0},
            {"id": "b", "name": "func_b", "path": "/b.py", "depth": 1},  # Appears first in execution
            {"id": "a", "name": "func_a", "path": "/a.py", "depth": 1},  # Appears second
            {"id": "c", "name": "func_c", "path": "/c.py", "depth": 1}   # Appears third
        ]
        
        edges = [
            {"caller_id": "main", "callee_id": "b", "depth": 1, "step_order": 0}
        ]
        
        result = _create_bridge_edges(nodes, edges)
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        
        # Should create bridges in execution order: b→a, a→c
        assert len(bridge_edges) == 2
        
        # First bridge: b→a
        first_bridge = next(e for e in bridge_edges if e["caller_id"] == "b")
        assert first_bridge["callee_id"] == "a"
        
        # Second bridge: a→c
        second_bridge = next(e for e in bridge_edges if e["caller_id"] == "a")
        assert second_bridge["callee_id"] == "c"
        
    def test_complex_real_world_scenario(self) -> None:
        """Test the actual scenario from the user's example."""
        # Recreating the exact scenario described
        nodes = [
            {"id": "93f77d77e170620b2d73c5caca19c49d", "name": "main_diff", 
             "path": "file:///Users/berrazuriz/Desktop/Blar/repositories/blarify/blarify/main.py", "depth": 0},
            {"id": "91824f57fdfdad7eac8228af6e0dfcf8", "name": "start", 
             "path": "file:///Users/berrazuriz/Desktop/Blar/repositories/blarify/blarify/code_references/lsp_helper.py", "depth": 1},
            {"id": "d8e6865b17f206f5c5bed946ef020b3e", "name": "build", 
             "path": "file:///Users/berrazuriz/Desktop/Blar/repositories/blarify/blarify/project_graph_diff_creator.py", "depth": 1},
            {"id": "5cda78ee6056051fd4bdf378f1adb4a0", "name": "_create_code_hierarchy", 
             "path": "file:///Users/berrazuriz/Desktop/Blar/repositories/blarify/blarify/project_graph_creator.py", "depth": 2}
        ]
        
        # Missing main_diff→build edge due to LCP
        edges = [
            {
                "caller_id": "93f77d77e170620b2d73c5caca19c49d",
                "callee_id": "91824f57fdfdad7eac8228af6e0dfcf8",
                "caller": "main_diff",
                "callee": "start",
                "depth": 1,
                "step_order": 0
            },
            {
                "caller_id": "d8e6865b17f206f5c5bed946ef020b3e",
                "callee_id": "5cda78ee6056051fd4bdf378f1adb4a0",
                "caller": "build",
                "callee": "_create_code_hierarchy",
                "depth": 2,
                "step_order": 1
            }
        ]
        
        result = _create_bridge_edges(nodes, edges)
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        
        # Should create a bridge between start and build
        assert len(bridge_edges) == 1
        
        bridge = bridge_edges[0]
        assert bridge["caller_id"] == "91824f57fdfdad7eac8228af6e0dfcf8"  # start
        assert bridge["callee_id"] == "d8e6865b17f206f5c5bed946ef020b3e"  # build
        assert bridge["caller"] == "start"
        assert bridge["callee"] == "build"
        assert bridge["depth"] == 2  # Edge depth for nodes at depth 1
        assert bridge["is_bridge_edge"] is True
        
        # This bridge edge enables continuous execution trace