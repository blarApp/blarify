# SCIP Setup Guide

This guide explains how to set up SCIP (Source Code Intelligence Protocol) for ultra-fast reference resolution in blarify.

## Quick Setup

### 1. Install Prerequisites

```bash
# Install scip-python (required for generating SCIP indexes)
npm install -g @sourcegraph/scip-python

# Verify installation
scip-python --version
```

### 2. Initialize SCIP

```bash
# Run the initialization script
python scripts/initialize_scip.py

# Or initialize for a specific project
python scripts/initialize_scip.py /path/to/project --project-name "my-project"
```

### 3. Use SCIP in Your Code

```python
from blarify.code_references.scip_helper import ScipReferenceResolver

# Initialize resolver
resolver = ScipReferenceResolver("/path/to/project")

# Get references for a node
references = resolver.get_references_for_node(node)
```

## Troubleshooting Import Issues

### Problem: `ImportError: No module named 'scip_pb2'`

The blarify package includes robust import handling that automatically falls back to a mock implementation when SCIP bindings are not available. However, if you want full SCIP functionality:

**Solution 1: Use the initialization script**
```bash
python scripts/initialize_scip.py
```

**Solution 2: Manual setup**
```bash
# Ensure protobuf is installed
pip install protobuf>=6.30.0

# Download the SCIP protocol definition
curl -o scip.proto https://raw.githubusercontent.com/sourcegraph/scip/main/scip.proto

# Generate Python bindings (requires protoc)
protoc --python_out=. scip.proto
```

**Solution 3: Install protoc compiler**
```bash
# macOS
brew install protobuf

# Ubuntu/Debian
sudo apt-get install protobuf-compiler

# Then run initialization script
python scripts/initialize_scip.py
```

### How Import Fallback Works

The blarify package uses a multi-tier import strategy:

1. **First attempt**: `from blarify import scip_pb2 as scip` (package-relative)
2. **Second attempt**: `import scip_pb2 as scip` (global import)
3. **Third attempt**: `from . import scip_pb2 as scip` (relative import)
4. **Fallback**: Mock implementation that disables SCIP features gracefully

This ensures the package works even when SCIP bindings are not available, with helpful warnings about missing functionality.

## Performance Benefits

When properly configured, SCIP provides:

- **330x faster** reference resolution compared to LSP
- **Identical accuracy** to LSP results
- **No runtime dependencies** on language servers
- **Automatic index management** (regenerates when files change)

## Protobuf Version Warnings

You may see warnings like:
```
Protobuf gencode version 5.29.3 is exactly one major version older than the runtime version 6.30.0
```

This is expected and doesn't affect functionality. To resolve:

```bash
# Regenerate with current protobuf version
python scripts/initialize_scip.py
```

## File Structure

After setup, your project will have:

```
project/
├── scip.proto              # SCIP protocol definition
├── scip_pb2.py             # Generated Python bindings
├── index.scip              # SCIP index (binary)
└── blarify/
    └── scip_pb2.py         # Package-bundled bindings
```

## Environment Variables

Optional environment variables:

```bash
# Disable SCIP entirely (useful for problematic projects like Django)
export BLARIFY_DISABLE_SCIP=true

# Disable protobuf version checks (if needed)
export TEMPORARILY_DISABLE_PROTOBUF_VERSION_CHECK=true

# Enable debug logging for SCIP imports
export BLARIFY_DEBUG=true
```

### When to Disable SCIP

You may want to disable SCIP in certain scenarios:

```bash
# For large projects that cause SCIP buffer overflow
export BLARIFY_DISABLE_SCIP=true

# For projects in temporary directories (like SWE-Bench)
export BLARIFY_DISABLE_SCIP=true

# For CI/CD environments where SCIP indexing is too slow
export BLARIFY_DISABLE_SCIP=true
```

## Validation

Test your SCIP setup:

```python
from blarify.code_references.scip_helper import SCIP_AVAILABLE, ScipReferenceResolver

print(f"SCIP Available: {SCIP_AVAILABLE}")

if SCIP_AVAILABLE:
    resolver = ScipReferenceResolver(".")
    stats = resolver.get_statistics()
    print(f"SCIP Index: {stats}")
else:
    print("Using fallback implementation")
```

## Support

If you encounter issues:

1. Check that `scip-python --version` works
2. Verify `protoc --version` is available (for fresh bindings)
3. Run `python scripts/initialize_scip.py --verbose` for detailed output
4. Check that `protobuf>=6.30.0` is installed: `pip show protobuf`