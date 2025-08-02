#\!/bin/bash
echo "$(date): Starting Pyright Batch 2 - Test Fixtures" | tee batch2.log
cd /Users/ryan/src/cue

# Fix test fixtures and high-error test files
echo "$(date): Processing test fixtures and high-error tests" | tee -a .parallel-execution/pyright-batches/batch2.log

# Update pyright status  
pyright tests/test_tree_sitter_helper.py tests/test_gitignore_integration.py tests/test_project_file_explorer.py tests/fixtures/node_factories.py --outputjson > .parallel-execution/pyright-batches/batch2-progress.json 2>&1

echo "$(date): Batch 2 completed" | tee -a .parallel-execution/pyright-batches/batch2.log
