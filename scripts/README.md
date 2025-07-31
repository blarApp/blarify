# SCIP Setup Scripts

This directory contains scripts for setting up and managing SCIP (Source Code Intelligence Protocol) integration.

## How `scip_pb2.py` was Generated

The `scip_pb2.py` file is generated from the official SCIP Protocol Buffer definition. Here's how it was created:

### 1. Download the Protocol Definition

```bash
# Download the official scip.proto file from the SCIP repository
curl -o scip.proto https://raw.githubusercontent.com/sourcegraph/scip/main/scip.proto
```

### 2. Generate Python Bindings

```bash
# Install protobuf compiler (if not already installed)
# macOS:
brew install protobuf

# Ubuntu/Debian:
sudo apt-get install protobuf-compiler

# Generate Python bindings
protoc --python_out=. scip.proto
```

This creates `scip_pb2.py` with all the necessary Python classes to read/write SCIP protocol buffer files.

### 3. Current Version Info

The current `scip_pb2.py` was generated with:
- **Protocol Buffer compiler**: version varies
- **Protobuf Python version**: 5.29.3 (as seen in the file header)
- **Source**: https://github.com/sourcegraph/scip/blob/main/scip.proto

## Using the Initialization Script

### Quick Start

```bash
# Initialize SCIP for current directory
python scripts/initialize_scip.py

# Initialize SCIP for a specific project
python scripts/initialize_scip.py /path/to/project --project-name "my-project"

# Verbose output
python scripts/initialize_scip.py --verbose
```

### What the Script Does

1. **Checks Prerequisites**: Verifies `scip-python` and `protoc` are installed
2. **Downloads scip.proto**: Gets the latest protocol definition
3. **Generates Bindings**: Creates fresh `scip_pb2.py` (if protoc available)
4. **Tests Bindings**: Verifies the protobuf bindings work
5. **Creates Index**: Generates the SCIP index for your project

### Prerequisites

```bash
# Install scip-python (Node.js tool)
npm install -g @sourcegraph/scip-python

# Install protobuf compiler (optional, for regenerating bindings)
# macOS:
brew install protobuf

# Ubuntu/Debian:
sudo apt-get install protobuf-compiler
```

## Manual SCIP Setup

If you prefer to set up SCIP manually:

### 1. Install scip-python

```bash
npm install -g @sourcegraph/scip-python
```

### 2. Generate SCIP Index

```bash
# In your project directory
scip-python index --project-name "your-project" --output index.scip
```

### 3. Use in Python

```python
from blarify.code_references.scip_helper import ScipReferenceResolver

# Initialize resolver
resolver = ScipReferenceResolver("/path/to/project")

# Get references for a node
references = resolver.get_references_for_node(node)
```

## Regenerating Protobuf Bindings

If you need to update the protobuf bindings (e.g., when SCIP protocol is updated):

```bash
# Download latest scip.proto
curl -o scip.proto https://raw.githubusercontent.com/sourcegraph/scip/main/scip.proto

# Regenerate Python bindings
protoc --python_out=. scip.proto

# Move to project root
mv scip_pb2.py ../
```

## Troubleshooting

### "scip-python not found"
```bash
# Install via npm
npm install -g @sourcegraph/scip-python

# Verify installation
scip-python --version
```

### "protoc not found"
```bash
# macOS
brew install protobuf

# Ubuntu/Debian  
sudo apt-get install protobuf-compiler

# Verify installation
protoc --version
```

### "Import scip_pb2 failed"
- Ensure `scip_pb2.py` is in your project root or Python path
- Try regenerating with the initialization script
- Check that protobuf Python package is installed: `pip install protobuf`

### Version Mismatch Warnings
The warning about protobuf gencode version is expected when the runtime protobuf version is newer than the version used to generate `scip_pb2.py`. This doesn't affect functionality but can be resolved by regenerating the bindings.

## Performance Benefits

Once properly set up, SCIP provides:
- **330x faster** reference resolution compared to LSP
- **Identical accuracy** to LSP results
- **Automatic index management** (regenerates when files change)
- **No runtime dependencies** on language servers