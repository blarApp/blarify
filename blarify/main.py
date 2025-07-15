from typing import Optional

from blarify.project_graph_creator import ProjectGraphCreator
from blarify.project_file_explorer import ProjectFilesIterator
from blarify.project_file_explorer import ProjectFileStats
from blarify.project_graph_updater import ProjectGraphUpdater
from blarify.project_graph_diff_creator import PreviousNodeState, ProjectGraphDiffCreator
from blarify.db_managers.neo4j_manager import Neo4jManager
from blarify.code_references import LspQueryHelper
from blarify.graph.graph_environment import GraphEnvironment
from blarify.utils.file_remover import FileRemover
from blarify.agents.llm_provider import LLMProvider
from blarify.documentation.workflow import DocumentationWorkflow

import dotenv
import os

import logging

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")


def main_with_documentation(root_path: str = None, blarignore_path: str = None):
    """Main function that builds the graph and then runs the documentation generation workflow."""
    print("🚀 Starting integrated graph building and documentation generation...")

    # Step 1: Build the graph using existing infrastructure
    print("\n📊 Phase 1: Building code graph...")
    lsp_query_helper = LspQueryHelper(root_uri=root_path)
    lsp_query_helper.start()

    project_files_iterator = ProjectFilesIterator(
        root_path=root_path, blarignore_path=blarignore_path, extensions_to_skip=[".json", ".xml"]
    )

    ProjectFileStats(project_files_iterator).print(limit=10)
    FileRemover.soft_delete_if_exists(root_path, "Gemfile")

    repoId = "test"
    entity_id = "test"
    graph_manager = Neo4jManager(repoId, entity_id)

    graph_creator = ProjectGraphCreator(root_path, lsp_query_helper, project_files_iterator)
    graph = graph_creator.build()

    relationships = graph.get_relationships_as_objects()
    nodes = graph.get_nodes_as_objects()

    print(f"✅ Graph building completed: {len(nodes)} nodes and {len(relationships)} relationships")
    graph_manager.save_graph(nodes, relationships)

    # Step 2: Run documentation generation workflow
    print("\n📚 Phase 2: Generating documentation layer...")
    try:
        # Initialize the documentation workflow
        llm_provider = LLMProvider()
        documentation_workflow = DocumentationWorkflow(
            company_id=entity_id, company_graph_manager=graph_manager, environment="default", agent_caller=llm_provider
        )

        print("📝 Starting documentation generation workflow...")

        # Run the workflow
        result = documentation_workflow.run()

        print("✅ Documentation generation completed successfully!")

        # Print results summary
        generated_docs = result.get("generated_docs", [])
        print("\n📋 Documentation Results:")
        print(f"   - Generated docs: {len(generated_docs)}")
        print(
            f"   - Framework detected: {result.get('detected_framework', {}).get('framework', {}).get('name', 'unknown')}"
        )
        print(f"   - Key components: {len(result.get('key_components', []))}")
        print(f"   - Analyzed nodes: {len(result.get('analyzed_nodes', []))}")

        # Print sample documentation
        if generated_docs:
            print("\n📄 Sample Documentation:")
            for i, doc in enumerate(generated_docs[:2]):  # Show first 2 docs
                doc_type = doc.get("type", "unknown")
                content = doc.get("content", doc.get("documentation", ""))[:200]
                print(f"   {i+1}. [{doc_type}] {content}...")

        return result

    except Exception as e:
        print(f"❌ Documentation generation failed: {e}")
        import traceback

        traceback.print_exc()
        return None

    finally:
        # Clean up resources
        graph_manager.close()
        lsp_query_helper.shutdown_exit_close()


def main(
    root_path: str = None,
    blarignore_path: str = None,
    include_documentation: bool = False,
    llm_provider: Optional[LLMProvider] = None,
):
    lsp_query_helper = LspQueryHelper(root_uri=root_path)

    lsp_query_helper.start()

    project_files_iterator = ProjectFilesIterator(
        root_path=root_path, blarignore_path=blarignore_path, extensions_to_skip=[".json", ".xml"]
    )

    ProjectFileStats(project_files_iterator).print(limit=10)

    FileRemover.soft_delete_if_exists(root_path, "Gemfile")

    repoId = "test"
    entity_id = "test"
    graph_manager = Neo4jManager(repoId, entity_id)

    graph_creator = ProjectGraphCreator(root_path, lsp_query_helper, project_files_iterator)

    graph = graph_creator.build()

    relationships = graph.get_relationships_as_objects()
    nodes = graph.get_nodes_as_objects()

    print(f"Saving graph with {len(nodes)} nodes and {len(relationships)} relationships")
    graph_manager.save_graph(nodes, relationships)
    graph_manager.close()

    lsp_query_helper.shutdown_exit_close()


def main_diff(file_diffs: list, root_uri: str = None, blarignore_path: str = None):
    lsp_query_helper = LspQueryHelper(root_uri=root_uri)
    lsp_query_helper.start()

    project_files_iterator = ProjectFilesIterator(
        root_path=root_uri,
        blarignore_path=blarignore_path,
    )

    repoId = "test"
    entity_id = "test"
    graph_manager = Neo4jManager(repoId, entity_id)

    graph_diff_creator = ProjectGraphDiffCreator(
        root_path=root_uri,
        lsp_query_helper=lsp_query_helper,
        project_files_iterator=project_files_iterator,
        file_diffs=file_diffs,
        graph_environment=GraphEnvironment("dev", "MAIN", root_uri),
        pr_environment=GraphEnvironment("dev", "pr-123", root_uri),
    )

    graph = graph_diff_creator.build()

    relationships = graph.get_relationships_as_objects()
    nodes = graph.get_nodes_as_objects()

    print(f"Saving graph with {len(nodes)} nodes and {len(relationships)} relationships")
    graph_manager.save_graph(nodes, relationships)
    graph_manager.close()
    lsp_query_helper.shutdown_exit_close()


