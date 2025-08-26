from typing import Optional

from blarify.project_graph_creator import ProjectGraphCreator
from blarify.project_file_explorer import ProjectFilesIterator
from blarify.project_file_explorer import ProjectFileStats
from blarify.project_graph_updater import ProjectGraphUpdater
from blarify.project_graph_diff_creator import (
    PreviousNodeState,
    ProjectGraphDiffCreator,
)
from blarify.db_managers.neo4j_manager import Neo4jManager
from blarify.code_references import LspQueryHelper
from blarify.graph.graph_environment import GraphEnvironment
from blarify.utils.file_remover import FileRemover
from blarify.agents.llm_provider import LLMProvider
from blarify.documentation.documentation_creator import DocumentationCreator
from blarify.documentation.workflow_creator import WorkflowCreator
from blarify.integrations.github_creator import GitHubCreator

import dotenv
import os

import logging

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

logger = logging.getLogger(__name__)


def main_with_documentation(root_path: str = None, blarignore_path: str = None):
    """Main function that builds the graph and then runs the documentation generation workflow."""
    print("🚀 Starting integrated graph building and documentation generation...")

    # Step 1: Build the graph using existing infrastructure
    print("\n📊 Phase 1: Building code graph...")
    lsp_query_helper = LspQueryHelper(root_uri=root_path)
    lsp_query_helper.start()

    project_files_iterator = ProjectFilesIterator(
        root_path=root_path,
        blarignore_path=blarignore_path,
        extensions_to_skip=[".json", ".xml"],
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
        # Initialize the documentation creator (new architecture)
        llm_provider = LLMProvider()
        graph_environment = GraphEnvironment("dev", "main", root_path)
        documentation_creator = DocumentationCreator(
            db_manager=graph_manager,
            agent_caller=llm_provider,
            graph_environment=graph_environment,
            company_id=entity_id,
            repo_id=repoId,
        )

        print("📝 Starting documentation generation...")

        # Run the documentation creation
        result = documentation_creator.create_documentation()

        if result.error:
            print(f"❌ Documentation generation failed: {result.error}")
        else:
            print("✅ Documentation generation completed successfully!")

            # Print results summary
            print("\n📋 Documentation Results:")
            print(f"   - Generated nodes: {len(result.information_nodes)}")
            print(f"   - Processing time: {result.processing_time_seconds:.2f} seconds")
            print(f"   - Framework detected: {result.detected_framework.get('primary_framework', 'unknown')}")
            print(f"   - Total nodes processed: {result.total_nodes_processed}")

            if result.warnings:
                print(f"   - Warnings: {len(result.warnings)}")
                for warning in result.warnings[:3]:  # Show first 3 warnings
                    print(f"     * {warning}")

        # Print sample documentation
        if result.information_nodes:
            print("\n📄 Sample Documentation:")
            for i, doc in enumerate(result.information_nodes[:2]):  # Show first 2 docs
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

    repoId = "pydata__xarray-6938"
    entity_id = "swe_agent"
    graph_manager = Neo4jManager(repoId, entity_id)

    try:
        # Initialize the documentation workflow
        llm_provider = LLMProvider()
        graph_environment = GraphEnvironment("dev", "main", root_path)
        documentation_creator = DocumentationCreator(
            db_manager=graph_manager,
            agent_caller=llm_provider,
            graph_environment=graph_environment,
            company_id=entity_id,
            repo_id=repoId,
            max_workers=75,
        )

        print("📝 Starting documentation creation...")

        # Run the documentation creation
        result = documentation_creator.create_documentation(
            target_paths=["/blarify/0/pydata__xarray-6938/xarray/core/dataset.py#Dataset.swap_dims"]
        )

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
        root_path=root_path,
        blarignore_path=blarignore_path,
        extensions_to_skip=[".json", ".xml", ".pyi"],
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

    # print(f"Saving graph with {len(nodes)} nodes and {len(relationships)} relationships")
    # graph_manager.save_graph(nodes, relationships)
    # graph_manager.close()

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


def test_workflow_discovery_only(root_path: str = None):
    """Test only the WorkflowCreator with real framework data."""
    print("🔬 Testing WorkflowCreator independently...")

    # Setup infrastructure
    repoId = "test"
    entity_id = "test"
    graph_manager = Neo4jManager(repoId, entity_id)

    try:
        # Create WorkflowCreator
        print("🔧 Setting up WorkflowCreator...")
        graph_environment = GraphEnvironment("dev", "main", root_path)
        workflow_creator = WorkflowCreator(
            db_manager=graph_manager,
            graph_environment=graph_environment,
            company_id=entity_id,
            repo_id=repoId,
        )

        # Run workflow discovery
        print("🚀 Running WorkflowCreator...")
        result = workflow_creator.discover_workflows()

        # Display results
        error = result.error

        if error:
            print(f"❌ WorkflowCreator encountered error: {error}")
        else:
            print("✅ WorkflowCreator completed successfully!")

            print(f"\n📋 Discovered {len(result.discovered_workflows)} workflows:")
            for i, workflow in enumerate(result.discovered_workflows[:5]):  # Show first 5
                print(
                    f"   {i + 1}. {workflow.entry_point_name} -> {workflow.end_point_name or 'N/A'} ({workflow.total_execution_steps} steps)"
                )

            # Show analysis details
            print("\n🔍 Analysis Details:")
            print(f"   - Entry points analyzed: {result.total_entry_points}")
            print(f"   - Total workflows discovered: {result.total_workflows}")
            print(f"   - Discovery time: {result.discovery_time_seconds:.2f} seconds")

            if result.warnings:
                print(f"   - Warnings: {len(result.warnings)}")
                for warning in result.warnings[:3]:
                    print(f"     * {warning}")

    except Exception as e:
        print(f"❌ WorkflowCreator test failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        print("🧹 Cleaning up resources...")
        graph_manager.close()


def test_github_integration_only(root_path: str = None):
    """Test only the GitHub integration with the existing Blarify repository graph.

    This assumes the code graph already exists in Neo4j and fetches just 1 PR
    to demonstrate the GitHub integration functionality.
    """
    print("🐙 Testing GitHub Integration Layer...")
    print("=" * 60)

    # Setup
    repoId = "test"
    entity_id = "test"
    graph_manager = Neo4jManager(repoId, entity_id)

    try:
        # Initialize GitHub integration
        print("🔧 Setting up GitHub integration...")
        graph_environment = GraphEnvironment("dev", "main", root_path)

        # Get GitHub token from environment
        github_token = os.getenv("GITHUB_TOKEN")
        if not github_token:
            print("⚠️  No GITHUB_TOKEN found in environment, using unauthenticated access")
            print("   This may hit rate limits quickly!")

        # Create GitHubCreator for the Blarify repository
        github_creator = GitHubCreator(
            db_manager=graph_manager,
            graph_environment=graph_environment,
            github_token=github_token,
            repo_owner="blarApp",
            repo_name="blarify",
        )

        print("📍 Repository: blarApp/blarify")
        print(f"📍 Root path: {root_path}")
        print()

        print("🚀 Fetching GitHub data (1 merged PR only)...")
        print("-" * 40)

        # Fetch just 1 PR to demonstrate the integration
        result = github_creator.create_github_integration(pr_limit=1, save_to_database=True)

        if result.error:
            print(f"❌ GitHub integration failed: {result.error}")
            return None

        print()
        print("✅ GitHub Integration Complete!")
        print("=" * 60)

        # Display results
        print("\n📊 Integration Summary:")
        print(f"   - PRs processed: {result.total_prs}")
        print(f"   - Commits created: {result.total_commits}")
        print(f"   - Relationships created: {len(result.relationships)}")

        # Show PR details
        if result.pr_nodes:
            print("\n📋 Pull Request Details:")
            for pr in result.pr_nodes:
                print(f"   PR #{pr.external_id}: {pr.title}")
                print(f"   - Author: {pr.author}")
                print(f"   - Created: {pr.timestamp}")
                print(f"   - State: {pr.metadata.get('state', 'unknown')}")
                if pr.metadata.get("merged_at"):
                    print(f"   - Merged: {pr.metadata['merged_at']}")

        # Show commit details
        if result.commit_nodes:
            print(f"\n💾 Commits ({len(result.commit_nodes)} total):")
            for i, commit in enumerate(result.commit_nodes[:3]):  # Show first 3
                print(f"   {i + 1}. {commit.external_id[:7]}: {commit.title[:60]}")
                if commit.metadata.get("pr_number"):
                    print(f"      (Part of PR #{commit.metadata['pr_number']})")

        # Show relationship breakdown
        if result.relationships:
            print("\n🔗 Relationships Created:")
            rel_types = {}
            for rel in result.relationships:
                if hasattr(rel, "rel_type"):
                    rel_type_name = rel.rel_type.name
                    rel_types[rel_type_name] = rel_types.get(rel_type_name, 0) + 1

            for rel_type, count in rel_types.items():
                print(f"   - {rel_type}: {count}")

        # Query database to show MODIFIED_BY relationships
        print("\n🔍 Analyzing Code Modifications:")
        query = """
        MATCH (code:NODE)-[r:MODIFIED_BY]->(commit:INTEGRATION)
        RETURN code.name as code_name, 
               code.label as code_type,
               commit.title as commit_title,
               r.lines_added as lines_added,
               r.lines_deleted as lines_deleted
        LIMIT 5
        """

        with graph_manager.driver.session() as session:
            records = session.run(query).data()

            if records:
                print(f"   Found {len(records)} code modifications:")
                for record in records:
                    print(f"   - {record['code_type']} '{record['code_name']}'")
                    print(f"     Modified by: {record['commit_title'][:50]}")
                    print(f"     Changes: +{record['lines_added']}/-{record['lines_deleted']} lines")
            else:
                print("   No MODIFIED_BY relationships found (files may not be in code graph)")

        print("\n✨ GitHub integration test completed successfully!")
        return result

    except Exception as e:
        print(f"❌ GitHub integration test failed: {e}")
        import traceback

        traceback.print_exc()
        return None

    finally:
        print("\n🧹 Cleaning up resources...")
        graph_manager.close()


def test_targeted_workflow_discovery(root_path: str = None):
    """Test targeted workflow discovery with specific node_path."""
    print("🎯 Testing targeted workflow discovery...")

    repoId = "test"
    entity_id = "test"
    graph_manager = Neo4jManager(repoId, entity_id)

    test_node_path = "/blarify/0/blarify/blarify/project_graph_diff_creator.py#ProjectGraphDiffCreator.add_deleted_relationships_and_nodes"

    try:
        graph_environment = GraphEnvironment("dev", "main", root_path)
        workflow_creator = WorkflowCreator(
            db_manager=graph_manager,
            graph_environment=graph_environment,
            company_id=entity_id,
            repo_id=repoId,
        )

        print(f"🎯 Running targeted discovery for: {test_node_path}")
        result = workflow_creator.discover_workflows(node_path=test_node_path)

        if result.error:
            print(f"❌ Error: {result.error}")
        else:
            print("✅ Success!")
            print(f"   - Entry points: {result.total_entry_points}")
            print(f"   - Workflows: {result.total_workflows}")
            print(f"   - Time: {result.discovery_time_seconds:.2f}s")

        documentation_creator = DocumentationCreator(
            db_manager=graph_manager,
            agent_caller=LLMProvider(),
            graph_environment=graph_environment,
            company_id=entity_id,
            repo_id=repoId,
        )

        print("📝 Generating documentation for discovered workflows...")
        doc_result = documentation_creator.create_documentation(target_paths=[test_node_path])

        if doc_result.error:
            print(f"❌ Documentation generation failed: {doc_result.error}")
        else:
            print("✅ Documentation generated successfully!")
            print(f"   - Generated nodes: {len(doc_result.information_nodes)}")
            print(f"   - Processing time: {doc_result.processing_time_seconds:.2f} seconds")

            if doc_result.warnings:
                print(f"   - Warnings: {len(doc_result.warnings)}")
                for warning in doc_result.warnings[:3]:  # Show first 3 warnings
                    print(f"     * {warning}")

            # Print sample documentation
            if doc_result.information_nodes:
                print("\n📄 Sample Documentation:")
                for i, doc in enumerate(doc_result.information_nodes[:2]):  # Show first 2 docs
                    doc_type = doc.get("type", "unknown")
                    content = doc.get("content", doc.get("documentation", ""))[:200]
                    print(f"   {i + 1}. [{doc_type}] {content}...")

    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback

        traceback.print_exc()
    finally:
        graph_manager.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dotenv.load_dotenv()
    # Use current blarify repository for testing
    root_path = "/Users/berrazuriz/Desktop/Blar/repositories/blarify"
    # root_path = "/Users/berrazuriz/Desktop/Blar/repositories/blar-django-server"
    blarignore_path = os.getenv("BLARIGNORE_PATH")

    # Test the GitHub integration
    # test_github_integration_only(root_path=root_path)

    # Other test options (commented out):
    # main(root_path=root_path, blarignore_path=blarignore_path)  # Build graph
    # test_targeted_workflow_discovery(root_path=root_path)  # Test workflow discovery
    # Comment out regular main() and use documentation integration
    # main(root_path=root_path, blarignore_path=blarignore_path)

    # Test the targeted workflow discovery with node_path
    # test_targeted_workflow_discovery(root_path=root_path)

    # Other test options (commented out):
    test_documentation_only(root_path=root_path)  # Test full documentation workflow
    # main_with_documentation(root_path=root_path, blarignore_path=blarignore_path)  # Full pipeline
