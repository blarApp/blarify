# Refactor BottomUpBatchProcessor to Query-Based Processing

## Context

The current `BottomUpBatchProcessor` (formerly `RecursiveDFSProcessor`) in `blarify/documentation/utils/bottom_up_batch_processor.py` has a critical inefficiency:

1. **Problem**: It loads the entire graph into memory during the discovery phase (lines 218-247)
2. **Issue**: Makes N database queries (one per node) during BFS discovery, then stores everything in memory
3. **Impact**: Combines worst of both worlds - high query count AND high memory usage
4. **Current Flow**:
   - BFS traversal calls `_get_navigation_children()` for each node
   - Each call triggers a DB query via `get_direct_children()` or `get_call_stack_children()`
   - All results stored in memory dictionaries: `nodes_to_process`, `node_children`, `node_parents`
   - Only then starts processing

## Goal

Transform the processor to use efficient batch queries without storing the graph in memory, enabling true scalability for large codebases.

## Requirements

### User-Specified Requirements
1. Add `processing_status` and `processing_run_id` fields to `DocumentationNode`
2. Query for descriptions from DB when needed (not store in memory)
3. Save documentation immediately after each batch processing
4. Remove `root_file_folder_processing_workflow.py` and call `BottomUpBatchProcessor` directly from `DocumentationCreator`
5. Create queries in separate file: `blarify/documentation/queries/batch_processing_queries.py`

### Technical Requirements
1. Maintain existing functionality and test compatibility
2. Process nodes in bottom-up order (leaves first)
3. Handle cycles correctly
4. Support `overwrite_documentation` parameter
5. Use thread pool with `as_completed()` for immediate thread harvesting

## Implementation Plan

### 1. Create Query Module Structure

Create `blarify/documentation/queries/` folder:

#### `__init__.py`
```python
"""Database queries for batch processing documentation."""

from .batch_processing_queries import (
    initialize_processing_status_query,
    get_leaf_nodes_batch_query,
    get_processable_nodes_with_descriptions_query,
    save_documentation_and_mark_completed_query,
    cleanup_processing_status_query,
    check_pending_nodes_query,
)

__all__ = [
    "initialize_processing_status_query",
    "get_leaf_nodes_batch_query", 
    "get_processable_nodes_with_descriptions_query",
    "save_documentation_and_mark_completed_query",
    "cleanup_processing_status_query",
    "check_pending_nodes_query",
]
```

