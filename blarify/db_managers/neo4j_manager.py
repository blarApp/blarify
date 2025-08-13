"""Backward compatibility module for neo4j_manager.

This module provides backward compatibility for imports from the old location.
"""

from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager

__all__ = ['Neo4jManager']