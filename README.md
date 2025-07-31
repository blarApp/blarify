This repo introduces a method to represent a local code repository as a graph structure. The objective is to allow an LLM to traverse this graph to understand the code logic and flow. Providing the LLM with the power to debug, refactor, and optimize queries.

# Supported Languages

- Python
- JavaScript
- TypeScript
- Ruby
- Go
- C#

# Example

<img src="https://raw.githubusercontent.com/blarApp/blarify/refs/heads/main/docs/visualisation.png"></img>
This graph was generated from the code in this repository.

# Quickstart

Get started with blarify by following our quickstart guide:

[➡️ Quickstart Guide](https://github.com/blarApp/blarify/blob/main/docs/quickstart.md)

## Dependencies

### SCIP Support (Optional, for faster reference resolution)

For enhanced performance, blarify supports SCIP (Source Code Intelligence Protocol) which provides up to 330x faster reference resolution compared to LSP.

Install the SCIP Python indexer:

```bash
# Install scip-python globally via npm
npm install -g @sourcegraph/scip-python
```

**Note**: SCIP provides identical accuracy to LSP but with dramatically better performance. When available, blarify will automatically use SCIP for reference resolution.

# Article

Read our article on Medium to learn more about the motivation behind this project:

[➡️ How we built a tool to turn any codebase into a graph of its relationships](https://medium.com/@v4rgas/how-we-built-a-tool-to-turn-any-code-base-into-a-graph-of-its-relationships-23c7bd130f13)

# Future Work

- [x] Gracefully update the graph when new files are added, deleted, or modified
- [x] Add more language servers
- [ ] Experiment with parallelizing the language server requests

# Need help?

If you need help, want to report a bug, or have a feature request, please open an issue on this repository.

You can also reach out to us at [Discord](https://discord.gg/s8pqnPt5AP)
