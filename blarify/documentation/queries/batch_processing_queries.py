"""Cypher queries for batch processing documentation nodes."""

from typing import LiteralString


def get_leaf_nodes_batch_query() -> LiteralString:
    """
    Get batch of leaf nodes (FUNCTION nodes with no CALLS, FILE nodes with no children, or FOLDER nodes with no children).

    Returns nodes that:
    - Have no processing_status (implicitly pending)
    - Are either:
      - FUNCTION nodes with no outgoing CALLS relationships
      - FILE nodes with no FUNCTION_DEFINITION, CLASS_DEFINITION relationships and no CALLS
      - FOLDER nodes with no CONTAINS relationships
    - Sets them to in_progress and assigns run_id before returning
    """
    return """
    MATCH (n:NODE {entityId: $entity_id, repoId: $repo_id})
    WHERE (n.processing_status IS NULL OR n.processing_run_id <> $run_id) AND NOT n:DOCUMENTATION
      AND (
        // FUNCTION nodes with no calls
        ('FUNCTION' IN labels(n) AND NOT (n)-[:CALLS]->(:NODE))
        OR
        ('CLASS' IN labels(n) 
          AND NOT (n)-[:CALLS]->(:NODE)
          AND NOT (n)-[:FUNCTION_DEFINITION|CLASS_DEFINITION]->(:NODE))
        OR
        // FILE nodes with no hierarchical children and no calls
        ('FILE' IN labels(n) 
         AND NOT (n)-[:FUNCTION_DEFINITION|CLASS_DEFINITION]->(:NODE)
         AND NOT (n)-[:CALLS]->(:NODE))
        OR
        // FOLDER nodes with no hierarchical children
        ('FOLDER' IN labels(n) 
         AND NOT (n)-[:CONTAINS]->(:NODE))
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
    MATCH (root)-[:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION|CALL*0..]->(n:NODE)
    WHERE (n.processing_status IS NULL OR n.processing_run_id <> $run_id) AND NOT n:DOCUMENTATION

    // Check hierarchy children are all processed
    OPTIONAL MATCH (n)-[:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION]->(hier_child:NODE)
    WITH n, collect(DISTINCT hier_child) as hier_children
    WHERE ALL(child IN hier_children WHERE child.processing_status = 'completed' AND child.processing_run_id = $run_id)
    
    // Check call stack children are all processed (for functions)
    OPTIONAL MATCH (n)-[:CALLS]->(call_child:NODE)
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
    - FOLDER nodes with no CONTAINS children

    Scope is limited to descendants of the provided root node within the same
    entity/repo. This query does not update processing state.
    Expected params: $entity_id, $repo_id, $root_node_id
    """
    return """
        // Anchor via composite index (create it if you don't have it)
MATCH (root:NODE {node_id: $root_node_id, entityId: $entity_id, repoId: $repo_id})

CALL apoc.path.expandConfig(root, {
  relationshipFilter: 'CONTAINS>|FUNCTION_DEFINITION>|CLASS_DEFINITION>|CALLS>',
  minLevel: 1,
  maxLevel: 4,
  bfs: true,
  uniqueness: 'NODE_GLOBAL',
  labelFilter: '-DOCUMENTATION',
  filterStartNode: true
})
YIELD path
WITH last(nodes(path)) AS n
WHERE (n.processing_status IS NULL OR n.processing_run_id <> $run_id)
  AND (
    (n:FUNCTION AND NOT EXISTS { MATCH (n)-[:CALLS]->(:NODE) })
    OR
    (n:FILE
      AND NOT EXISTS { MATCH (n)-[:FUNCTION_DEFINITION|CLASS_DEFINITION]->(:NODE) }
      AND NOT EXISTS { MATCH (n)-[:CALLS]->(:NODE) })
    OR
    (n:FOLDER AND NOT EXISTS { MATCH (n)-[:CONTAINS]->(:NODE) })
  )
WITH DISTINCT n
LIMIT $batch_size

SET n.processing_status = 'in_progress',
    n.processing_run_id = $run_id
RETURN n.node_id    AS id,
       n.name       AS name,
       labels(n)    AS labels,
       n.path       AS path,
       n.start_line AS start_line,
       n.end_line   AS end_line,
       coalesce(n.text, '') AS content;
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


def get_remaining_pending_functions_query() -> LiteralString:
    """
    Get all pending FUNCTION nodes with their child descriptions.

    This query is used when normal processing is blocked (likely due to cycles).
    It retrieves pending FUNCTION nodes along with descriptions from any completed children,
    without requiring ALL children to be completed.

    Key difference from get_processable_nodes_with_descriptions_query:
    - Does NOT check if all children are completed
    - Only processes FUNCTION nodes
    - Returns same structure (hier_descriptions and call_descriptions)
    """
    return """
    MATCH (root:NODE {node_id: $root_node_id, entityId: $entity_id, repoId: $repo_id})
    MATCH (root)-[:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION|CALL*0..]->(n:FUNCTION)
    WHERE (n.processing_status IS NULL OR n.processing_run_id <> $run_id) AND NOT n:DOCUMENTATION

    // Get hierarchy children (if any) - don't check completion status
    OPTIONAL MATCH (n)-[:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION]->(hier_child:NODE)
    WITH n, collect(DISTINCT hier_child) as hier_children

    // Get call children (if any) - don't check completion status
    OPTIONAL MATCH (n)-[:CALLS]->(call_child:NODE)
    WITH n, hier_children, collect(DISTINCT call_child) as call_children

    // Get descriptions from completed children only
    OPTIONAL MATCH (hier_doc:DOCUMENTATION)-[:DESCRIBES]->(hier_child)
    WHERE hier_child IN hier_children
      AND hier_child.processing_status = 'completed'
      AND hier_child.processing_run_id = $run_id
    WITH n, call_children,
         collect(DISTINCT {
             id: hier_child.node_id,
             name: hier_child.name,
             labels: labels(hier_child),
             path: hier_child.path,
             description: hier_doc.content
         }) as hier_descriptions

    OPTIONAL MATCH (call_doc:DOCUMENTATION)-[:DESCRIBES]->(call_child)
    WHERE call_child IN call_children
      AND call_child.processing_status = 'completed'
      AND call_child.processing_run_id = $run_id
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


