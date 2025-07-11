from typing import Optional

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.db_managers.neo4j_manager import Neo4jManager
from blarify.db_managers.falkordb_manager import FalkorDBManager
from blarify.documentation.semantic_analyzer import LLMProvider

import dotenv


def build(root_path: str = None, include_documentation: bool = False, llm_provider: Optional[LLMProvider] = None):
    graph_builder = GraphBuilder(
        root_path=root_path, extensions_to_skip=[".json"], names_to_skip=["__pycache__", ".venv", ".git"]
    )
    
    # Use FalkorDB for this example
    db_manager = FalkorDBManager(repo_id="repo", entity_id="organization")
    
    # Build graph with optional documentation layer
    graph = graph_builder.build(
        include_documentation=include_documentation,
        llm_provider=llm_provider,
        db_manager=db_manager if include_documentation else None
    )

    relationships = graph.get_relationships_as_objects()
    nodes = graph.get_nodes_as_objects()
    
    # Filter nodes by layer if needed
    code_nodes = [n for n in nodes if n.get('attributes', {}).get('layer', 'code') == 'code']
    doc_nodes = [n for n in nodes if n.get('attributes', {}).get('layer', 'code') == 'documentation']
    
    print(f"Code layer: {len(code_nodes)} nodes")
    if include_documentation:
        print(f"Documentation layer: {len(doc_nodes)} nodes")

    # Save everything to database
    db_manager.save_graph(nodes, relationships)
    db_manager.close()


def save_to_neo4j(relationships, nodes):
    graph_manager = Neo4jManager(repo_id="repo", entity_id="organization")

    print(f"Saving graph with {len(nodes)} nodes and {len(relationships)} relationships")
    graph_manager.save_graph(nodes, relationships)
    graph_manager.close()


def save_to_falkordb(relationships, nodes):
    graph_manager = FalkorDBManager(repo_id="repo", entity_id="organization")

    print(f"Saving graph with {len(nodes)} nodes and {len(relationships)} relationships")
    graph_manager.save_graph(nodes, relationships)
    graph_manager.close()


def build_with_documentation_example(root_path: str):
    """Example of building a graph with documentation layer.
    
    Note: This requires an LLM provider to be implemented.
    """
    # TODO: Implement your LLM provider
    # Example:
    # class MyLLMProvider(LLMProvider):
    #     def analyze(self, prompt: str, context: Dict[str, Any]) -> str:
    #         # Your LLM implementation here
    #         pass
    #
    # llm = MyLLMProvider()
    # build(root_path=root_path, include_documentation=True, llm_provider=llm)
    pass


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)

    dotenv.load_dotenv()
    root_path = "/Users/berrazuriz/Desktop/Blar/repositories/blar-django-server"
    
    # Build without documentation (default)
    build(root_path=root_path)
    
    # To build with documentation, uncomment and implement LLM provider:
    # build_with_documentation_example(root_path)
