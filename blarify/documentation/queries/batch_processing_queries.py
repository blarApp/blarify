"""Cypher queries for batch processing documentation nodes."""

from typing import LiteralString


def get_leaf_nodes_batch_query() -> LiteralString:
    """
    Get batch of leaf nodes (FUNCTION nodes with no CALLS or FILE nodes with no children).

    Returns nodes that:
    - Have no processing_status (implicitly pending)
    - Are either:
      - FUNCTION nodes with no outgoing CALLS relationships
      - FILE nodes with no FUNCTION_DEFINITION, CLASS_DEFINITION relationships and no CALLS
    - Sets them to in_progress and assigns run_id before returning
    """
    return """
    MATCH (n:NODE {entityId: $entity_id, repoId: $repo_id})
    WHERE (n.processing_status IS NULL OR n.processing_run_id <> $run_id) AND NOT n:DOCUMENTATION
      AND (
        // FUNCTION nodes with no calls
        ('FUNCTION' IN labels(n) AND NOT (n)-[:CALLS]->(:NODE))
        OR
        // FILE nodes with no hierarchical children and no calls
        ('FILE' IN labels(n) 
         AND NOT (n)-[:FUNCTION_DEFINITION|CLASS_DEFINITION]->(:NODE)
         AND NOT (n)-[:CALLS]->(:NODE))
      )
    WITH n LIMIT $batch_size
    SET n.processing_status = 'in_progress',
        n.processing_run_id = $run_id
    RETURN n.node_id as id, 
           n.name as name, 
           labels(n) as labels,
           n.path as path, 
           n.start_line as start_line, 
           n.end_line as end_line,
           coalesce(n.text, '') as content
    """


def get_processable_nodes_with_descriptions_query() -> LiteralString:
    """
    Get nodes ready for processing with their children's descriptions.

    Returns nodes where all children have been processed, along with
    the descriptions of those children for context.
    """
    return """
    MATCH (root:NODE {node_id: $root_node_id, entityId: $entity_id, repoId: $repo_id})
    MATCH (root)-[:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION|CALL*1..]->(n:NODE)
    WHERE (n.processing_status IS NULL OR n.processing_run_id <> $run_id) AND NOT n:DOCUMENTATION

    // Check hierarchy children are all processed
    OPTIONAL MATCH (n)-[:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION]->(hier_child:NODE)
    WITH n, collect(DISTINCT hier_child) as hier_children
    WHERE ALL(child IN hier_children WHERE child.processing_status = 'completed' AND child.processing_run_id = $run_id)
    
    // Check call stack children are all processed (for functions)
    OPTIONAL MATCH (n)-[:CALLS|USES]->(call_child:NODE)
    WITH n, hier_children, collect(DISTINCT call_child) as call_children
    WHERE ALL(child IN call_children WHERE child.processing_status = 'completed' AND child.processing_run_id = $run_id)

    // Now get the descriptions - no entity/repo filter needed
    OPTIONAL MATCH (hier_doc:DOCUMENTATION)-[:DESCRIBES]->(hier_child)
    WHERE hier_child IN hier_children
    WITH n, hier_children, call_children,
         collect(DISTINCT {
             id: hier_child.node_id, 
             name: hier_child.name, 
             labels: labels(hier_child),
             path: hier_child.path,
             description: hier_doc.content
         }) as hier_descriptions
    
    OPTIONAL MATCH (call_doc:DOCUMENTATION)-[:DESCRIBES]->(call_child)  
    WHERE call_child IN call_children
    WITH n, hier_descriptions,
         collect(DISTINCT {
             id: call_child.node_id,
             name: call_child.name,
             labels: labels(call_child),
             path: call_child.path,
             description: call_doc.content
         }) as call_descriptions
    
    WITH n, hier_descriptions, call_descriptions
    LIMIT $batch_size
    
    SET n.processing_status = 'in_progress',
        n.processing_run_id = $run_id
    
    RETURN n.node_id as id,
           n.name as name,
           labels(n) as labels,
           n.path as path,
           n.start_line as start_line,
           n.end_line as end_line,
           coalesce(n.text, '') as content,
           hier_descriptions,
           call_descriptions
    """