def get_hierarchical_parents_query() -> LiteralString:
    """
    Get all hierarchical parent nodes (CONTAINS, FUNCTION_DEFINITION, CLASS_DEFINITION) of a given node.
    Used to traverse up the hierarchy from a node to its ancestors.
    """
    return """
    MATCH (child:NODE {node_id: $node_id, entityId: $entity_id, repoId: $repo_id})

    // Collect parent nodes with their depth relative to the child
    OPTIONAL MATCH path = (parent:NODE)-[:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION*1..]->(child)
    WITH child, collect(DISTINCT {node: parent, depth: length(path)}) as parents

    // Collect classes defined directly by the child node (e.g., FILE -> CLASS)
    OPTIONAL MATCH (child)-[:CLASS_DEFINITION]->(defined_class:CLASS)
    WITH child,
        parents,
        collect(DISTINCT defined_class) as defined_classes

    WITH [{node: child, depth: 0, sortKey: 0}] as child_entry,
        [class_node IN defined_classes | {node: class_node, depth: 1, sortKey: 1}] as class_entries,
        [parent_map IN parents | {node: parent_map.node, depth: parent_map.depth + 1, sortKey: 2}] as parent_entries

    WITH child_entry + class_entries + parent_entries as nodes_info
    UNWIND nodes_info as info
    WITH info
    RETURN info.node.node_id as id,
         info.node.name as name,
         labels(info.node) as labels,
         info.node.path as path,
         info.node.start_line as start_line,
         info.node.end_line as end_line
    ORDER BY info.sortKey ASC, info.depth ASC
    """


def get_direct_callers_of_nodes_in_files_query() -> LiteralString:
    """
    Find nodes that directly CALL functions within the specified file paths (1 level).

    This query finds all FUNCTION nodes that call any function defined within
    the specified files. Used to identify which callers need re-documentation
    when a file changes.

    Expected params: $entity_id, $repo_ids (optional), $file_paths
    """
    return """
    MATCH (file:FILE {entityId: $entity_id})
    WHERE ($repo_ids IS NULL OR file.repoId IN $repo_ids)
      AND file.node_path IN $file_paths
    MATCH (file)-[:FUNCTION_DEFINITION|CLASS_DEFINITION*1..]->(target:FUNCTION)
    MATCH (caller:FUNCTION)-[:CALLS]->(target)
    WHERE NOT caller.node_path STARTS WITH file.node_path
    RETURN DISTINCT caller.node_id as id, caller.node_path as path
    """


def reset_processing_status_for_nodes_query() -> LiteralString:
    """
    Reset processing_status to NULL for specified nodes in a single batch.

    Used during incremental documentation to mark affected nodes (callers, parent folders)
    for re-processing without affecting unrelated nodes.

    Expected params: $entity_id, $repo_ids (optional), $node_ids
    """
    return """
    MATCH (n:NODE {entityId: $entity_id})
    WHERE ($repo_ids IS NULL OR n.repoId IN $repo_ids)
      AND n.node_id IN $node_ids
    SET n.processing_status = NULL, n.processing_run_id = NULL
    RETURN count(n) as reset_count
    """


def get_parent_folders_for_files_query() -> LiteralString:
    """
    Get all parent folder nodes for the specified file paths.

    Traverses up the CONTAINS relationship to find all ancestor folders.
    Used to identify which folders need re-documentation when a file changes.

    Expected params: $entity_id, $repo_ids (optional), $file_paths
    """
    return """
    MATCH (file:FILE {entityId: $entity_id})
    WHERE ($repo_ids IS NULL OR file.repoId IN $repo_ids)
      AND file.node_path IN $file_paths
    MATCH (parent:FOLDER)-[:CONTAINS*1..]->(file)
    RETURN DISTINCT parent.node_id as id, parent.node_path as path
    """


def get_latest_processing_run_id_query() -> LiteralString:
    """
    Get the most recent processing_run_id from any completed node.

    Used to retrieve the run_id from the previous documentation run,
    so incremental updates can reuse it and skip already-processed nodes.

    Expected params: $entity_id, $repo_ids (optional)
    """
    return """
    MATCH (n:NODE {entityId: $entity_id})
    WHERE ($repo_ids IS NULL OR n.repoId IN $repo_ids)
      AND n.processing_run_id IS NOT NULL
      AND n.processing_status = 'completed'
    RETURN n.processing_run_id as run_id
    LIMIT 1
    """