#### `batch_processing_queries.py`
```python
"""Cypher queries for batch processing documentation nodes."""

def initialize_processing_status_query() -> str:
    """
    Initialize processing status for all nodes under root.
    
    Sets all descendants of root node to 'pending' status with current run ID.
    Note: Since we filter the root by entityId/repoId, all descendants are guaranteed
    to be from the same entity/repo (graph structure ensures no cross-repo relationships).
    """
    return """
    MATCH path = (root:NODE {node_id: $root_id, entityId: $entity_id, repoId: $repo_id})
          -[:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION|CALLS|USES*]->(descendant:NODE)
    SET descendant.processing_status = CASE 
        WHEN $overwrite = true OR descendant.processing_status IS NULL 
        THEN 'pending' 
        ELSE descendant.processing_status 
        END,
        descendant.processing_run_id = CASE 
        WHEN $overwrite = true OR descendant.processing_status IS NULL 
        THEN $run_id 
        ELSE descendant.processing_run_id 
        END
    WITH root, count(DISTINCT descendant) as descendant_count
    SET root.processing_status = CASE 
        WHEN $overwrite = true OR root.processing_status IS NULL 
        THEN 'pending' 
        ELSE root.processing_status 
        END,
        root.processing_run_id = CASE 
        WHEN $overwrite = true OR root.processing_status IS NULL 
        THEN $run_id 
        ELSE root.processing_run_id 
        END
    RETURN descendant_count + 1 as initialized_count
    """

def get_leaf_nodes_batch_query() -> str:
    """
    Get batch of leaf nodes (FUNCTION nodes with no CALLS).
    
    Returns FUNCTION nodes that:
    - Have pending status for current run
    - Have no outgoing CALLS relationships
    - Sets them to in_progress before returning
    """
    return """
    MATCH (n:NODE:FUNCTION {entityId: $entity_id, repoId: $repo_id})
    WHERE n.processing_status = 'pending' 
      AND n.processing_run_id = $run_id
      AND NOT (n)-[:CALLS]->(:NODE)
    WITH n LIMIT $batch_size
    SET n.processing_status = 'in_progress'
    RETURN n.node_id as id, 
           n.name as name, 
           labels(n) as labels,
           n.path as path, 
           n.start_line as start_line, 
           n.end_line as end_line,
           coalesce(n.text, '') as content
    """

def get_processable_nodes_with_descriptions_query() -> str:
    """
    Get nodes ready for processing with their children's descriptions.
    
    Returns nodes where all children have been processed, along with
    the descriptions of those children for context.
    """
    return """
    MATCH (n:NODE {entityId: $entity_id, repoId: $repo_id})
    WHERE n.processing_status = 'pending' 
       AND n.processing_run_id = $run_id
    
    // Check hierarchy children are all processed
    OPTIONAL MATCH (n)-[:CONTAINS|FUNCTION_DEFINITION|CLASS_DEFINITION]->(hier_child:NODE)
    WHERE hier_child.processing_run_id = $run_id
    WITH n, collect(DISTINCT hier_child) as hier_children
    WHERE ALL(child IN hier_children WHERE child.processing_status = 'completed' OR child.processing_status IS NULL)
    
    // Check call stack children are all processed (for functions)
    OPTIONAL MATCH (n)-[:CALLS|USES]->(call_child:NODE)
    WHERE 'FUNCTION' IN labels(n) AND call_child.processing_run_id = $run_id
    WITH n, hier_children, collect(DISTINCT call_child) as call_children
    WHERE ALL(child IN call_children WHERE child.processing_status = 'completed' OR child.processing_status IS NULL)
    
    // Now get the descriptions - no entity/repo filter needed
    OPTIONAL MATCH (hier_doc:DOCUMENTATION)-[:DESCRIBES]->(hier_child)
    WHERE hier_child IN hier_children AND hier_doc.processing_run_id = $run_id
    WITH n, hier_children, call_children,
         collect(DISTINCT {
             id: hier_child.node_id, 
             name: hier_child.name, 
             labels: labels(hier_child),
             path: hier_child.path,
             description: hier_doc.content
         }) as hier_descriptions
    
    OPTIONAL MATCH (call_doc:DOCUMENTATION)-[:DESCRIBES]->(call_child)  
    WHERE call_child IN call_children AND call_doc.processing_run_id = $run_id
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
    
    SET n.processing_status = 'in_progress'
    
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

def save_documentation_and_mark_completed_query() -> str:
    """
    Save documentation nodes and mark source nodes as completed.
    
    Creates DOCUMENTATION nodes and DESCRIBES relationships,
    then marks source nodes as completed.
    """
    return """
    UNWIND $docs as doc
    CREATE (d:DOCUMENTATION {
        node_id: doc.node_id,
        hashed_id: doc.hashed_id,
        content: doc.content,
        info_type: doc.info_type,
        source_path: doc.source_path,
        source_name: doc.source_name,
        source_id: doc.source_id,
        source_labels: doc.source_labels,
        source_type: doc.source_type,
        processing_run_id: $run_id,
        processing_status: 'completed',
        entityId: $entity_id,
        repoId: $repo_id
    })
    WITH d, doc
    MATCH (source:NODE {node_id: doc.source_id})
    WHERE source.entityId = $entity_id AND source.repoId = $repo_id
    SET source.processing_status = 'completed'
    CREATE (d)-[:DESCRIBES]->(source)
    RETURN count(d) as saved_count
    """

def cleanup_processing_status_query() -> str:
    """
    Remove processing status fields from all nodes for this run.
    
    Cleans up temporary processing fields after completion.
    """
    return """
    MATCH (n:NODE {entityId: $entity_id, repoId: $repo_id})
    WHERE n.processing_run_id = $run_id
    REMOVE n.processing_status, n.processing_run_id
    RETURN count(n) as cleaned_count
    """

def check_pending_nodes_query() -> str:
    """
    Check if there are any pending nodes remaining.
    
    Used to determine if processing is complete.
    """
    return """
    MATCH (n:NODE {entityId: $entity_id, repoId: $repo_id})
    WHERE n.processing_status = 'pending' AND n.processing_run_id = $run_id
    RETURN count(n) as pending_count
    """
```

