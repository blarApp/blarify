"""
Graph update query functions for Neo4j database operations.

This module contains pre-defined Cypher queries for creating, updating,
and managing nodes and relationships in the Neo4j graph database.
Note: Index and constraint creation queries are handled by neo4j_manager.py methods.
"""

from typing import LiteralString


def detach_delete_nodes_by_paths_query() -> LiteralString:
    """
    Returns the Cypher query for deleting nodes by file paths.

    Returns:
        str: The Cypher query string
    """
    return """
    UNWIND $file_paths AS path
    MATCH (n:NODE {path: path, entityId: $entity_id, repoId: $repo_id})
    DETACH DELETE n
    """


def detach_delete_nodes_by_diff_identifier_query() -> LiteralString:
    """
    Returns the Cypher query for deleting nodes by diff identifier.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (n:NODE {diff_identifier: $diff_identifier, entityId: $entity_id, repoId: $repo_id})
    DETACH DELETE n
    """


def detach_delete_nodes_by_node_ids_query() -> LiteralString:
    """
    Returns the Cypher query for deleting nodes by their IDs.

    Returns:
        str: The Cypher query string
    """
    return """
    UNWIND $node_ids AS node_id
    MATCH (n:NODE {entityId: $entity_id, repoId: $repo_id, node_id: node_id})
    DETACH DELETE n
    """


def match_empty_folders_query() -> LiteralString:
    """
    Returns the Cypher query for finding empty folder nodes.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (folder:FOLDER {entityId: $entity_id, repoId: $repo_id})
    WHERE NOT EXISTS {
        MATCH (folder)-[:CONTAINS]->(:FOLDER)
        UNION
        MATCH (folder)-[:CONTAINS]->(:FILE)
    }
    RETURN folder
    """
