"""Backward compatibility module for db_managers.

This module provides backward compatibility for imports from the old location.
The actual implementation has been moved to blarify.repositories.graph_db_manager.
"""

from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager

__all__ = ['AbstractDbManager']