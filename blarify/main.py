from typing import Optional
from blarify.project_graph_creator import ProjectGraphCreator
from blarify.project_file_explorer import ProjectFilesIterator
from blarify.project_file_explorer import ProjectFileStats
from blarify.project_graph_updater import ProjectGraphUpdater
from blarify.project_graph_diff_creator import (
    PreviousNodeState,
    ProjectGraphDiffCreator,
)
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
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


def main_with_documentation(root_path: str = None, blarignore_path: Optional[str] = None):
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
    graph_creator = ProjectGraphCreator(
        root_path,
        lsp_query_helper,
        project_files_iterator,
    )
    graph = graph_creator.build()

    # Get graph data
    relationships = graph.get_relationships_as_objects()
    nodes = graph.get_nodes_as_objects()

    print(f"\n✅ Graph built: {len(nodes)} nodes and {len(relationships)} relationships")

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
            max_workers=100,
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

    repoId = "test"
    entity_id = "test"
    graph_manager = Neo4jManager(repoId, entity_id)

    # Initialize LLM provider
    llm_provider = LLMProvider()

    # Initialize graph environment
    graph_environment = GraphEnvironment(
        entity_id,
        repoId,
        root_path,
    )

    documentation_creator = DocumentationCreator(
        db_manager=graph_manager,
        agent_caller=llm_provider,
        graph_environment=graph_environment,
        max_workers=50,
    )

    # Step 3: Run documentation generation
    print("\n🚀 Phase 3: Running documentation generation workflow...")
    print("   Processing code structure and generating descriptions...")

    # Create documentation using the simple method orchestration
    doc_result = documentation_creator.create_documentation(
        target_paths=None,  # Process entire codebase
        generate_embeddings=False,  # Skip embeddings for now
    )

    # Step 4: Show results
    print("\n📊 Documentation Generation Results:")
    if doc_result.error:
        print(f"   ❌ Error: {doc_result.error}")
    else:
        print("   ✅ Success!")
        print(f"   - Information nodes created: {doc_result.total_nodes_processed}")
        print(f"   - Documentation nodes: {len(doc_result.documentation_nodes)}")
        print(f"   - Processing time: {doc_result.processing_time_seconds:.2f} seconds")

    # Step 5: Close resources
    graph_manager.close()

    print("\n✨ Integrated workflow completed!")


def main_with_documentation_new(root_path: str = None, blarignore_path: str = None):
    """Main function that demonstrates the integrated documentation generation workflow."""
    print("🚀 Starting integrated graph building and documentation generation (4-layer architecture)...")

    # Use the newer code...
    lsp_query_helper = LspQueryHelper(root_uri=root_path)
    lsp_query_helper.start()

    project_files_iterator = ProjectFilesIterator(
        root_path=root_path,
        blarignore_path=blarignore_path,
        extensions_to_skip=[".json", ".xml"],
    )

    ProjectFileStats(project_files_iterator).print(limit=10)
    repoId = "test_repo"

    # Build the graph
    graph_creator = ProjectGraphCreator(
        root_path,
        lsp_query_helper,
        project_files_iterator,
    )
    graph = graph_creator.build()

    relationships = graph.get_relationships_as_objects()
    nodes = graph.get_nodes_as_objects()

    print(f"Graph built: {len(nodes)} nodes and {len(relationships)} relationships")

    # Initialize components
    entity_id = "test_company"
    graph_manager = Neo4jManager(repoId, entity_id)
    graph_manager.save_graph(nodes, relationships)
    print("Graph saved to database")

    # Get documentation result using the newer workflow creator
    llm_provider = LLMProvider()
    graph_environment = GraphEnvironment(entity_id, repoId, root_path)

    workflow_creator = WorkflowCreator(
        db_manager=graph_manager,
        graph_environment=graph_environment,
    )

    # Run the documentation workflow
    workflow_result = workflow_creator.run_documentation_workflow()

    # Parse and display results
    if workflow_result.get("success"):
        print("\n✅ Documentation generation successful!")
        doc_result = workflow_result.get("documentation_result", {})
        print(f"   - Information nodes created: {doc_result.get('information_nodes_count', 0)}")
        print(f"   - Documentation nodes: {doc_result.get('documentation_nodes_count', 0)}")
        print(f"   - Total processing time: {doc_result.get('processing_time', 0):.2f} seconds")
    else:
        print(f"❌ Documentation generation failed: {workflow_result.get('error')}")

    # Step 5: Close resources
    print("\n🧹 Cleaning up...")
    lsp_query_helper.shutdown_exit_close()
    graph_manager.close()

    print("\n✨ Integrated workflow completed!")