def mark_nodes_completed_query() -> LiteralString:
    """
    Mark nodes as completed after documentation has been saved.

    Updates processing_status to 'completed' for specified nodes.
    """
    return """
    UNWIND $node_ids as node_id
    MATCH (n:NODE {node_id: node_id, entityId: $entity_id, repoId: $repo_id})
    WHERE n.processing_run_id = $run_id
    SET n.processing_status = 'completed'
    RETURN count(n) as completed_count
    """


def check_pending_nodes_query() -> LiteralString:
    """
    Check if there are any pending nodes remaining under the root node.

    Used to determine if processing is complete for a specific root node.
    Counts nodes without processing_status as pending that are descendants of the root.
    """
    return """
    // First match the root node
    MATCH (root:NODE {node_id: $root_node_id, entityId: $entity_id, repoId: $repo_id})
    // Then find all descendants under this root
    MATCH (root)-[:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION|CALL*0..]->(n:NODE)
    WHERE n.processing_status IS NULL AND NOT n:DOCUMENTATION
    RETURN count(n) as pending_count
    """


def get_leaf_nodes_under_node_query() -> LiteralString:
    """
    Get all leaf nodes that are under a given root node (descendants only).

    Leaf definition mirrors get_leaf_nodes_batch_query:
    - FUNCTION nodes with no outgoing CALLS relationships
    - FILE nodes with no FUNCTION_DEFINITION, CLASS_DEFINITION children and no CALLS

    Scope is limited to descendants of the provided root node within the same
    entity/repo. This query does not update processing state.
    Expected params: $entity_id, $repo_id, $root_node_id
    """
    return """
        // Anchor to the specified root in this entity/repo
        MATCH (root:NODE {node_id: $root_node_id, entityId: $entity_id, repoId: $repo_id})
        // Traverse hierarchical relationships to find descendants
        MATCH (root)-[:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION|CALL*1..]->(n:NODE)
        WHERE (n.processing_status IS NULL OR n.processing_run_id <> $run_id) AND NOT n:DOCUMENTATION
            AND (
                // FUNCTION nodes with no calls
                ('FUNCTION' IN labels(n) AND NOT (n)-[:CALLS]->(:NODE))
                OR
                // FILE nodes with no hierarchical children and no calls
                ('FILE' IN labels(n)
                 AND NOT (n)-[:FUNCTION_DEFINITION|CLASS_DEFINITION]->(:NODE)
                 AND NOT (n)-[:CALLS]->(:NODE))
            )
        WITH n LIMIT $batch_size
        SET n.processing_status = 'in_progress',
            n.processing_run_id = $run_id
        RETURN n.node_id as id,
                     n.name as name,
                     labels(n) as labels,
                     n.path as path,
                     n.start_line as start_line,
                     n.end_line as end_line,
                     coalesce(n.text, '') as content
        """


def get_child_descriptions_query() -> LiteralString:
    """
    Get descriptions for all child nodes of a given parent node.

    This query collects descriptions from all child nodes (direct descendants)
    of the specified parent node.

    Expected params: $entity_id, $repo_id, $parent_node_id
    """
    return """
    MATCH (parent:NODE {node_id: $parent_node_id, entityId: $entity_id, repoId: $repo_id})
    // Find all direct children of the parent node
    MATCH (parent)-[:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION|CALL]->(child:NODE)
    MATCH (child_doc)-[:DESCRIBES]->(child)
    RETURN child.node_id as id,
           child.name as name,
           labels(child) as labels,
           child.path as path,
           child.start_line as start_line,
           child.end_line as end_line,
           child_doc.content as description
    """
