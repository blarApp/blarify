from blarify.project_graph_creator import ProjectGraphCreator
from blarify.project_file_explorer import ProjectFilesIterator
from blarify.project_file_explorer import ProjectFileStats
from blarify.project_graph_updater import ProjectGraphUpdater
from blarify.project_graph_diff_creator import PreviousNodeState, ProjectGraphDiffCreator
from blarify.db_managers.neo4j_manager import Neo4jManager
from blarify.code_references import LspQueryHelper
from blarify.graph.graph_environment import GraphEnvironment
from blarify.utils.file_remover import FileRemover

import dotenv
import os
import time
import tracemalloc
import psutil
import gc
from contextlib import contextmanager
from dataclasses import dataclass

import logging

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Container for benchmark results"""
    total_time: float
    memory_peak: float
    memory_current: float
    cpu_percent: float
    node_count: int
    relationship_count: int
    file_count: int
    
    def __str__(self) -> str:
        return (
            f"Benchmark Results:\n"
            f"  Total Time: {self.total_time:.2f}s\n"
            f"  Peak Memory: {self.memory_peak:.2f} MB\n"
            f"  Current Memory: {self.memory_current:.2f} MB\n"
            f"  CPU Usage: {self.cpu_percent:.1f}%\n"
            f"  Node Count: {self.node_count:,}\n"
            f"  Relationship Count: {self.relationship_count:,}\n"
            f"  File Count: {self.file_count:,}\n"
        )


class PerformanceProfiler:
    """Performance profiling context manager"""
    
    def __init__(self):
        self.process = psutil.Process()
        
    @contextmanager
    def profile(self):
        """Context manager for performance profiling"""
        tracemalloc.start()
        gc.collect()
        initial_memory = self.process.memory_info().rss / 1024 / 1024
        cpu_start = self.process.cpu_percent()
        start_time = time.perf_counter()
        
        try:
            yield
        finally:
            end_time = time.perf_counter()
            cpu_end = self.process.cpu_percent()
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            final_memory = self.process.memory_info().rss / 1024 / 1024
            
            self.stats = {
                'total_time': end_time - start_time,
                'peak_mb': peak / 1024 / 1024,
                'current_mb': current / 1024 / 1024,
                'initial_memory_mb': initial_memory,
                'final_memory_mb': final_memory,
                'cpu_percent': (cpu_start + cpu_end) / 2
            }


def main(root_path: str = None, blarignore_path: str = None, enable_profiling: bool = False):
    """Main function with optional profiling"""
    if enable_profiling:
        return main_with_profiling(root_path, blarignore_path)
    else:
        return main_without_profiling(root_path, blarignore_path)


def main_without_profiling(root_path: str = None, blarignore_path: str = None):
    lsp_query_helper = LspQueryHelper(root_uri=root_path, max_lsp_instances=10)

    lsp_query_helper.start()

    project_files_iterator = ProjectFilesIterator(
        root_path=root_path, blarignore_path=blarignore_path, extensions_to_skip=[".json", ".xml", ".pyi"]
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


def main_with_profiling(root_path: str = None, blarignore_path: str = None):
    """Main function with detailed profiling and timing"""
    print(f"🚀 Starting profiled graph creation for: {root_path}")
    
    profiler = PerformanceProfiler()
    step_times = {}
    
    with profiler.profile():
        # LSP Setup
        print("⏱️  Setting up LSP Query Helper...")
        step_start = time.perf_counter()
        lsp_query_helper = LspQueryHelper(root_uri=root_path, max_lsp_instances=8)
        lsp_query_helper.start()
        step_times['lsp_setup'] = time.perf_counter() - step_start
        logger.info(f"LSP setup completed in {step_times['lsp_setup']:.2f}s")
        
        # File Iterator Setup
        print("📁 Setting up Project Files Iterator...")
        step_start = time.perf_counter()
        project_files_iterator = ProjectFilesIterator(
            root_path=root_path, 
            blarignore_path=blarignore_path, 
            extensions_to_skip=[".json", ".xml", ".pyi"]
        )
        
        ProjectFileStats(project_files_iterator).print(limit=10)
        FileRemover.soft_delete_if_exists(root_path, "Gemfile")
        step_times['file_iterator'] = time.perf_counter() - step_start
        logger.info(f"File iterator setup completed in {step_times['file_iterator']:.2f}s")
        
        # Database Setup
        print("💾 Setting up database connection...")
        step_start = time.perf_counter()
        repoId = "test"
        entity_id = "test"
        graph_manager = Neo4jManager(repoId, entity_id)
        step_times['db_setup'] = time.perf_counter() - step_start
        logger.info(f"Database setup completed in {step_times['db_setup']:.2f}s")
        
        # Graph Creation (Main Operation)
        print("🏗️  Creating Project Graph...")
        step_start = time.perf_counter()
        graph_creator = ProjectGraphCreator(root_path, lsp_query_helper, project_files_iterator)
        graph = graph_creator.build()
        step_times['graph_creation'] = time.perf_counter() - step_start
        logger.info(f"Graph creation completed in {step_times['graph_creation']:.2f}s")
        
        # Data Extraction
        print("📊 Extracting graph data...")
        step_start = time.perf_counter()
        relationships = graph.get_relationships_as_objects()
        nodes = graph.get_nodes_as_objects()
        step_times['data_extraction'] = time.perf_counter() - step_start
        logger.info(f"Data extraction completed in {step_times['data_extraction']:.2f}s")
        
        # Database Save
        print(f"💾 Saving graph with {len(nodes)} nodes and {len(relationships)} relationships")
        step_start = time.perf_counter()
        # graph_manager.save_graph(nodes, relationships)
        # graph_manager.close()
        step_times['db_save'] = time.perf_counter() - step_start
        logger.info(f"Database save completed in {step_times['db_save']:.2f}s")
        
        # LSP Shutdown
        print("🔄 Shutting down LSP...")
        step_start = time.perf_counter()
        lsp_query_helper.shutdown_exit_close()
        step_times['lsp_shutdown'] = time.perf_counter() - step_start
        logger.info(f"LSP shutdown completed in {step_times['lsp_shutdown']:.2f}s")
    
    # Create benchmark result
    file_count = len([n for n in nodes if n.get('label') == 'FILE'])
    result = BenchmarkResult(
        total_time=profiler.stats['total_time'],
        memory_peak=profiler.stats['peak_mb'],
        memory_current=profiler.stats['current_mb'],
        cpu_percent=profiler.stats['cpu_percent'],
        node_count=len(nodes),
        relationship_count=len(relationships),
        file_count=file_count
    )
    
    # Print detailed results
    print("\n" + "="*60)
    print("🏁 PERFORMANCE RESULTS")
    print("="*60)
    print(str(result))
    
    # Timing breakdown
    total_time = profiler.stats['total_time']
    print(f"\n⏱️  TIMING BREAKDOWN:")
    print(f"  LSP Setup: {step_times['lsp_setup']:.2f}s ({step_times['lsp_setup']/total_time*100:.1f}%)")
    print(f"  File Iterator: {step_times['file_iterator']:.2f}s ({step_times['file_iterator']/total_time*100:.1f}%)")
    print(f"  Database Setup: {step_times['db_setup']:.2f}s ({step_times['db_setup']/total_time*100:.1f}%)")
    print(f"  Graph Creation: {step_times['graph_creation']:.2f}s ({step_times['graph_creation']/total_time*100:.1f}%)")
    print(f"  Data Extraction: {step_times['data_extraction']:.2f}s ({step_times['data_extraction']/total_time*100:.1f}%)")
    print(f"  Database Save: {step_times['db_save']:.2f}s ({step_times['db_save']/total_time*100:.1f}%)")
    print(f"  LSP Shutdown: {step_times['lsp_shutdown']:.2f}s ({step_times['lsp_shutdown']/total_time*100:.1f}%)")
    
    # Performance insights
    print(f"\n🔍 PERFORMANCE INSIGHTS:")
    if step_times['graph_creation'] > total_time * 0.8:
        print("  📈 Graph creation dominates execution time - focus optimization here")
    if step_times['lsp_setup'] > 10:
        print("  ⚠️  LSP setup is slow - consider LSP optimization")
    if result.memory_peak > 1000:
        print("  🧠 High memory usage detected - consider memory optimization")
    if file_count > 0:
        files_per_second = file_count / step_times['graph_creation']
        print(f"  📁 Processing rate: {files_per_second:.1f} files/second")
        if files_per_second < 10:
            print("  ⚠️  Low file processing rate - check for bottlenecks")
    
    # Save detailed report
    report_file = f"performance_report_{int(time.time())}.txt"
    with open(report_file, 'w') as f:
        f.write("BLARIFY PERFORMANCE REPORT\n")
        f.write("="*60 + "\n")
        f.write(f"Project Path: {root_path}\n")
        f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(str(result) + "\n\n")
        f.write("TIMING BREAKDOWN:\n")
        for step, duration in step_times.items():
            f.write(f"{step}: {duration:.2f}s ({duration/total_time*100:.1f}%)\n")
    
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
    
    # Get configuration from environment
    root_path = os.getenv("ROOT_PATH") or "/Users/pepemanu/Desktop/Trabajo/Blar/Dev/django"
    blarignore_path = os.getenv("BLARIGNORE_PATH")
    
    # Enable profiling by setting ENABLE_PROFILING=1 in environment or .env file
    enable_profiling = True
    main(root_path=root_path, blarignore_path=blarignore_path, enable_profiling=enable_profiling)
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
