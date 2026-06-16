# NOTE: This file was partially generated using AI assistance.
#
# This script calculates SOP (Semantic-Overlap Pathways) with incremental checkpointing.
# Every N pairs (default 20), a cumulative checkpoint is saved to GCS containing all pairs
# processed so far. Each checkpoint file grows progressively larger:
#   - checkpoint_20.json contains first 20 pairs
#   - checkpoint_40.json contains first 40 pairs
#   - checkpoint_60.json contains first 60 pairs
#   - etc.
# This provides safety against crashes while allowing recovery from the latest checkpoint.

import polars as pl
import argparse
from tqdm import tqdm
import rustworkx as rx
import json
from google.cloud import storage
from joblib import Parallel, delayed
import os

PAIRS_PATH = '/home/jupyter/ec-kg/data/off_label_pairs_sop.parquet'

parser = argparse.ArgumentParser()
parser.add_argument('--kg_name', type=str, required=True)
parser.add_argument('--kg_path', type=str, required=True)
parser.add_argument('--n_jobs', type=int, default=8, help='Number of parallel jobs (-1 for all CPUs)')
parser.add_argument('--chunk_size', type=int, default=100, help='Number of pairs to process per chunk')
parser.add_argument('--checkpoint_interval', type=int, default=20, help='Save checkpoint every N pairs (cumulative)')
args = parser.parse_args()


def calculate_sop_for_pair(source, target, g, node_id_to_idx, null=False):
    """Calculate SOP for a single pair."""
    source_idx = node_id_to_idx.get(source)
    target_idx = node_id_to_idx.get(target)
    
    if source_idx is not None and target_idx is not None:
        paths = list(rx.all_simple_paths(g, source_idx, target_idx, min_depth=0, cutoff=4))
        sop = len(paths)
    else:
        paths = []
        sop = 0
    
    if null:
        return f'{source}|{target}', {'sop': sop, 'paths': []}
    else:
        return f'{source}|{target}', {'sop': sop, 'paths': paths}


def calculate_sop(pairs, g, node_id_to_idx, null=False, n_jobs=-1, chunk_size=100, checkpoint_interval=20, checkpoint_callback=None):
    """
    Calculate SOP for all pairs using parallel processing with checkpointing.
    
    Args:
        pairs: DataFrame with source and target columns
        g: rustworkx graph
        node_id_to_idx: mapping from node IDs to graph indices
        null: if True, don't store paths (for null model)
        n_jobs: number of parallel jobs
        chunk_size: number of pairs to process in each chunk
        checkpoint_interval: save checkpoint every N pairs
        checkpoint_callback: function to call with (sop_dict, pairs_processed) for checkpointing
    
    Returns:
        Dictionary mapping pair keys to SOP results
    """
    pairs_list = list(pairs.iter_rows(named=False))
    sop_dict = {}
    
    # Process pairs in chunks for checkpointing
    for i in range(0, len(pairs_list), checkpoint_interval):
        chunk = pairs_list[i:i + checkpoint_interval]
        
        # Process this chunk in parallel
        results = Parallel(n_jobs=n_jobs, backend='loky', verbose=10)(
            delayed(calculate_sop_for_pair)(source, target, g, node_id_to_idx, null)
            for source, target in chunk
        )
        
        # Add chunk results to overall dictionary
        sop_dict.update(dict(results))
        
        # Checkpoint if callback provided
        if checkpoint_callback:
            checkpoint_callback(sop_dict, i + len(chunk))
    
    return sop_dict


def build_graph(edges):
    """Build rustworkx graph from edges DataFrame."""
    g = rx.PyGraph()
    node_ids = list(set(edges['subject'].to_list()) | set(edges['object'].to_list()))
    node_id_to_idx = {node_id: idx for idx, node_id in enumerate(node_ids)}
    g.add_nodes_from([None] * len(node_ids))
    edge_tuples = [
        (node_id_to_idx[subj], node_id_to_idx[obj], pred)
        for subj, obj, pred in zip(edges['subject'], edges['object'], edges['predicate'])
    ]
    g.add_edges_from(edge_tuples)
    return g, node_id_to_idx

