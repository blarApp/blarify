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
from blarify.code_references.hybrid_resolver import (
    HybridReferenceResolver,
    ResolverMode,
)
from blarify.graph.graph_environment import GraphEnvironment
from blarify.utils.file_remover import FileRemover
from blarify.agents.llm_provider import LLMProvider
from blarify.documentation.documentation_creator import DocumentationCreator
from blarify.documentation.workflow_creator import WorkflowCreator

import dotenv
import os
import time

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
        root_path=root_path,
        blarignore_path=blarignore_path,
        extensions_to_skip=[".json", ".xml"],
    )

    ProjectFileStats(project_files_iterator).print(limit=10)
    FileRemover.soft_delete_if_exists(root_path, "Gemfile")

    repoId = "test"
    entity_id = "test"
    graph_manager = Neo4jManager(repoId, entity_id)

    graph_creator = ProjectGraphCreator(
        root_path, lsp_query_helper, project_files_iterator
    )
    graph = graph_creator.build()

    relationships = graph.get_relationships_as_objects()
    nodes = graph.get_nodes_as_objects()

    print(
        f"✅ Graph building completed: {len(nodes)} nodes and {len(relationships)} relationships"
    )
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
            print(
                f"   - Framework detected: {result.detected_framework.get('primary_framework', 'unknown')}"
            )
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
        )

        print("📝 Starting documentation creation...")

        # Run the documentation creation
        result = documentation_creator.create_documentation()

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

    graph_creator = ProjectGraphCreator(
        root_path, lsp_query_helper, project_files_iterator
    )

    graph = graph_creator.build()

    relationships = graph.get_relationships_as_objects()
    nodes = graph.get_nodes_as_objects()

    # print(f"Saving graph with {len(nodes)} nodes and {len(relationships)} relationships")
    # graph_manager.save_graph(nodes, relationships)
    # graph_manager.close()

    lsp_query_helper.shutdown_exit_close()


