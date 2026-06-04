import polars as pl
import json
import random
import gcsfs
KG_DICT = {
    'PrimeKG': '/Users/piotrkaniewski/work/ec-kg-analysis/data/sop_no_filtered_kg/prm/primekg_sop.json',
    'Robokop': '/Users/piotrkaniewski/work/ec-kg-analysis/data/sop_no_filtered_kg/prm/robokop_sop.json',
    'RTX-KG2': '/Users/piotrkaniewski/work/ec-kg-analysis/data/sop_no_filtered_kg/prm/rtx_kg2_sop.json',
    'Integrated-KG': '/Users/piotrkaniewski/work/ec-kg-analysis/data/sop_no_filtered_kg/prm/integrated_kg_sop.json'
}

OFF_LABEL_PAIRS_PATH = "/Users/piotrkaniewski/work/ec-kg-analysis/data/off_label_pairs_sop.parquet"

def compute_average_sop(kg_results):
    """Returns the average SOP for a dict of {pair: {..., 'sop': int, ...}, ...}."""
    sops = [v.get('sop', 0) for v in kg_results.values()]
    if len(sops) == 0:
        return 0
    return sum(sops) / len(sops)

def main():
    fs = gcsfs.GCSFileSystem()
    # 1. Load all KG SOP dicts (restrict to first 100 pairs for each KG)
    kg_dict = {}
    for kg, kg_path in KG_DICT.items():
        print('loading kg: ', kg)

        with fs.open(kg_path, 'rb') as f:
            sop_dict = json.load(f)
        # Take only the first 100 pairs (head 100) as per insertion order
        head_100_dict = dict(list(sop_dict.items()))
        kg_dict[kg] = head_100_dict

    # 2. Calculate average SOP per KG and summarize
    averages = []
    for kg, sop_dict in kg_dict.items():
        avg_sop = compute_average_sop(sop_dict)
        averages.append({"KG": kg, "avg_SOP": avg_sop, "num_pairs": len(sop_dict)})
    avg_table = pl.DataFrame(averages)
    print("\n### Average SOPs per KG")
    print(avg_table)

    # 3. Load off-label pairs for info (names, etc)
    pairs_df = pl.read_parquet(OFF_LABEL_PAIRS_PATH)

    # 4. Pick 10 diverse drug-disease pairs as good examples of repurposing
    # We'll take 10 pairs randomly among those still counted as 'off-label', 
    # with at least some nonzero SOP in at least one KG
    candidates = []
    # Make a list of all pairs that have at least one KG with a valid SOP > 0
    for pair in pairs_df.iter_rows(named=True):
        key = f"{pair['source']}|{pair['target']}"
        in_any_kg = any(
            key in kg_dict[kg] and kg_dict[kg][key].get("sop", 0) > 0
            for kg in kg_dict
        )
        if in_any_kg:
            candidates.append(pair)

    # Shuffle and select 10 (or less if <10 available)
    random.seed(42)  # For reproducibility
    random.shuffle(candidates)
    selected = candidates

    print("\n### 100 Example Drug Repurposing Pairs")
    example_rows = []
    for ex in selected:
        key = f"{ex['source']}|{ex['target']}"
        ex_row = {
            "Drug": ex["drug_name"],
            "Disease": ex["disease_name"],
            "Source ID": ex["source"],
            "Target ID": ex["target"]
        }
        # For each KG: what is the SOP? What are the unique node categories in the paths?
        for kg in KG_DICT:
            kg_pair = kg_dict[kg].get(key, None)
            if kg_pair is None:
                ex_row[f"{kg} SOP"] = 0
                ex_row[f"{kg} categories"] = ""
            else:
                sop_val = kg_pair.get("sop", 0)
                ex_row[f"{kg} SOP"] = sop_val
                # Gather node categories from paths_metadata
                cat_set = set()
                paths_meta = kg_pair.get("paths_metadata", [])
                for p in paths_meta:
                    for c in p.get("node_categories", []):
                        if isinstance(c, list):
                            cat_set.update(c)
                        elif c is not None:
                            cat_set.add(c)
                # remove None values
                cat_set = {c for c in cat_set if c is not None}
                ex_row[f"{kg} categories"] = ", ".join(sorted(cat_set))
        example_rows.append(ex_row)

    ex_tbl = pl.DataFrame(example_rows)
    print(ex_tbl)

    # Save the summary tables for downstream / reporting if desired
    avg_table.write_csv("data/sop/output/average_SOPs.csv")
    ex_tbl.write_csv("data/sop/output/repurposing_examples.csv")

    print(
        "\nSaved: 'data/sop/summary/average_SOPs.csv' and 'repurposing_examples.csv'"
        "\nYou can further analyze/explore the 'repurposing_examples.csv' to inspect individual SOP paths and categories."
    )

if __name__ == '__main__':
    main()
