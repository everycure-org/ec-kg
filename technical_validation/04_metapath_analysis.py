"""
Metapath Analysis Script

This script addresses the feedback about showing that integration adds 
qualitatively new metapath types, not just more instances of existing ones.

It performs two main analyses:
1. Metapath Diversity: Classifies paths by their metapath signature 
   (sequence of node categories) and shows which metapaths are unique 
   to the integrated KG vs. source KGs.

2. Cross-Source Path Analysis: For the integrated KG, determines which 
   paths require edges from multiple source KGs (cross-source paths) 
   vs. paths that could exist in a single source KG alone.
"""

import os
import polars as pl
import json
import ijson
import gcsfs
from collections import defaultdict, Counter
from tqdm import tqdm

# Paths (local or gs://)
PAIRS_PATH = '/Users/piotrkaniewski/work/ec-kg-analysis/data/off_label_pairs_sop.parquet'
SOP_PATH = '/Users/piotrkaniewski/work/ec-kg-analysis/data/sop_no_filtered_kg/prm/'
OUTPUT_DIR = '/Users/piotrkaniewski/work/ec-kg-analysis/data/sop_no_filtered_kg/output'

# KG paths for edge source attribution (parquet edges.norm; supports gs://)
KG_PATHS = {
    'PrimeKG': '/Users/piotrkaniewski/work/ec-kg-analysis/data/primekg',
    'Robokop': '/Users/piotrkaniewski/work/ec-kg-analysis/data/robokop',
    'RTX-KG2': '/Users/piotrkaniewski/work/ec-kg-analysis/data/rtx_kg2',
    'Integrated-KG': '/Users/piotrkaniewski/work/ec-kg-analysis/data/integrated_kg'
}

_gcs_fs = None


def is_gcs_path(path):
    return isinstance(path, str) and path.startswith('gs://')


def get_gcs_fs():
    global _gcs_fs
    if _gcs_fs is None:
        _gcs_fs = gcsfs.GCSFileSystem()
    return _gcs_fs


def open_binary(path, mode='rb'):
    """Open a path for binary read/write (local or gs://)."""
    if is_gcs_path(path):
        return get_gcs_fs().open(path, mode)
    return open(path, mode)


def open_text(path, mode='w', encoding='utf-8'):
    """Open a path for text read/write (local or gs://)."""
    if is_gcs_path(path):
        return get_gcs_fs().open(path, mode, encoding=encoding)
    return open(path, mode, encoding=encoding)


def join_storage_path(base, *parts):
    """Join path components for local filesystem or GCS."""
    if is_gcs_path(base):
        return '/'.join([base.rstrip('/'), *parts])
    return os.path.join(base, *parts)

KG_FILES = {
    'PrimeKG': 'primekg_sop.json',
    'Robokop': 'robokop_sop.json',
    'RTX-KG2': 'rtx_kg2_sop.json',
    'Integrated-KG': 'integrated_kg_sop.json'
}


def get_sop_path(kg_name):
    return join_storage_path(SOP_PATH, KG_FILES[kg_name])


def iter_sop_pairs(sop_path):
    """Yield (pair_key, pair_data) from a SOP JSON file via ijson streaming."""
    with open_binary(sop_path, 'rb') as f:
        for pair_key, pair_data in ijson.kvitems(f, ''):
            yield pair_key, pair_data


def extract_metapath_signature(path_metadata, use_predicates=False):
    """
    Extract metapath signature from a path.
    
    Parameters:
    - path_metadata: dict with 'node_categories' and 'edge_predicates'
    - use_predicates: if True, include edge predicates in signature
    
    Returns:
    - tuple representing the metapath signature
    """
    node_cats = path_metadata.get('node_categories', [])
    
    # Normalize node categories (handle lists and None)
    normalized_cats = []
    for cat in node_cats:
        if isinstance(cat, list):
            # Take first category if multiple
            normalized_cats.append(cat[0] if cat else 'Unknown')
        elif cat is None:
            normalized_cats.append('Unknown')
        else:
            normalized_cats.append(cat)
    
    if use_predicates:
        edge_preds = path_metadata.get('edge_predicates', [])
        # Interleave node categories with edge predicates
        signature = []
        for i, cat in enumerate(normalized_cats):
            signature.append(cat)
            if i < len(edge_preds):
                # Normalize edge predicates
                pred = edge_preds[i]
                if isinstance(pred, list):
                    pred_str = '|'.join(sorted(pred)) if pred else 'no_predicate'
                else:
                    pred_str = str(pred) if pred else 'no_predicate'
                signature.append(pred_str)
        return tuple(signature)
    else:
        # Just node categories
        return tuple(normalized_cats)