def upload_to_gcs(data, gcs_path):
    """Upload JSON data to Google Cloud Storage."""
    path_parts = gcs_path.replace('gs://', '').split('/', 1)
    bucket_name = path_parts[0]
    blob_path = path_parts[1] if len(path_parts) > 1 else ''
    
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    
    blob.upload_from_string(
        json.dumps(data, separators=(",", ":")),
        content_type='application/json'
    )

def translate_paths_for_pair(pair_key, paths, node_idx_to_id):
    """Translate paths for a single pair."""
    translated_paths = []
    for path in paths:
        translated_path = [node_idx_to_id[node] for node in path]
        translated_paths.append(translated_path)
    return pair_key, translated_paths


def translate_paths(sop_dict, node_id_to_idx, n_jobs=-1, checkpoint_interval=20, checkpoint_callback=None):
    """
    Translate path indices to node IDs in parallel with checkpointing.
    
    Args:
        sop_dict: dictionary with SOP results
        node_id_to_idx: mapping from node IDs to graph indices
        n_jobs: number of parallel jobs
        checkpoint_interval: save checkpoint every N pairs
        checkpoint_callback: function to call with (sop_dict, pairs_processed) for checkpointing
    
    Returns:
        Updated sop_dict with translated_paths
    """
    node_idx_to_id = {v: k for k, v in node_id_to_idx.items()}
    
    # Prepare data for parallel processing
    pairs_and_paths = [
        (pair, data['paths'], node_idx_to_id)
        for pair, data in sop_dict.items()
    ]
    
    # Process in chunks for checkpointing
    for i in tqdm(range(0, len(pairs_and_paths), checkpoint_interval), desc='Translating paths'):
        chunk = pairs_and_paths[i:i + checkpoint_interval]
        
        # Process this chunk in parallel
        results = Parallel(n_jobs=n_jobs, backend='loky', verbose=5)(
            delayed(translate_paths_for_pair)(pair, paths, node_idx_to_id)
            for pair, paths, node_idx_to_id in chunk
        )
        
        # Update sop_dict with results
        for pair_key, translated_paths in results:
            sop_dict[pair_key]['translated_paths'] = translated_paths
            del sop_dict[pair_key]['paths']
        
        # Checkpoint if callback provided
        if checkpoint_callback:
            checkpoint_callback(sop_dict, i + len(chunk))
    
    return sop_dict


def add_edge_type_for_pair(pair_key, translated_paths, predicate_lookup, id_to_cat):
    """Add edge type and node category metadata for a single pair."""
    paths_metadata = []
    seen = set()
    
    for path in translated_paths:
        edge_types = []
        node_categories = []
        redundant_key = []
        
        for i, node in enumerate(path):
            node_categories.append(id_to_cat.get(node, None))
            redundant_key.append(node)
            if i < len(path) - 1:
                src = path[i]
                tgt = path[i + 1]
                preds = list(predicate_lookup.get((src, tgt), set()))
                edge_types.append(preds)
        
        redundant_key = tuple(redundant_key)
        if redundant_key not in seen:
            paths_metadata.append({
                "nodes": path,
                "node_categories": node_categories,
                "edge_predicates": edge_types
            })
            seen.add(redundant_key)
    
    return pair_key, paths_metadata