def main_full(root_path: str = None, blarignore_path: str = None) -> None:
    """Original main function - builds the complete code graph from scratch."""
    print("\n🔨 Building complete code graph from scratch...")

    lsp_query_helper = LspQueryHelper(root_uri=root_path)
    lsp_query_helper.start()

    project_files_iterator = ProjectFilesIterator(
        root_path=root_path,
        blarignore_path=blarignore_path,
        extensions_to_skip=[".json", ".xml"],
        names_to_skip=[],
    )

    ProjectFileStats(project_files_iterator).print(limit=10)
    FileRemover.soft_delete_if_exists(root_path, "Gemfile")

    repoId = "test"
    graph_manager = Neo4jManager(repoId, "test")

    graph_creator = ProjectGraphCreator(
        root_path,
        lsp_query_helper,
        project_files_iterator,
    )
    graph = graph_creator.build()

    relationships = graph.get_relationships_as_objects()
    nodes = graph.get_nodes_as_objects()

    graph_manager.save_graph(nodes, relationships)

    print("\n✅ Full graph build complete")
    print(f"   - Nodes created: {len(nodes)}")
    print(f"   - Relationships created: {len(relationships)}")

    graph_manager.close()
    lsp_query_helper.shutdown_exit_close()


def main_diff(root_path: str = None, blarignore_path: str = None, updated_files: list = None) -> None:
    """Creates a diff graph showing only changed files."""
    print("\n📝 Creating diff graph for changed files...")

    lsp_query_helper = LspQueryHelper(root_uri=root_path)
    lsp_query_helper.start()

    project_files_iterator = ProjectFilesIterator(
        root_path=root_path,
        blarignore_path=blarignore_path,
        extensions_to_skip=[".json", ".xml"],
        names_to_skip=[],
        updated_files=updated_files,
    )

    ProjectFileStats(project_files_iterator).print(limit=10)

    repoId = "test"
    graph_manager = Neo4jManager(repoId, "test")

    graph_creator = ProjectGraphCreator(
        root_path,
        lsp_query_helper,
        project_files_iterator,
    )
    graph = graph_creator.build()

    relationships = graph.get_relationships_as_objects()
    nodes = graph.get_nodes_as_objects()

    graph_manager.save_graph(nodes, relationships)

    print("\n✅ Diff graph created")
    print(f"   - Changed nodes: {len(nodes)}")
    print(f"   - Relationships: {len(relationships)}")

    graph_manager.close()
    lsp_query_helper.shutdown_exit_close()


def main_update(root_path: str = None, blarignore_path: str = None, updated_files=None):
    """Updates an existing graph with changes from specific files."""
    print("\n♻️ Updating existing graph with file changes...")

    if updated_files is None:
        updated_files = []

    lsp_query_helper = LspQueryHelper(root_uri=root_path)
    lsp_query_helper.start()

    project_files_iterator = ProjectFilesIterator(
        root_path=root_path,
        blarignore_path=blarignore_path,
        extensions_to_skip=[".json", ".xml"],
        names_to_skip=[],
        updated_files=updated_files,
    )

    ProjectFileStats(project_files_iterator).print(limit=10)

    repoId = "test"
    graph_manager = Neo4jManager(repoId, "test")

    updater = ProjectGraphUpdater(
        root_path,
        lsp_query_helper,
        project_files_iterator,
        graph_manager,
    )

    updater.update()

    print("\n✅ Graph update complete")

    graph_manager.close()
    lsp_query_helper.shutdown_exit_close()


