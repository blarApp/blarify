from blarify.project_file_explorer import ProjectFilesIterator
from blarify.project_graph_updater import ProjectGraphUpdater, UpdatedFile
from blarify.db_managers.neo4j_manager import Neo4jManager
from blarify.code_references import LspQueryHelper
from blarify.graph.graph_environment import GraphEnvironment

import dotenv
import os

import logging

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

NAMES_TO_SKIP = [
    ".env",
    ".git",
    ".venv",
    ".ruff_cache",
    "__pycache__",
    "poetry.lock",
    "yarn.lock",
    "Pipfile.lock",
    "Gemfile.lock",
    "Guardfile",
    "422.html",
    "package-lock.json",
    "migrations",
    "node_modules",
    "public",
    "build",
    "dist",
    "static",
    "versions",
]

def update(updated_files: list, root_uri: str = None, blarignore_path: str = None):
    lsp_query_helper = LspQueryHelper(root_uri=root_uri)
    lsp_query_helper.start()

    project_files_iterator = ProjectFilesIterator(
        root_path=root_uri,
        blarignore_path=blarignore_path,
        names_to_skip=NAMES_TO_SKIP,
    )

    repoId = "test"
    entity_id = "test"
    graph_manager = Neo4jManager(repoId, entity_id)

    delete_updated_files_from_neo4j(updated_files, graph_manager)

    graph_diff_creator = ProjectGraphUpdater(
        updated_files=updated_files,
        root_path=root_uri,
        lsp_query_helper=lsp_query_helper,
        project_files_iterator=project_files_iterator,
        graph_environment=GraphEnvironment("dev", "MAIN", root_uri),
    )

    graph = graph_diff_creator.build_hierarchy_only()

    relationships = graph.get_relationships_as_objects()
    nodes = graph.get_nodes_as_objects()

    print(f"Saving graph with {len(nodes)} nodes and {len(relationships)} relationships")
    graph_manager.save_graph(nodes, relationships)
    graph_manager.close()
    lsp_query_helper.shutdown_exit_close()


def delete_updated_files_from_neo4j(updated_files, db_manager: Neo4jManager):
    for updated_file in updated_files:
        db_manager.detatch_delete_nodes_with_path(updated_file.path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dotenv.load_dotenv()
    root_path = os.getenv("ROOT_PATH")
    blarignore_path = os.getenv("BLARIGNORE_PATH")
    paths_to_update = os.getenv("PATHS_TO_UPDATE")
    paths_to_update = paths_to_update.split(";")



    print("Updating")
    update(
        updated_files=[
            UpdatedFile(
                path=path,
            )
            for path in paths_to_update
        ],
        root_uri=root_path,
    )