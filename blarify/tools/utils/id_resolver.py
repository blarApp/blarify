from typing import Optional

from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager


def resolve_reference_id(
    db_manager: AbstractDbManager,
    reference_id: Optional[str] = None,
    file_path: Optional[str] = None,
    symbol_name: Optional[str] = None
) -> str:
    """
    Resolve a reference_id from either direct ID or file_path + symbol_name.

    Args:
        db_manager: Database manager for queries
        reference_id: Direct reference ID (32-char hash)
        file_path: Path to file containing symbol
        symbol_name: Name of symbol (function/class)

    Returns:
        Resolved reference_id

    Raises:
        ValueError: If inputs are invalid or symbol not found
    """
    if reference_id:
        return reference_id

    if not file_path or not symbol_name:
        raise ValueError("Must provide either reference_id OR (file_path AND symbol_name)")

    # Query database for node with matching file_path and name
    # Use get_node_by_name_and_type but need to determine type
    # First try as FUNCTION, then CLASS
    for node_type in ["FUNCTION", "CLASS", "METHOD"]:
        nodes = db_manager.get_node_by_name_and_type(
            name=symbol_name,
            node_type=node_type
        )

        # Filter by file_path if we got results
        for node in nodes:
            if node.file_path == file_path:
                return node.node_id

    raise ValueError(f"Symbol '{symbol_name}' not found in '{file_path}'")