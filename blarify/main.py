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
from blarify.documentation.workflow_analysis_workflow import WorkflowAnalysisWorkflow

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
        graph_environment = GraphEnvironment("dev", "main", root_path)
        documentation_workflow = DocumentationWorkflow(
            company_id=entity_id,
            company_graph_manager=graph_manager,
            repo_id=repoId,
            graph_environment=graph_environment,
            agent_caller=llm_provider,
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
                print(f"   {i + 1}. [{doc_type}] {content}...")

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


def test_documentation_only(root_path: str = None):
    """Test only the documentation workflow, assuming the graph already exists in the database."""
    print("📚 Testing documentation generation workflow only...")

    repoId = "test"
    entity_id = "test"
    graph_manager = Neo4jManager(repoId, entity_id)

    try:
        # Initialize the documentation workflow
        llm_provider = LLMProvider()
        graph_environment = GraphEnvironment("dev", "main", root_path)
        documentation_workflow = DocumentationWorkflow(
            company_id=entity_id,
            company_graph_manager=graph_manager,
            repo_id=repoId,
            graph_environment=graph_environment,
            agent_caller=llm_provider,
        )

        print("📝 Compiling do        cumentation workflow...")
        documentation_workflow.compile_graph()

        print("🔄 Starting documentation generation...")

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
                print(f"   {i + 1}. [{doc_type}] {content}...")

        return result

    except Exception as e:
        print(f"❌ Documentation generation failed: {e}")
        import traceback

        traceback.print_exc()
        return None

    finally:
        # Clean up resources
        graph_manager.close()


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


def test_workflow_analysis_only(root_path: str = None):
    """Test only the WorkflowAnalysisWorkflow with real framework data and InformationNodes."""
    print("🔬 Testing WorkflowAnalysisWorkflow independently...")

    # Setup infrastructure
    repoId = "test"
    entity_id = "test"
    graph_manager = Neo4jManager(repoId, entity_id)

    try:
        # Real framework detection data (from actual run)
        detected_framework = {
            "description": "This project is a modern, modular Python application focused on multi-language code analysis and graph building using the Language Server Protocol (LSP). The technology stack centers on Python 3.10+, Poetry for dependency management, and a heavy use of libraries for syntax analysis (tree-sitter and multiple language grammars), code intelligence (jedi-language-server, multilspy), and graph database integration (Neo4j, falkordb). The architecture is built for extensibility and multi-language support, emphasizing code parsing, semantic enrichment, and transformation workflows. There is no web, frontend, or desktop/mobile GUI aspect: the project is a sophisticated backend service or developer tool. The directory structure is highly modular, with clear separations for graph database management (db_managers/), core graph modeling (graph/), LSP/code analysis and cross-referencing (code_hierarchy/, code_references/), AI-driven or agent workflows (agents/), and key supporting infrastructure (utils/, vendor/). This points to a component-based, layered architecture designed for maintainability and easy extension to new code languages or analysis features. The integration with LLM frameworks (langchain, langgraph) suggests advanced capabilities for semantic code search, summarization, or transformation. The project's primary purpose is to abstract, parse, and represent codebases from multiple languages as rich graphs of entities and relationships. It leverages LSP servers and tree-sitter grammars to extract code structure, then stores and analyzes this information in an external graph database. The system can be used for code exploration, documentation, refactoring assistance, or as a foundation for more advanced developer tools. Test files in the root and the presence of extensive documentation indicate a mature, well-structured project workflow. Development environment expectations assume familiarity with Poetry, graph/Neo4j ecosystems, and code intelligence libraries. For strategic analysis, focus should be given to the main business logic and graph orchestration folders: db_managers/ for database interaction, graph/ for core graph computation and modeling, agents/ for automation/AI/LSP integrations, code_hierarchy/ and code_references/ for code structure and semantic relationships, project_file_explorer/ for code/project abstraction, and utils/ and vendor/ for supporting infrastructure. This modular breakup is essential for understanding how the system ingests code, builds graphs, and orchestrates external intelligence.",
            "name": "Python LSP Code Analysis Framework",
            "type": "Python Backend Service",
        }

        # Real main folders (from actual run)
        main_folders = [
            "blarify/blarify/graph/",
            "blarify/blarify/db_managers/",
            "blarify/blarify/agents/",
            "blarify/blarify/code_hierarchy/",
            "blarify/blarify/code_references/",
            "blarify/blarify/project_file_explorer/",
            "blarify/blarify/utils/",
            "blarify/blarify/vendor/",
        ]

        # Create WorkflowAnalysisWorkflow
        print("🔧 Setting up WorkflowAnalysisWorkflow...")
        llm_provider = LLMProvider()
        graph_environment = GraphEnvironment("dev", "main", root_path)
        workflow_analysis = WorkflowAnalysisWorkflow(
            company_id=entity_id,
            company_graph_manager=graph_manager,
            repo_id=repoId,
            graph_environment=graph_environment,
            agent_caller=llm_provider,
        )

        # Prepare input data
        workflow_input = {
            "main_folders": main_folders,
            "detected_framework": detected_framework,
        }

        # Run the workflow analysis
        print(f"🚀 Running WorkflowAnalysisWorkflow with {len(main_folders)} main folders...")
        result = workflow_analysis.run(workflow_input)

        # Display results
        discovered_workflows = result.get("discovered_workflows", [])
        error = result.get("error")

        if error:
            print(f"❌ WorkflowAnalysisWorkflow encountered error: {error}")
        else:
            print("✅ WorkflowAnalysisWorkflow completed successfully!")
            print(f"📋 Results: {len(discovered_workflows)} workflows discovered")

            if discovered_workflows:
                print("\n🔍 Discovered Workflows:")
                for i, workflow in enumerate(discovered_workflows):
                    name = workflow.get("name", "Unknown")
                    description = workflow.get("description", "No description")
                    entry_points = workflow.get("entry_points", [])
                    scope = workflow.get("scope", "Unknown")

                    print(f"   {i + 1}. **{name}**")
                    print(f"      Description: {description[:150]}{'...' if len(description) > 150 else ''}")
                    print(f"      Entry Points: {', '.join(entry_points) if entry_points else 'None'}")
                    print(f"      Scope: {scope}")
                    print()
            else:
                print("📋 No workflows were discovered.")

    except Exception as e:
        print(f"❌ WorkflowAnalysisWorkflow test failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        print("🧹 Cleaning up resources...")
        graph_manager.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dotenv.load_dotenv()
    # Use current blarify repository for testing
    root_path = "/Users/berrazuriz/Desktop/Blar/repositories/blarify"
    # root_path = "/Users/berrazuriz/Desktop/Blar/repositories/blar-django-server"
    blarignore_path = os.getenv("BLARIGNORE_PATH")
    # Comment out regular main() and use documentation integration
    # main(root_path=root_path, blarignore_path=blarignore_path)

    # Test the WorkflowAnalysisWorkflow only (assuming InformationNodes exist)
    # test_workflow_analysis_only(root_path=root_path)

    # Other test options (commented out):
    test_documentation_only(root_path=root_path)  # Test full documentation workflow
    # main_with_documentation(root_path=root_path, blarignore_path=blarignore_path)  # Full pipeline
