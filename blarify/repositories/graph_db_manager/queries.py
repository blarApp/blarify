"""
Database query functions for the semantic documentation layer.

This module contains pre-defined Cypher queries and helper functions for
retrieving structured data from the graph database.
"""

from typing import Dict, List, Any, LiteralString, Optional, Tuple
import logging

from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager
from blarify.repositories.graph_db_manager.dtos.leaf_node_dto import LeafNodeDto
from blarify.repositories.graph_db_manager.dtos.node_with_content_dto import NodeWithContentDto

logger = logging.getLogger(__name__)


def get_codebase_skeleton_query() -> LiteralString:
    """
    Returns the Cypher query for retrieving the codebase skeleton structure.

    This query directly fetches all FILE and FOLDER nodes and their CONTAINS
    relationships, avoiding duplicate nodes and complex path traversal.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (n:NODE {entityId: $entity_id, repoId: $repo_id})
    WHERE (n:FILE OR n:FOLDER)
    WITH n
    OPTIONAL MATCH (n)-[r:CONTAINS]->(child:NODE)
    WHERE (child:FILE OR child:FOLDER)
    WITH n, COLLECT(DISTINCT {
        type: type(r),
        start_node_id: n.node_id,
        end_node_id: child.node_id
    }) AS outgoing_rels
    RETURN {
        name: n.name,
        type: labels(n),
        node_id: coalesce(n.node_id, "N/A"),
        path: n.path
    } AS node_info,
    outgoing_rels AS relationships
    """


