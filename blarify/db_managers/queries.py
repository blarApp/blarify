"""
Database query functions for the semantic documentation layer.

This module contains pre-defined Cypher queries and helper functions for
retrieving structured data from the graph database.
"""

from typing import Dict, List, Any, Optional
import logging

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
    MATCH (info:INFORMATION {entityId: $entity_id, repoId: $repo_id, layer: 'documentation'})
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
                "labels": ["INFORMATION"],
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
    MATCH (info:INFORMATION)-[:DESCRIBES]->(code)
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
