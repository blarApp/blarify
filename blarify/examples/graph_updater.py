from blarify.project_graph_updater import ProjectGraphUpdater, UpdatedFile
from blarify.db_managers.neo4j_manager import Neo4jManager
from blarify.db_managers.falkordb_manager import FalkorDBManager
from blarify.graph.graph_environment import GraphEnvironment

import dotenv
import os


def build(root_path: str = None):
    graph_environment = GraphEnvironment(entity_id="organization", repo_id="repo")
    
    updater = ProjectGraphUpdater(
        updated_files=get_updated_files(),
        graph_environment=graph_environment,
        root_path=root_path,
        extensions_to_skip=[".json"],
        names_to_skip=["__pycache__", ".venv", ".git", ".env", "node_modules"],
    )
    graph_update = updater.build()

    relationships = graph_update.graph.get_relationships_as_objects()
    nodes = graph_update.graph.get_nodes_as_objects()

    save_to_neo4j(relationships, nodes)


def get_updated_files():
    # List of files that have been modified
    return [
        UpdatedFile(path="file:///path/to/project/src/services/user_service.py"),
        UpdatedFile(path="file:///path/to/project/src/utils/helpers.py"),
    ]


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


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)

    dotenv.load_dotenv()
    root_path = os.getenv("ROOT_PATH")
    build(root_path=root_path)