def format_codebase_skeleton_result(query_result: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Formats the result of the codebase skeleton query into a structured format.

    Args:
        query_result: Raw result from the database query - list of records with node_info and relationships

    Returns:
        Dict containing formatted nodes and relationships
    """
    if not query_result:
        return {"nodes": [], "relationships": []}

    try:
        # Collect all nodes and relationships from all records
        all_nodes = []
        all_relationships = []

        for record in query_result:
            # Extract node information from this record
            node_info = record.get("node_info", {})

            # Add the node (already filtered to FILE/FOLDER by query)
            if node_info:
                formatted_node = {
                    "name": node_info.get("name", ""),
                    "type": node_info.get("type", []),
                    "node_id": node_info.get("node_id", ""),
                    "path": node_info.get("path", ""),
                }
                all_nodes.append(formatted_node)

            # Add relationships from this record
            relationships = record.get("relationships", [])
            for rel in relationships:
                if rel:  # Skip empty relationships
                    formatted_rel = {
                        "type": rel.get("type", ""),
                        "start_node_id": rel.get("start_node_id", ""),
                        "end_node_id": rel.get("end_node_id", ""),
                    }
                    all_relationships.append(formatted_rel)

        return {"nodes": all_nodes, "relationships": all_relationships}

    except (KeyError, IndexError) as e:
        logger.exception(f"Error formatting codebase skeleton result: {e}")
        return {"nodes": [], "relationships": []}


def get_node_details_query() -> LiteralString:
    """
    Returns a query for retrieving detailed information about a specific node.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (n:NODE {node_id: $node_id, entityId: $entity_id, repoId: $repo_id})
    RETURN n.name as name,
           labels(n) as type,
           n.node_id as node_id,
           n.path as path,
           n.start_line as start_line,
           n.end_line as end_line,
           n.content as content
    """


def get_node_relationships_query() -> LiteralString:
    """
    Returns a query for retrieving relationships of a specific node.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (n:NODE {node_id: $node_id, entityId: $entity_id, repoId: $repo_id})
    OPTIONAL MATCH (n)-[r]->(related:NODE)
    RETURN type(r) as relationship_type,
           related.node_id as related_node_id,
           related.name as related_name,
           labels(related) as related_type,
           r.scopeText as scope_text,
           'outgoing' as direction
    UNION
    MATCH (n:NODE {node_id: $node_id, entityId: $entity_id, repoId: $repo_id})
    OPTIONAL MATCH (related:NODE)-[r]->(n)
    RETURN type(r) as relationship_type,
           related.node_id as related_node_id,
           related.name as related_name,
           labels(related) as related_type,
           r.scopeText as scope_text,
           'incoming' as direction
    """


def format_node_details_result(query_result: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Formats the result of a node details query.

    Args:
        query_result: Raw result from the database query

    Returns:
        Dict containing formatted node details or None if not found
    """
    if not query_result:
        return None

    try:
        record = query_result[0]
        return {
            "name": record.get("name", ""),
            "type": record.get("type", []),
            "node_id": record.get("node_id", ""),
            "path": record.get("path", ""),
            "start_line": record.get("start_line"),
            "end_line": record.get("end_line"),
            "content": record.get("content", ""),
        }
    except (KeyError, IndexError) as e:
        logger.exception(f"Error formatting node details result: {e}")
        return None


def format_node_relationships_result(query_result: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Formats the result of a node relationships query.

    Args:
        query_result: Raw result from the database query

    Returns:
        List of formatted relationship dictionaries
    """
    if not query_result:
        return []

    try:
        formatted_relationships = []
        for record in query_result:
            if record.get("relationship_type"):  # Skip null relationships
                formatted_rel = {
                    "relationship_type": record.get("relationship_type", ""),
                    "related_node_id": record.get("related_node_id", ""),
                    "related_name": record.get("related_name", ""),
                    "related_type": record.get("related_type", []),
                    "scope_text": record.get("scope_text", ""),
                    "direction": record.get("direction", ""),
                }
                formatted_relationships.append(formatted_rel)

        return formatted_relationships

    except (KeyError, IndexError) as e:
        logger.exception(f"Error formatting node relationships result: {e}")
        return []


def get_codebase_skeleton(db_manager: AbstractDbManager, entity_id: str, repo_id: str) -> str:
    """
    Retrieves the codebase skeleton structure and formats it as a structured string.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID to query
        repo_id: The repository ID to query

    Returns:
        Formatted string representation of the codebase structure
    """
    try:
        # Get the query and execute it
        query = get_codebase_skeleton_query()
        parameters = {"entity_id": entity_id, "repo_id": repo_id}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        # Format the result
        formatted_result = format_codebase_skeleton_result(query_result)

        # Convert to structured string representation
        return format_skeleton_as_string(formatted_result)

    except Exception as e:
        logger.exception(f"Error retrieving codebase skeleton: {e}")
        return f"Error retrieving codebase skeleton: {str(e)}"


def format_skeleton_as_string(skeleton_data: Dict[str, Any]) -> str:
    """
    Formats skeleton data as a structured string representation.

    Args:
        skeleton_data: Dictionary containing nodes and relationships

    Returns:
        Formatted string representation of the codebase structure
    """
    if not skeleton_data or not skeleton_data.get("nodes"):
        return "No codebase structure found."

    nodes = skeleton_data["nodes"]
    relationships = skeleton_data["relationships"]

    # Build a hierarchy based on relationships
    hierarchy = build_hierarchy(nodes, relationships)

    # Format as tree structure
    output = ["# Codebase Structure"]
    output.append("")
    output.extend(format_hierarchy_tree(hierarchy))

    return "\n".join(output)


def build_hierarchy(nodes: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Builds a hierarchical structure from nodes and relationships.

    Args:
        nodes: List of node dictionaries
        relationships: List of relationship dictionaries

    Returns:
        Hierarchical structure dictionary
    """
    # Create node lookup
    node_lookup = {node["node_id"]: node for node in nodes}

    # Build parent-child relationships
    children = {}
    for rel in relationships:
        if rel["type"] in ["CONTAINS", "FUNCTION_DEFINITION", "CLASS_DEFINITION"]:
            parent_id = rel["start_node_id"]
            child_id = rel["end_node_id"]

            if parent_id not in children:
                children[parent_id] = []
            children[parent_id].append(child_id)

    # Find root nodes (nodes without parents)
    all_children = set()
    for child_list in children.values():
        all_children.update(child_list)

    root_nodes = [node_id for node_id in node_lookup.keys() if node_id not in all_children]

    # Build hierarchy starting from roots
    hierarchy = {"roots": root_nodes, "children": children, "nodes": node_lookup}

    return hierarchy


def format_hierarchy_tree(hierarchy: Dict[str, Any]) -> List[str]:
    """
    Formats hierarchy as a tree structure with indentation and arrows.

    Args:
        hierarchy: Hierarchical structure dictionary

    Returns:
        List of formatted tree lines
    """
    output = []

    def format_node(node_id: str, level: int = 0, is_last: bool = False, parent_prefix: str = "") -> List[str]:
        node = hierarchy["nodes"].get(node_id)
        if not node:
            return []

        # Format node information
        name = node.get("name", "")

        # Determine if this is a file or folder based on node labels
        children = hierarchy["children"].get(node_id, [])
        has_children = len(children) > 0

        # Use actual node labels from database instead of guessing from name
        node_labels = node.get("type", [])
        if "FILE" in node_labels:
            type_str = "FILE"
        elif "FOLDER" in node_labels:
            type_str = "FOLDER"
        else:
            # Fallback to old logic only if no type information is available
            has_extension = name and "." in name.split("/")[-1]
            if has_children or not has_extension:
                type_str = "FOLDER"
            else:
                type_str = "FILE"

        # Create display name (without path) and include node_id
        display_name = name if name else node_id

        # Choose the appropriate tree symbol and format
        if level == 0:
            prefix = ""
            current_prefix = ""
        else:
            prefix = parent_prefix + ("└── " if is_last else "├── ")
            current_prefix = parent_prefix + ("    " if is_last else "│   ")

        # Format with FOLDER/FILE labels and node IDs in brackets
        lines = [
            f"{prefix}{display_name}{'/' if type_str == 'FOLDER' else ''}                     # {type_str} [ID: {node_id}]"
        ]

        # Add children
        children = hierarchy["children"].get(node_id, [])
        for i, child_id in enumerate(children):
            is_last_child = i == len(children) - 1
            lines.extend(format_node(child_id, level + 1, is_last_child, current_prefix))

        return lines

    # Format all root nodes
    for i, root_id in enumerate(hierarchy["roots"]):
        is_last_root = i == len(hierarchy["roots"]) - 1
        output.extend(format_node(root_id, 0, is_last_root, ""))

    return output


def get_code_nodes_by_ids_query() -> LiteralString:
    """Returns Cypher query to get code nodes by their IDs.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (n:NODE)
    WHERE n.node_id IN $node_ids
      AND n.entityId = $entity_id
      AND n.repoId = $repo_id
    RETURN n.node_id as id,
           n.name as name,
           n.label as label,
           n.path as path,
           n.start_line as start_line,
           n.end_line as end_line
    """


def get_all_leaf_nodes_query() -> LiteralString:
    """
    Returns a Cypher query for retrieving all leaf nodes in the codebase hierarchy.

    Leaf nodes are defined as nodes with no outgoing hierarchical relationships
    (CONTAINS, FUNCTION_DEFINITION, CLASS_DEFINITION). They can still have LSP/semantic
    relationships like CALLS, IMPORTS, etc.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (n:NODE {entityId: $entity_id, repoId: $repo_id, diff_identifier: '0'})
    WHERE NOT (n)-[:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION]->()
    RETURN n.node_id as id,
           n.name as name,
           labels(n) as labels,
           n.path as path,
           n.start_line as start_line,
           n.end_line as end_line,
           coalesce(n.text, '') as content
    ORDER BY n.path, coalesce(n.start_line, 0)
    """


def get_folder_leaf_nodes_query() -> LiteralString:
    """
    Returns a Cypher query for retrieving leaf nodes under a specific folder path.

    Leaf nodes are defined as nodes with no outgoing hierarchical relationships
    (CONTAINS, FUNCTION_DEFINITION, CLASS_DEFINITION). This query filters by folder path
    at the database level for efficient per-folder processing.

    Uses CONTAINS to match folder paths within the full database path structure,
    since database paths include full prefixes like /env/repo/folder_path.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (n:NODE {entityId: $entity_id, repoId: $repo_id, diff_identifier: '0'})
    WHERE NOT (n)-[:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION]->()
      AND n.path CONTAINS $folder_path
    RETURN n.node_id as id,
           n.name as name,
           labels(n) as labels,
           n.path as path,
           n.start_line as start_line,
           n.end_line as end_line,
           coalesce(n.text, '') as content
    ORDER BY n.path, coalesce(n.start_line, 0)
    """


def format_leaf_nodes_result(query_result: List[Dict[str, Any]]) -> List[LeafNodeDto]:
    """
    Formats the result of the leaf nodes query into LeafNodeDto objects.

    Args:
        query_result: Raw result from the database query

    Returns:
        List of LeafNodeDto objects
    """
    if not query_result:
        return []

    try:
        leaf_nodes = []
        for record in query_result:
            leaf_node = LeafNodeDto(
                id=record.get("id", ""),
                name=record.get("name", ""),
                labels=record.get("labels", []),
                path=record.get("path", ""),
                start_line=record.get("start_line"),
                end_line=record.get("end_line"),
                content=record.get("content", ""),
            )
            leaf_nodes.append(leaf_node)

        return leaf_nodes

    except Exception as e:
        logger.exception(f"Error formatting leaf nodes result: {e}")
        return []


def get_all_leaf_nodes(db_manager: AbstractDbManager, entity_id: str, repo_id: str) -> List[LeafNodeDto]:
    """
    Retrieves all leaf nodes from the codebase hierarchy.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID to query
        repo_id: The repository ID to query

    Returns:
        List of LeafNodeDto objects representing all leaf nodes
    """
    try:
        # Get the query and execute it
        query = get_all_leaf_nodes_query()
        parameters = {"entity_id": entity_id, "repo_id": repo_id}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        # Format the result into DTOs
        return format_leaf_nodes_result(query_result)

    except Exception as e:
        logger.exception(f"Error retrieving leaf nodes: {e}")
        return []


def get_folder_leaf_nodes(
    db_manager: AbstractDbManager, entity_id: str, repo_id: str, folder_path: str
) -> List[LeafNodeDto]:
    """
    Retrieves leaf nodes under a specific folder path.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID to query
        repo_id: The repository ID to query
        folder_path: The folder path to filter by (e.g., "src/", "components/")

    Returns:
        List of LeafNodeDto objects representing leaf nodes under the specified folder
    """
    try:
        # Get the query and execute it
        query = get_folder_leaf_nodes_query()
        parameters = {"entity_id": entity_id, "repo_id": repo_id, "folder_path": folder_path}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        # Format the result into DTOs
        return format_leaf_nodes_result(query_result)

    except Exception as e:
        logger.exception(f"Error retrieving folder leaf nodes for path '{folder_path}': {e}")
        return []


def get_node_by_path_query() -> LiteralString:
    """
    Returns a Cypher query for retrieving a node (folder or file) by its path.

    This query finds the specific folder or file node that matches the given path.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (n:NODE {entityId: $entity_id, repoId: $repo_id})
    WHERE n.node_path CONTAINS $node_path
    RETURN n.node_id as id,
           n.name as name,
           labels(n) as labels,
           n.path as path,
           n.start_line as start_line,
           n.end_line as end_line,
           coalesce(n.text, '') as content
    ORDER BY size(n.path)
    LIMIT 1
    """


def get_direct_children_query() -> LiteralString:
    """
    Returns a Cypher query for retrieving immediate children of a node.

    Gets direct children through hierarchical relationships (CONTAINS, FUNCTION_DEFINITION, CLASS_DEFINITION).

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (parent:NODE {node_id: $node_id, entityId: $entity_id, repoId: $repo_id})
    -[r:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION]->(child:NODE)
    RETURN child.node_id as id,
           child.name as name,
           labels(child) as labels,
           child.path as path,
           child.start_line as start_line,
           child.end_line as end_line,
           coalesce(child.text, '') as content,
           type(r) as relationship_type
    ORDER BY child.path, coalesce(child.start_line, 0)
    """


def format_node_with_content_result(query_result: List[Dict[str, Any]]) -> Optional[NodeWithContentDto]:
    """
    Formats the result of a single node query into a NodeWithContentDto.

    Args:
        query_result: Raw result from the database query

    Returns:
        NodeWithContentDto object or None if not found
    """
    if not query_result:
        return None

    try:
        record = query_result[0]
        return NodeWithContentDto(
            id=record.get("id", ""),
            name=record.get("name", ""),
            labels=record.get("labels", []),
            path=record.get("path", ""),
            start_line=record.get("start_line"),
            end_line=record.get("end_line"),
            content=record.get("content", ""),
        )
    except Exception as e:
        logger.exception(f"Error formatting node with content result: {e}")
        return None


def format_children_with_content_result(query_result: List[Dict[str, Any]]) -> List[NodeWithContentDto]:
    """
    Formats the result of a children query into NodeWithContentDto objects.

    Args:
        query_result: Raw result from the database query

    Returns:
        List of NodeWithContentDto objects
    """
    if not query_result:
        return []

    try:
        children = []
        for record in query_result:
            child = NodeWithContentDto(
                id=record.get("id", ""),
                name=record.get("name", ""),
                labels=record.get("labels", []),
                path=record.get("path", ""),
                start_line=record.get("start_line"),
                end_line=record.get("end_line"),
                content=record.get("content", ""),
                relationship_type=record.get("relationship_type"),
            )
            children.append(child)

        return children

    except Exception as e:
        logger.exception(f"Error formatting children with content result: {e}")
        return []


def get_node_by_path(db_manager: AbstractDbManager, node_path: str) -> Optional[NodeWithContentDto]:
    """
    Retrieves a node (folder or file) by its path.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID to query
        repo_id: The repository ID to query
        node_path: The node path to find

    Returns:
        NodeWithContentDto object or None if not found
    """
    try:
        # Strip trailing slash to match nodes properly
        # This handles cases where paths may have trailing slashes
        normalized_path = node_path.rstrip("/")

        query = get_node_by_path_query()
        parameters = {"node_path": normalized_path}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        return format_node_with_content_result(query_result)

    except Exception as e:
        logger.exception(f"Error retrieving node for path '{node_path}': {e}")
        return None


# Keep the old function name for backward compatibility
def get_folder_node_by_path(db_manager: AbstractDbManager, folder_path: str) -> Optional[NodeWithContentDto]:
    """
    Retrieves a folder node by its path.

    DEPRECATED: Use get_node_by_path instead. This function is kept for backward compatibility.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID to query
        repo_id: The repository ID to query
        folder_path: The folder path to find

    Returns:
        NodeWithContentDto object or None if not found
    """
    return get_node_by_path(db_manager, folder_path)


def get_direct_children(db_manager: AbstractDbManager, node_id: str) -> List[NodeWithContentDto]:
    """
    Retrieves immediate children of a node.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID to query
        repo_id: The repository ID to query
        node_id: The parent node ID

    Returns:
        List of NodeWithContentDto objects
    """
    try:
        query = get_direct_children_query()
        parameters = {"node_id": node_id}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        return format_children_with_content_result(query_result)

    except Exception as e:
        logger.exception(f"Error retrieving children for node '{node_id}': {e}")
        return []


def get_information_nodes_by_folder_query() -> LiteralString:
    """
    Returns a Cypher query for retrieving the information node for a specific folder.

    Filters information nodes by source_path using ENDS WITH to match the exact folder path.
    This returns only the InformationNode that describes the folder itself.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (info:DOCUMENTATION {entityId: $entity_id, repoId: $repo_id, layer: 'documentation'})
    WHERE info.source_path ENDS WITH $folder_path
    RETURN info.node_id as node_id,
           info.title as title,
           info.content as content,
           info.info_type as info_type,
           info.source_path as source_path,
           info.source_labels as source_labels,  
           info.source_type as source_type,
           info.layer as layer
    ORDER BY info.source_path, info.title
    """


def format_information_nodes_result(query_result: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Formats the result of information nodes query into standardized dictionaries.

    Returns the same format used by InformationNode.as_object() for consistency.

    Args:
        query_result: Raw result from the database query

    Returns:
        List of information node dictionaries
    """
    if not query_result:
        return []

    try:
        information_nodes = []
        for record in query_result:
            # Format as dictionary matching InformationNode.as_object() structure
            info_node = {
                "labels": ["DOCUMENTATION"],
                "attributes": {
                    "node_id": record.get("node_id", ""),
                    "title": record.get("title", ""),
                    "content": record.get("content", ""),
                    "info_type": record.get("info_type", ""),
                    "source_path": record.get("source_path", ""),
                    "source_labels": record.get("source_labels", []),
                    "source_type": record.get("source_type", ""),
                    "layer": record.get("layer", "documentation"),
                    "entityId": record.get("entity_id", ""),
                    "repoId": record.get("repo_id", ""),
                },
            }
            information_nodes.append(info_node)

        return information_nodes

    except Exception as e:
        logger.exception(f"Error formatting information nodes result: {e}")
        return []


def get_information_nodes_by_folder(db_manager: AbstractDbManager, folder_path: str) -> List[Dict[str, Any]]:
    """
    Retrieves information nodes from a specific folder path.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID to query
        repo_id: The repository ID to query
        folder_path: The folder path to filter by (e.g., "src", "components")

    Returns:
        List of information node dictionaries from the specified folder
    """
    try:
        # For folder "src", we want to match the exact folder path ending with "/src"
        # This returns only the InformationNode that describes the folder itself
        normalized_path = folder_path.strip("/")
        folder_path_match = f"/{normalized_path}"

        query = get_information_nodes_by_folder_query()
        parameters = {"folder_path": folder_path_match}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        return format_information_nodes_result(query_result)

    except Exception as e:
        logger.exception(f"Error retrieving information nodes for folder '{folder_path}': {e}")
        return []


def get_root_information_nodes_query() -> LiteralString:
    """
    Returns a Cypher query for retrieving information nodes for root-level code nodes.

    Queries code nodes at level 1 (root level) and traverses to their information nodes
    through DESCRIBES relationships.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (code:NODE {entityId: $entity_id, repoId: $repo_id, level: 1})
    WHERE (code:FILE OR code:FOLDER)
    MATCH (info:DOCUMENTATION)-[:DESCRIBES]->(code)
    WHERE info.layer = 'documentation'
    RETURN info.node_id as node_id,
           info.title as title,
           info.content as content,
           info.info_type as info_type,
           info.source_path as source_path,
           info.source_labels as source_labels,  
           info.source_type as source_type,
           info.layer as layer
    ORDER BY info.source_path, info.title
    """


def get_root_information_nodes(db_manager: AbstractDbManager) -> List[Dict[str, Any]]:
    """
    Retrieves information nodes for all root-level code nodes.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID to query
        repo_id: The repository ID to query

    Returns:
        List of information node dictionaries for root-level code nodes
    """
    try:
        query = get_root_information_nodes_query()
        parameters = {}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        return format_information_nodes_result(query_result)

    except Exception as e:
        logger.exception(f"Error retrieving root information nodes: {e}")
        return []


def get_root_path_query() -> LiteralString:
    """
    Returns a Cypher query for retrieving root-level folders and files.

    Queries code nodes at level 1 (root level) and returns their paths.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (code:NODE {entityId: $entity_id, repoId: $repo_id, level: 0})
    WHERE (code:FILE OR code:FOLDER)
    RETURN code.node_path as path,
           code.name as name,
           labels(code) as labels
    """


def get_root_path(db_manager: AbstractDbManager) -> LiteralString:
    """
    Retrieves paths of all root-level folders and files.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID to query
        repo_id: The repository ID to query

    Returns:
        List of root-level folder and file paths
    """
    try:
        query = get_root_path_query()

        query_result = db_manager.query(cypher_query=query, parameters={})

        return query_result[0].get("path", "") if query_result else ""

    except Exception as e:
        logger.exception(f"Error retrieving root folders and files: {e}")
        return ""


# 4-Layer Architecture Queries for Spec Analysis


def find_independent_workflows_query() -> LiteralString:
    """
    Returns a Cypher query for finding workflow execution traces with documentation nodes.

    This query builds execution traces through code nodes but returns documentation node IDs
    for workflow relationships. The caller_id and callee_id in edges refer to documentation
    node IDs, eliminating the need for separate queries during relationship creation.

    Returns:
        str: The Cypher query string with documentation nodes and their relationships
    """
    return """
    WITH 20 AS maxDepth

    // Entry code node
    MATCH (entry:NODE {
      node_id: $entry_point_id,
      layer: 'code', entityId: $entity_id, repoId: $repo_id
    })

    // Enumerate DFS paths through code nodes
    CALL apoc.path.expandConfig(entry, {
    relationshipFilter: "CALLS>",
    minLevel: 0, maxLevel: maxDepth,
    bfs: false,
    uniqueness: "NODE_PATH"
    }) YIELD path

    // Keep leaves or frontier-at-maxDepth
    WITH entry, path, last(nodes(path)) AS leaf, maxDepth
    WHERE length(path) = 0
    OR coalesce(apoc.node.degree.out(leaf,'CALLS'),0) = 0
    OR length(path) = maxDepth

    // Sort paths by call order
    WITH entry, path,
        [r IN relationships(path) |
            [coalesce(r.startLine, 999999), coalesce(r.referenceCharacter, 999999)]
        ] AS sortKey
    ORDER BY sortKey

    // Work with ordered paths
    WITH entry, collect({ns: nodes(path), rels: relationships(path)}) AS paths

    // For each path, emit only the suffix beyond the LCP with previous path
    UNWIND range(0, size(paths)-1) AS k
    WITH entry, paths[k] AS cur,
        CASE WHEN k = 0 THEN null ELSE paths[k-1] END AS prev

    WITH entry,
        cur.ns   AS ns,
        cur.rels AS rels,
        (CASE WHEN prev IS NULL THEN [] ELSE prev.ns END)   AS prevNs,
        (CASE WHEN prev IS NULL THEN 0  ELSE size(prev.rels) END) AS prevRelsSize

    // Compute LCP length
    WITH entry, ns, rels, prevNs, prevRelsSize,
        CASE
        WHEN prevRelsSize = 0 THEN 0
        ELSE
            coalesce(
            last([
                i IN range(0, apoc.coll.min([size(prevNs), size(ns)]) - 1)
                WHERE prevNs[i].node_id = ns[i].node_id | i
            ]),
            -1
            ) + 1
        END AS lcpLen

    UNWIND range(lcpLen, size(rels)-1) AS i
    WITH entry,
        ns[i]   AS callerCode,
        ns[i+1] AS calleeCode,
        rels[i] AS r,
        i       AS depthWithinPath

    // Find documentation nodes for caller and callee
    OPTIONAL MATCH (callerDoc:DOCUMENTATION {layer: 'documentation'})-[:DESCRIBES]->(callerCode)
    OPTIONAL MATCH (calleeDoc:DOCUMENTATION {layer: 'documentation'})-[:DESCRIBES]->(calleeCode)

    // Collect edges with documentation IDs and code node info
    WITH entry, callerCode, calleeCode, callerDoc, calleeDoc, r, depthWithinPath
    WHERE callerDoc IS NOT NULL AND calleeDoc IS NOT NULL

    WITH entry,
        collect({
        caller_id: callerDoc.node_id, caller: callerCode.name, caller_path: callerCode.path,
        callee_id: calleeDoc.node_id, callee: calleeCode.name, callee_path: calleeCode.path,
        caller_code_node: callerCode, callee_code_node: calleeCode,
        call_line: r.startLine, call_character: r.referenceCharacter,
        depth: depthWithinPath + 1
        }) AS docCalls

    // Get all unique code nodes in execution and their documentation
    WITH entry, docCalls,
        [entry] + [c IN docCalls | c.caller_code_node] + [c IN docCalls | c.callee_code_node] AS allCodeNodes
    
    UNWIND allCodeNodes AS codeNode
    OPTIONAL MATCH (doc:DOCUMENTATION {layer: 'documentation'})-[:DESCRIBES]->(codeNode)
    WITH entry, docCalls, 
        collect(DISTINCT {
            id: codeNode.node_id, 
            name: codeNode.name, 
            path: codeNode.path,
            start_line: codeNode.start_line, 
            end_line: codeNode.end_line,
            doc_node_id: CASE WHEN doc IS NOT NULL THEN doc.node_id ELSE null END,
            depth: CASE WHEN codeNode.node_id = entry.node_id THEN 0 ELSE null END
        }) AS allNodes

    // Filter nodes that have documentation and build execution nodes
    WITH entry, docCalls,
        [n IN allNodes WHERE n.doc_node_id IS NOT NULL] AS documentedNodes

    // Clean up docCalls to remove code node references
    WITH documentedNodes,
        [c IN docCalls | {
            caller_id: c.caller_id, caller: c.caller, caller_path: c.caller_path,
            callee_id: c.callee_id, callee: c.callee, callee_path: c.callee_path,
            call_line: c.call_line, call_character: c.call_character,
            depth: c.depth
        }] AS cleanDocCalls

    RETURN
    documentedNodes AS executionNodes,
    cleanDocCalls AS executionEdges;
    """


def find_independent_workflows(db_manager: AbstractDbManager, entry_point_id: str) -> List[Dict[str, Any]]:
    """
    Finds workflow execution traces with documentation node relationships.

    This function discovers execution flow through code nodes but returns documentation
    node IDs for relationship creation. Each trace represents a complete workflow with
    documentation nodes that can be directly used for creating WORKFLOW_STEP relationships.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID to query
        repo_id: The repository ID to query
        entry_point_id: Single code node ID that is an entry point

    Returns:
        List of workflow dictionaries, each including:
        - entryPointId, entryPointName, entryPointPath: Entry point details (code node)
        - endPointId, endPointName, endPointPath: Final function in call chain (code node)
        - executionNodes: List of code nodes with doc_node_id field for documentation
        - executionEdges: List of edges with caller_id/callee_id as documentation node IDs
        - documentationNodeIds: List of all documentation node IDs in the workflow
        - pathLength: Number of function calls in the chain
        - totalExecutionSteps: Total number of execution steps
        - workflowType: 'documentation_based_workflow' to indicate optimization
        - discoveredBy: 'apoc_dfs_with_documentation'
    """
    try:
        query = find_independent_workflows_query()
        parameters = {"entry_point_id": entry_point_id}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        # Process new documentation-based query result format
        workflows = []
        for record in query_result:
            execution_nodes = record.get("executionNodes", [])
            execution_edges = record.get("executionEdges", [])

            if execution_nodes:
                # Extract entry and end point information (code node details)
                entry_node = execution_nodes[0]
                end_node = execution_nodes[-1] if execution_nodes else entry_node

                # Extract all documentation node IDs from execution nodes and edges
                documentation_node_ids = []

                # Get documentation IDs from execution nodes
                for node in execution_nodes:
                    doc_id = node.get("doc_node_id")
                    if doc_id and doc_id not in documentation_node_ids:
                        documentation_node_ids.append(doc_id)

                # Get documentation IDs from execution edges (should already be included above)
                for edge in execution_edges:
                    caller_doc_id = edge.get("caller_id")  # This is already a documentation ID
                    callee_doc_id = edge.get("callee_id")  # This is already a documentation ID
                    if caller_doc_id and caller_doc_id not in documentation_node_ids:
                        documentation_node_ids.append(caller_doc_id)
                    if callee_doc_id and callee_doc_id not in documentation_node_ids:
                        documentation_node_ids.append(callee_doc_id)

                # Format workflow data in expected structure
                workflow = {
                    "entryPointId": entry_node.get("id", ""),
                    "entryPointName": entry_node.get("name", ""),
                    "entryPointPath": entry_node.get("path", ""),
                    "endPointId": end_node.get("id", ""),
                    "endPointName": end_node.get("name", ""),
                    "endPointPath": end_node.get("path", ""),
                    "executionNodes": execution_nodes,
                    "executionEdges": execution_edges,
                    "documentationNodeIds": documentation_node_ids,  # New field for direct access
                    "pathLength": len(execution_edges),
                    "totalExecutionSteps": len(execution_nodes),
                    "totalEdges": len(execution_edges),
                    "workflowType": "documentation_based_workflow",
                    "discoveredBy": "apoc_dfs_with_documentation",
                }
                workflows.append(workflow)

        logger.info(f"Found {len(workflows)} independent workflows for entry point {entry_point_id}")
        return workflows

    except Exception as e:
        logger.exception(f"Error finding independent workflows for entry point {entry_point_id}: {e}")
        return []


def _create_bridge_edges(
    execution_nodes: List[Dict[str, Any]], execution_edges: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Create bridge edges to connect consecutive DFS paths for continuous execution traces.

    This function addresses the gap problem where consecutive DFS paths are independent,
    preventing LLM agents from understanding complete execution flows. It uses a hybrid
    approach:
    1. Detects path boundaries based on depth decreases
    2. Connects nodes at the same depth level within paths

    Bridge edges have identical structure to CALLS edges and are created only in memory
    (not stored in the database), ensuring database integrity while providing continuous
    traces for LLM analysis.

    Args:
        execution_nodes: Ordered list of execution nodes from DFS traversal
        execution_edges: Original execution edges from the Cypher query

    Returns:
        Combined list of original and bridge edges with proper step ordering

    Example:
        Input: main_diff calls both start and build at depth 1
        Edges: main_diff→start, build→_create_code_hierarchy

        Bridge edge created: start→build (connecting same-depth nodes)
        Result enables continuous trace through all execution paths
    """
    if not execution_nodes or not execution_edges:
        return execution_edges

    if len(execution_nodes) <= 1:
        return execution_edges

    # Create a copy of original edges to avoid modifying input
    all_edges = execution_edges.copy()

    # Build a map of existing edges for quick lookup
    edge_map = set()
    for edge in execution_edges:
        edge_map.add((edge.get("caller_id"), edge.get("callee_id")))

    bridge_edges = []

    # Step 1: Detect path boundaries based on depth decreases
    path_boundaries = [0]  # First node is always start of a path
    for i in range(1, len(execution_nodes)):
        current_depth = execution_nodes[i].get("depth", 0)
        previous_depth = execution_nodes[i - 1].get("depth", 0)

        # New path starts when depth decreases
        if current_depth < previous_depth:
            path_boundaries.append(i)

    # Add end boundary
    path_boundaries.append(len(execution_nodes))

    # Step 2: Create bridges between consecutive paths
    for i in range(len(path_boundaries) - 2):
        path_end_idx = path_boundaries[i + 1] - 1
        path_start_idx = path_boundaries[i + 1]

        if path_end_idx >= 0 and path_start_idx < len(execution_nodes):
            end_node = execution_nodes[path_end_idx]
            start_node = execution_nodes[path_start_idx]

            end_id = end_node.get("id")
            start_id = start_node.get("id")

            # Create bridge between paths if edge doesn't exist
            if (end_id, start_id) not in edge_map and end_id != start_id:
                bridge_edge = {
                    "caller_id": end_id,
                    "caller": end_node.get("name", ""),
                    "caller_path": end_node.get("path", ""),
                    "callee_id": start_id,
                    "callee": start_node.get("name", ""),
                    "callee_path": start_node.get("path", ""),
                    "call_line": None,
                    "call_character": None,
                    "depth": 1,  # Bridge edges connect at top level
                    "step_order": len(all_edges) + len(bridge_edges),
                    "is_bridge_edge": True,
                }
                bridge_edges.append(bridge_edge)
                edge_map.add((end_id, start_id))

    # Step 3: Within each path, connect nodes at the same depth
    for i in range(len(path_boundaries) - 1):
        path_start = path_boundaries[i]
        path_end = path_boundaries[i + 1]

        # Group nodes by depth within this path
        nodes_by_depth: Dict[int, List[Tuple[int, Dict[str, Any]]]] = {}
        for idx in range(path_start, path_end):
            node = execution_nodes[idx]
            depth = node.get("depth", 0)
            if depth not in nodes_by_depth:
                nodes_by_depth[depth] = []
            nodes_by_depth[depth].append((idx, node))

        # Connect nodes at the same depth
        for depth, nodes_at_depth in nodes_by_depth.items():
            if len(nodes_at_depth) < 2:
                continue

            # Sort by index to maintain execution order
            nodes_at_depth.sort(key=lambda x: x[0])

            # Check consecutive nodes at this depth
            for j in range(len(nodes_at_depth) - 1):
                _, current_node = nodes_at_depth[j]
                _, next_node = nodes_at_depth[j + 1]

                current_id = current_node.get("id")
                next_id = next_node.get("id")

                # Skip if edge already exists or nodes are the same
                if (current_id, next_id) in edge_map or current_id == next_id:
                    continue

                # Create bridge edge
                bridge_edge = {
                    "caller_id": current_id,
                    "caller": current_node.get("name", ""),
                    "caller_path": current_node.get("path", ""),
                    "callee_id": next_id,
                    "callee": next_node.get("name", ""),
                    "callee_path": next_node.get("path", ""),
                    "call_line": None,
                    "call_character": None,
                    "depth": depth + 1,  # Depth of the edge is one more than the nodes
                    "step_order": len(all_edges) + len(bridge_edges),
                    "is_bridge_edge": True,
                }

                bridge_edges.append(bridge_edge)
                edge_map.add((current_id, next_id))

    # Add bridge edges to the result
    all_edges.extend(bridge_edges)

    logger.debug(f"Created {len(bridge_edges)} bridge edges for path connectivity")

    return all_edges


def find_code_workflows_query() -> LiteralString:
    """
    Returns a Cypher query for finding workflow execution traces using proper DFS traversal.

    This query builds a complete execution trace by enumerating all DFS paths and creating
    a unified node and edge stream that represents the full workflow execution sequence.

    Returns:
        str: The Cypher query string that returns executionNodes and executionEdges
    """
    return """
    WITH $maxDepth AS maxDepth

    // Entry
    MATCH (entry:NODE {
      node_id: $entry_point_id,
      layer: 'code', 
      entityId: $entity_id, 
      repoId: $repo_id
    })

    // Enumerate DFS paths
    CALL apoc.path.expandConfig(entry, {
      relationshipFilter: "CALLS>",
      minLevel: 0, maxLevel: maxDepth,
      bfs: false,
      uniqueness: "NODE_PATH"
    }) YIELD path

    // Keep leaves or frontier-at-maxDepth (keep 0-length path too; we handle it below)
    WITH entry, path, last(nodes(path)) AS leaf, maxDepth
    WHERE length(path) = 0
       OR coalesce(apoc.node.degree.out(leaf,'CALLS'),0) = 0
       OR length(path) = maxDepth

    // Sort paths by per-edge (line,col) to fix traversal order
    WITH entry, path,
         [r IN relationships(path) |
            [coalesce(r.startLine, 999999), coalesce(r.referenceCharacter, 999999)]
         ] AS sortKey
    ORDER BY sortKey

    // Work with ordered paths
    WITH entry, collect({ns: nodes(path), rels: relationships(path)}) AS paths

    // For each path, emit only the suffix beyond the LCP with previous path
    UNWIND range(0, size(paths)-1) AS k
    WITH entry, paths[k] AS cur,
         CASE WHEN k = 0 THEN null ELSE paths[k-1] END AS prev

    // 1) Alias pieces we need
    WITH entry,
         cur.ns   AS ns,
         cur.rels AS rels,
         (CASE WHEN prev IS NULL THEN [] ELSE prev.ns END)   AS prevNs,
         (CASE WHEN prev IS NULL THEN 0  ELSE size(prev.rels) END) AS prevRelsSize

    // 2) Compute LCP length; if previous path had no rels (0-length), start at 0
    WITH entry, ns, rels, prevNs, prevRelsSize,
         CASE
           WHEN prevRelsSize = 0 THEN 0
           ELSE
             coalesce(
               last([
                 i IN range(0, apoc.coll.min([size(prevNs), size(ns)]) - 1)
                 WHERE prevNs[i].node_id = ns[i].node_id | i
               ]),
               -1
             ) + 1
         END AS lcpLen

    UNWIND range(lcpLen, size(rels)-1) AS i
    WITH entry,
         ns[i]   AS caller,
         ns[i+1] AS callee,
         rels[i] AS r,
         i + 1   AS actualDepthFromEntry  // i+1 gives the actual depth from entry point in the original path

    // Collect the DFS edge stream
    WITH entry,
         collect({
           caller_id: caller.node_id, caller: caller.name, caller_path: caller.path,
           callee_id: callee.node_id, callee: callee.name, callee_path: callee.path,
           call_line: r.startLine, call_character: r.referenceCharacter,
           depth: actualDepthFromEntry
         }) AS calls

    // Collect execution nodes in chronological order (preserving DFS traversal sequence)
    WITH entry, calls
    WITH entry, calls,
         // Build execution nodes list by iterating through calls in order
         REDUCE(
           acc = {
             nodes: [{
               id: entry.node_id, name: entry.name, path: entry.path,
               start_line: entry.start_line, end_line: entry.end_line,
               depth: 0, call_line: '0', call_character: '0'
             }],
             seen: [entry.node_id]
           },
           c IN calls |
           {
             // Add caller if not seen (one level up from edge depth)
             nodes: acc.nodes +
               CASE 
                 WHEN c.caller_id IN acc.seen THEN []
                 ELSE [{
                   id: c.caller_id, name: c.caller, path: c.caller_path,
                   depth: c.depth - 1, call_line: c.call_line, call_character: c.call_character
                 }]
               END +
               // Add callee if not seen (at edge depth)
               CASE 
                 WHEN c.callee_id IN acc.seen THEN []
                 ELSE [{
                   id: c.callee_id, name: c.callee, path: c.callee_path,
                   depth: c.depth, call_line: c.call_line, call_character: c.call_character
                 }]
               END,
             // Track seen node IDs
             seen: acc.seen + 
               CASE WHEN c.caller_id IN acc.seen THEN [] ELSE [c.caller_id] END +
               CASE WHEN c.callee_id IN acc.seen THEN [] ELSE [c.callee_id] END
           }
         ) AS nodeAccumulator
    
    RETURN
      nodeAccumulator.nodes AS executionNodes,
      calls AS executionEdges
    """


def find_code_workflows(
    db_manager: AbstractDbManager, entry_point_id: str, max_depth: int = 20
) -> List[Dict[str, Any]]:
    """
    Finds workflow execution traces using direct code analysis with continuous path sequencing.

    This function provides fast workflow discovery that works directly with code structure,
    creating continuous execution traces for LLM agent analysis. It addresses the DFS path
    sequencing gap problem by adding bridge edges between consecutive paths, ensuring
    complete workflow understanding without database pollution.

    The function performs DFS traversal to discover execution paths, then adds synthetic
    "bridge edges" in memory to connect the last callee of one path to the first callee
    of the next path. This creates continuous execution traces while maintaining database
    integrity (synthetic edges are never stored).

    Bridge edges have identical structure to CALLS edges, ensuring uniform processing
    by downstream LLM agents and analysis tools. They are marked with `is_bridge_edge: True`
    for debugging purposes.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID to query
        repo_id: The repository ID to query
        entry_point_id: Code node ID that is an entry point
        max_depth: Maximum depth for workflow traversal (default: 20)

    Returns:
        List of workflow dictionaries, each including:
        - entryPointId, entryPointName, entryPointPath: Entry point details
        - endPointId, endPointName, endPointPath: Final function in call chain
        - workflowNodes: List of code nodes in execution order
        - workflowEdges: List of CALLS relationships between nodes (includes bridge edges)
        - pathLength: Number of function calls in the chain
        - totalExecutionSteps: Total number of execution steps (includes bridge edges)
        - workflowType: 'dfs_execution_trace_with_edges'
        - discoveredBy: 'apoc_dfs_traversal'

    Note:
        Bridge edges are synthetic connections created in memory only. They connect
        consecutive DFS paths to provide continuous execution traces for LLM analysis
        while preserving database integrity. Bridge edges have `call_line` and
        `call_character` set to None since they don't correspond to actual source code locations.

    Example:
        For DFS paths:
        - Path 1: main → process → validate
        - Path 2: main → cleanup

        A bridge edge is created: validate → cleanup, resulting in continuous flow:
        main → process → validate → cleanup → main → cleanup
    """
    try:
        query = find_code_workflows_query()
        parameters = {
            "entry_point_id": entry_point_id,
            "maxDepth": max_depth,
        }

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        workflows = []
        for record in query_result:
            execution_nodes = record.get("executionNodes", [])
            execution_edges = record.get("executionEdges", [])

            # Create bridge edges to connect consecutive DFS paths for continuous traces
            # This must be done BEFORE assigning step_order to create proper connectivity
            execution_edges = _create_bridge_edges(execution_nodes, execution_edges)

            # Set step_order for all edges (original + bridges) to create continuous sequence
            for index, edge in enumerate(execution_edges):
                edge["step_order"] = index

            if execution_nodes:
                # Extract entry and end point from execution nodes
                entry_node = execution_nodes[0] if execution_nodes else {}
                end_node = execution_nodes[-1] if len(execution_nodes) > 1 else entry_node

                # Build workflow data structure expected by downstream code
                workflow_data = {
                    "entryPointId": entry_node.get("id", ""),
                    "entryPointName": entry_node.get("name", ""),
                    "entryPointPath": entry_node.get("path", ""),
                    "endPointId": end_node.get("id", ""),
                    "endPointName": end_node.get("name", ""),
                    "endPointPath": end_node.get("path", ""),
                    "workflowNodes": execution_nodes,  # Keep as executionNodes data structure
                    "workflowEdges": execution_edges,  # Keep as executionEdges data structure
                    "pathLength": len(execution_edges),
                    "totalExecutionSteps": len(execution_edges),
                    "totalEdges": len(execution_edges),
                    "workflowType": "dfs_execution_trace_with_edges",
                    "discoveredBy": "apoc_dfs_traversal",
                }
                workflows.append(workflow_data)

        logger.info(f"Found {len(workflows)} code-based workflows for entry point {entry_point_id}")
        return workflows

    except Exception as e:
        logger.exception(f"Error finding code workflows for entry point {entry_point_id}: {e}")
        return []


def create_spec_node_query() -> LiteralString:
    """
    Returns a Cypher query for creating a spec node in the specifications layer.

    Returns:
        str: The Cypher query string
    """
    return """
    CREATE (spec:DOCUMENTATION:NODE {
        layer: 'specifications',
        info_type: 'business_spec',
        node_id: $spec_id,
        id: $spec_id,
        entityId: $entity_id,
        repoId: $repo_id,
        title: $spec_name,
        content: $spec_description,
        entry_points: $entry_points,
        scope: $spec_scope,
        framework_context: $framework_context
    })
    RETURN spec.node_id AS spec_id
    """


def create_workflow_node_query() -> LiteralString:
    """
    Returns a Cypher query for creating a workflow node in the workflows layer.

    Returns:
        str: The Cypher query string
    """
    return """
    CREATE (workflow:WORKFLOW:NODE {
        layer: 'workflows',
        info_type: 'business_workflow',
        node_id: $workflow_id,
        id: $workflow_id,
        entityId: $entity_id,
        repoId: $repo_id,
        title: $workflow_title,
        content: $workflow_description,
        entry_point: $entry_point_id
    })
    RETURN workflow.node_id AS workflow_id
    """


def create_workflow_belongs_to_spec_query() -> LiteralString:
    """
    Returns a Cypher query for creating BELONGS_TO_SPEC relationship.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (workflow:WORKFLOW {node_id: $workflow_id, layer: 'workflows'})
    MATCH (spec:DOCUMENTATION {node_id: $spec_id, layer: 'specifications'})
    CREATE (workflow)-[:BELONGS_TO_SPEC]->(spec)
    RETURN workflow.node_id AS workflow_id
    """


def create_documentation_belongs_to_workflow_query() -> LiteralString:
    """
    Returns a Cypher query for creating BELONGS_TO_WORKFLOW relationships.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (workflow:WORKFLOW {node_id: $workflow_id, layer: 'workflows'})
    UNWIND $workflow_code_node_ids AS codeNodeId
    MATCH (doc:DOCUMENTATION {layer: 'documentation'})-[:DESCRIBES]->(code:NODE {id: codeNodeId})
    CREATE (doc)-[:BELONGS_TO_WORKFLOW]->(workflow)
    RETURN count(doc) AS connected_docs
    """


def create_workflow_steps_query() -> LiteralString:
    """
    Returns a Cypher query for creating WORKFLOW_STEP relationships between documentation nodes.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (workflow:WORKFLOW {node_id: $workflow_id, layer: 'workflows'})
    UNWIND range(0, size($workflow_code_node_ids)-2) AS idx
    WITH workflow, idx, $workflow_code_node_ids[idx] AS currentId, $workflow_code_node_ids[idx+1] AS nextId
    MATCH (currentDoc:DOCUMENTATION {layer: 'documentation'})-[:DESCRIBES]->(currentCode:NODE {id: currentId})
    MATCH (currentDoc)-[:BELONGS_TO_WORKFLOW]->(workflow)
    MATCH (nextDoc:DOCUMENTATION {layer: 'documentation'})-[:DESCRIBES]->(nextCode:NODE {id: nextId})
    MATCH (nextDoc)-[:BELONGS_TO_WORKFLOW]->(workflow)
    CREATE (currentDoc)-[:WORKFLOW_STEP {order: idx, workflow_id: workflow.node_id}]->(nextDoc)
    RETURN count(*) AS created_steps
    """


# Hybrid Entry Point Discovery Queries


def find_potential_entry_points_query() -> LiteralString:
    """
    Returns a Cypher query for finding potential entry points using comprehensive relationship checking.

    Entry points are defined as nodes with no incoming relationships from:
    - CALLS (not called by other functions)
    - USES (not used by other code)
    - ASSIGNS (not assigned to variables)
    - IMPORTS (not imported by other modules)

    Uses correct node labels: FUNCTION, CLASS, FILE (METHOD label is never used in codebase)

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (entry:NODE {entityId: $entity_id, repoId: $repo_id, layer: 'code'})
    WHERE (entry:FUNCTION)
      AND NOT ()-[:CALLS|USES|ASSIGNS]->(entry) // No incoming relationships = true entry point
      AND (entry)-[:CALLS|USES|ASSIGNS]->()
      AND NOT entry.name IN ['__init__', '__new__', 'constructor', 'initialize', 'init', 'new']
    RETURN entry.node_id as id, 
           entry.name as name, 
           entry.path as path,
           labels(entry) as labels
    ORDER BY entry.path, entry.name
    LIMIT 200
    """


def find_all_entry_points(db_manager: AbstractDbManager) -> List[Dict[str, Any]]:
    """
    Finds all potential entry points using comprehensive relationship checking.

    This is the database component of hybrid entry point discovery.
    Agent exploration will find additional entry points that this query misses.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID to query
        repo_id: The repository ID to query

    Returns:
        List of entry point dictionaries with id, name, path, labels
    """
    try:
        query = find_potential_entry_points_query()

        query_result = db_manager.query(cypher_query=query, parameters={})

        if not query_result:
            return []

        # Format results for hybrid discovery
        entry_points = []
        for record in query_result:
            entry_point = {
                "id": record.get("id", ""),
                "name": record.get("name", ""),
                "path": record.get("path", ""),
                "labels": record.get("labels", []),
            }
            entry_points.append(entry_point)

        logger.info(f"Database query found {len(entry_points)} potential entry points")
        return entry_points

    except Exception as e:
        logger.exception(f"Error finding entry points with hybrid approach: {e}")
        return []


def find_nodes_by_text_query() -> LiteralString:
    """
    Returns the Cypher query for finding nodes by text content.

    This query searches for nodes in the code layer that contain the specified text
    in their text attribute using the CONTAINS operator.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (n:NODE {entityId: $entity_id, repoId: $repo_id, diff_identifier: $diff_identifier})
    WHERE n.text IS NOT NULL AND n.text CONTAINS $search_text
    AND NOT n:FOLDER
    RETURN 
        n.node_id as id,
        n.name as name,
        labels(n) as label,
        coalesce(n.diff_text, '') as diff_text,
        substring(n.text, 0, 200) as relevant_snippet,
        n.path as node_path
    ORDER BY n.name
    LIMIT 20
    """


def find_nodes_by_text_content(db_manager: AbstractDbManager, search_text: str) -> List[Dict[str, Any]]:
    """
    Find nodes by searching for text content in their text attribute.

    Args:
        db_manager: Database manager instance
        entity_id: Company/entity ID
        repo_id: Repository ID
        diff_identifier: Diff identifier for version control
        search_text: Text to search for

    Returns:
        List of dictionaries with node information
    """
    try:
        logger.info(f"Searching for nodes containing text: '{search_text}'")

        query_params = {
            "search_text": search_text,
        }

        result = db_manager.query(cypher_query=find_nodes_by_text_query(), parameters=query_params)

        nodes = []
        for record in result:
            nodes.append(
                {
                    "id": record.get("id", ""),
                    "name": record.get("name", ""),
                    "label": record.get("label", []),
                    "diff_text": record.get("diff_text", ""),
                    "relevant_snippet": record.get("relevant_snippet", ""),
                    "node_path": record.get("node_path", ""),
                }
            )

        logger.info(f"Found {len(nodes)} nodes containing the text")
        return nodes

    except Exception as e:
        logger.exception(f"Error finding nodes by text content: {e}")
        return []


def get_file_context_by_id_query() -> LiteralString:
    """
    Returns the Cypher query for getting file context by node ID.

    This query returns a chain of (node_id, text) tuples for context assembly.
    Based on the original Neo4jManager implementation.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH path = (ancestor)-[:FUNCTION_DEFINITION|CLASS_DEFINITION*0..]->(n:NODE {node_id: $node_id, entityId: $entity_id, environment: $environment})
    WITH path
    ORDER BY length(path) DESC
    LIMIT 1
    WITH [node IN reverse(nodes(path)) | {id: node.node_id, txt: node.text}] AS chain
    UNWIND chain AS entry
    RETURN entry.node_id AS node_id, entry.txt AS text
    """


def get_file_context_by_id(db_manager: AbstractDbManager, node_id: str) -> List[tuple[str, str]]:
    """
    Get file context by node ID, returning a chain of (node_id, text) tuples.

    Based on the original Neo4jManager.get_file_context_by_id implementation.

    Args:
        db_manager: Database manager instance
        node_id: The node ID to get context for
        company_id: Company ID to filter by

    Returns:
        List of (node_id, text) tuples in order [child, ..., parent]
    """
    try:
        logger.info(f"Getting file context for node: {node_id}")

        query_params = {
            "node_id": node_id,
            "environment": "main",
        }

        result = db_manager.query(cypher_query=get_file_context_by_id_query(), parameters=query_params)

        if not result:
            raise ValueError(f"Node {node_id} not found")

        # Convert results to list of tuples as expected by the original implementation
        chain = [(rec["node_id"], rec["text"]) for rec in result]

        logger.info(f"Built context chain with {len(chain)} elements")
        return chain

    except Exception as e:
        logger.exception(f"Error getting file context for node {node_id}: {e}")
        raise ValueError(f"Node {node_id} not found")


def get_mermaid_graph_query() -> LiteralString:
    """
    Returns the Cypher query for generating a mermaid diagram showing relationships.

    Gets a node and its immediate relationships for diagram generation.
    Based on the original Neo4jManager._build_node_query implementation.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (n:NODE {node_id: $node_id, entityId: $entity_id, environment: $environment})

    OPTIONAL MATCH (n)-[r_out]->(o)
    WHERE o.name IS NOT NULL
    WITH n, labels(n) AS labels,
         COLLECT(
           DISTINCT {
             relationship_type: type(r_out),
             node_id: o.node_id,
             node_name: o.name,
             node_type: labels(o),
             diff_identifier: o.diff_identifier
           }
         ) AS outbound_temp
    WITH n, labels,
         [ rel IN outbound_temp WHERE rel.node_id IS NOT NULL ] AS outbound_relations

    OPTIONAL MATCH (n)<-[r_in]-(i)
    WHERE i.name IS NOT NULL
    WITH n, labels, outbound_relations,
         COLLECT(
           DISTINCT {
             relationship_type: type(r_in),
             node_id: i.node_id,
             node_name: i.name,
             node_type: labels(i),
             diff_identifier: i.diff_identifier
           }
         ) AS inbound_temp
    WITH n, labels, outbound_relations,
         [ rel IN inbound_temp WHERE rel.node_id IS NOT NULL ] AS inbound_relations

    RETURN
      n,
      labels,
      outbound_relations,
      inbound_relations
    """


def get_mermaid_graph(db_manager: AbstractDbManager, node_id: str) -> str:
    """
    Generate a mermaid diagram showing relationships for a given node.

    Based on the original Neo4jManager.get_mermaid_graph implementation.

    Args:
        db_manager: Database manager instance
        node_id: The center node ID
        company_id: Company ID to filter by
        diff_identifier: Diff identifier for version control

    Returns:
        Mermaid diagram as a string
    """
    try:
        logger.info(f"Generating mermaid graph for node: {node_id}")

        query_params = {
            "node_id": node_id,
        }

        result = db_manager.query(cypher_query=get_mermaid_graph_query(), parameters=query_params)

        if not result:
            return f"Node {node_id} not found"

        record = result[0]
        node = record.get("n", {})
        center_name = node.get("name", "Unknown")
        outbound_relations = record.get("outbound_relations", [])
        inbound_relations = record.get("inbound_relations", [])

        # Build mermaid diagram
        mermaid_lines = ["flowchart TD"]
        mermaid_lines.append(f'    {node_id}["{center_name}"]')

        # Add outgoing relationships
        for rel in outbound_relations:
            if rel.get("node_id") and rel.get("relationship_type"):
                target_name = rel.get("node_name", "Unknown")
                relationship = rel.get("relationship_type", "")
                target_id = rel.get("node_id")
                mermaid_lines.append(f'    {node_id} -->|{relationship}| {target_id}["{target_name}"]')

        # Add incoming relationships
        for rel in inbound_relations:
            if rel.get("node_id") and rel.get("relationship_type"):
                source_name = rel.get("node_name", "Unknown")
                relationship = rel.get("relationship_type", "")
                source_id = rel.get("node_id")
                mermaid_lines.append(f'    {source_id}["{source_name}"] -->|{relationship}| {node_id}')

        logger.info(f"Generated mermaid diagram with {len(mermaid_lines)} lines")
        return "\n".join(mermaid_lines)

    except Exception as e:
        logger.exception(f"Error generating mermaid graph for node {node_id}: {e}")
        return f"Error generating diagram for node {node_id}: {str(e)}"


def get_code_by_id_query() -> LiteralString:
    """
    Returns a simple Cypher query for getting node information by node ID.

    This query follows the pattern of simple node_id queries used by other tools.
    Returns basic node attributes like name, labels, text, path, etc.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (n:NODE {node_id: $node_id, entityId: $entity_id})
    RETURN n.node_id as node_id, n.name as name, labels(n) as labels, 
           n.path as path, n.node_path as node_path, n.text as text
    """


def get_code_by_id(db_manager: AbstractDbManager, node_id: str) -> Optional[Dict[str, Any]]:
    """
    Get node information by node ID, returning basic node data.

    Args:
        db_manager: Database manager instance
        node_id: The node ID to get information for
        entity_id: Entity ID to filter by

    Returns:
        Dictionary with node information or None if not found
    """
    try:
        logger.info(f"Getting code by node ID: {node_id}")

        node_id = node_id.strip()
        query_params = {"node_id": node_id}

        result = db_manager.query(cypher_query=get_code_by_id_query(), parameters=query_params)

        if not result:
            logger.warning(f"Node {node_id} not found")
            return None

        # Return the node information
        record = result[0]
        node_data = {
            "node_id": record.get("node_id", ""),
            "name": record.get("name", ""),
            "labels": record.get("labels", []),
            "path": record.get("path", ""),
            "node_path": record.get("node_path", ""),
            "text": record.get("text", ""),
            "diff_identifier": record.get("diff_identifier", ""),
            "level": record.get("level", 0),
            "hashed_id": record.get("hashed_id", ""),
            "layer": record.get("layer", ""),
            "diff_text": record.get("diff_text", ""),
        }

        logger.info(f"Retrieved node information for {node_id}")
        return node_data

    except Exception as e:
        logger.exception(f"Error getting code by node ID {node_id}: {e}")
        return None


# Call Stack Navigation Queries


def get_call_stack_children_query() -> LiteralString:
    """
    Returns a Cypher query for retrieving functions/modules called or used by a function.

    This query finds all nodes that are called or used by the given function through
    CALLS and USES relationships, including the precise call locations.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (parent:NODE {node_id: $node_id, entityId: $entity_id, repoId: $repo_id})
    -[r:CALLS|USES]->(child:NODE)
    RETURN child.node_id as id,
           child.name as name,
           labels(child) as labels,
           child.path as path,
           child.start_line as start_line,
           child.end_line as end_line,
           coalesce(child.text, '') as content,
           type(r) as relationship_type,
           r.start_line as call_line,
           r.referenceCharacter as call_character
    ORDER BY r.start_line, r.referenceCharacter
    """


def get_call_stack_children(db_manager: AbstractDbManager, node_id: str) -> List[NodeWithContentDto]:
    """
    Retrieves functions/modules called or used by a function.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID to query
        repo_id: The repository ID to query
        node_id: The function node ID to get call stack children for

    Returns:
        List of NodeWithContentDto objects representing called/used functions
    """
    try:
        query = get_call_stack_children_query()
        parameters = {"node_id": node_id}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        return format_children_with_content_result(query_result)

    except Exception as e:
        logger.exception(f"Error retrieving call stack children for node '{node_id}': {e}")
        return []


def get_function_cycle_detection_query() -> LiteralString:
    """
    Query to detect if a function participates in a call cycle.

    Returns:
        Cypher query string for cycle detection
    """
    return """
    MATCH path = (start:FUNCTION {node_id: $node_id, entityId: $entity_id, repoId: $repo_id})
    -[:CALLS*1..10]->(start)
    WITH path, [n IN nodes(path) | n.name] as function_names
    RETURN DISTINCT function_names, length(path) as cycle_length
    ORDER BY cycle_length
    LIMIT 10
    """


def get_existing_documentation_for_node_query() -> LiteralString:
    """
    Returns a Cypher query for retrieving existing documentation for a specific code node.

    This query checks if a code node already has documentation through DESCRIBES relationships.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (doc:DOCUMENTATION)-[:DESCRIBES]->(code:NODE {node_id: $node_id, entityId: $entity_id, repoId: $repo_id})
    WHERE doc.layer = 'documentation'
    RETURN doc.node_id as doc_node_id,
           doc.title as title,
           doc.content as content,
           doc.info_type as info_type,
           doc.source_path as source_path,
           doc.source_labels as source_labels,
           doc.source_type as source_type,
           doc.enhanced_content as enhanced_content,
           doc.children_count as children_count
    LIMIT 1
    """


def get_existing_documentation_for_node(db_manager: AbstractDbManager, node_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves existing documentation for a specific code node.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID to query
        repo_id: The repository ID to query
        node_id: The code node ID to check for existing documentation

    Returns:
        Dictionary with documentation data or None if not found
    """
    try:
        query = get_existing_documentation_for_node_query()
        parameters = {"node_id": node_id}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        if not query_result:
            return None

        # Return the documentation data
        record = query_result[0]
        return {
            "doc_node_id": record.get("doc_node_id", ""),
            "title": record.get("title", ""),
            "content": record.get("content", ""),
            "info_type": record.get("info_type", ""),
            "source_path": record.get("source_path", ""),
            "source_labels": record.get("source_labels", []),
            "source_type": record.get("source_type", ""),
            "enhanced_content": record.get("enhanced_content"),
            "children_count": record.get("children_count"),
        }

    except Exception as e:
        logger.exception(f"Error retrieving existing documentation for node '{node_id}': {e}")
        return None


def detect_function_cycles(db_manager: AbstractDbManager, node_id: str) -> List[List[str]]:
    """
    Detect if a function participates in call cycles.

    Args:
        db_manager: Database manager instance
        entity_id: Entity/company ID
        repo_id: Repository ID
        node_id: Function node ID to check for cycles

    Returns:
        List of cycle paths (each path is a list of function names)
    """
    try:
        query = get_function_cycle_detection_query()
        parameters = {"node_id": node_id}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        cycles = []
        for record in query_result:
            cycle_path = record["function_names"]
            cycles.append(cycle_path)

        return cycles

    except Exception as e:
        logger.exception(f"Error detecting cycles for function '{node_id}': {e}")
        return []


def find_entry_points_for_node_path_query() -> LiteralString:
    """
    Find entry points that eventually reach a specific node path.

    Uses reverse traversal: starts from nodes matching node_path,
    traverses upward through CALLS relationships to find nodes
    with no incoming CALLS (true entry points).

    Returns:
        Cypher query string for finding targeted entry points.
    """
    return """
    // Find the target node by path
    MATCH (target:NODE {entityId: $entity_id, repoId: $repo_id, layer: 'code'})
    WHERE target.node_path = $node_path
    
    // Find all nodes that can reach the target through CALLS relationships
    CALL apoc.path.expandConfig(target, {
        relationshipFilter: "<CALLS",
        uniqueness: "NODE_GLOBAL"
    }) YIELD path
    
    WITH last(nodes(path)) AS potential_entry
    
    // Filter to only nodes that have no incoming CALLS relationships (true entry points)
    WHERE NOT (potential_entry)<-[:CALLS]-()
    
    // Return only the node_id
    RETURN DISTINCT potential_entry.node_id as id, potential_entry.node_path as path
    ORDER BY potential_entry.node_id
    """


def find_entry_points_for_node_path(db_manager: AbstractDbManager, node_path: str) -> List[Dict[str, Any]]:
    """
    Find entry points that eventually reach a specific node path.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID to query
        repo_id: The repository ID to query
        node_path: The node path to find entry points for

    Returns:
        List of entry point dictionaries with id.
    """
    try:
        query = find_entry_points_for_node_path_query()
        parameters = {"node_path": node_path}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        entry_points = []
        for record in query_result:
            entry_points.append(
                {
                    "id": record.get("id", ""),
                    "path": record.get("path", ""),
                }
            )

        logger.info(f"Found {len(entry_points)} entry points for node path '{node_path}'")
        return entry_points

    except Exception as e:
        logger.exception(f"Error finding entry points for node path '{node_path}': {e}")
        return []


def get_documentation_nodes_for_embedding_query() -> LiteralString:
    """Query to retrieve documentation nodes for embedding processing.

    Returns:
        Cypher query string for fetching documentation nodes
    """
    return """
    MATCH (n:DOCUMENTATION {entityId: $entity_id, repoId: $repo_id})
    RETURN n.node_id as node_id,
           n.content as content,
           n.info_type as info_type,
           n.source_type as source_type,
           n.source_path as source_path,
           n.source_node_id as source_id,
           n.source_labels as source_labels,
           n.content_embedding as content_embedding
    LIMIT $batch_size
    """


def update_documentation_embeddings_query() -> LiteralString:
    """Query to update embeddings for documentation nodes.

    Returns:
        Cypher query string for updating embeddings
    """
    return """
    UNWIND $updates as update
    MATCH (n:DOCUMENTATION {node_id: update.node_id, entityId: $entity_id, repoId: $repo_id})
    SET n.content_embedding = update.embedding
    RETURN n.node_id as node_id
    """


def get_processable_nodes_query() -> LiteralString:
    """
    Get nodes that are ready for processing in bottom-up order.

    Returns nodes that:
    1. Have 'pending' status
    2. Either have no children OR all children are 'completed'

    This ensures bottom-up processing order where leaf nodes are processed
    before their parents.

    Parameters expected:
        - batch_size: Maximum number of nodes to return
        - entity_id: Entity identifier for the nodes
        - repo_id: Repository identifier for the nodes

    Returns:
        str: The Cypher query string
    """
    return """
    // Find all nodes with pending status
    MATCH (n:NODE {entityId: $entity_id, repoId: $repo_id})
    WHERE n.processing_status = 'pending'
    
    // Check if node is processable (no children or all children completed)
    OPTIONAL MATCH (n)-[:CONTAINS]->(child:NODE)
    WHERE child.entityId = $entity_id 
      AND child.repoId = $repo_id
    WITH n, collect(child) as children
    
    // Filter to only nodes where all children are completed (or no children)
    WHERE size(children) = 0 OR 
          all(child IN children WHERE child.processing_status = 'completed')
    
    RETURN n.path as path, 
           n.name as name,
           n.node_id as node_id,
           labels(n) as labels
    LIMIT $batch_size
    """


def cleanup_processing_query() -> LiteralString:
    """
    Remove all processing status data from nodes.

    Cleans up the processing status fields. This should be called when
    processing completes or is abandoned.

    Parameters expected:
        - entity_id: Entity identifier for the nodes
        - repo_id: Repository identifier for the nodes

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (n:NODE {entityId: $entity_id, repoId: $repo_id})
    WHERE n.processing_status IS NOT NULL
    REMOVE n.processing_status
    RETURN count(n) as cleaned_count
"""


def create_vector_index_query() -> LiteralString:
    """Create Neo4j vector index for documentation embeddings.

    Returns:
        Cypher query string for creating the vector index
    """
    return """
    CREATE VECTOR INDEX documentation_embeddings IF NOT EXISTS
    FOR (n:DOCUMENTATION) 
    ON n.content_embedding
    OPTIONS {indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: 'cosine'
    }}
    """


def vector_similarity_search_query() -> LiteralString:
    """Cypher query for vector similarity search using Neo4j vector index.

    Returns:
        Cypher query string for vector similarity search
    """
    return """
    CALL db.index.vector.queryNodes('documentation_embeddings', $top_k, $query_embedding)
    YIELD node, score
    WHERE score >= $min_similarity
    RETURN node.node_id as node_id,
           node.title as title,
           node.content as content,
           score as similarity_score,
           node.source_path as source_path,
           node.source_labels as source_labels,
           node.info_type as info_type,
           node.enhanced_content as enhanced_content
    ORDER BY score DESC
    """


def hybrid_search_query() -> LiteralString:
    """Cypher query for hybrid search combining vector and keyword similarity.

    Returns:
        Cypher query string for hybrid search
    """
    return """
    // Vector similarity search
    CALL db.index.vector.queryNodes('documentation_embeddings', $top_k, $query_embedding)
    YIELD node, score as vector_score
    
    // Keyword matching
    WITH node, vector_score,
         CASE 
           WHEN toLower(node.content) CONTAINS toLower($keyword) THEN 1.0
           WHEN toLower(node.title) CONTAINS toLower($keyword) THEN 0.8
           ELSE 0.0
         END as keyword_score
    
    // Combine scores with weights
    WITH node, 
         ($vector_weight * vector_score + $keyword_weight * keyword_score) as combined_score
    WHERE combined_score >= $min_score
    
    RETURN node.node_id as node_id,
           node.title as title,
           node.content as content,
           combined_score as similarity_score,
           node.source_path as source_path,
           node.source_labels as source_labels,
           node.info_type as info_type,
           node.enhanced_content as enhanced_content
    ORDER BY combined_score DESC
    LIMIT $limit
    """


def get_node_by_id_query() -> LiteralString:
    """Cypher query to retrieve a node by its ID.

    Returns:
        Cypher query string for retrieving a node by its ID
    """
    return """
        MATCH (n:NODE {node_id: $node_id, repoId: $repo_id, entityId: $entity_id})
        CALL (n) {
            MATCH (n)-[out_rel]->(out_node)
            RETURN collect(DISTINCT {
                node_id: out_node.node_id,
                node_name: out_node.name,
                node_type: labels(out_node),
                relationship_type: type(out_rel)
            })[0..100] AS outbound_relations
        }
        CALL (n) {
            MATCH (in_node)-[in_rel]->(n)
            RETURN collect(DISTINCT {
                node_id: in_node.node_id,
                node_name: in_node.name,
                node_type: labels(in_node),
                relationship_type: type(in_rel)
            })[0..100] AS inbound_relations
        }
        CALL (n) {
            OPTIONAL MATCH (doc_node)-[:DESCRIBES]->(n)
            WHERE 'DOCUMENTATION' IN labels(doc_node)
            RETURN doc_node.content as documentation
            LIMIT 1
        }
        CALL (n) {
            OPTIONAL MATCH (n)-[:BELONGS_TO_WORKFLOW]->(w:NODE)
            WHERE w.layer = 'workflows'
            WITH w, n
            WHERE w IS NOT NULL
            OPTIONAL MATCH (n1:NODE)-[r:WORKFLOW_STEP]->(n2:NODE)
            WHERE r.scopeText CONTAINS ('workflow_id:' + w.node_id)
            WITH w, n, collect(DISTINCT {
                from_id: n1.node_id,
                from_name: n1.name,
                to_id: n2.node_id,
                to_name: n2.name,
                step_order: r.step_order,
                depth: r.depth,
                call_line: r.call_line
            }) as steps
            RETURN collect(DISTINCT {
                workflow_id: w.node_id,
                workflow_name: w.title,
                entry_point_name: w.entry_point_name,
                exit_point_name: w.end_point_name,
                entry_point_path: w.entry_point_path,
                exit_point_path: w.end_point_path,
                total_steps: w.steps,
                execution_chain: steps
            }) as workflows
        }
        RETURN n,
            labels(n) AS labels,
            outbound_relations,
            inbound_relations,
            documentation,
            workflows
        LIMIT 1
    """


def get_node_by_name_and_type_query() -> LiteralString:
    """Cypher query to retrieve nodes by name and type.

    Returns:
        Cypher query string for retrieving nodes by name and type
    """
    return """
        MATCH (n:NODE {repoId: $repo_id, entityId: $entity_id})
        WHERE n.name = $name AND $node_type IN labels(n)
        RETURN n.node_id as node_id, n.name as node_name, labels(n) as node_type,
               n.path as file_path, n.text as code
    """