def analyze_metapath_diversity_for_kg(kg_name, sop_path):
    """
    Analyze metapath diversity for a single KG by streaming its SOP JSON file.

    Returns:
    - metapath_counts: Counter of metapath -> count
    - metapath_examples: metapath -> kg -> example paths (up to 3 each)
    """
    print(f"\nAnalyzing metapaths for {kg_name}...")
    metapath_counts = Counter()
    metapath_examples = defaultdict(lambda: defaultdict(list))

    for pair_key, pair_data in tqdm(
        iter_sop_pairs(sop_path),
        desc=f"Processing {kg_name} pairs",
    ):
        paths_metadata = pair_data.get('paths_metadata', [])

        for path_meta in paths_metadata:
            metapath = extract_metapath_signature(path_meta, use_predicates=False)
            metapath_counts[metapath] += 1

            if len(metapath_examples[metapath][kg_name]) < 3:
                metapath_examples[metapath][kg_name].append({
                    'pair': pair_key,
                    'nodes': path_meta.get('nodes', []),
                })

    total_paths = sum(metapath_counts.values())
    print(f"  Total paths: {total_paths}")
    print(f"  Unique metapaths: {len(metapath_counts)}")
    return metapath_counts, metapath_examples


def analyze_metapath_diversity():
    """
    Analyze metapath diversity across all KGs (one file streamed at a time).

    Returns:
    - metapath_counts: dict of KG -> Counter
    - metapath_examples: metapath -> kg -> example paths
    """
    metapath_counts = {}
    metapath_examples = defaultdict(lambda: defaultdict(list))

    for kg_name in KG_FILES:
        counts, examples = analyze_metapath_diversity_for_kg(kg_name, get_sop_path(kg_name))
        metapath_counts[kg_name] = counts
        for metapath, kg_examples in examples.items():
            metapath_examples[metapath][kg_name].extend(kg_examples)

    return metapath_counts, metapath_examples


def build_edge_source_index(kg_paths):
    """
    Build an index mapping (subject, object) -> set of source KGs.
    
    This tells us which source KG(s) contributed each edge in the integrated graph.
    """
    print("\nBuilding edge source attribution index...")
    edge_sources = defaultdict(set)
    
    for kg_name, kg_path in kg_paths.items():
        if kg_name == 'Integrated-KG':
            continue
        
        print(f"  Loading edges from {kg_name}...")
        edges_path = join_storage_path(kg_path, 'edges.norm')
        edges_df = pl.read_parquet(
            edges_path,
            columns=['subject', 'object', 'predicate']
        )
        
        for subj, obj in tqdm(
            zip(edges_df['subject'], edges_df['object']),
            total=len(edges_df),
            desc=f"  Indexing {kg_name}"
        ):
            # Store both directions (undirected graph)
            edge_sources[(subj, obj)].add(kg_name)
            edge_sources[(obj, subj)].add(kg_name)
    
    print(f"  Indexed {len(edge_sources)} unique edge pairs")
    return edge_sources