def main_with_profiling(root_path: str = None, blarignore_path: str = None):
    """Main function with detailed profiling and timing"""
    print(f"🚀 Starting profiled graph creation for: {root_path}")

    profiler = PerformanceProfiler()
    step_times = {}

    with profiler.profile():
        # Reference Resolver Setup (SCIP + LSP Hybrid)
        print("⏱️  Setting up Hybrid Reference Resolver (SCIP + LSP)...")
        step_start = time.perf_counter()
        # Get resolver mode from environment variable for benchmarking
        resolver_mode_str = os.getenv("RESOLVER_MODE", "AUTO")
        if resolver_mode_str == "LSP_ONLY":
            resolver_mode = ResolverMode.LSP_ONLY
        elif resolver_mode_str == "SCIP_ONLY":
            resolver_mode = ResolverMode.SCIP_ONLY
        else:
            resolver_mode = ResolverMode.AUTO

        reference_resolver = HybridReferenceResolver(
            root_uri=root_path,
            mode=resolver_mode,
            max_lsp_instances=8,  # LSP fallback configuration
        )
        step_times["resolver_setup"] = time.perf_counter() - step_start
        logger.info(
            f"Reference resolver setup completed in {step_times['resolver_setup']:.2f}s"
        )

        # Log resolver configuration
        resolver_info = reference_resolver.get_resolver_info()
        logger.info(f"📊 Resolver config: {resolver_info}")

        # File Iterator Setup
        print("📁 Setting up Project Files Iterator...")
        step_start = time.perf_counter()
        project_files_iterator = ProjectFilesIterator(
            root_path=root_path,
            blarignore_path=blarignore_path,
            extensions_to_skip=[".json", ".xml", ".pyi"],
        )

        ProjectFileStats(project_files_iterator).print(limit=10)
        FileRemover.soft_delete_if_exists(root_path, "Gemfile")
        step_times["file_iterator"] = time.perf_counter() - step_start
        logger.info(
            f"File iterator setup completed in {step_times['file_iterator']:.2f}s"
        )

        # Database Setup
        print("💾 Setting up database connection...")
        step_start = time.perf_counter()
        repoId = os.getenv("RESOLVER_MODE", "AUTO")
        entity_id = os.getenv("RESOLVER_MODE", "AUTO")
        graph_manager = Neo4jManager(repoId, entity_id)
        step_times["db_setup"] = time.perf_counter() - step_start
        logger.info(f"Database setup completed in {step_times['db_setup']:.2f}s")

        # Graph Creation (Main Operation)
        print("🏗️  Creating Project Graph...")
        step_start = time.perf_counter()
        graph_creator = ProjectGraphCreator(
            root_path, reference_resolver, project_files_iterator
        )
        graph = graph_creator.build()
        step_times["graph_creation"] = time.perf_counter() - step_start
        logger.info(f"Graph creation completed in {step_times['graph_creation']:.2f}s")

        # Data Extraction
        print("📊 Extracting graph data...")
        step_start = time.perf_counter()
        relationships = graph.get_relationships_as_objects()
        nodes = graph.get_nodes_as_objects()
        step_times["data_extraction"] = time.perf_counter() - step_start
        logger.info(
            f"Data extraction completed in {step_times['data_extraction']:.2f}s"
        )

        # Database Save
        print(
            f"💾 Saving graph with {len(nodes)} nodes and {len(relationships)} relationships"
        )
        step_start = time.perf_counter()
        # graph_manager.save_graph(nodes, relationships)
        # graph_manager.close()
        step_times["db_save"] = time.perf_counter() - step_start
        logger.info(f"Database save completed in {step_times['db_save']:.2f}s")

        # Reference Resolver Shutdown
        print("🔄 Shutting down Reference Resolver...")
        step_start = time.perf_counter()
        reference_resolver.shutdown()
        step_times["resolver_shutdown"] = time.perf_counter() - step_start
        logger.info(
            f"Reference resolver shutdown completed in {step_times['resolver_shutdown']:.2f}s"
        )

    # Create benchmark result
    file_count = len([n for n in nodes if n.get("label") == "FILE"])
    result = BenchmarkResult(
        total_time=profiler.stats["total_time"],
        memory_peak=profiler.stats["peak_mb"],
        memory_current=profiler.stats["current_mb"],
        cpu_percent=profiler.stats["cpu_percent"],
        node_count=len(nodes),
        relationship_count=len(relationships),
        file_count=file_count,
    )

    # Print detailed results
    print("\n" + "=" * 60)
    print("🏁 PERFORMANCE RESULTS")
    print("=" * 60)
    print(str(result))

    # Timing breakdown
    total_time = profiler.stats["total_time"]
    print("\n⏱️  TIMING BREAKDOWN:")
    print(
        f"  Resolver Setup: {step_times['resolver_setup']:.2f}s ({step_times['resolver_setup'] / total_time * 100:.1f}%)"
    )
    print(
        f"  File Iterator: {step_times['file_iterator']:.2f}s ({step_times['file_iterator'] / total_time * 100:.1f}%)"
    )
    print(
        f"  Database Setup: {step_times['db_setup']:.2f}s ({step_times['db_setup'] / total_time * 100:.1f}%)"
    )
    print(
        f"  Graph Creation: {step_times['graph_creation']:.2f}s ({step_times['graph_creation'] / total_time * 100:.1f}%)"
    )
    print(
        f"  Data Extraction: {step_times['data_extraction']:.2f}s ({step_times['data_extraction'] / total_time * 100:.1f}%)"
    )
    print(
        f"  Database Save: {step_times['db_save']:.2f}s ({step_times['db_save'] / total_time * 100:.1f}%)"
    )
    print(
        f"  Resolver Shutdown: {step_times['resolver_shutdown']:.2f}s ({step_times['resolver_shutdown'] / total_time * 100:.1f}%)"
    )

    # Performance insights
    print("\n🔍 PERFORMANCE INSIGHTS:")
    if step_times["graph_creation"] > total_time * 0.8:
        print("  📈 Graph creation dominates execution time - focus optimization here")
    if step_times["resolver_setup"] > 10:
        print("  ⚠️  Reference resolver setup is slow - check SCIP index generation")

    # Add SCIP-specific insights
    if resolver_info.get("scip_enabled"):
        scip_stats = resolver_info.get("scip_stats", {})
        print(
            f"  📚 SCIP index: {scip_stats.get('documents', 0)} docs, {scip_stats.get('symbols', 0)} symbols"
        )
        print("  🚀 Using SCIP for faster reference resolution!")
    elif resolver_info.get("lsp_enabled"):
        print("  🔧 Using LSP fallback - SCIP index may be missing or invalid")
    if result.memory_peak > 1000:
        print("  🧠 High memory usage detected - consider memory optimization")
    if file_count > 0:
        files_per_second = file_count / step_times["graph_creation"]
        print(f"  📁 Processing rate: {files_per_second:.1f} files/second")
        if files_per_second < 10:
            print("  ⚠️  Low file processing rate - check for bottlenecks")

    # Save detailed report
    report_file = f"performance_report_{int(time.time())}.txt"
    with open(report_file, "w") as f:
        f.write("BLARIFY PERFORMANCE REPORT\n")
        f.write("=" * 60 + "\n")
        f.write(f"Project Path: {root_path}\n")
        f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(str(result) + "\n\n")
        f.write("TIMING BREAKDOWN:\n")
        for step, duration in step_times.items():
            f.write(f"{step}: {duration:.2f}s ({duration / total_time * 100:.1f}%)\n")

        # Add resolver information to report
        f.write("\nRESOLVER CONFIGURATION:\n")
        for key, value in resolver_info.items():
            f.write(f"{key}: {value}\n")

    print(f"\n📝 Detailed report saved to: {report_file}")

    return result


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

    print(
        f"Saving graph with {len(nodes)} nodes and {len(relationships)} relationships"
    )
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

    print(
        f"Saving graph with {len(nodes)} nodes and {len(relationships)} relationships"
    )
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

    graph = graph_diff_creator.build_with_previous_node_states(
        previous_node_states=previous_node_states
    )

    relationships = graph.get_relationships_as_objects()
    nodes = graph.get_nodes_as_objects()

    print(
        f"Saving graph with {len(nodes)} nodes and {len(relationships)} relationships"
    )

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
            for i, workflow in enumerate(
                result.discovered_workflows[:5]
            ):  # Show first 5
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
    # Comment out regular main() and use documentation integration
    # main(root_path=root_path, blarignore_path=blarignore_path)

    # Test the targeted workflow discovery with node_path
    test_targeted_workflow_discovery(root_path=root_path)

    # Other test options (commented out):
    # test_documentation_only(root_path=root_path)  # Test full documentation workflow
    # main_with_documentation(root_path=root_path, blarignore_path=blarignore_path)  # Full pipeline
