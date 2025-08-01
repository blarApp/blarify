"""
Database query functions for the semantic documentation layer.

This module contains pre-defined Cypher queries and helper functions for
retrieving structured data from the graph database.
"""

from typing import Dict, List, Any, Optional
import logging
import json

from blarify.db_managers.db_manager import AbstractDbManager
from blarify.db_managers.dtos.leaf_node_dto import LeafNodeDto
from blarify.db_managers.dtos.node_with_content_dto import NodeWithContentDto

logger = logging.getLogger(__name__)


def get_codebase_skeleton_query() -> str:
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


def get_node_details_query() -> str:
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


def get_node_relationships_query() -> str:
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


def get_all_leaf_nodes_query() -> str:
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


def get_folder_leaf_nodes_query() -> str:
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


def get_node_by_path_query() -> str:
    """
    Returns a Cypher query for retrieving a node (folder or file) by its path.

    This query finds the specific folder or file node that matches the given path.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (n:NODE {entityId: $entity_id, repoId: $repo_id})
    WHERE n.path CONTAINS $folder_path AND (n:FOLDER OR n:FILE)
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


def get_direct_children_query() -> str:
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


def get_node_by_path(
    db_manager: AbstractDbManager, entity_id: str, repo_id: str, node_path: str
) -> Optional[NodeWithContentDto]:
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
        parameters = {"entity_id": entity_id, "repo_id": repo_id, "folder_path": normalized_path}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        return format_node_with_content_result(query_result)

    except Exception as e:
        logger.exception(f"Error retrieving node for path '{node_path}': {e}")
        return None


# Keep the old function name for backward compatibility
def get_folder_node_by_path(
    db_manager: AbstractDbManager, entity_id: str, repo_id: str, folder_path: str
) -> Optional[NodeWithContentDto]:
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
    return get_node_by_path(db_manager, entity_id, repo_id, folder_path)


def get_direct_children(
    db_manager: AbstractDbManager, entity_id: str, repo_id: str, node_id: str
) -> List[NodeWithContentDto]:
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
        parameters = {"entity_id": entity_id, "repo_id": repo_id, "node_id": node_id}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        return format_children_with_content_result(query_result)

    except Exception as e:
        logger.exception(f"Error retrieving children for node '{node_id}': {e}")
        return []


def get_information_nodes_by_folder_query() -> str:
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


def get_information_nodes_by_folder(
    db_manager: AbstractDbManager, entity_id: str, repo_id: str, folder_path: str
) -> List[Dict[str, Any]]:
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
        parameters = {"entity_id": entity_id, "repo_id": repo_id, "folder_path": folder_path_match}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        return format_information_nodes_result(query_result)

    except Exception as e:
        logger.exception(f"Error retrieving information nodes for folder '{folder_path}': {e}")
        return []


def get_root_information_nodes_query() -> str:
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


def get_root_information_nodes(db_manager: AbstractDbManager, entity_id: str, repo_id: str) -> List[Dict[str, Any]]:
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
        parameters = {"entity_id": entity_id, "repo_id": repo_id}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        return format_information_nodes_result(query_result)

    except Exception as e:
        logger.exception(f"Error retrieving root information nodes: {e}")
        return []


def get_root_folders_and_files_query() -> str:
    """
    Returns a Cypher query for retrieving root-level folders and files.

    Queries code nodes at level 1 (root level) and returns their paths.

    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (code:NODE {entityId: $entity_id, repoId: $repo_id, level: 1})
    WHERE (code:FILE OR code:FOLDER)
    RETURN code.path as path,
           code.name as name,
           labels(code) as labels
    ORDER BY code.path
    """


def get_root_folders_and_files(db_manager: AbstractDbManager, entity_id: str, repo_id: str) -> List[str]:
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
        query = get_root_folders_and_files_query()
        parameters = {"entity_id": entity_id, "repo_id": repo_id}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        # Extract paths from the query result
        root_paths = []
        for record in query_result:
            path = record.get("path", "")
            if path:
                root_paths.append(path)

        return root_paths

    except Exception as e:
        logger.exception(f"Error retrieving root folders and files: {e}")
        return []


# 4-Layer Architecture Queries for Spec Analysis


def find_independent_workflows_query() -> str:
    """
    Returns a Cypher query for finding a single complete execution trace from an entry point.

    This query builds ONE comprehensive execution trace that includes ALL functions
    called by the entry point, creating a single unified call stack trace like:
    entry_point() -> all_functions_it_calls() -> their_functions() -> etc.

    Returns:
        str: The Cypher query string
    """
    return """
    // Find the entry point
    MATCH (entry:NODE {node_id: $entry_point_id, layer: 'code', entityId: $entity_id, repoId: $repo_id})
    
    // Expand with DFS; avoid revisiting nodes (NODE_PATH) to prevent recursion loops
    CALL apoc.path.expandConfig(entry, {
      relationshipFilter: "CALLS>",
      minLevel: 0, maxLevel: 20,
      bfs: false,                      // DFS traversal
      uniqueness: "NODE_PATH"
    }) YIELD path
    
    // Keep only root→leaf paths (or the 0-length path if there are no calls)
    WITH path
    WHERE length(path) = 0 OR NOT (last(nodes(path)))-[:CALLS]->()
    
    // Build a lexicographic ordering key from call-site (line/column) pairs.
    // This yields the same ordering as doing DFS while choosing the next edge
    // by the smallest (startLine, referenceCharacter) at each branch.
    WITH path,
         relationships(path) AS rels,
         nodes(path) AS pathNodes
    WITH path, rels, pathNodes,
         [r IN rels | toString(coalesce(r.startLine, 999999)) + "/" +
                      toString(coalesce(r.referenceCharacter, 999999))] AS sortKey
    ORDER BY sortKey  // lexicographic list ordering ≈ DFS-by-callsite order
    LIMIT 1  // Get the first (lexicographically smallest) execution path
    
    // Create execution trace with proper DFS ordering
    WITH pathNodes, rels, path,
         [i IN range(0, size(pathNodes)-1) | {
           id: pathNodes[i].node_id,
           name: pathNodes[i].name,
           path: pathNodes[i].path,
           labels: labels(pathNodes[i]),
           start_line: pathNodes[i].start_line,
           end_line: pathNodes[i].end_line,
           call_order: i,
           execution_step: i + 1,
           call_depth: i,
           call_line: CASE WHEN i < size(rels) THEN rels[i].startLine ELSE null END,
           call_character: CASE WHEN i < size(rels) THEN rels[i].referenceCharacter ELSE null END
         }] as executionTrace
    
    // Return DFS execution trace
    RETURN {
        entryPointId: pathNodes[0].node_id,
        entryPointName: pathNodes[0].name,
        entryPointPath: pathNodes[0].path,
        endPointId: last(pathNodes).node_id,
        endPointName: last(pathNodes).name,
        endPointPath: last(pathNodes).path,
        workflowNodes: executionTrace,
        pathLength: length(path),
        totalExecutionSteps: size(pathNodes),
        workflowType: 'dfs_execution_trace',
        discoveredBy: 'apoc_dfs_traversal'
    } AS workflow
    """


def find_independent_workflows(
    db_manager: AbstractDbManager, entity_id: str, repo_id: str, entry_point_id: str
) -> List[Dict[str, Any]]:
    """
    Finds complete execution traces starting from a single entry point.

    This function discovers the ENTIRE execution flow by following CALLS relationships
    to build complete call stack traces. Each trace represents the full sequence of
    function calls that would occur when the entry point is invoked.

    Similar to the Julia example:
    main() -> first_function() -> second_function() -> third_function() -> ... (and back)

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID to query
        repo_id: The repository ID to query
        entry_point_id: Single code node ID that is an entry point

    Returns:
        List of execution trace dictionaries, each including:
        - entryPointId, entryPointName, entryPointPath: Entry point details
        - endPointId, endPointName, endPointPath: Final function in call chain
        - workflowNodes: Ordered list of all functions in execution sequence
        - pathLength: Number of function calls in the chain
        - totalExecutionSteps: Total number of execution steps
        - workflowType: 'execution_trace' to indicate complete call flow
        - discoveredBy: 'complete_call_flow'
    """
    if entry_point_id == "93f77d77e170620b2d73c5caca19c49d":
        logger.info("hi")

    try:
        query = find_independent_workflows_query()
        parameters = {"entity_id": entity_id, "repo_id": repo_id, "entry_point_id": entry_point_id}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        # Extract workflows
        workflows = []
        for record in query_result:
            workflow = record.get("workflow", {})
            if workflow:
                workflows.append(workflow)

        logger.info(f"Found {len(workflows)} independent workflows for entry point {entry_point_id}")
        return workflows

    except Exception as e:
        logger.exception(f"Error finding independent workflows for entry point {entry_point_id}: {e}")
        return []


def create_spec_node_query() -> str:
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


def create_spec_node(
    db_manager: AbstractDbManager, entity_id: str, repo_id: str, spec_data: Dict[str, Any]
) -> Optional[str]:
    """
    Creates a spec node in the specifications layer.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID
        repo_id: The repository ID
        spec_data: Dictionary containing spec information

    Returns:
        The created spec node ID or None if creation failed
    """
    try:
        import uuid

        spec_id = f"spec_{uuid.uuid4().hex[:8]}"

        # Convert entry points to a simple list for storage
        entry_points_data = []
        for ep in spec_data.get("entry_points", []):
            if isinstance(ep, dict):
                entry_points_data.append(
                    {
                        "node_id": ep.get("node_id", ""),
                        "name": ep.get("name", ""),
                        "source_node_id": ep.get("source_node_id", ""),
                    }
                )
            else:
                # Handle legacy string format
                entry_points_data.append({"name": str(ep), "node_id": "", "source_node_id": ""})

        query = create_spec_node_query()
        parameters = {
            "entity_id": entity_id,
            "repo_id": repo_id,
            "spec_id": spec_id,
            "spec_name": spec_data.get("name", ""),
            "spec_description": spec_data.get("description", ""),
            "entry_points": json.dumps(entry_points_data),  # Store as JSON string
            "spec_scope": spec_data.get("scope", ""),
            "framework_context": spec_data.get("framework_context", ""),
        }

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        if query_result and len(query_result) > 0:
            logger.info(f"Created spec node: {spec_id}")
            return spec_id

        return None

    except Exception as e:
        logger.exception(f"Error creating spec node: {e}")
        return None


def create_workflow_node_query() -> str:
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


def create_workflow_belongs_to_spec_query() -> str:
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


def create_documentation_belongs_to_workflow_query() -> str:
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


def create_workflow_steps_query() -> str:
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


def create_workflow_with_relationships(
    db_manager: AbstractDbManager, entity_id: str, repo_id: str, spec_id: str, workflow_data: Dict[str, Any]
) -> Optional[str]:
    """
    Creates a workflow node and all its relationships in the 4-layer architecture.
    This function executes multiple queries in sequence for better error handling.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID
        repo_id: The repository ID
        spec_id: The spec node ID this workflow belongs to
        workflow_data: Dictionary containing workflow information including:
            - entryPointId: The entry point code node ID
            - entryPointName: Name of the entry point
            - workflowNodes: List of nodes in the workflow execution path

    Returns:
        The created workflow node ID or None if creation failed
    """
    try:
        import uuid

        workflow_id = f"workflow_{uuid.uuid4().hex[:8]}"

        # Extract code node IDs in execution order
        workflow_nodes = workflow_data.get("workflowNodes", [])
        workflow_code_node_ids = [node["id"] for node in workflow_nodes]

        # Create workflow title and description
        entry_name = workflow_data.get("entryPointName", "Unknown")
        workflow_title = f"Workflow: {entry_name}"
        workflow_description = f"Business workflow starting from {entry_name} with {len(workflow_nodes)} steps"

        # Step 1: Create workflow node
        create_node_params = {
            "entity_id": entity_id,
            "repo_id": repo_id,
            "workflow_id": workflow_id,
            "workflow_title": workflow_title,
            "workflow_description": workflow_description,
            "entry_point_id": workflow_data.get("entryPointId"),
        }

        result = db_manager.query(cypher_query=create_workflow_node_query(), parameters=create_node_params)

        if not result or not result[0].get("workflow_id"):
            logger.error("Failed to create workflow node")
            return None

        # Step 2: Connect workflow to spec
        spec_rel_params = {"workflow_id": workflow_id, "spec_id": spec_id}

        db_manager.query(cypher_query=create_workflow_belongs_to_spec_query(), parameters=spec_rel_params)

        # Step 3: Connect documentation nodes to workflow
        doc_rel_params = {"workflow_id": workflow_id, "workflow_code_node_ids": workflow_code_node_ids}

        result = db_manager.query(
            cypher_query=create_documentation_belongs_to_workflow_query(), parameters=doc_rel_params
        )

        connected_docs = result[0].get("connected_docs", 0) if result else 0
        logger.info(f"Connected {connected_docs} documentation nodes to workflow {workflow_id}")

        # Step 4: Create workflow steps
        if len(workflow_code_node_ids) > 1:
            steps_params = {"workflow_id": workflow_id, "workflow_code_node_ids": workflow_code_node_ids}

            result = db_manager.query(cypher_query=create_workflow_steps_query(), parameters=steps_params)

            created_steps = result[0].get("created_steps", 0) if result else 0
            logger.info(f"Created {created_steps} workflow steps for workflow {workflow_id}")

        logger.info(f"Successfully created workflow {workflow_id} for entry point {entry_name}")
        return workflow_id

    except Exception as e:
        logger.exception(f"Error creating workflow with relationships: {e}")
        return None


def get_spec_with_layers_query() -> str:
    """
    Returns a Cypher query for retrieving a complete spec with all 4 layers.

    Returns:
        str: The Cypher query string
    """
    return """
    // Get spec node
    MATCH (spec:DOCUMENTATION {layer: 'specifications', node_id: $spec_id})
    
    // Get workflows belonging to this spec
    OPTIONAL MATCH (workflow:WORKFLOW {layer: 'workflows'})-[:BELONGS_TO_SPEC]->(spec)
    
    // Get documentation nodes belonging to workflows
    OPTIONAL MATCH (doc:DOCUMENTATION {layer: 'documentation'})-[:BELONGS_TO_WORKFLOW]->(workflow)
    
    // Get code nodes described by documentation
    OPTIONAL MATCH (doc)-[:DESCRIBES]->(code:NODE {layer: 'code'})
    
    // Get workflow steps
    OPTIONAL MATCH (doc)-[step:WORKFLOW_STEP]->(nextDoc:DOCUMENTATION)
    WHERE step.workflow_id = workflow.node_id
    
    RETURN spec,
           collect(DISTINCT workflow) AS workflows,
           collect(DISTINCT {
               doc: doc,
               code: code,
               workflow_id: workflow.node_id,
               next_doc: nextDoc,
               step_order: step.order
           }) AS documentation_details
    """


def get_spec_with_layers(db_manager: AbstractDbManager, entity_id: str, repo_id: str, spec_id: str) -> Dict[str, Any]:
    """
    Retrieves a complete spec with all 4 layers of the architecture.

    Args:
        db_manager: Database manager instance
        entity_id: The entity ID
        repo_id: The repository ID
        spec_id: The spec node ID to retrieve

    Returns:
        Dictionary containing the spec and all its layers
    """
    try:
        query = get_spec_with_layers_query()
        parameters = {"entity_id": entity_id, "repo_id": repo_id, "spec_id": spec_id}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

        if not query_result:
            return {}

        # Format the result
        result = query_result[0]
        return {
            "spec": result.get("spec"),
            "workflows": result.get("workflows", []),
            "documentation_details": result.get("documentation_details", []),
        }

    except Exception as e:
        logger.exception(f"Error retrieving spec with layers: {e}")
        return {}


# Hybrid Entry Point Discovery Queries


def find_potential_entry_points_query() -> str:
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


def find_all_entry_points_hybrid(db_manager: AbstractDbManager, entity_id: str, repo_id: str) -> List[Dict[str, Any]]:
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
        parameters = {"entity_id": entity_id, "repo_id": repo_id}

        query_result = db_manager.query(cypher_query=query, parameters=parameters)

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


def find_nodes_by_text_query() -> str:
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


def find_nodes_by_text_content(
    db_manager: AbstractDbManager, entity_id: str, repo_id: str, diff_identifier: str, search_text: str
) -> List[Dict[str, Any]]:
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
            "entity_id": entity_id,
            "repo_id": repo_id,
            "diff_identifier": diff_identifier,
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


def get_file_context_by_id_query() -> str:
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


def get_file_context_by_id(db_manager: AbstractDbManager, node_id: str, company_id: str) -> List[tuple[str, str]]:
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
            "entity_id": company_id,
            "environment": "production",  # Using default environment
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


def get_mermaid_graph_query() -> str:
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


def get_mermaid_graph(db_manager: AbstractDbManager, node_id: str, company_id: str, diff_identifier: str) -> str:
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
            "entity_id": company_id,
            "environment": "production",  # Using default environment
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


def get_code_by_id_query() -> str:
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


def get_code_by_id(db_manager: AbstractDbManager, node_id: str, entity_id: str) -> Optional[Dict[str, Any]]:
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
        query_params = {"node_id": node_id, "entity_id": entity_id}

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


def get_call_stack_children_query() -> str:
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


def get_call_stack_children(
    db_manager: AbstractDbManager, entity_id: str, repo_id: str, node_id: str
) -> List[NodeWithContentDto]:
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
        parameters = {"entity_id": entity_id, "repo_id": repo_id, "node_id": node_id}
        
        query_result = db_manager.query(cypher_query=query, parameters=parameters)
        
        return format_children_with_content_result(query_result)
        
    except Exception as e:
        logger.exception(f"Error retrieving call stack children for node '{node_id}': {e}")
        return []


def get_function_cycle_detection_query() -> str:
    """
    Query to detect if a function participates in a call cycle.
    
    Returns:
        Cypher query string for cycle detection
    """
    return """
    MATCH path = (start:NODE {node_id: $node_id, entityId: $entity_id, repoId: $repo_id})
    -[:CALLS|USES*1..10]->
    (start)
    WHERE "FUNCTION" IN labels(start)
    WITH path, [n IN nodes(path) | n.name] as function_names
    RETURN DISTINCT function_names, length(path) as cycle_length
    ORDER BY cycle_length
    LIMIT 10
    """


def get_existing_documentation_for_node_query() -> str:
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


def get_existing_documentation_for_node(
    db_manager: AbstractDbManager, entity_id: str, repo_id: str, node_id: str
) -> Optional[Dict[str, Any]]:
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
        parameters = {"entity_id": entity_id, "repo_id": repo_id, "node_id": node_id}
        
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


def detect_function_cycles(
    db_manager: AbstractDbManager, entity_id: str, repo_id: str, node_id: str
) -> List[List[str]]:
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
        parameters = {"entity_id": entity_id, "repo_id": repo_id, "node_id": node_id}
        
        query_result = db_manager.query(cypher_query=query, parameters=parameters)
        
        cycles = []
        for record in query_result:
            cycle_path = record["function_names"]
            cycles.append(cycle_path)
        
        return cycles
        
    except Exception as e:
        logger.exception(f"Error detecting cycles for function '{node_id}': {e}")
        return []