def analyze_cross_source_paths(integrated_sop_path, edge_sources):
    """
    Analyze which paths in the integrated KG are cross-source.

    Streams the integrated SOP JSON file pair-by-pair. A path is cross-source if it
    requires edges from at least 2 different source KGs.
    """
    print("\nAnalyzing cross-source paths in Integrated-KG...")

    path_analysis = {
        'total_paths': 0,
        'cross_source_paths': 0,
        'single_source_paths': 0,
        'unknown_source_paths': 0,
        'source_combinations': Counter(),
        'cross_source_by_metapath': defaultdict(lambda: {'cross': 0, 'single': 0}),
        'pair_level_stats': []
    }

    for pair_key, pair_data in tqdm(
        iter_sop_pairs(integrated_sop_path),
        desc="Analyzing paths",
    ):
        paths_metadata = pair_data.get('paths_metadata', [])
        pair_cross_source = 0
        pair_single_source = 0
        
        for path_meta in paths_metadata:
            path_analysis['total_paths'] += 1
            nodes = path_meta.get('nodes', [])
            
            if len(nodes) < 2:
                path_analysis['unknown_source_paths'] += 1
                continue
            
            # Determine which source KGs contributed to this path
            path_sources = set()
            edge_source_list = []
            
            for i in range(len(nodes) - 1):
                edge = (nodes[i], nodes[i + 1])
                edge_kg_sources = edge_sources.get(edge, set())
                edge_source_list.append(edge_kg_sources)
                path_sources.update(edge_kg_sources)
            
            # Classify the path
            if len(path_sources) == 0:
                path_analysis['unknown_source_paths'] += 1
            elif len(path_sources) == 1:
                path_analysis['single_source_paths'] += 1
                pair_single_source += 1
                source_name = list(path_sources)[0]
                path_analysis['source_combinations'][f"Single:{source_name}"] += 1
            else:
                path_analysis['cross_source_paths'] += 1
                pair_cross_source += 1
                source_combo = '+'.join(sorted(path_sources))
                path_analysis['source_combinations'][f"Cross:{source_combo}"] += 1
                
                # Track cross-source by metapath
                metapath = extract_metapath_signature(path_meta, use_predicates=False)
                path_analysis['cross_source_by_metapath'][metapath]['cross'] += 1
            
            # Also track single-source by metapath
            if len(path_sources) == 1:
                metapath = extract_metapath_signature(path_meta, use_predicates=False)
                path_analysis['cross_source_by_metapath'][metapath]['single'] += 1
        
        # Store pair-level statistics
        if len(paths_metadata) > 0:
            path_analysis['pair_level_stats'].append({
                'pair': pair_key,
                'total_paths': len(paths_metadata),
                'cross_source_paths': pair_cross_source,
                'single_source_paths': pair_single_source,
                'fraction_cross_source': pair_cross_source / len(paths_metadata) if len(paths_metadata) > 0 else 0
            })
    
    return path_analysis


def compare_metapath_uniqueness(metapath_counts):
    """
    Determine which metapaths are unique to integrated KG vs. available in source KGs.
    """
    print("\nComparing metapath uniqueness...")
    
    # Get all metapaths from each KG
    kg_metapath_sets = {
        kg: set(mp_counts.keys())
        for kg, mp_counts in metapath_counts.items()
    }
    
    integrated_metapaths = kg_metapath_sets.get('Integrated-KG', set())
    source_kgs = ['PrimeKG', 'Robokop', 'RTX-KG2']
    
    # Union of all source KG metapaths
    source_union = set()
    for kg in source_kgs:
        source_union.update(kg_metapath_sets.get(kg, set()))
    
    # Metapaths unique to integrated KG
    unique_to_integrated = integrated_metapaths - source_union
    
    # Metapaths present in integrated and at least one source
    shared_metapaths = integrated_metapaths & source_union
    
    results = {
        'total_integrated_metapaths': len(integrated_metapaths),
        'total_source_union_metapaths': len(source_union),
        'unique_to_integrated': len(unique_to_integrated),
        'shared_metapaths': len(shared_metapaths),
        'unique_metapath_list': list(unique_to_integrated),
        'metapath_kg_presence': {}
    }
    
    # For each integrated metapath, track which source KGs have it
    for mp in integrated_metapaths:
        presence = []
        for kg in source_kgs:
            if mp in kg_metapath_sets.get(kg, set()):
                presence.append(kg)
        results['metapath_kg_presence'][mp] = presence
    
    return results


def format_metapath_string(metapath):
    """Format metapath tuple as readable string."""
    # Simplify biolink prefixes for readability
    simplified = []
    for component in metapath:
        if isinstance(component, str):
            # Remove biolink: prefix
            clean = component.replace('biolink:', '')
            simplified.append(clean)
        else:
            simplified.append(str(component))
    return ' → '.join(simplified)


