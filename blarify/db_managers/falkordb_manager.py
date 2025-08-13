"""Backward compatibility module for falkordb_manager.

This module provides backward compatibility for imports from the old location.
"""

from blarify.repositories.graph_db_manager.falkordb_manager import FalkorDBManager

__all__ = ['FalkorDBManager']