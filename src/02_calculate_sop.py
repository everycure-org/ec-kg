import polars as pl
import argparse
from tqdm import tqdm
import rustworkx as rx
import json

PAIRS_PATH = '/Users/piotrkaniewski/work/ec-kg-analysis/data/off_label_pairs_sop.parquet'

parser = argparse.ArgumentParser()
parser.add_argument('--kg_name', type=str, required=True)
parser.add_argument('--kg_path', type=str, required=True)
args = parser.parse_args()

def calculate_sop(pairs, g, node_id_to_idx):
    # Create a mapping from node IDs to internal indices (used in build_graph)
    sop_dict = {}
    for pair in tqdm(pairs.to_dicts()):
        source = pair['source']
        target = pair['target']
        # Map node ids to indices in the graph
        source_idx = node_id_to_idx[source]
        target_idx = node_id_to_idx[target]
        if source_idx is not None and target_idx is not None:
            # Find all simple paths between source_idx and target_idx
            paths = list(rx.all_simple_paths(g, source_idx, target_idx, min_depth=1, cutoff=3))
            sop = len(paths)
        sop_dict[f'{source}|{target}'] = {'sop': sop, 'paths': paths}
    return sop_dict
        

def build_graph(edges):
    g = rx.PyGraph()
    node_ids = list(set(edges['subject'].to_list()) | set(edges['object'].to_list()))
    node_id_to_idx = {node_id: idx for idx, node_id in enumerate(node_ids)}
    g.add_nodes_from([None] * len(node_ids))  # PyGraph requires list of payloads, dummy None
    edge_tuples = [
        (node_id_to_idx[subj], node_id_to_idx[obj], pred)
        for subj, obj, pred in zip(edges['subject'], edges['object'], edges['predicate'])
    ]
    g.add_edges_from(edge_tuples)
    return g, node_id_to_idx

def translate_paths(sop_dict, node_id_to_idx):
    node_idx_to_id = {v: k for k, v in node_id_to_idx.items()}
    for pair, data in sop_dict.items():
        paths = data['paths']
        sop_dict[pair]['translated_paths'] = []
        for path in tqdm(paths, f'Processing paths for {pair}'):
            translated_path = []
            for node in path:
                translated_path.append(node_idx_to_id[node])
            sop_dict[pair]['translated_paths'].append(translated_path)
        del sop_dict[pair]['paths']
    return sop_dict

def add_edge_type(sop_dict, edges, nodes):
    """
    Adds predicate (edge type) information and node category information to the paths in sop_dict.
    Adds result as 'paths_metadata' key per pair.
    """
    # Build lookup for predicates: (src_id, tgt_id) -> list of predicates
    predicate_lookup = {}
    for subj, obj, pred in zip(edges['subject'], edges['object'], edges['predicate']):
        predicate_lookup.setdefault((subj, obj), set()).add(pred)

    # Build lookup for node categories
    if "id" in nodes.columns and "category" in nodes.columns:
        id_to_cat = dict(zip(nodes["id"], nodes["category"]))
    else:
        id_to_cat = {}

    for pair, data in sop_dict.items():
        # Use translated_paths for this function, which are lists of node ids
        translated_paths = data.get('translated_paths', [])
        paths_metadata = []
        seen = set()
        for path in tqdm(translated_paths, desc=f'Adding edge type for {pair}'):
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
        sop_dict[pair]['paths_metadata'] = paths_metadata
    return sop_dict

def main():
    pairs = pl.read_parquet(PAIRS_PATH, columns=['source','target'])
    edges = pl.read_parquet(f'{args.kg_path}/edges.norm', columns=['subject','predicate','object'])
    nodes = pl.read_parquet(f'{args.kg_path}/nodes.norm', columns=['id','category'])
    kg_name = args.kg_name
    
    print(f'Building graph for {kg_name}...')
    g, node_id_to_idx = build_graph(edges)
    
    print(f'Calculating SOP for {kg_name}...')
    sop_dict = calculate_sop(pairs, g, node_id_to_idx)
    
    print(f'Writing raw sop results for {kg_name}...')
    with open(f'data/sop/raw/{kg_name}_sop.json', 'w') as f:
        json.dump(sop_dict, f)
    
    print(f'Translating paths for {kg_name}...')
    sop_dict = translate_paths(sop_dict, node_id_to_idx)
    
    print(f'Writing intermediate sop results for {kg_name}...')
    with open(f'data/sop/int/{kg_name}_sop.json', 'w') as f:
        json.dump(sop_dict, f)

    sop_dict = add_edge_type(sop_dict, edges, nodes)
    print(f'Writing primary sop results for {kg_name}...')
    with open(f'data/sop/prm/{kg_name}_sop.json', 'w') as f:
        json.dump(sop_dict, f)

if __name__ == '__main__':
    main()