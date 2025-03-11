from blarify.db_managers.kuzudb_manager import KuzuDBManager
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.db_managers.neo4j_manager import Neo4jManager
from blarify.db_managers.falkordb_manager import FalkorDBManager

import dotenv
import os


def build(root_path: str = None):
    graph_builder = GraphBuilder(
        root_path=root_path, extensions_to_skip=[".json"], names_to_skip=["__pycache__", ".venv", ".git"]
    )
    graph = graph_builder.build()

    relationships = graph.get_relationships_as_objects()
    nodes = graph.get_nodes_as_objects()

    # save_to_falkordb(relationships, nodes)
    save_to_kuzudb(relationships, nodes)


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
    
def save_to_kuzudb(relationships, nodes):
    graph_manager = KuzuDBManager()

    print(f"Saving graph with {len(nodes)} nodes and {len(relationships)} relationships")
    graph_manager.save_graph(nodes, relationships)
    graph_manager.close()


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)

    dotenv.load_dotenv()
    root_path = "/home/juan/devel/blar/examples/ts-project"
    build(root_path=root_path)