def main_update(updated_files: list, root_uri: str = None, blarignore_path: str = None):
    lsp_query_helper = LspQueryHelper(root_uri=root_uri)
    lsp_query_helper.start()

    project_files_iterator = ProjectFilesIterator(
        root_path=root_uri,
        blarignore_path=blarignore_path,
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

    graph = graph_diff_creator.build()

    relationships = graph.get_relationships_as_objects()
    nodes = graph.get_nodes_as_objects()

    print(f"Saving graph with {len(nodes)} nodes and {len(relationships)} relationships")
    graph_manager.save_graph(nodes, relationships)
    graph_manager.close()
    lsp_query_helper.shutdown_exit_close()


def delete_updated_files_from_neo4j(updated_files, db_manager: Neo4jManager):
    for updated_file in updated_files:
        db_manager.detatch_delete_nodes_with_path(updated_file.path)


def main_diff_with_previous(
    file_diffs: list,
    root_uri: str = None,
    blarignore_path: str = None,
    previous_node_states: list[PreviousNodeState] = None,
):
    lsp_query_helper = LspQueryHelper(root_uri=root_uri)
    lsp_query_helper.start()

    project_files_iterator = ProjectFilesIterator(
        root_path=root_uri,
        blarignore_path=blarignore_path,
    )

    repoId = "test"
    entity_id = "test"
    graph_manager = Neo4jManager(repoId, entity_id)

    graph_diff_creator = ProjectGraphDiffCreator(
        root_path=root_uri,
        lsp_query_helper=lsp_query_helper,
        project_files_iterator=project_files_iterator,
        file_diffs=file_diffs,
        graph_environment=GraphEnvironment("dev", "MAIN", root_uri),
        pr_environment=GraphEnvironment("dev", "pr-123", root_uri),
    )

    graph = graph_diff_creator.build_with_previous_node_states(previous_node_states=previous_node_states)

    relationships = graph.get_relationships_as_objects()
    nodes = graph.get_nodes_as_objects()

    print(f"Saving graph with {len(nodes)} nodes and {len(relationships)} relationships")

    # batch create nodes and relationships

    graph_manager.save_graph(nodes, relationships)
    graph_manager.close()
    lsp_query_helper.shutdown_exit_close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dotenv.load_dotenv()
    # Use current blarify repository for testing
    root_path = "/Users/berrazuriz/Desktop/Blar/repositories/blarify"
    # root_path = "/Users/berrazuriz/Desktop/Blar/repositories/blar-django-server"
    blarignore_path = os.getenv("BLARIGNORE_PATH")
    # Comment out regular main() and use documentation integration
    # main(root_path=root_path, blarignore_path=blarignore_path)

    # Test the documentation layer integration
    main_with_documentation(root_path=root_path, blarignore_path=blarignore_path)
    # main_diff(
    #     file_diffs=[
    #         FileDiff(
    #             path="file:///home/juan/devel/blar/lsp-poc/blarify/graph/node/utils/node_factory.py",
    #             diff_text="diff+++",
    #             change_type=ChangeType.ADDED,
    #         ),
    #         FileDiff(
    #             path="file:///home/juan/devel/blar/lsp-poc/blarify/graph/relationship/relationship_type.py",
    #             diff_text="diff+++",
    #             change_type=ChangeType.ADDED,
    #         ),
    #         FileDiff(
    #             path="file:///home/juan/devel/blar/lsp-poc/blarify/graph/relationship/relationship_creator.py",
    #             diff_text="diff+++",
    #             change_type=ChangeType.DELETED,
    #         ),
    #     ],
    #     root_uri=root_path,
    #     blarignore_path=blarignore_path,
    # )

    print("Updating")
    # main_update(
    #     updated_files=[
    #         # UpdatedFile("file:///temp/repos/development/main/0/encuadrado-web/encuadrado-web/schemas.py"),
    #         # UpdatedFile("file:///temp/repos/development/main/0/encuadrado-web/encuadrado-web/models.py"),
    #     ],
    #     root_uri=root_path,
    #     blarignore_path=blarignore_path,
    # )
    # main_update(
    #     updated_files=[
    #         UpdatedFile("file:///temp/repos/development/main/0/encuadrado-web/encuadrado-web/schemas.py"),
    #         UpdatedFile("file:///temp/repos/development/main/0/encuadrado-web/encuadrado-web/models.py"),
    #     ],
    #     root_uri=root_path,
    #     blarignore_path=blarignore_path,
    # )

    # main_diff_with_previous(
    #     file_diffs=[
    #         FileDiff(
    #             path="file:///home/juan/devel/blar/blar-qa/blar/agents/tasks.py",
    #             diff_text="diff+++",
    #             change_type=ChangeType.MODIFIED,
    #         ),
    #     ],
    #     root_uri=root_path,
    #     blarignore_path=blarignore_path,
    #     previous_node_states=[
    #         PreviousNodeState(
    #             "/dev/MAIN/blar-qa/blar/agents/tasks.py.execute_pr_report_agent_task",
    #             open("/home/juan/devel/blar/lsp-poc/blarify/example", "r").read(),
    #         ),
    #         PreviousNodeState(
    #             "/dev/MAIN/blar-qa/blar/agents/tasks.py.execute_pr_report_agent_taski",
    #             open("/home/juan/devel/blar/lsp-poc/blarify/example", "r").read(),
    #         ),
    #     ],
    # )