### 2. Update DocumentationNode

Modify `blarify/graph/node/documentation_node.py`:

Add to the `__init__` method parameters:
```python
processing_status: Optional[str] = None,
processing_run_id: Optional[str] = None,
```

Add as class attributes:
```python
self.processing_status = processing_status
self.processing_run_id = processing_run_id
```

Update `as_object()` method to include these fields.

### 3. Refactor BottomUpBatchProcessor

Key changes to `blarify/documentation/utils/bottom_up_batch_processor.py`:

```python
import uuid
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..queries.batch_processing_queries import (
    initialize_processing_status_query,
    get_leaf_nodes_batch_query,
    get_processable_nodes_with_descriptions_query,
    save_documentation_and_mark_completed_query,
    cleanup_processing_status_query,
    check_pending_nodes_query,
)

class BottomUpBatchProcessor:
    def __init__(
        self,
        db_manager: AbstractDbManager,
        agent_caller: LLMProvider,
        company_id: str,
        repo_id: str,
        graph_environment: GraphEnvironment,
        max_workers: int = 5,
        root_node: Optional[NodeWithContentDto] = None,
        overwrite_documentation: bool = False,
        batch_size: int = 50,
    ):
        """Initialize with query-based processing."""
        self.db_manager = db_manager
        self.agent_caller = agent_caller
        self.company_id = company_id
        self.repo_id = repo_id
        self.graph_environment = graph_environment
        self.max_workers = max_workers
        self.root_node = root_node
        self.overwrite_documentation = overwrite_documentation
        self.batch_size = batch_size
        
        # Unique ID for this processing run
        self.processing_run_id = str(uuid.uuid4())
        
        # Remove ALL in-memory caches
        # No node_descriptions, no source_nodes_cache, no source_to_description
        
    def process_node(self, node_path: str) -> ProcessingResult:
        """Entry point - process using database queries only."""
        try:
            # Get root node
            root_node = self.root_node
            if not root_node:
                root_node = get_node_by_path(
                    self.db_manager, self.company_id, self.repo_id, node_path
                )
                if not root_node:
                    return ProcessingResult(
                        node_path=node_path, 
                        error=f"Node not found: {node_path}"
                    )
            
            # Process using queries
            total_processed = self._process_node_query_based(root_node)
            
            return ProcessingResult(
                node_path=node_path,
                hierarchical_analysis={"complete": True},
                total_nodes_processed=total_processed,
                error=None,
                # Don't return nodes - they're in the database
                information_nodes=[],
                documentation_nodes=[],
                source_nodes=[]
            )
            
        except Exception as e:
            logger.exception(f"Error in query-based processing: {e}")
            return ProcessingResult(node_path=node_path, error=str(e))
    
    def _process_node_query_based(self, root_node: NodeWithContentDto) -> int:
        """Process using database queries without memory storage."""
        
        # Step 1: Initialize processing status for all nodes
        self._initialize_processing_status(root_node)
        
        total_processed = 0
        max_iterations = 1000  # Safety limit
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Try to process leaf nodes first
            leaf_count = self._process_leaf_batch()
            if leaf_count > 0:
                total_processed += leaf_count
                continue
            
            # Then process parent nodes with descriptions
            parent_count = self._process_parent_batch()
            if parent_count > 0:
                total_processed += parent_count
                continue
            
            # Check if any nodes remain
            if not self._has_pending_nodes():
                break
                
            # If we have pending nodes but can't process them, there might be a cycle issue
            logger.warning(f"Iteration {iteration}: Pending nodes exist but none processable")
            break
        
        # Cleanup processing status
        self._cleanup_processing_status()
        
        return total_processed
    
    def _initialize_processing_status(self, root_node: NodeWithContentDto):
        """Mark all nodes under root as pending."""
        query = initialize_processing_status_query()
        params = {
            "root_id": root_node.id,
            "entity_id": self.company_id,
            "repo_id": self.repo_id,
            "run_id": self.processing_run_id,
            "overwrite": self.overwrite_documentation
        }
        result = self.db_manager.query(query, params)
        if result:
            count = result[0].get("initialized_count", 0)
            logger.info(f"Initialized {count} nodes for processing")
    
    def _process_leaf_batch(self) -> int:
        """Process a batch of leaf nodes."""
        # Get leaf nodes from database
        query = get_leaf_nodes_batch_query()
        params = {
            "entity_id": self.company_id,
            "repo_id": self.repo_id,
            "run_id": self.processing_run_id,
            "batch_size": self.batch_size
        }
        
        batch_results = self.db_manager.query(query, params)
        if not batch_results:
            return 0
        
        # Process batch with thread pool
        documentation_nodes = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            
            for node_data in batch_results:
                # Create NodeWithContentDto from query result
                node = NodeWithContentDto(**node_data)
                future = executor.submit(self._process_leaf_node, node)
                futures.append(future)
            
            # Harvest results as they complete
            for future in as_completed(futures):
                try:
                    doc_node = future.result(timeout=10)
                    if doc_node:
                        # Add processing metadata
                        doc_node.processing_status = 'completed'
                        doc_node.processing_run_id = self.processing_run_id
                        documentation_nodes.append(doc_node)
                except Exception as e:
                    logger.error(f"Error processing leaf node: {e}")
        
        # Save batch to database immediately
        if documentation_nodes:
            self._save_documentation_batch(documentation_nodes)
        
        return len(batch_results)
    
    def _process_parent_batch(self) -> int:
        """Process a batch of parent nodes with child descriptions."""
        # Get parent nodes with descriptions from database
        query = get_processable_nodes_with_descriptions_query()
        params = {
            "entity_id": self.company_id,
            "repo_id": self.repo_id,
            "run_id": self.processing_run_id,
            "batch_size": self.batch_size
        }
        
        batch_results = self.db_manager.query(query, params)
        if not batch_results:
            return 0
        
        # Process batch with thread pool
        documentation_nodes = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            
            for node_data in batch_results:
                # Extract node info
                node = NodeWithContentDto(
                    id=node_data['id'],
                    name=node_data['name'],
                    labels=node_data['labels'],
                    path=node_data['path'],
                    start_line=node_data.get('start_line'),
                    end_line=node_data.get('end_line'),
                    content=node_data['content']
                )
                
                # Extract child descriptions
                hier_descriptions = node_data.get('hier_descriptions', [])
                call_descriptions = node_data.get('call_descriptions', [])
                
                # Convert descriptions to DocumentationNode-like objects for processing
                child_descriptions = []
                for desc in hier_descriptions + call_descriptions:
                    if desc and desc.get('description'):
                        # Create minimal DocumentationNode for child context
                        child_doc = DocumentationNode(
                            content=desc['description'],
                            info_type="child_description",
                            source_path=desc.get('path', ''),
                            source_name=desc.get('name', ''),
                            source_id=desc.get('id', ''),
                            source_labels=desc.get('labels', []),
                            source_type="child",
                            graph_environment=self.graph_environment
                        )
                        child_descriptions.append(child_doc)
                
                future = executor.submit(
                    self._process_parent_node, 
                    node, 
                    child_descriptions
                )
                futures.append(future)
            
            # Harvest results
            for future in as_completed(futures):
                try:
                    doc_node = future.result(timeout=10)
                    if doc_node:
                        # Add processing metadata
                        doc_node.processing_status = 'completed'
                        doc_node.processing_run_id = self.processing_run_id
                        documentation_nodes.append(doc_node)
                except Exception as e:
                    logger.error(f"Error processing parent node: {e}")
        
        # Save batch immediately
        if documentation_nodes:
            self._save_documentation_batch(documentation_nodes)
        
        return len(batch_results)
    
    def _save_documentation_batch(self, documentation_nodes: List[DocumentationNode]):
        """Save documentation to database and mark nodes completed."""
        if not documentation_nodes:
            return
        
        # Convert to dictionaries for query
        docs = []
        for node in documentation_nodes:
            doc_dict = node.as_object()
            # Ensure required fields are present
            doc_dict['hashed_id'] = node.hashed_id
            doc_dict['source_id'] = node.source_id
            docs.append(doc_dict)
        
        query = save_documentation_and_mark_completed_query()
        params = {
            "docs": docs,
            "entity_id": self.company_id,
            "repo_id": self.repo_id,
            "run_id": self.processing_run_id
        }
        
        result = self.db_manager.query(query, params)
        if result:
            saved_count = result[0].get("saved_count", 0)
            logger.debug(f"Saved {saved_count} documentation nodes to database")
    
    def _has_pending_nodes(self) -> bool:
        """Check if there are still pending nodes."""
        query = check_pending_nodes_query()
        params = {
            "entity_id": self.company_id,
            "repo_id": self.repo_id,
            "run_id": self.processing_run_id
        }
        
        result = self.db_manager.query(query, params)
        if result:
            pending_count = result[0].get("pending_count", 0)
            return pending_count > 0
        return False
    
    def _cleanup_processing_status(self):
        """Remove processing status fields after completion."""
        query = cleanup_processing_status_query()
        params = {
            "entity_id": self.company_id,
            "repo_id": self.repo_id,
            "run_id": self.processing_run_id
        }
        
        result = self.db_manager.query(query, params)
        if result:
            cleaned = result[0].get("cleaned_count", 0)
            logger.info(f"Cleaned processing status from {cleaned} nodes")
    
    # Keep existing _process_leaf_node and _process_parent_node methods
    # They work on individual nodes and return DocumentationNode objects
```

