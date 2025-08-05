#!/usr/bin/env python3
"""
Simple script to compare LSP vs SCIP reference results for real nodes.
"""

import os
import sys
import logging
import time

# Add blarify to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from blarify.project_graph_creator import ProjectGraphCreator
from blarify.project_file_explorer import ProjectFilesIterator
from blarify.code_references.scip_helper import ScipReferenceResolver
from blarify.code_references.lsp_helper import LspQueryHelper

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _try_setup_scip(scip_resolver) -> bool:
    """Try to set up SCIP resolver."""
    try:
        # Try to generate index if needed
        if not scip_resolver.generate_index_if_needed("blarify"):
            return False
            
        # Try to load the index
        if not scip_resolver.ensure_loaded():
            return False
            
        stats = scip_resolver.get_statistics()
        logger.info(f"📚 SCIP index loaded: {stats}")
        return True
        
    except Exception as e:
        logger.warning(f"Failed to setup SCIP resolver: {e}")
        return False

def generate_comparison_report(results):
    """Generate comprehensive comparison report"""
    if not results:
        print("❌ No results to analyze")
        return
    
    print(f"\n{'='*100}")
    print(f"📊 COMPREHENSIVE SCIP vs LSP COMPARISON REPORT")
    print(f"{'='*100}")
    
    total_nodes = len(results)
    print(f"📈 Total nodes analyzed: {total_nodes}")
    
    # Overall statistics
    total_scip_refs = sum(r['scip_refs_count'] for r in results)
    total_lsp_refs = sum(r['lsp_refs_count'] for r in results)
    total_scip_time = sum(r['scip_time'] for r in results)
    total_lsp_time = sum(r['lsp_time'] for r in results)
    
    print(f"\n⏱️  PERFORMANCE SUMMARY:")
    print(f"   Total SCIP time: {total_scip_time:.2f}s")
    print(f"   Total LSP time: {total_lsp_time:.2f}s")
    print(f"   Average SCIP time per node: {total_scip_time/total_nodes:.3f}s")
    print(f"   Average LSP time per node: {total_lsp_time/total_nodes:.3f}s")
    if total_scip_time > 0 and total_lsp_time > 0:
        if total_scip_time < total_lsp_time:
            speedup = total_lsp_time / total_scip_time
            print(f"   ⚡ SCIP is {speedup:.1f}x faster overall")
        else:
            speedup = total_scip_time / total_lsp_time
            print(f"   ⚡ LSP is {speedup:.1f}x faster overall")
    
    print(f"\n🔗 REFERENCE COUNT SUMMARY:")
    print(f"   Total SCIP references: {total_scip_refs}")
    print(f"   Total LSP references: {total_lsp_refs}")
    print(f"   Average SCIP refs per node: {total_scip_refs/total_nodes:.1f}")
    print(f"   Average LSP refs per node: {total_lsp_refs/total_nodes:.1f}")
    
    # Categorize nodes by difference
    identical_nodes = []
    scip_advantage = []
    lsp_advantage = []
    both_empty = []
    
    for result in results:
        scip_count = result['scip_refs_count']
        lsp_count = result['lsp_refs_count']
        
        if scip_count == 0 and lsp_count == 0:
            both_empty.append(result)
        elif scip_count == lsp_count:
            identical_nodes.append(result)
        elif scip_count > lsp_count:
            scip_advantage.append(result)
        else:
            lsp_advantage.append(result)
    
    print(f"\n📊 NODE CATEGORIZATION:")
    print(f"   Identical results: {len(identical_nodes)} nodes ({len(identical_nodes)/total_nodes*100:.1f}%)")
    print(f"   SCIP found more: {len(scip_advantage)} nodes ({len(scip_advantage)/total_nodes*100:.1f}%)")
    print(f"   LSP found more: {len(lsp_advantage)} nodes ({len(lsp_advantage)/total_nodes*100:.1f}%)")
    print(f"   No references found by either: {len(both_empty)} nodes ({len(both_empty)/total_nodes*100:.1f}%)")
    
    # Show most significant differences
    print(f"\n🔍 TOP DIFFERENCES (SCIP advantage):")
    scip_sorted = sorted(scip_advantage, key=lambda x: x['scip_refs_count'] - x['lsp_refs_count'], reverse=True)
    for i, result in enumerate(scip_sorted[:5], 1):
        diff = result['scip_refs_count'] - result['lsp_refs_count']
        print(f"   [{i}] {result['node_name']} ({result['node_type']}): SCIP={result['scip_refs_count']}, LSP={result['lsp_refs_count']} (Δ+{diff})")
    
    print(f"\n🔍 TOP DIFFERENCES (LSP advantage):")
    lsp_sorted = sorted(lsp_advantage, key=lambda x: x['lsp_refs_count'] - x['scip_refs_count'], reverse=True)
    for i, result in enumerate(lsp_sorted[:5], 1):
        diff = result['lsp_refs_count'] - result['scip_refs_count']
        print(f"   [{i}] {result['node_name']} ({result['node_type']}): LSP={result['lsp_refs_count']}, SCIP={result['scip_refs_count']} (Δ+{diff})")
    
    # File overlap analysis
    print(f"\n📁 FILE OVERLAP ANALYSIS:")
    total_common_files = sum(len(r['common_files']) for r in results)
    total_scip_only = sum(len(r['scip_only_files']) for r in results)
    total_lsp_only = sum(len(r['lsp_only_files']) for r in results)
    
    print(f"   Total common files: {total_common_files}")
    print(f"   Total SCIP-only files: {total_scip_only}")
    print(f"   Total LSP-only files: {total_lsp_only}")
    
    # Detailed analysis for significant differences
    print(f"\n🔎 DETAILED ANALYSIS OF SIGNIFICANT DIFFERENCES:")
    
    # Show nodes where there are major discrepancies
    significant_diff = [r for r in results if abs(r['scip_refs_count'] - r['lsp_refs_count']) >= 3]
    if significant_diff:
        print(f"\n   Nodes with ≥3 reference difference:")
        for result in significant_diff[:10]:  # Show top 10
            scip_files = list(result['scip_only_files'])[:3]
            lsp_files = list(result['lsp_only_files'])[:3]
            common_files = list(result['common_files'])[:3]
            
            print(f"\n   📝 {result['node_path']} ({result['node_type']}):")
            print(f"      SCIP: {result['scip_refs_count']} refs, LSP: {result['lsp_refs_count']} refs")
            print(f"      Common files: {common_files}")
            print(f"      SCIP-only files: {scip_files}")
            print(f"      LSP-only files: {lsp_files}")
    
    print(f"\n{'='*100}")

