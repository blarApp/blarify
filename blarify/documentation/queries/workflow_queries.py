"""Cypher queries for workflow and documentation operations."""

from typing import LiteralString


def cleanup_orphaned_documentation_query() -> LiteralString:
    """
    Delete orphaned documentation nodes that have no DESCRIBES relationship.

    This cleanup query removes documentation nodes that became disconnected
    after code nodes were deleted during incremental updates.

    Returns:
        deleted_orphans: count of orphaned DocumentationNodes deleted
    """
    return """
    MATCH (doc:DOCUMENTATION {layer: 'documentation'})
    WHERE NOT (doc)-[:DESCRIBES]->()
    DETACH DELETE doc
    RETURN count(doc) as deleted_orphans
    """


def delete_workflows_for_entry_points_query() -> LiteralString:
    """
    Delete workflow nodes and all related relationships for given entry points.

    This performs a two-step deletion:
    1. Delete WORKFLOW_STEP relationships that reference these workflows (scopeText contains workflow_id)
    2. DETACH DELETE WorkflowNodes (removes BELONGS_TO_WORKFLOW relationships)

    Expected params: $entry_point_ids (list of entry point IDs)

    Returns:
        deleted_workflows: count of WorkflowNodes deleted
        total_deleted_steps: count of WORKFLOW_STEP relationships deleted
    """
    return """
    MATCH (w:NODE {layer: 'workflows'})
    WHERE w.entry_point_id IN $entry_point_ids
    WITH w, w.node_id as workflow_id
    OPTIONAL MATCH ()-[ws:WORKFLOW_STEP]->()
    WHERE ws.scopeText CONTAINS ('workflow_id:' + workflow_id)
    DELETE ws
    WITH w, count(ws) as deleted_steps
    DETACH DELETE w
    RETURN count(w) as deleted_workflows, sum(deleted_steps) as total_deleted_steps
    """