### 4. Update DocumentationCreator

Modify `blarify/documentation/documentation_creator.py`:

```python
def __init__(self, ..., overwrite_documentation: bool = False):
    """Add overwrite parameter."""
    # ... existing init code ...
    self.overwrite_documentation = overwrite_documentation

def _create_full_documentation(self) -> DocumentationResult:
    """Create documentation for entire codebase."""
    try:
        logger.info("Creating full codebase documentation")
        
        # Get all root folders and files from database
        root_paths = get_root_folders_and_files(
            db_manager=self.db_manager,
            entity_id=self.company_id,
            repo_id=self.repo_id,
        )
        
        if not root_paths:
            logger.warning("No root folders and files found")
            return DocumentationResult(warnings=["No root folders and files found"])
        
        total_processed = 0
        
        # Process each root directly with BottomUpBatchProcessor
        for root_path in root_paths:
            logger.info(f"Processing root: {root_path}")
            
            processor = BottomUpBatchProcessor(
                db_manager=self.db_manager,
                agent_caller=self.agent_caller,
                company_id=self.company_id,
                repo_id=self.repo_id,
                graph_environment=self.graph_environment,
                max_workers=self.max_workers,
                overwrite_documentation=self.overwrite_documentation
            )
            
            result = processor.process_node(root_path)
            
            if result.error:
                logger.warning(f"Error processing {root_path}: {result.error}")
            else:
                total_processed += result.total_nodes_processed
        
        logger.info(f"Full documentation completed: {total_processed} nodes processed")
        
        return DocumentationResult(
            total_nodes_processed=total_processed,
            analyzed_nodes=[{
                "type": "full_codebase",
                "root_paths_count": len(root_paths),
                "total_nodes": total_processed,
            }]
        )
        
    except Exception as e:
        logger.exception(f"Error in full documentation creation: {e}")
        return DocumentationResult(error=str(e))
```

