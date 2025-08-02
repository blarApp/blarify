#\!/bin/bash  
echo "$(date): Starting Pyright Batch 3 - Core Tests" | tee batch3.log
cd /Users/ryan/src/cue

# Fix core test files
echo "$(date): Processing core test files" | tee -a .parallel-execution/pyright-batches/batch3.log

# Update pyright status
pyright tests/test_code_complexity.py tests/test_filesystem_operations.py tests/test_description_generator.py tests/test_lsp_helper.py --outputjson > .parallel-execution/pyright-batches/batch3-progress.json 2>&1

echo "$(date): Batch 3 completed" | tee -a .parallel-execution/pyright-batches/batch3.log