def main_diff_with_previous(
    root_path: str = None, blarignore_path: str = None, previous_nodes_state: list[PreviousNodeState] = None
):
    """Creates a diff graph comparing current state to previous node states."""
    print("\n🔍 Creating diff graph with previous state comparison...")

    lsp_query_helper = LspQueryHelper(root_uri=root_path)
    lsp_query_helper.start()

    project_files_iterator = ProjectFilesIterator(
        root_path=root_path,
        blarignore_path=blarignore_path,
        extensions_to_skip=[".json", ".xml"],
        names_to_skip=[],
    )

    ProjectFileStats(project_files_iterator).print(limit=10)

    repoId = "test"
    graph_manager = Neo4jManager(repoId, "test")

    diff_creator = ProjectGraphDiffCreator(
        root_path,
        lsp_query_helper,
        project_files_iterator,
        previous_nodes_state,
    )

    graph = diff_creator.build()

    relationships = graph.get_relationships_as_objects()
    nodes = graph.get_nodes_as_objects()

    graph_manager.save_graph(nodes, relationships)

    print("\n✅ Diff graph with previous state created")
    print(f"   - Nodes: {len(nodes)}")
    print(f"   - Relationships: {len(relationships)}")

    graph_manager.close()
    lsp_query_helper.shutdown_exit_close()


def test_github_integration(root_path: str = None, blarignore_path: str = None):
    """Test function to verify GitHub integration with a simple Blarify graph."""
    print("🧪 Testing GitHub Integration...")

    # Build a minimal graph for testing
    lsp_query_helper = LspQueryHelper(root_uri=root_path)
    lsp_query_helper.start()

    project_files_iterator = ProjectFilesIterator(
        root_path=root_path,
        blarignore_path=blarignore_path,
        extensions_to_skip=[".json", ".xml"],
        names_to_skip=["__pycache__", ".git", "node_modules"],
        # Only process a subset of files for faster testing
        updated_files=["blarify/integrations/github_creator.py", "tests/unit/test_github_creator.py"],
    )

    repoId = "github_test"
    entity_id = "test_entity"
    graph_manager = Neo4jManager(repoId, entity_id)

    try:
        # Build minimal graph
        graph_creator = ProjectGraphCreator(root_path, lsp_query_helper, project_files_iterator)
        graph = graph_creator.build()

        relationships = graph.get_relationships_as_objects()
        nodes = graph.get_nodes_as_objects()

        print(f"Test graph built: {len(nodes)} nodes and {len(relationships)} relationships")

        # Save to database
        graph_manager.save_graph(nodes, relationships)

        # Set up GitHub integration
        graph_environment = GraphEnvironment("test", "main", root_path)

        # Get GitHub token from environment
        github_token = os.getenv("GITHUB_TOKEN")
        if not github_token:
            print("⚠️ No GITHUB_TOKEN found, using unauthenticated access (rate limited)")

        # Initialize GitHubCreator for the Blarify repository
        github_creator = GitHubCreator(
            db_manager=graph_manager,
            graph_environment=graph_environment,
            github_token=github_token,
            repo_owner="blarApp",  # Blarify repository owner
            repo_name="blarify",  # Blarify repository name
        )

        print("\n🔄 Running PR-based integration (traditional approach)...")

        # Test PR-based integration (traditional approach)
        pr_result = github_creator.create_github_integration_from_prs(pr_numbers=[100], save_to_database=True)

        if pr_result.error:
            print(f"❌ PR integration failed: {pr_result.error}")
        else:
            print("✅ PR integration successful!")
            print(f"   - PRs processed: {pr_result.total_prs}")
            print(f"   - Commits found: {pr_result.total_commits}")
            print(f"   - Relationships created: {len(pr_result.relationships)}")

        print("\n🔄 Running blame-based integration (node-based approach)...")

        # Test blame-based integration for specific nodes
        # First, get some sample nodes from the graph
        with graph_manager.driver.session() as session:
            result = session.run(
                """
                MATCH (n:FUNCTION)
                RETURN n.hashed_id as id LIMIT 3
                """
            ).data()

            if result:
                node_ids = [r["id"] for r in result]
                print(f"   Testing with {len(node_ids)} function nodes")

                blame_result = github_creator.create_github_integration_from_nodes(
                    node_ids=node_ids, save_to_database=True
                )

                if blame_result.error:
                    print(f"❌ Blame integration failed: {blame_result.error}")
                else:
                    print("✅ Blame integration successful!")
                    print(f"   - Commits found: {blame_result.total_commits}")
                    print(f"   - PRs found: {blame_result.total_prs}")
                    print(f"   - Relationships created: {len(blame_result.relationships)}")

        print("\n✨ GitHub integration test completed!")

    finally:
        graph_manager.close()
        lsp_query_helper.shutdown_exit_close()


