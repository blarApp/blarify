"""
Comprehensive tests for bridge edge step_order correctness.

This module tests that bridge edges maintain proper step_order continuity
and integration with original edges in the _create_bridge_edges function.
"""

from typing import Dict, Any

from blarify.db_managers.queries import _create_bridge_edges  # pyright: ignore[reportPrivateUsage]


class TestBridgeStepOrder:
    """Test suite for bridge edge step_order correctness."""

    def test_step_order_continuity_simple_case(self) -> None:
        """Test step_order continuity in simple two-path scenario."""
        nodes = [
            {"id": "a", "name": "func_a", "path": "/test.py", "depth": 0},
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
        
        # Sort by step_order
        result.sort(key=lambda e: e["step_order"])
        
        # Verify continuous step ordering
        expected_orders = [0, 1, 2, 3]  # 3 original + 1 bridge
        actual_orders = [edge["step_order"] for edge in result]
        assert actual_orders == expected_orders
        
        # Verify the bridge edge has correct step_order
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        assert len(bridge_edges) == 1
        assert bridge_edges[0]["step_order"] == 3
        assert bridge_edges[0]["caller_id"] == "x"
        assert bridge_edges[0]["callee_id"] == "c"

    def test_step_order_with_multiple_bridges(self) -> None:
        """Test step_order continuity with multiple bridge edges."""
        nodes = [
            {"id": "a", "name": "func_a", "path": "/test.py", "depth": 0},
            {"id": "b", "name": "func_b", "path": "/test.py", "depth": 0},
            {"id": "x", "name": "func_x", "path": "/test.py", "depth": 1},
            {"id": "y", "name": "func_y", "path": "/test.py", "depth": 2},
            {"id": "c", "name": "func_c", "path": "/test.py", "depth": 0},  # Path 2 starts
            {"id": "d", "name": "func_d", "path": "/test.py", "depth": 0},  # Path 3 starts
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
        result.sort(key=lambda e: e["step_order"])
        
        # Should have 6 original + 2 bridge edges with continuous ordering
        assert len(result) == 8
        expected_orders = list(range(8))  # [0, 1, 2, 3, 4, 5, 6, 7]
        actual_orders = [edge["step_order"] for edge in result]
        assert actual_orders == expected_orders
        
        # Verify bridge edges have correct step_orders
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        assert len(bridge_edges) == 2
        
        bridge_edges.sort(key=lambda e: e["step_order"])
        
        # First bridge: y → c (step_order 6)
        assert bridge_edges[0]["step_order"] == 6
        assert bridge_edges[0]["caller_id"] == "y"
        assert bridge_edges[0]["callee_id"] == "c"
        
        # Second bridge: c → d (step_order 7)
        assert bridge_edges[1]["step_order"] == 7
        assert bridge_edges[1]["caller_id"] == "c"
        assert bridge_edges[1]["callee_id"] == "d"

    def test_step_order_increments_correctly(self) -> None:
        """Test that bridge edge step_orders increment correctly from last original edge."""
        nodes = [
            {"id": "main", "name": "main", "path": "/main.py", "depth": 0},
            {"id": "process", "name": "process", "path": "/process.py", "depth": 0},
            {"id": "validate", "name": "validate", "path": "/validate.py", "depth": 1},
            {"id": "cleanup", "name": "cleanup", "path": "/cleanup.py", "depth": 0}  # New path
        ]
        edges = [
            {"caller_id": "main", "callee_id": "process", "step_order": 10},  # Original values don't matter
            {"caller_id": "process", "callee_id": "validate", "step_order": 11},  # Bridge function uses len(edges)
            {"caller_id": "main", "callee_id": "cleanup", "step_order": 12}   # to start bridge step_orders
        ]
        
        result = _create_bridge_edges(nodes, edges)
        
        # Find bridge edge
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        assert len(bridge_edges) == 1
        
        # Bridge step_order should be 3 (len(edges) = 3, so next is 3)
        # Note: _create_bridge_edges uses len(execution_edges) as starting point
        assert bridge_edges[0]["step_order"] == 3
        assert bridge_edges[0]["caller_id"] == "validate"
        assert bridge_edges[0]["callee_id"] == "cleanup"

    def test_step_order_preserves_original_ordering(self) -> None:
        """Test that original edges maintain their step_order after bridge creation."""
        nodes = [
            {"id": "a", "name": "func_a", "path": "/test.py", "depth": 0},
            {"id": "b", "name": "func_b", "path": "/test.py", "depth": 1},
            {"id": "c", "name": "func_c", "path": "/test.py", "depth": 0}  # New path
        ]
        original_edges = [
            {"caller_id": "a", "callee_id": "b", "step_order": 5, "call_line": 10},
            {"caller_id": "a", "callee_id": "c", "step_order": 8, "call_line": 15}
        ]
        
        result = _create_bridge_edges(nodes, original_edges.copy())
        
        # Check that original edges are preserved
        non_bridge_edges = [edge for edge in result if not edge.get("is_bridge_edge", False)]
        assert len(non_bridge_edges) == 2
        
        # Verify original edge properties are intact
        for original_edge in original_edges:
            matching_edges = [
                edge for edge in non_bridge_edges
                if (edge["caller_id"] == original_edge["caller_id"] and
                    edge["callee_id"] == original_edge["callee_id"])
            ]
            assert len(matching_edges) == 1
            
            matching_edge = matching_edges[0]
            assert matching_edge["step_order"] == original_edge["step_order"]
            assert matching_edge["call_line"] == original_edge["call_line"]

    def test_step_order_with_complex_workflow_sequence(self) -> None:
        """Test step_order correctness in complex workflow with realistic step orders."""
        nodes = [
            {"id": "main", "name": "main", "path": "/main.py", "depth": 0},
            {"id": "service", "name": "service", "path": "/service.py", "depth": 0},
            {"id": "database", "name": "database", "path": "/db.py", "depth": 1},
            {"id": "validator", "name": "validator", "path": "/validator.py", "depth": 2},
            {"id": "logger", "name": "logger", "path": "/logger.py", "depth": 0},  # Path 2
            {"id": "metrics", "name": "metrics", "path": "/metrics.py", "depth": 0},  # Path 3
            {"id": "reporter", "name": "reporter", "path": "/reporter.py", "depth": 1}
        ]
        edges = [
            {"caller_id": "main", "callee_id": "service", "step_order": 0},
            {"caller_id": "service", "callee_id": "database", "step_order": 1},
            {"caller_id": "database", "callee_id": "validator", "step_order": 2},
            {"caller_id": "main", "callee_id": "logger", "step_order": 3},
            {"caller_id": "main", "callee_id": "metrics", "step_order": 4},
            {"caller_id": "metrics", "callee_id": "reporter", "step_order": 5}
        ]
        
        result = _create_bridge_edges(nodes, edges)
        result.sort(key=lambda e: e["step_order"])
        
        # Verify continuous step ordering from 0 to N
        expected_orders = list(range(len(result)))
        actual_orders = [edge["step_order"] for edge in result]
        assert actual_orders == expected_orders
        
        # Check execution sequence is logical
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        assert len(bridge_edges) == 2
        
        # Bridge edges should connect paths logically
        bridge_edges.sort(key=lambda e: e["step_order"])
        
        # First bridge: validator → logger (end of path 1 → start of path 2)
        assert bridge_edges[0]["caller_id"] == "validator"
        assert bridge_edges[0]["callee_id"] == "logger"
        assert bridge_edges[0]["step_order"] == 6
        
        # Second bridge: logger → metrics (end of path 2 → start of path 3)
        assert bridge_edges[1]["caller_id"] == "logger"
        assert bridge_edges[1]["callee_id"] == "metrics"
        assert bridge_edges[1]["step_order"] == 7

    def test_no_bridge_edges_preserves_original_step_order(self) -> None:
        """Test that when no bridge edges are created, original step_order is preserved."""
        # Linear path - no bridges needed
        nodes = [
            {"id": "a", "name": "func_a", "path": "/test.py", "depth": 0},
            {"id": "b", "name": "func_b", "path": "/test.py", "depth": 1},
            {"id": "c", "name": "func_c", "path": "/test.py", "depth": 2}
        ]
        edges = [
            {"caller_id": "a", "callee_id": "b", "step_order": 100},
            {"caller_id": "b", "callee_id": "c", "step_order": 200}
        ]
        
        result = _create_bridge_edges(nodes, edges)
        
        # Should return exactly the original edges
        assert len(result) == 2
        assert result == edges
        
        # Verify step orders are unchanged
        result.sort(key=lambda e: e["step_order"])
        assert result[0]["step_order"] == 100
        assert result[1]["step_order"] == 200

    def test_step_order_with_first_entry_call_skipped(self) -> None:
        """Test that step_order is correct when first entry call is properly skipped."""
        nodes = [
            {"id": "a", "name": "func_a", "path": "/test.py", "depth": 0},
            {"id": "b", "name": "func_b", "path": "/test.py", "depth": 0},  # First call (should be skipped)
            {"id": "x", "name": "func_x", "path": "/test.py", "depth": 1},
            {"id": "c", "name": "func_c", "path": "/test.py", "depth": 0},  # Second call (should create boundary)
            {"id": "d", "name": "func_d", "path": "/test.py", "depth": 0}   # Third call (should create boundary)
        ]
        edges = [
            {"caller_id": "a", "callee_id": "b", "step_order": 0},  # First entry call
            {"caller_id": "b", "callee_id": "x", "step_order": 1},
            {"caller_id": "a", "callee_id": "c", "step_order": 2},  # Second entry call
            {"caller_id": "a", "callee_id": "d", "step_order": 3}   # Third entry call
        ]
        
        result = _create_bridge_edges(nodes, edges)
        result.sort(key=lambda e: e["step_order"])
        
        # Should have 4 original + 2 bridge edges (x→c, c→d)
        assert len(result) == 6
        
        # Verify no bridge for first entry call a→b
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        first_call_bridge = any(
            bridge["caller_id"] == "a" and bridge["callee_id"] == "b"
            for bridge in bridge_edges
        )
        assert not first_call_bridge, "Should not create bridge for first entry call"
        
        # Verify correct bridges are created
        assert len(bridge_edges) == 2
        bridge_edges.sort(key=lambda e: e["step_order"])
        
        # Bridge 1: x → c (step_order 4)
        assert bridge_edges[0]["caller_id"] == "x"
        assert bridge_edges[0]["callee_id"] == "c"
        assert bridge_edges[0]["step_order"] == 4
        
        # Bridge 2: c → d (step_order 5)
        assert bridge_edges[1]["caller_id"] == "c"
        assert bridge_edges[1]["callee_id"] == "d"
        assert bridge_edges[1]["step_order"] == 5

    def test_step_order_maintains_execution_chronology(self) -> None:
        """Test that final step_order sequence represents correct execution chronology."""
        nodes = [
            {"id": "start", "name": "start", "path": "/main.py", "depth": 0},
            {"id": "phase1", "name": "phase1", "path": "/phase1.py", "depth": 0},
            {"id": "task1", "name": "task1", "path": "/task1.py", "depth": 1},
            {"id": "phase2", "name": "phase2", "path": "/phase2.py", "depth": 0},  # New path
            {"id": "task2", "name": "task2", "path": "/task2.py", "depth": 1},
            {"id": "phase3", "name": "phase3", "path": "/phase3.py", "depth": 0}   # New path
        ]
        edges = [
            {"caller_id": "start", "callee_id": "phase1", "step_order": 0},
            {"caller_id": "phase1", "callee_id": "task1", "step_order": 1},
            {"caller_id": "start", "callee_id": "phase2", "step_order": 2},
            {"caller_id": "phase2", "callee_id": "task2", "step_order": 3},
            {"caller_id": "start", "callee_id": "phase3", "step_order": 4}
        ]
        
        result = _create_bridge_edges(nodes, edges)
        result.sort(key=lambda e: e["step_order"])
        
        # Expected execution chronology:
        # 0: start → phase1
        # 1: phase1 → task1  
        # 2: start → phase2
        # 3: phase2 → task2
        # 4: start → phase3
        # 5: task1 → phase2 [BRIDGE]
        # 6: task2 → phase3 [BRIDGE]
        
        expected_sequence = [
            ("start", "phase1", False),
            ("phase1", "task1", False),
            ("start", "phase2", False),
            ("phase2", "task2", False),
            ("start", "phase3", False),
            ("task1", "phase2", True),   # Bridge
            ("task2", "phase3", True)    # Bridge
        ]
        
        assert len(result) == len(expected_sequence)
        
        for i, (expected_caller, expected_callee, is_bridge) in enumerate(expected_sequence):
            edge = result[i]
            assert edge["step_order"] == i
            assert edge["caller_id"] == expected_caller
            assert edge["callee_id"] == expected_callee
            assert edge.get("is_bridge_edge", False) == is_bridge

    def test_edge_connectivity_forms_continuous_chain(self) -> None:
        """Test that bridge edges create continuous connectivity where each caller is the previous callee."""
        nodes = [
            {"id": "a", "name": "func_a", "path": "/test.py", "depth": 0},
            {"id": "b", "name": "func_b", "path": "/test.py", "depth": 0},
            {"id": "x", "name": "func_x", "path": "/test.py", "depth": 1},
            {"id": "y", "name": "func_y", "path": "/test.py", "depth": 2},
            {"id": "c", "name": "func_c", "path": "/test.py", "depth": 0},  # New path starts
            {"id": "d", "name": "func_d", "path": "/test.py", "depth": 0}   # Another path starts
        ]
        edges = [
            {"caller_id": "a", "callee_id": "b", "step_order": 0},
            {"caller_id": "b", "callee_id": "x", "step_order": 1},
            {"caller_id": "x", "callee_id": "y", "step_order": 2},
            {"caller_id": "a", "callee_id": "c", "step_order": 3},
            {"caller_id": "a", "callee_id": "d", "step_order": 4}
        ]
        
        result = _create_bridge_edges(nodes, edges)
        result.sort(key=lambda e: e["step_order"])
        
        # Expected continuous chain:
        # a → b → x → y → c → d (with bridges: y → c, c → d)
        
        # Verify connectivity: each edge's caller should be previous edge's callee
        connectivity_breaks: list[Dict[str, Any]] = []
        for i in range(1, len(result)):
            current_edge = result[i]
            previous_edge = result[i-1]
            
            current_caller = current_edge["caller_id"]
            previous_callee = previous_edge["callee_id"]
            
            if current_caller != previous_callee:
                connectivity_breaks.append({
                    "index": i,
                    "previous_edge": f"{previous_edge['caller_id']} → {previous_edge['callee_id']}",
                    "current_edge": f"{current_edge['caller_id']} → {current_edge['callee_id']}",
                    "expected_caller": previous_callee,
                    "actual_caller": current_caller
                })
        
        # Should have no connectivity breaks
        assert len(connectivity_breaks) == 0, f"Found connectivity breaks: {connectivity_breaks}"
        
        # Verify the complete execution chain
        execution_chain = [result[0]["caller_id"]]  # Start with first caller
        for edge in result:
            execution_chain.append(edge["callee_id"])
        
        expected_chain = ["a", "b", "x", "y", "c", "d"]
        assert execution_chain == expected_chain, f"Expected chain {expected_chain}, got {execution_chain}"

    def test_edge_connectivity_with_complex_branching(self) -> None:
        """Test edge connectivity in complex scenarios with multiple bridge edges."""
        nodes = [
            {"id": "main", "name": "main", "path": "/main.py", "depth": 0},
            {"id": "service", "name": "service", "path": "/service.py", "depth": 0},
            {"id": "database", "name": "database", "path": "/db.py", "depth": 1},
            {"id": "validator", "name": "validator", "path": "/validator.py", "depth": 2},
            {"id": "logger", "name": "logger", "path": "/logger.py", "depth": 0},  # Path 2
            {"id": "metrics", "name": "metrics", "path": "/metrics.py", "depth": 0},  # Path 3
            {"id": "reporter", "name": "reporter", "path": "/reporter.py", "depth": 1}
        ]
        edges = [
            {"caller_id": "main", "callee_id": "service", "step_order": 0},
            {"caller_id": "service", "callee_id": "database", "step_order": 1},
            {"caller_id": "database", "callee_id": "validator", "step_order": 2},
            {"caller_id": "main", "callee_id": "logger", "step_order": 3},
            {"caller_id": "main", "callee_id": "metrics", "step_order": 4},
            {"caller_id": "metrics", "callee_id": "reporter", "step_order": 5}
        ]
        
        result = _create_bridge_edges(nodes, edges)
        result.sort(key=lambda e: e["step_order"])
        
        # Verify complete connectivity
        connectivity_breaks: list[Dict[str, Any]] = []
        for i in range(1, len(result)):
            current_caller = result[i]["caller_id"]
            previous_callee = result[i-1]["callee_id"]
            
            if current_caller != previous_callee:
                connectivity_breaks.append({
                    "position": i,
                    "break": f"{result[i-1]['callee_id']} ↛ {current_caller}",
                    "previous": f"{result[i-1]['caller_id']} → {result[i-1]['callee_id']}",
                    "current": f"{result[i]['caller_id']} → {result[i]['callee_id']}"
                })
        
        assert len(connectivity_breaks) == 0, f"Connectivity breaks found: {connectivity_breaks}"
        
        # Verify expected execution flow
        execution_sequence: list[str] = []
        for edge in result:
            if not execution_sequence:
                execution_sequence.append(edge["caller_id"])
            execution_sequence.append(edge["callee_id"])
        
        # Should form: main → service → database → validator → logger → metrics → reporter
        expected_sequence = ["main", "service", "database", "validator", "logger", "metrics", "reporter"]
        assert execution_sequence == expected_sequence

    def test_edge_connectivity_detects_broken_chains(self) -> None:
        """Test that the connectivity test would detect broken chains if bridge edges were missing."""
        nodes = [
            {"id": "a", "name": "func_a", "path": "/test.py", "depth": 0},
            {"id": "b", "name": "func_b", "path": "/test.py", "depth": 1},
            {"id": "c", "name": "func_c", "path": "/test.py", "depth": 0}  # This should create a gap without bridge
        ]
        # Simulate missing bridge edge scenario (what would happen without _create_bridge_edges)
        broken_edges = [
            {"caller_id": "a", "callee_id": "b", "step_order": 0},
            {"caller_id": "a", "callee_id": "c", "step_order": 1}  # Gap: b ↛ a
        ]
        
        # Check connectivity manually (as if bridges weren't created)
        connectivity_breaks: list[Dict[str, Any]] = []
        for i in range(1, len(broken_edges)):
            current_caller = broken_edges[i]["caller_id"]
            previous_callee = broken_edges[i-1]["callee_id"]
            
            if current_caller != previous_callee:
                connectivity_breaks.append({
                    "position": i,
                    "gap": f"{previous_callee} ↛ {current_caller}"
                })
        
        # Should detect the connectivity break
        assert len(connectivity_breaks) == 1
        assert connectivity_breaks[0]["gap"] == "b ↛ a"
        
        # Now test that _create_bridge_edges fixes this
        fixed_edges = _create_bridge_edges(nodes, broken_edges.copy())
        fixed_edges.sort(key=lambda e: e["step_order"])
        
        # Verify connectivity is restored
        fixed_connectivity_breaks: list[Dict[str, Any]] = []
        for i in range(1, len(fixed_edges)):
            current_caller = fixed_edges[i]["caller_id"]
            previous_callee = fixed_edges[i-1]["callee_id"]
            
            if current_caller != previous_callee:
                fixed_connectivity_breaks.append({
                    "position": i,
                    "gap": f"{previous_callee} ↛ {current_caller}"
                })
        
        # Should have no breaks after bridge creation
        assert len(fixed_connectivity_breaks) == 0, f"Bridge edges failed to fix connectivity: {fixed_connectivity_breaks}"

    def test_edge_connectivity_preserves_original_valid_chains(self) -> None:
        """Test that connectivity is preserved for originally valid linear chains."""
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
        result.sort(key=lambda e: e["step_order"])
        
        # Should have no bridge edges for linear chain
        bridge_edges = [edge for edge in result if edge.get("is_bridge_edge", False)]
        assert len(bridge_edges) == 0
        
        # Verify perfect connectivity
        for i in range(1, len(result)):
            current_caller = result[i]["caller_id"]
            previous_callee = result[i-1]["callee_id"]
            assert current_caller == previous_callee, f"Connectivity break at position {i}: {previous_callee} ↛ {current_caller}"
        
        # Verify execution chain
        execution_chain = [result[0]["caller_id"]]
        for edge in result:
            execution_chain.append(edge["callee_id"])
        
        assert execution_chain == ["a", "b", "c"]