def add_edge_type(sop_dict, edges, nodes, n_jobs=-1, checkpoint_interval=20, checkpoint_callback=None):
    """
    Add predicate and node category information to paths in parallel with checkpointing.
    
    Args:
        sop_dict: dictionary with SOP results
        edges: DataFrame with edges
        nodes: DataFrame with nodes
        n_jobs: number of parallel jobs
        checkpoint_interval: save checkpoint every N pairs
        checkpoint_callback: function to call with (sop_dict, pairs_processed) for checkpointing
    
    Returns:
        Updated sop_dict with paths_metadata
    """
    print('Building lookup tables...')
    # Build lookup for predicates
    predicate_lookup = {}
    for subj, obj, pred in zip(edges['subject'], edges['object'], edges['predicate']):
        predicate_lookup.setdefault((subj, obj), set()).add(pred)
    
    # Build lookup for node categories
    if "id" in nodes.columns and "category" in nodes.columns:
        id_to_cat = dict(zip(nodes["id"], nodes["category"]))
    else:
        id_to_cat = {}
    
    # Prepare data for parallel processing
    pairs_and_paths = [
        (pair, data.get('translated_paths', []), predicate_lookup, id_to_cat)
        for pair, data in sop_dict.items()
    ]
    
    # Process in chunks for checkpointing
    for i in tqdm(range(0, len(pairs_and_paths), checkpoint_interval), desc='Adding edge types'):
        chunk = pairs_and_paths[i:i + checkpoint_interval]
        
        # Process this chunk in parallel
        results = Parallel(n_jobs=n_jobs, backend='loky', verbose=5)(
            delayed(add_edge_type_for_pair)(pair, paths, predicate_lookup, id_to_cat)
            for pair, paths, predicate_lookup, id_to_cat in chunk
        )
        
        # Update sop_dict with results
        for pair_key, paths_metadata in results:
            sop_dict[pair_key]['paths_metadata'] = paths_metadata
        
        # Checkpoint if callback provided
        if checkpoint_callback:
            checkpoint_callback(sop_dict, i + len(chunk))
    
    return sop_dict


def calculate_null_iteration(iteration, raw_edges, pairs, node_id_to_idx_template):
    """Calculate SOP for one null model iteration."""
    print(f'Iteration {iteration}: Rewiring...')
    edges = raw_edges.with_columns(pl.col('subject').shuffle(seed=iteration)).unique()
    
    print(f'Iteration {iteration}: Building graph...')
    g, node_id_to_idx = build_graph(edges)
    
    print(f'Iteration {iteration}: Calculating SOP...')
    null_sop = calculate_sop(pairs, g, node_id_to_idx, null=True, n_jobs=1)  # Use single job per iteration
    
    return iteration, null_sop


def calculate_null_model(nodes, raw_edges, pairs, n_iterations=500, n_jobs=-1):
    """
    Calculate null model by running multiple iterations in parallel.
    
    Args:
        nodes: DataFrame with nodes
        raw_edges: DataFrame with edges
        pairs: DataFrame with pairs to analyze
        n_iterations: number of null model iterations
        n_jobs: number of parallel jobs for iterations
    
    Returns:
        Dictionary mapping iteration number to SOP results
    """
    # Each iteration processes pairs sequentially but iterations run in parallel
    results = Parallel(n_jobs=n_jobs, backend='loky', verbose=10)(
        delayed(calculate_null_iteration)(i, raw_edges, pairs, None)
        for i in tqdm(range(n_iterations), desc='Null model iterations')
    )
    
    # Convert results to dictionary
    null_sop_dict = dict(results)
    return null_sop_dict