def test_blame_integration_single_function(root_path: str = None, blarignore_path: str = None):
    """Test the blame integration for a single random function using existing graph.

    This function:
    1. Uses existing Neo4j credentials from .env
    2. Connects to existing graph in Neo4j database
    3. Runs the GitHub blame integration for one random function
    4. Verifies the MODIFIED_BY relationships are created with blame attribution
    """

    print("🔬 Testing Blame Integration for Blarify Repository...")
    print("=" * 60)

    # Use .env Neo4j credentials
    print("\n🗄️ Using Neo4j from .env configuration...")
    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_username = os.getenv("NEO4J_USERNAME")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    if not neo4j_uri or not neo4j_username or not neo4j_password:
        print("❌ Missing Neo4j credentials in .env file!")
        return None

    print(f"   Neo4j URI: {neo4j_uri}")
    print(f"   Username: {neo4j_username}")

    # Use test repo configuration with entity_id = 'test-blame'
    repoId = "blarify_blame_test"
    entity_id = "test-blame"
    graph_manager = Neo4jManager(repoId, entity_id)

    try:
        # Step 1: Get a function from embedding_service.py (modified in PR #275)
        print("\n🎲 Selecting a function from embedding_service.py (from PR #275)...")
        with graph_manager.driver.session() as session:
            # Query specifically for functions in embedding_service.py
            query = """
            MATCH (f:FUNCTION)
            WHERE f.path CONTAINS 'embedding_service.py'
                AND f.path CONTAINS 'services'
            RETURN f.hashed_id as id, f.name as name, f.path as path, f.start_line as start_line, f.end_line as end_line
            ORDER BY f.name
            LIMIT 20
            """
            result = session.run(query).data()

            if not result:
                print("❌ No functions found in embedding_service.py! Trying all functions...")
                # Fallback to any test function
                query = """
                MATCH (f:FUNCTION)
                WHERE f.path CONTAINS 'test_documentation_creation.py'
                RETURN f.hashed_id as id, f.name as name, f.path as path, f.start_line as start_line, f.end_line as end_line
                LIMIT 50
                """
                result = session.run(query).data()

            if not result:
                print("❌ No functions found in the graph!")
                return None

            # Select the first function (more predictable for testing)
            selected_function = result[0]
            print(f"   Selected: {selected_function['name']} in {selected_function['path']}")
            print(f"   Lines: {selected_function['start_line']}-{selected_function['end_line']}")
            print(f"   Available functions: {len(result)}")
            print("   This test file should have commits with PRs attached")

        # Step 2: Set up GitHub integration with blame
        print("\n🐙 Running GitHub Blame Integration...")
        graph_environment = GraphEnvironment("test", "main", root_path)

        # Get GitHub token from environment
        github_token = os.getenv("GITHUB_TOKEN")
        if not github_token:
            print("⚠️  No GITHUB_TOKEN found, using unauthenticated access")

        # Create GitHubCreator for the Blarify repository
        github_creator = GitHubCreator(
            db_manager=graph_manager,
            graph_environment=graph_environment,
            github_token=github_token,
            repo_owner="blarApp",
            repo_name="blarify",
        )

        # Step 4: Run blame-based integration for the selected function
        print(f"\n🔍 Fetching blame information for function: {selected_function['name']}...")

        # Use the node-based blame approach
        result = github_creator.create_github_integration_from_nodes(
            node_ids=[selected_function["id"]], save_to_database=True
        )

        if result.error:
            print(f"❌ Blame integration failed: {result.error}")
            return None

        print("✅ Blame integration completed!")
        print(f"   - Commits found: {result.total_commits}")
        print(f"   - PRs found: {result.total_prs}")
        print(f"   - Relationships created: {len(result.relationships)}")

        # Step 5: Verify the blame attribution in the database
        print("\n🔎 Verifying blame attribution...")
        with graph_manager.driver.session() as session:
            # Query for MODIFIED_BY relationships with blame attribution
            query = """
            MATCH (f:FUNCTION {hashed_id: $function_id})-[r:MODIFIED_BY]->(c:INTEGRATION)
            WHERE r.attribution_method = 'blame'
            RETURN f.name as function_name,
                   c.external_id as commit_sha,
                   c.author as author,
                   c.title as commit_message,
                   r.blamed_lines as blamed_lines,
                   r.total_lines_affected as lines_affected
            """

            blame_results = session.run(query, function_id=selected_function["id"]).data()

            if blame_results:
                print(f"   Found {len(blame_results)} blame attributions:")
                for i, blame in enumerate(blame_results[:3], 1):  # Show first 3
                    print(f"\n   {i}. Commit: {blame['commit_sha'][:8]}")
                    print(f"      Author: {blame['author']}")
                    print(f"      Message: {blame['commit_message'][:60]}...")
                    print(f"      Lines affected: {blame['lines_affected']}")
            else:
                print("   ⚠️  No blame attributions found (function may be new or API limits reached)")

        # Step 6: Show integration summary
        print("\n📊 Integration Summary:")
        with graph_manager.driver.session() as session:
            # Count all MODIFIED_BY relationships created
            query = """
            MATCH ()-[r:MODIFIED_BY]->(:INTEGRATION)
            WHERE r.attribution_method = 'blame'
            RETURN count(r) as total_blame_relationships
            """
            count_result = session.run(query).single()
            print(f"   Total MODIFIED_BY relationships with blame: {count_result['total_blame_relationships']}")

            # Show commit details
            if result.commit_nodes:
                print(f"\n   Commits processed ({len(result.commit_nodes)} total):")
                for commit in result.commit_nodes[:5]:  # Show first 5
                    print(f"   - {commit.external_id[:8]}: {commit.title[:50]}...")
                    if commit.metadata.get("pr_number"):
                        print(f"     (Part of PR #{commit.metadata['pr_number']})")

            # Show PR details
            if result.pr_nodes:
                print(f"\n   Pull Requests linked ({len(result.pr_nodes)} total):")
                for pr in result.pr_nodes[:3]:  # Show first 3
                    print(f"   - PR #{pr.external_id}: {pr.title[:50]}...")

        print("\n✨ Blame integration test completed successfully!")
        print("=" * 60)

        return result

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return None

    finally:
        print("\n🧹 Cleaning up resources...")
        graph_manager.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dotenv.load_dotenv()

    # Use current blarify repository for testing
    root_path = "/Users/berrazuriz/Desktop/Blar/repositories/temp/blarify"
    blarignore_path = os.getenv("BLARIGNORE_PATH")

    # Run the new blame integration test for a single function
    test_documentation_only(root_path=root_path)
