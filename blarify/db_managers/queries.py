"""
Database query functions for the semantic documentation layer.

This module contains pre-defined Cypher queries and helper functions for
retrieving structured data from the graph database.
"""

from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


def get_codebase_skeleton_query() -> str:
    """
    Returns the Cypher query for retrieving the codebase skeleton structure.
    
    This query traverses the graph starting from a root node and returns
    a spanning tree of nodes and relationships up to 2 levels deep, focusing
    on structural elements like files, classes, and functions.
    
    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (root:NODE {entityId: $entity_id, environment: $environment, level: 0})
    CALL apoc.path.spanningTree(root, {
      relationshipFilter: "CONTAINS>|FUNCTION_DEFINITION>|CLASS_DEFINITION>",
      labelFilter: "NODE",
      maxLevel: 2
    })
    YIELD path
    WITH nodes(path) AS nodeList, relationships(path) AS relList
    RETURN
    [ n IN nodeList |
        {
            name: n.name,
            type: labels(n),
            node_id: coalesce(n.node_id, "N/A"),
            path: n.path
        }
    ] AS nodes_info,
    [
      r IN relList |
        {
            type: type(r),
            start_node_id: startNode(r).node_id,
            end_node_id: endNode(r).node_id
        }
    ] AS path_info
    """


def format_codebase_skeleton_result(query_result: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Formats the result of the codebase skeleton query into a structured format.
    
    Args:
        query_result: Raw result from the database query
        
    Returns:
        Dict containing formatted nodes and relationships
    """
    if not query_result:
        return {"nodes": [], "relationships": []}
    
    try:
        # Extract nodes and relationships from the first record
        record = query_result[0]
        nodes = record.get("nodes_info", [])
        relationships = record.get("path_info", [])
        
        # Format nodes
        formatted_nodes = []
        for node in nodes:
            formatted_node = {
                "name": node.get("name", ""),
                "type": node.get("type", []),
                "node_id": node.get("node_id", ""),
                "path": node.get("path", "")
            }
            formatted_nodes.append(formatted_node)
        
        # Format relationships
        formatted_relationships = []
        for rel in relationships:
            formatted_rel = {
                "type": rel.get("type", ""),
                "start_node_id": rel.get("start_node_id", ""),
                "end_node_id": rel.get("end_node_id", "")
            }
            formatted_relationships.append(formatted_rel)
        
        return {
            "nodes": formatted_nodes,
            "relationships": formatted_relationships
        }
        
    except (KeyError, IndexError) as e:
        logger.error(f"Error formatting codebase skeleton result: {e}")
        return {"nodes": [], "relationships": []}


def get_node_details_query() -> str:
    """
    Returns a query for retrieving detailed information about a specific node.
    
    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (n:NODE {node_id: $node_id, entityId: $entity_id})
    RETURN n.name as name,
           labels(n) as type,
           n.node_id as node_id,
           n.path as path,
           n.start_line as start_line,
           n.end_line as end_line,
           n.content as content,
           n.environment as environment
    """


def get_node_relationships_query() -> str:
    """
    Returns a query for retrieving relationships of a specific node.
    
    Returns:
        str: The Cypher query string
    """
    return """
    MATCH (n:NODE {node_id: $node_id, entityId: $entity_id})
    OPTIONAL MATCH (n)-[r]->(related:NODE)
    RETURN type(r) as relationship_type,
           related.node_id as related_node_id,
           related.name as related_name,
           labels(related) as related_type,
           r.scopeText as scope_text,
           'outgoing' as direction
    UNION
    MATCH (n:NODE {node_id: $node_id, entityId: $entity_id})
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
            "environment": record.get("environment", "")
        }
    except (KeyError, IndexError) as e:
        logger.error(f"Error formatting node details result: {e}")
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
                    "direction": record.get("direction", "")
                }
                formatted_relationships.append(formatted_rel)
        
        return formatted_relationships
        
    except (KeyError, IndexError) as e:
        logger.error(f"Error formatting node relationships result: {e}")
        return []


def get_codebase_skeleton(db_manager, entity_id: str, environment: str = "default") -> str:
    """
    Retrieves the codebase skeleton structure and formats it as a structured string.
    
    Args:
        db_manager: Database manager instance
        entity_id: The entity ID to query
        environment: The environment to query (default: "default")
        
    Returns:
        Formatted string representation of the codebase structure
    """
    try:
        # Get the query and execute it
        query = get_codebase_skeleton_query()
        parameters = {"entity_id": entity_id, "environment": environment}
        
        query_result = db_manager.query(query, parameters)
        
        # Format the result
        formatted_result = format_codebase_skeleton_result(query_result)
        
        # Convert to structured string representation
        return format_skeleton_as_string(formatted_result)
        
    except Exception as e:
        logger.error(f"Error retrieving codebase skeleton: {e}")
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
    hierarchy = {
        "roots": root_nodes,
        "children": children,
        "nodes": node_lookup
    }
    
    return hierarchy


def format_hierarchy_tree(hierarchy: Dict[str, Any], indent: int = 0) -> List[str]:
    """
    Formats hierarchy as a tree structure.
    
    Args:
        hierarchy: Hierarchical structure dictionary
        indent: Current indentation level
        
    Returns:
        List of formatted tree lines
    """
    output = []
    
    def format_node(node_id: str, level: int = 0) -> List[str]:
        node = hierarchy["nodes"].get(node_id)
        if not node:
            return []
        
        # Format node information
        indent_str = "  " * level
        node_types = node.get("type", [])
        type_str = "/".join(node_types) if node_types else "NODE"
        
        path = node.get("path", "")
        name = node.get("name", "")
        
        # Create display name
        if path and name:
            display_name = f"{name} ({path})"
        elif name:
            display_name = name
        elif path:
            display_name = path
        else:
            display_name = node_id
        
        lines = [f"{indent_str}├── [{type_str}] {display_name}"]
        
        # Add children
        children = hierarchy["children"].get(node_id, [])
        for child_id in children:
            lines.extend(format_node(child_id, level + 1))
        
        return lines
    
    # Format all root nodes
    for root_id in hierarchy["roots"]:
        output.extend(format_node(root_id))
    
    return output