def main():
    # Create output directories
    os.makedirs('data/sop/raw', exist_ok=True)
    os.makedirs('data/sop/int', exist_ok=True)
    os.makedirs('data/sop/prm', exist_ok=True)
    os.makedirs('data/sop/null_4hop', exist_ok=True)
    
    print(f'Loading data...')
    pairs = pl.read_parquet(PAIRS_PATH, columns=['source', 'target'])
    edges = pl.read_parquet(f'{args.kg_path}/edges.norm', columns=['subject', 'predicate', 'object'])
    nodes = pl.read_parquet(f'{args.kg_path}/nodes.norm', columns=['id', 'category'])
    kg_name = args.kg_name
    
    print(f'Building graph for {kg_name}...')
    g, node_id_to_idx = build_graph(edges)
    
    # Define checkpoint callback for raw SOP calculation
    def checkpoint_raw_sop(sop_dict, pairs_processed):
        print(f'Checkpoint: {pairs_processed} pairs processed. Saving cumulative results...')
        gcs_path = f'gs://mtrx-us-central1-wg2-modeling-dev-storage/Piotr/sop_4hop/raw/{kg_name}_sop_checkpoint_{pairs_processed}.json'
        upload_to_gcs(sop_dict, gcs_path)
    
    print(f'Calculating SOP for {kg_name} (using {args.n_jobs} jobs, checkpointing every {args.checkpoint_interval} pairs)...')
    sop_dict = calculate_sop(
        pairs, g, node_id_to_idx, 
        n_jobs=args.n_jobs, 
        chunk_size=args.chunk_size,
        checkpoint_interval=args.checkpoint_interval,
        checkpoint_callback=checkpoint_raw_sop
    )

    print(f'Writing final raw sop results for {kg_name}...')
    gcs_path = f'gs://mtrx-us-central1-wg2-modeling-dev-storage/Piotr/sop_4hop/raw/{kg_name}_sop.json'
    upload_to_gcs(sop_dict, gcs_path)
    
    # Define checkpoint callback for translation
    def checkpoint_translated(sop_dict, pairs_processed):
        print(f'Checkpoint: {pairs_processed} pairs translated. Saving cumulative results...')
        gcs_path = f'gs://mtrx-us-central1-wg2-modeling-dev-storage/Piotr/sop_4hop/int/{kg_name}_sop_checkpoint_{pairs_processed}.json'
        upload_to_gcs(sop_dict, gcs_path)
    
    print(f'Translating paths for {kg_name} (checkpointing every {args.checkpoint_interval} pairs)...')
    sop_dict = translate_paths(
        sop_dict, node_id_to_idx, 
        n_jobs=args.n_jobs,
        checkpoint_interval=args.checkpoint_interval,
        checkpoint_callback=checkpoint_translated
    )
    
    print(f'Writing final intermediate sop results for {kg_name}...')
    gcs_path = f'gs://mtrx-us-central1-wg2-modeling-dev-storage/Piotr/sop_4hop/int/{kg_name}_sop.json'
    upload_to_gcs(sop_dict, gcs_path)
    
    # Define checkpoint callback for edge types
    def checkpoint_edge_types(sop_dict, pairs_processed):
        print(f'Checkpoint: {pairs_processed} pairs with edge types. Saving cumulative results...')
        gcs_path = f'gs://mtrx-us-central1-wg2-modeling-dev-storage/Piotr/sop_4hop/prm/{kg_name}_sop_checkpoint_{pairs_processed}.json'
        upload_to_gcs(sop_dict, gcs_path)
    
    print(f'Adding edge types for {kg_name} (checkpointing every {args.checkpoint_interval} pairs)...')
    sop_dict = add_edge_type(
        sop_dict, edges, nodes, 
        n_jobs=args.n_jobs,
        checkpoint_interval=args.checkpoint_interval,
        checkpoint_callback=checkpoint_edge_types
    )
    
    print(f'Writing final primary sop results for {kg_name}...')
    gcs_path = f'gs://mtrx-us-central1-wg2-modeling-dev-storage/Piotr/sop_4hop/prm/{kg_name}_sop.json'
    upload_to_gcs(sop_dict, gcs_path)

#     print('Calculating null model...')
#     null_model_sop_dict = calculate_null_model(nodes, edges, pairs, n_iterations=500, n_jobs=args.n_jobs)

#     print(f'Writing null model sop results for {kg_name}...')
#     with open(f'data/sop/null_4hop/{kg_name}_sop.json', 'w') as f:
#         json.dump(null_model_sop_dict, f, indent=2, sort_keys=True)

#     print('Done!')


if __name__ == '__main__':
    main()
