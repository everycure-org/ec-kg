"""
Venn diagrams showing overlap of node types, primary knowledge sources,
and exact node IDs across the three upstream sources: ROBOKOP, RTX-KG2, PrimeKG.

Requires upstream_distribution.py to have been run first (reads its cache).
Requires: pip install matplotlib-venn
"""
import os

import matplotlib.pyplot as plt
import pandas as pd
from google.cloud import bigquery
from matplotlib_venn import venn3, venn3_circles

from eckg.colors import UPSTREAM_REGION_COLORS as REGION_COLORS
from eckg.colors import UPSTREAM_SOURCE_COLORS as SOURCE_COLORS

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Per-source node/edge/PKS counts live in distribution/upstream_cache/
DIST_CACHE_DIR = os.path.join(SCRIPT_DIR, "..", "distribution", "upstream_cache")
# Venn-specific BigQuery result caches live alongside this script
VENN_CACHE_DIR = SCRIPT_DIR

# ── Source definitions ─────────────────────────────────────────────────────────
SOURCE_NAMES = ["ROBOKOP", "RTX-KG2", "PrimeKG"]

PROJECT = "mtrx-hub-dev-3of"
DATASET = "release_v0_15_19"

RCPARAMS = {
    "font.family":     "Helvetica",
    "pdf.fonttype":    42,
    "ps.fonttype":     42,
    "font.size":       7,
    "axes.linewidth":  0.5,
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _dist_cache(source: str, kind: str) -> str:
    return os.path.join(DIST_CACHE_DIR, f"{source.lower().replace('-', '_')}_{kind}.csv")


def load_sets(kind: str, index_col: str) -> dict:
    """Return {source_name: set_of_labels} from upstream_distribution.py cache."""
    sets = {}
    for src in SOURCE_NAMES:
        cache = _dist_cache(src, kind)
        if not os.path.exists(cache):
            raise FileNotFoundError(
                f"Cache file not found: {cache}\n"
                "Run distribution/upstream_distribution.py first."
            )
        df = pd.read_csv(cache)
        sets[src] = set(df[index_col].dropna())
        print(f"  {src}: {len(sets[src])} {kind}")
    return sets


def strip_prefix(s: str, prefix: str) -> str:
    return s[len(prefix):] if s.startswith(prefix) else s


# ── Set-based Venn (node types, PKS) ──────────────────────────────────────────

def build_venn(
    sets: dict,
    title: str,
    prefix: str = "biolink:",
    list_labels: bool = True,
    max_list: int = 14,
    label_fontsize: float = 4.5,
) -> plt.Figure:
    """
    Three-set Venn diagram built from Python sets.
    Regions with ≤ max_list items show item names (prefix stripped).
    Larger regions show just the count.
    """
    plt.rcParams.update(RCPARAMS)

    A = sets[SOURCE_NAMES[0]]
    B = sets[SOURCE_NAMES[1]]
    C = sets[SOURCE_NAMES[2]]

    fig, ax = plt.subplots(figsize=(6.5, 5.8))
    fig.subplots_adjust(left=0.05, right=0.95, bottom=0.04, top=0.88)

    v = venn3([A, B, C], set_labels=SOURCE_NAMES, ax=ax, alpha=0.48)

    for rid, col in REGION_COLORS.items():
        patch = v.get_patch_by_id(rid)
        if patch:
            patch.set_facecolor(col)

    venn3_circles([A, B, C], ax=ax, linewidth=0.8, color="#555555")

    for lbl in v.set_labels:
        if lbl:
            lbl.set_fontsize(9)
            lbl.set_fontweight("bold")

    regions = {
        "100": A - B - C,
        "010": B - A - C,
        "001": C - A - B,
        "110": (A & B) - C,
        "101": (A & C) - B,
        "011": (B & C) - A,
        "111": A & B & C,
    }

    for rid, items in regions.items():
        lbl = v.get_label_by_id(rid)
        if lbl is None:
            continue
        n = len(items)
        if list_labels and 0 < n <= max_list:
            names = sorted(strip_prefix(s, prefix) for s in items)
            lbl.set_text("\n".join(names))
            lbl.set_fontsize(label_fontsize)
            lbl.set_linespacing(1.3)
        else:
            lbl.set_text(str(n) if n > 0 else "")
            lbl.set_fontsize(7.5)

    ax.set_title(title, fontsize=10, fontweight="bold", loc="left", pad=6)
    return fig


# ── Count-based Venn (node IDs, edge triples) ─────────────────────────────────

# venn3 subsets tuple order: (Abc, aBc, ABc, abC, AbC, aBC, ABC)
# A=ROBOKOP  B=RTX-KG2  C=PrimeKG
_REGION_MAP = {
    (True,  False, False): "Abc",
    (False, True,  False): "aBc",
    (True,  True,  False): "ABc",
    (False, False, True):  "abC",
    (True,  False, True):  "AbC",
    (False, True,  True):  "aBC",
    (True,  True,  True):  "ABC",
}

# Maps venn3 letter key → binary string ID used by get_patch_by_id / get_label_by_id
_VENN_TO_REGION = {
    "Abc": "100", "aBc": "010", "ABc": "110",
    "abC": "001", "AbC": "101", "aBC": "011", "ABC": "111",
}

_REGION_LABELS = {
    "100": "ROBOKOP only", "010": "RTX-KG2 only", "001": "PrimeKG only",
    "110": "ROBOKOP ∩ RTX-KG2", "101": "ROBOKOP ∩ PrimeKG",
    "011": "RTX-KG2 ∩ PrimeKG", "111": "All three",
}

NODE_ID_CACHE     = os.path.join(VENN_CACHE_DIR, "node_id_venn_counts.csv")
EDGE_TRIPLE_CACHE = os.path.join(VENN_CACHE_DIR, "edge_triple_venn_counts.csv")


def _run_bq_membership_query(sql: str) -> dict:
    client = bigquery.Client(project=PROJECT)
    df = client.query(sql).to_dataframe()
    counts = {}
    for _, row in df.iterrows():
        key = _REGION_MAP.get((row["in_robokop"], row["in_rtx"], row["in_primekg"]))
        if key:
            counts[key] = int(row["count"])
    return counts


def load_node_id_counts() -> dict:
    if os.path.exists(NODE_ID_CACHE):
        print("  [cache] node ID venn counts")
        df = pd.read_csv(NODE_ID_CACHE)
        return dict(zip(df["region"], df["count"]))

    print("  [BQ] querying node ID overlap (this may take a few minutes)...")
    counts = _run_bq_membership_query(f"""
        WITH tagged AS (
            SELECT id, 'R' AS src FROM `{PROJECT}.{DATASET}.robokop_nodes_normalized`
            UNION ALL
            SELECT id, 'T' AS src FROM `{PROJECT}.{DATASET}.rtx_kg2_nodes_normalized`
            UNION ALL
            SELECT id, 'P' AS src FROM `{PROJECT}.{DATASET}.primekg_nodes_normalized`
        ),
        membership AS (
            SELECT
                id,
                LOGICAL_OR(src = 'R') AS in_robokop,
                LOGICAL_OR(src = 'T') AS in_rtx,
                LOGICAL_OR(src = 'P') AS in_primekg
            FROM tagged
            GROUP BY id
        )
        SELECT in_robokop, in_rtx, in_primekg, COUNT(*) AS count
        FROM membership
        GROUP BY in_robokop, in_rtx, in_primekg
    """)
    pd.DataFrame(list(counts.items()), columns=["region", "count"]).to_csv(NODE_ID_CACHE, index=False)
    return counts


def load_edge_triple_counts() -> dict:
    if os.path.exists(EDGE_TRIPLE_CACHE):
        print("  [cache] edge triple venn counts")
        df = pd.read_csv(EDGE_TRIPLE_CACHE)
        return dict(zip(df["region"], df["count"]))

    print("  [BQ] querying edge triple overlap (this may take several minutes)...")
    counts = _run_bq_membership_query(f"""
        WITH tagged AS (
            SELECT DISTINCT subject, predicate, object, 'R' AS src
            FROM `{PROJECT}.{DATASET}.robokop_edges_normalized`
            UNION ALL
            SELECT DISTINCT subject, predicate, object, 'T' AS src
            FROM `{PROJECT}.{DATASET}.rtx_kg2_edges_normalized`
            UNION ALL
            SELECT DISTINCT subject, predicate, object, 'P' AS src
            FROM `{PROJECT}.{DATASET}.primekg_edges_normalized`
        ),
        membership AS (
            SELECT
                subject, predicate, object,
                LOGICAL_OR(src = 'R') AS in_robokop,
                LOGICAL_OR(src = 'T') AS in_rtx,
                LOGICAL_OR(src = 'P') AS in_primekg
            FROM tagged
            GROUP BY subject, predicate, object
        )
        SELECT in_robokop, in_rtx, in_primekg, COUNT(*) AS count
        FROM membership
        GROUP BY in_robokop, in_rtx, in_primekg
    """)
    pd.DataFrame(list(counts.items()), columns=["region", "count"]).to_csv(EDGE_TRIPLE_CACHE, index=False)
    return counts


def build_venn_from_counts(counts: dict, title: str) -> plt.Figure:
    plt.rcParams.update(RCPARAMS)

    subsets = tuple(counts.get(k, 0) for k in
                    ["Abc", "aBc", "ABc", "abC", "AbC", "aBC", "ABC"])

    fig, ax = plt.subplots(figsize=(6.5, 5.8))
    fig.subplots_adjust(left=0.05, right=0.95, bottom=0.04, top=0.88)

    v = venn3(subsets=subsets, set_labels=SOURCE_NAMES, ax=ax, alpha=0.48)

    for vkey, rid in _VENN_TO_REGION.items():
        patch = v.get_patch_by_id(rid)
        if patch:
            patch.set_facecolor(REGION_COLORS[rid])

    venn3_circles(subsets=subsets, ax=ax, linewidth=0.8, color="#555555")

    for lbl in v.set_labels:
        if lbl:
            lbl.set_fontsize(9)
            lbl.set_fontweight("bold")

    for vkey, rid in _VENN_TO_REGION.items():
        lbl = v.get_label_by_id(rid)
        if lbl is None:
            continue
        n = counts.get(vkey, 0)
        lbl.set_text(f"{n:,}" if n > 0 else "")
        lbl.set_fontsize(6.5)

    ax.set_title(title, fontsize=10, fontweight="bold", loc="left", pad=6)
    return fig


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    # ── Node types ────────────────────────────────────────────────────────────
    print("Node types:")
    node_sets = load_sets("nodes", "category")

    fig = build_venn(
        node_sets,
        title="Node type overlap across upstream sources",
        prefix="biolink:",
        list_labels=False,
    )
    fig.savefig(os.path.join(SCRIPT_DIR, "upstream_venn_nodes.pdf"), dpi=300, bbox_inches="tight")
    print(f"Saved → upstream_venn_nodes.pdf\n")

    A, B, C = node_sets[SOURCE_NAMES[0]], node_sets[SOURCE_NAMES[1]], node_sets[SOURCE_NAMES[2]]
    for label, region in [
        ("ROBOKOP only",       A - B - C),
        ("RTX-KG2 only",       B - A - C),
        ("PrimeKG only",       C - A - B),
        ("ROBOKOP ∩ RTX-KG2", (A & B) - C),
        ("ROBOKOP ∩ PrimeKG", (A & C) - B),
        ("RTX-KG2 ∩ PrimeKG", (B & C) - A),
        ("All three",          A & B & C),
    ]:
        items = sorted(strip_prefix(s, "biolink:") for s in region)
        print(f"  {label} ({len(items)}): {', '.join(items) if items else '—'}")

    # ── Primary knowledge source ───────────────────────────────────────────────
    print("\nPrimary knowledge sources:")
    pks_sets = load_sets("pks", "primary_knowledge_source")

    fig = build_venn(
        pks_sets,
        title="Primary knowledge source overlap across upstream sources",
        prefix="infores:",
        list_labels=True,
        max_list=14,
        label_fontsize=4.2,
    )
    fig.savefig(os.path.join(SCRIPT_DIR, "upstream_venn_pks.pdf"), dpi=300, bbox_inches="tight")
    print(f"Saved → upstream_venn_pks.pdf")

    # ── Node IDs ───────────────────────────────────────────────────────────────
    print("\nNode IDs:")
    id_counts = load_node_id_counts()
    for vkey, rid in _VENN_TO_REGION.items():
        print(f"  {_REGION_LABELS[rid]}: {id_counts.get(vkey, 0):,}")

    fig = build_venn_from_counts(id_counts, title="Node overlap by ID across upstream sources")
    fig.savefig(os.path.join(SCRIPT_DIR, "upstream_venn_node_ids.pdf"), dpi=300, bbox_inches="tight")
    print(f"Saved → upstream_venn_node_ids.pdf")

    # ── Edge triples ───────────────────────────────────────────────────────────
    print("\nEdge triples (unique subject, predicate, object):")
    edge_counts = load_edge_triple_counts()
    for vkey, rid in _VENN_TO_REGION.items():
        print(f"  {_REGION_LABELS[rid]}: {edge_counts.get(vkey, 0):,}")

    fig = build_venn_from_counts(edge_counts, title="Edge overlap by unique triple across upstream sources")
    fig.savefig(os.path.join(SCRIPT_DIR, "upstream_venn_edge_triples.pdf"), dpi=300, bbox_inches="tight")
    print(f"Saved → upstream_venn_edge_triples.pdf")


if __name__ == "__main__":
    main()