def compare_node_references(root_path: str):
    """Compare LSP vs SCIP for real nodes from the graph"""
    
    print(f"🔍 Analyzing project at: {root_path}")
    
    # Initialize resolvers
    scip_resolver = ScipReferenceResolver(root_path)
    if not _try_setup_scip(scip_resolver):
        print("❌ Failed to setup SCIP resolver")
        return
    
    lsp_helper = LspQueryHelper(f"file://{root_path}")
    
    # Setup project iterator
    project_files_iterator = ProjectFilesIterator(
        root_path=root_path,
        extensions_to_skip=[".json", ".xml", ".pyi"]
    )
    
    try:
        # Create graph to get real nodes
        graph_creator = ProjectGraphCreator(root_path, lsp_helper, project_files_iterator)
        graph = graph_creator.build_hierarchy_only()
        
        # Get the actual node objects from the graph's internal structure
        print("🔍 Searching for real node objects...")
        
        # Access the graph's internal nodes dictionary (private attribute __nodes)
        real_nodes = []
        if hasattr(graph, '_Graph__nodes'):
            for node in graph._Graph__nodes.values():
                # Check if it's a definition node (function/class) with the attributes we need
                if (hasattr(node, 'name') and hasattr(node, 'path') and 
                    hasattr(node, 'definition_range') and hasattr(node, 'extension')):
                    # Check if it's a function or class node
                    node_type = type(node).__name__
                    if node_type in ['FunctionNode', 'ClassNode']:
                        real_nodes.append(node)
                        print(f"   Found {node_type}: {node.name}")
                        if len(real_nodes) >= 300:  # Get first 50 nodes for testing
                            break
        
        print(f"📊 Found {len(real_nodes)} real node objects")
        
        if not real_nodes:
            print("❌ No function/class nodes found. Let's examine available nodes:")
            if hasattr(graph, '_Graph__nodes'):
                sample_nodes = list(graph._Graph__nodes.values())[:10] 
                node_types = {}
                for node in sample_nodes:
                    node_type = type(node).__name__
                    node_types[node_type] = node_types.get(node_type, 0) + 1
                    if hasattr(node, 'name'):
                        print(f"   {node_type}: {node.name}")
                print(f"\n   Node type distribution: {node_types}")
            return
        
        # Results tracking
        results = []
        
        # Compare references for each real node
        for i, node in enumerate(real_nodes, 1):
            if i % 10 == 1:
                print(f"\n🔄 Processing nodes {i}-{min(i+9, len(real_nodes))}...")
            
            # Handle different definition_range structures
            if hasattr(node.definition_range, 'start_dict'):
                start_line = node.definition_range.start_dict.get('line', 0)
                start_char = node.definition_range.start_dict.get('character', 0)
            elif hasattr(node.definition_range, 'start'):
                start_line = node.definition_range.start.line
                start_char = node.definition_range.start.character
            else:
                start_line = 0
                start_char = 0
            
            # Query SCIP
            scip_start = time.time()
            try:
                scip_refs = scip_resolver.get_references_for_node(node)
                scip_time = time.time() - scip_start
            except Exception as e:
                scip_refs = []
                scip_time = time.time() - scip_start
                if i <= 5:  # Only log errors for first few nodes to avoid spam
                    print(f"   SCIP failed for {node.name}: {e}")
            
            # Query LSP
            lsp_start = time.time()
            try:
                lsp_refs_raw = lsp_helper.get_paths_where_node_is_referenced(node)
                lsp_time = time.time() - lsp_start
                
                # Filter out self-definition from LSP results
                # LSP includes the definition itself, but we want only references
                lsp_refs = []
                for ref in lsp_refs_raw:
                    # Skip if this reference is at the same location as the node definition
                    if hasattr(ref, 'range') and hasattr(ref.range, 'start'):
                        ref_line = ref.range.start.line
                        ref_char = ref.range.start.character
                        # Skip if it's the same position as the definition
                        if ref_line == start_line and ref_char == start_char:
                            continue
                    lsp_refs.append(ref)
                    
            except Exception as e:
                lsp_refs = []
                lsp_time = time.time() - lsp_start
                if i <= 5:  # Only log errors for first few nodes to avoid spam
                    print(f"   LSP failed for {node.name}: {e}")
            
            # Collect results for analysis
            # Extract file paths for comparison
            scip_files = set()
            lsp_files = set()
            
            for ref in scip_refs:
                
                file_path = getattr(ref, 'relativePath', getattr(ref, 'path', 'unknown'))
                scip_files.add(file_path)
            
            for ref in lsp_refs:
                file_path = getattr(ref, 'relativePath', getattr(ref, 'path', 'unknown'))
                lsp_files.add(file_path)
            
            common_files = scip_files.intersection(lsp_files)
            scip_only = scip_files - lsp_files
            lsp_only = lsp_files - scip_files
            
            # Store result
            result = {
                'node_name': node.name,
                'node_type': type(node).__name__,
                'node_path': node.path,
                'node_line': start_line,
                'node_char': start_char,
                'scip_refs_count': len(scip_refs),
                'lsp_refs_count': len(lsp_refs),
                'scip_time': scip_time,
                'lsp_time': lsp_time,
                'scip_files': scip_files,
                'lsp_files': lsp_files,
                'common_files': common_files,
                'scip_only_files': scip_only,
                'lsp_only_files': lsp_only,
                'scip_refs': scip_refs,
                'lsp_refs': lsp_refs
            }
            results.append(result)
        
        # Generate comprehensive report
        generate_comparison_report(results)
            
    except Exception as e:
        logger.error(f"Error during comparison: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        try:
            lsp_helper.shutdown_exit_close()
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")

def main():
    """Main entry point"""
    root_path = os.getenv("ROOT_PATH") or "/Users/pepemanu/Desktop/Trabajo/Blar/Dev/blarify"
    
    if not os.path.exists(root_path):
        print(f"❌ Error: Path {root_path} does not exist")
        sys.exit(1)
    
    compare_node_references(root_path)

if __name__ == "__main__":
    main()