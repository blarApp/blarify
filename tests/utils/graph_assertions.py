"""
Graph assertion utilities for Blarify integration tests.

This module provides helper functions for validating graph structures
in Neo4j using Cypher queries.
"""

from typing import List, Dict, Any, Optional, Set
from neo4j_container_manager.types import Neo4jContainerInstance


class GraphAssertions:
    """Utility class for making assertions about graph structure in Neo4j."""

    def __init__(self, neo4j_instance: Neo4jContainerInstance):
        """Initialize with a Neo4j container instance."""
        self.neo4j_instance = neo4j_instance

    async def assert_node_exists(self, label: str, properties: Optional[Dict[str, Any]] = None) -> None:
        """Assert that a node with given label and properties exists."""
        query = f"MATCH (n:{label})"

        if properties:
            where_clauses = []
            for key, value in properties.items():
                if isinstance(value, str):
                    where_clauses.append(f"n.{key} = '{value}'")
                else:
                    where_clauses.append(f"n.{key} = {value}")

            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)

        query += " RETURN count(n) as count"

        result = await self.neo4j_instance.execute_cypher(query)
        count = result[0]["count"]

        assert count > 0, f"No node found with label '{label}' and properties {properties}"

    async def assert_node_count(
        self, label: str, expected_count: int, properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """Assert that exactly the expected number of nodes exist."""
        query = f"MATCH (n:{label})"

        if properties:
            where_clauses = []
            for key, value in properties.items():
                if isinstance(value, str):
                    where_clauses.append(f"n.{key} = '{value}'")
                else:
                    where_clauses.append(f"n.{key} = {value}")

            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)

        query += " RETURN count(n) as count"

        result = await self.neo4j_instance.execute_cypher(query)
        actual_count = result[0]["count"]

        assert actual_count == expected_count, (
            f"Expected {expected_count} nodes with label '{label}', but found {actual_count}"
        )

    async def assert_relationship_exists(
        self,
        start_label: str,
        relationship_type: str,
        end_label: str,
        start_properties: Optional[Dict[str, Any]] = None,
        end_properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Assert that a relationship exists between specified nodes."""
        query = f"MATCH (start:{start_label})-[r:{relationship_type}]->(end:{end_label})"

        where_clauses = []

        if start_properties:
            for key, value in start_properties.items():
                if isinstance(value, str):
                    where_clauses.append(f"start.{key} = '{value}'")
                else:
                    where_clauses.append(f"start.{key} = {value}")

        if end_properties:
            for key, value in end_properties.items():
                if isinstance(value, str):
                    where_clauses.append(f"end.{key} = '{value}'")
                else:
                    where_clauses.append(f"end.{key} = {value}")

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        query += " RETURN count(r) as count"

        result = await self.neo4j_instance.execute_cypher(query)
        count = result[0]["count"]

        assert count > 0, (
            f"No relationship found: ({start_label})-[:{relationship_type}]->({end_label}) "
            f"with start_properties={start_properties}, end_properties={end_properties}"
        )

    async def assert_relationship_count(
        self,
        start_label: str,
        relationship_type: str,
        end_label: str,
        expected_count: int,
        start_properties: Optional[Dict[str, Any]] = None,
        end_properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Assert that exactly the expected number of relationships exist."""
        query = f"MATCH (start:{start_label})-[r:{relationship_type}]->(end:{end_label})"

        where_clauses = []

        if start_properties:
            for key, value in start_properties.items():
                if isinstance(value, str):
                    where_clauses.append(f"start.{key} = '{value}'")
                else:
                    where_clauses.append(f"start.{key} = {value}")

        if end_properties:
            for key, value in end_properties.items():
                if isinstance(value, str):
                    where_clauses.append(f"end.{key} = '{value}'")
                else:
                    where_clauses.append(f"end.{key} = {value}")

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        query += " RETURN count(r) as count"

        result = await self.neo4j_instance.execute_cypher(query)
        actual_count = result[0]["count"]

        assert actual_count == expected_count, (
            f"Expected {expected_count} relationships: "
            f"({start_label})-[:{relationship_type}]->({end_label}), "
            f"but found {actual_count}"
        )

    async def get_node_properties(
        self, label: str, filter_properties: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get all properties of nodes matching the criteria."""
        query = f"MATCH (n:{label})"

        if filter_properties:
            where_clauses = []
            for key, value in filter_properties.items():
                if isinstance(value, str):
                    where_clauses.append(f"n.{key} = '{value}'")
                else:
                    where_clauses.append(f"n.{key} = {value}")

            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)

        query += " RETURN properties(n) as props"

        result = await self.neo4j_instance.execute_cypher(query)
        return [record["props"] for record in result]

    async def get_relationship_properties(
        self, start_label: str, relationship_type: str, end_label: str
    ) -> List[Dict[str, Any]]:
        """Get all properties of relationships matching the criteria."""
        query = (
            f"MATCH (start:{start_label})-[r:{relationship_type}]->(end:{end_label}) "
            f"RETURN properties(r) as props, properties(start) as start_props, "
            f"properties(end) as end_props"
        )

        result = await self.neo4j_instance.execute_cypher(query)
        return result

    async def assert_node_has_property(
        self,
        label: str,
        property_name: str,
        property_value: Any,
        additional_properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Assert that a node has a specific property with the expected value."""
        properties = {property_name: property_value}
        if additional_properties:
            properties.update(additional_properties)

        await self.assert_node_exists(label, properties)

    async def assert_nodes_connected_by_path(
        self,
        start_label: str,
        end_label: str,
        path_pattern: str,
        start_properties: Optional[Dict[str, Any]] = None,
        end_properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Assert that nodes are connected by a specific path pattern."""
        query = f"MATCH (start:{start_label}){path_pattern}(end:{end_label})"

        where_clauses = []

        if start_properties:
            for key, value in start_properties.items():
                if isinstance(value, str):
                    where_clauses.append(f"start.{key} = '{value}'")
                else:
                    where_clauses.append(f"start.{key} = {value}")

        if end_properties:
            for key, value in end_properties.items():
                if isinstance(value, str):
                    where_clauses.append(f"end.{key} = '{value}'")
                else:
                    where_clauses.append(f"end.{key} = {value}")

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        query += " RETURN count(*) as count"

        result = await self.neo4j_instance.execute_cypher(query)
        count = result[0]["count"]

        assert count > 0, f"No path found matching pattern: ({start_label}){path_pattern}({end_label})"

    async def get_node_labels(self) -> Set[str]:
        """Get all node labels in the database."""
        query = "CALL db.labels()"
        result = await self.neo4j_instance.execute_cypher(query)
        return {record["label"] for record in result}

    async def get_relationship_types(self) -> Set[str]:
        """Get all relationship types in the database."""
        query = "CALL db.relationshipTypes()"
        result = await self.neo4j_instance.execute_cypher(query)
        return {record["relationshipType"] for record in result}

    async def assert_graph_structure_basics(
        self, expected_node_labels: Set[str], expected_relationship_types: Set[str]
    ) -> None:
        """Assert basic graph structure expectations."""
        actual_labels = await self.get_node_labels()
        actual_relationships = await self.get_relationship_types()

        # Check that expected labels exist (allow for additional labels)
        missing_labels = expected_node_labels - actual_labels
        assert not missing_labels, f"Missing expected node labels: {missing_labels}"

        # Check that expected relationship types exist (allow for additional types)
        missing_relationships = expected_relationship_types - actual_relationships
        assert not missing_relationships, f"Missing expected relationship types: {missing_relationships}"

    async def debug_print_graph_summary(self) -> Dict[str, Any]:
        """Print a summary of the graph for debugging purposes."""
        # Get node counts by label
        node_query = """
        MATCH (n)
        RETURN labels(n) as labels, count(n) as count
        ORDER BY count DESC
        """

        node_result = await self.neo4j_instance.execute_cypher(node_query)

        # Get relationship counts by type
        rel_query = """
        MATCH ()-[r]->()
        RETURN type(r) as type, count(r) as count
        ORDER BY count DESC
        """

        rel_result = await self.neo4j_instance.execute_cypher(rel_query)

        # Get total counts
        total_nodes_result = await self.neo4j_instance.execute_cypher("MATCH (n) RETURN count(n) as count")
        total_rels_result = await self.neo4j_instance.execute_cypher("MATCH ()-[r]->() RETURN count(r) as count")

        summary = {
            "total_nodes": total_nodes_result[0]["count"],
            "total_relationships": total_rels_result[0]["count"],
            "nodes_by_label": node_result,
            "relationships_by_type": rel_result,
        }

        print("\n=== Graph Summary ===")
        print(f"Total Nodes: {summary['total_nodes']}")
        print(f"Total Relationships: {summary['total_relationships']}")
        print("\nNodes by Label:")
        for item in summary["nodes_by_label"]:
            print(f"  {item['labels']}: {item['count']}")
        print("\nRelationships by Type:")
        for item in summary["relationships_by_type"]:
            print(f"  {item['type']}: {item['count']}")
        print("====================\n")

        return summary


# Convenience function for creating assertions
def create_graph_assertions(neo4j_instance: Neo4jContainerInstance) -> GraphAssertions:
    """Create a GraphAssertions instance for the given Neo4j instance."""
    return GraphAssertions(neo4j_instance)
