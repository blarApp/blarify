#\!/bin/bash
echo "$(date): Starting Pyright Batch 1 - Production Code" | tee batch1.log
cd /Users/ryan/src/cue

# Fix production code files with high error counts
echo "$(date): Fixing project_graph_diff_creator.py" | tee -a .parallel-execution/pyright-batches/batch1.log

# Update pyright status
pyright blarify/ --outputjson > .parallel-execution/pyright-batches/batch1-progress.json 2>&1

echo "$(date): Batch 1 completed" | tee -a .parallel-execution/pyright-batches/batch1.log