### 5. Delete Workflow File

Delete: `blarify/documentation/root_file_folder_processing_workflow.py`

Remove its import from `documentation_creator.py`.

## Testing Considerations

The existing tests should continue working with minimal changes:

1. **test_documentation_creation.py**: Tests the full documentation flow
   - May need to adjust assertions since nodes won't be returned in memory
   - Verify documentation in database instead

2. **test_thread_pool_exhaustion.py**: Tests thread management
   - Should work better with new batch processing
   - Thread reuse should be more efficient

3. **test_cycle_detection.py**: Tests cycle detection
   - Cycle detection remains unchanged at the individual node level
   - Should continue to work as expected

## Benefits

1. **Memory Efficiency**: O(batch_size) instead of O(total_nodes)
2. **Query Efficiency**: ~10-20 strategic queries instead of N individual queries  
3. **True Scalability**: Can handle codebases of any size
4. **Immediate Persistence**: Documentation saved immediately after processing
5. **Resume Capability**: Can restart interrupted processing using status fields
6. **Simpler Architecture**: Direct processor usage without workflow layer

## Rollback Plan

If issues arise:
1. The original code is preserved in git history
2. Tests will catch any functional regressions
3. Can temporarily increase memory limits while debugging

## Success Criteria

1. All existing tests pass
2. Memory usage remains constant regardless of codebase size
3. Processing completes successfully for large codebases (1000+ nodes)
4. Documentation quality remains unchanged
5. Performance improves or remains similar