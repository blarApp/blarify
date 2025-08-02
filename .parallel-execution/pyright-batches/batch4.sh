#\!/bin/bash
echo "$(date): Starting Pyright Batch 4 - Remaining Tests" | tee batch4.log  
cd /Users/ryan/src/cue

# Fix remaining test files
echo "$(date): Processing remaining test files" | tee -a .parallel-execution/pyright-batches/batch4.log

# Update pyright status
pyright tests/test_graph_comprehensive.py tests/test_documentation_extraction.py tests/test_graph_operations.py tests/test_llm_description_nodes.py tests/test_filesystem_nodes.py --outputjson > .parallel-execution/pyright-batches/batch4-progress.json 2>&1

echo "$(date): Batch 4 completed" | tee -a .parallel-execution/pyright-batches/batch4.log