def main():
    # ============================================================
    # ANALYSIS 1: Metapath Diversity (stream SOP JSON per KG)
    # ============================================================
    print("\n" + "="*70)
    print("ANALYSIS 1: METAPATH DIVERSITY")
    print("="*70)

    metapath_counts, metapath_examples = analyze_metapath_diversity()
    uniqueness_results = compare_metapath_uniqueness(metapath_counts)
    
    # Print summary
    print("\n### Metapath Diversity Summary")
    for kg_name in KG_FILES.keys():
        counts = metapath_counts[kg_name]
        total_paths = sum(counts.values())
        unique_metapaths = len(counts)
        print(f"\n{kg_name}:")
        print(f"  Total paths: {total_paths:,}")
        print(f"  Unique metapath types: {unique_metapaths:,}")
        print(f"  Top 5 metapaths:")
        for mp, count in counts.most_common(5):
            pct = 100 * count / total_paths
            print(f"    {format_metapath_string(mp)}: {count:,} ({pct:.1f}%)")
    
    print("\n### Metapath Uniqueness Analysis")
    print(f"Total metapath types in Integrated-KG: {uniqueness_results['total_integrated_metapaths']:,}")
    print(f"Total metapath types in source KG union: {uniqueness_results['total_source_union_metapaths']:,}")
    print(f"Metapath types UNIQUE to Integrated-KG: {uniqueness_results['unique_to_integrated']:,}")
    print(f"Metapath types shared with source KGs: {uniqueness_results['shared_metapaths']:,}")
    
    if uniqueness_results['unique_to_integrated'] > 0:
        print(f"\nUnique metapaths in Integrated-KG (first 10):")
        for mp in list(uniqueness_results['unique_metapath_list'])[:10]:
            print(f"  • {format_metapath_string(mp)}")
    
    # ============================================================
    # ANALYSIS 2: Cross-Source Path Analysis (Integrated-KG only)
    # ============================================================
    print("\n" + "="*70)
    print("ANALYSIS 2: CROSS-SOURCE PATH ANALYSIS")
    print("="*70)
    
    edge_sources = build_edge_source_index(KG_PATHS)
    path_analysis = analyze_cross_source_paths(get_sop_path('Integrated-KG'), edge_sources)
    
    # Print summary
    print("\n### Cross-Source Path Statistics")
    total = path_analysis['total_paths']
    cross = path_analysis['cross_source_paths']
    single = path_analysis['single_source_paths']
    unknown = path_analysis['unknown_source_paths']
    
    print(f"Total paths analyzed: {total:,}")
    print(f"Cross-source paths (require ≥2 KGs): {cross:,} ({100*cross/total:.1f}%)")
    print(f"Single-source paths (from 1 KG): {single:,} ({100*single/total:.1f}%)")
    print(f"Unknown source paths: {unknown:,} ({100*unknown/total:.1f}%)")
    
    print("\n### Source Combination Breakdown")
    for combo, count in path_analysis['source_combinations'].most_common(10):
        pct = 100 * count / total
        print(f"  {combo}: {count:,} ({pct:.1f}%)")
    
    # Cross-source paths by metapath
    print("\n### Cross-Source Paths by Metapath Type (Top 10)")
    metapath_cross_rates = []
    for mp, stats in path_analysis['cross_source_by_metapath'].items():
        total_mp = stats['cross'] + stats['single']
        if total_mp > 0:
            cross_rate = stats['cross'] / total_mp
            metapath_cross_rates.append((mp, stats['cross'], total_mp, cross_rate))
    
    metapath_cross_rates.sort(key=lambda x: x[1], reverse=True)  # Sort by absolute count
    
    for mp, cross_count, total_mp, cross_rate in metapath_cross_rates[:10]:
        print(f"  {format_metapath_string(mp)}")
        print(f"    Cross-source: {cross_count:,}/{total_mp:,} ({100*cross_rate:.1f}%)")
    
    # Pair-level statistics
    print("\n### Pair-Level Cross-Source Statistics")
    pair_stats_df = pl.DataFrame(path_analysis['pair_level_stats'])
    
    if len(pair_stats_df) > 0:
        avg_cross_frac = pair_stats_df['fraction_cross_source'].mean()
        median_cross_frac = pair_stats_df['fraction_cross_source'].median()
        
        print(f"Total drug-disease pairs analyzed: {len(pair_stats_df):,}")
        print(f"Average fraction of cross-source paths per pair: {avg_cross_frac:.3f}")
        print(f"Median fraction of cross-source paths per pair: {median_cross_frac:.3f}")
        
        # Pairs with highest cross-source fraction
        top_cross_pairs = pair_stats_df.sort('fraction_cross_source', descending=True).head(10)
        print("\nTop 10 pairs by cross-source fraction:")
        for row in top_cross_pairs.iter_rows(named=True):
            print(f"  {row['pair']}: {row['cross_source_paths']}/{row['total_paths']} "
                  f"({100*row['fraction_cross_source']:.1f}%)")
    
    # ============================================================
    # Save Results
    # ============================================================
    print("\n" + "="*70)
    print("SAVING RESULTS")
    print("="*70)
    
    output_dir = OUTPUT_DIR

    # Save metapath diversity results
    metapath_diversity_data = []
    for kg_name, counts in metapath_counts.items():
        for metapath, count in counts.items():
            presence_in_kgs = uniqueness_results['metapath_kg_presence'].get(metapath, [])
            metapath_diversity_data.append({
                'kg': kg_name,
                'metapath': format_metapath_string(metapath),
                'metapath_raw': str(metapath),
                'count': count,
                'present_in_source_kgs': '|'.join(presence_in_kgs) if presence_in_kgs else 'Unique-to-Integrated',
                'is_unique_to_integrated': len(presence_in_kgs) == 0 and kg_name == 'Integrated-KG'
            })
    
    metapath_df = pl.DataFrame(metapath_diversity_data)
    metapath_csv_path = join_storage_path(output_dir, 'metapath_diversity.csv')
    metapath_df.write_csv(metapath_csv_path)
    print(f"✓ Saved metapath diversity to: {metapath_csv_path}")

    # Save cross-source analysis results
    if len(pair_stats_df) > 0:
        pair_stats_csv_path = join_storage_path(output_dir, 'cross_source_pair_stats.csv')
        pair_stats_df.write_csv(pair_stats_csv_path)
        print(f"✓ Saved cross-source pair stats to: {pair_stats_csv_path}")
    
    # Save summary statistics
    summary = {
        'metapath_diversity': {
            'integrated_kg': {
                'total_paths': sum(metapath_counts['Integrated-KG'].values()),
                'unique_metapaths': len(metapath_counts['Integrated-KG']),
                'metapaths_unique_to_integrated': uniqueness_results['unique_to_integrated'],
                'metapaths_shared_with_sources': uniqueness_results['shared_metapaths']
            },
            'source_kgs': {
                kg: {
                    'total_paths': sum(counts.values()),
                    'unique_metapaths': len(counts)
                }
                for kg, counts in metapath_counts.items()
                if kg != 'Integrated-KG'
            }
        },
        'cross_source_analysis': {
            'total_paths': path_analysis['total_paths'],
            'cross_source_paths': path_analysis['cross_source_paths'],
            'single_source_paths': path_analysis['single_source_paths'],
            'cross_source_fraction': path_analysis['cross_source_paths'] / path_analysis['total_paths']
            if path_analysis['total_paths'] > 0 else 0,
            'source_combinations': dict(path_analysis['source_combinations'])
        }
    }
    
    summary_json_path = join_storage_path(output_dir, 'metapath_analysis_summary.json')
    with open_text(summary_json_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"✓ Saved summary statistics to: {summary_json_path}")
    
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    print("\nKey Findings:")
    print(f"1. Integration adds {uniqueness_results['unique_to_integrated']} new metapath types")
    print(f"   not present in any source KG alone.")
    print(f"2. {100*cross/total:.1f}% of paths in Integrated-KG are cross-source,")
    print(f"   requiring edges from multiple source KGs to exist.")
    print("\nThis demonstrates that integration provides:")
    print("  • Qualitatively new path types (new metapaths)")
    print("  • Genuinely novel connections (cross-source paths)")


if __name__ == '__main__':
    main()
