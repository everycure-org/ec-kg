"""
Mechanistic path network visualization — Bortezomib → CDKN2A → CTCL.

Draws a circular network graph showing 2-hop paths from Bortezomib to
primary cutaneous T-cell lymphoma (CTCL) that pass through CDKN2A,
overlaid on sampled background paths from the same drug–disease pair.

Main path edges are coloured by which upstream source KG they come from.
Node colours follow the project-wide semantic group palette.

Usage
-----
python 08_visualize_network_path.py
"""

import random
import sys
from pathlib import Path

import ijson
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import polars

sys.path.append(str(Path(__file__).parent.parent / "ml_validation"))
from fig_style import (
    apply_style,
    figsize,
    LEGEND_KWARGS,
    AXIS_LABEL_SIZE, TICK_LABEL_SIZE, LEGEND_SIZE,
    PAGE_WIDTH_IN, SAVE_DPI,
    savefig as save_fig,
)

# ── Paths ──────────────────────────────────────────────────────────────────
BASE = Path("/Users/piotrkaniewski/work/ec-kg-analysis")

SOP_PATH       = BASE / "data/sop_no_filtered_kg/prm/integrated_kg_sop.json"
NODES_PATH     = BASE / "data/integrated_kg/nodes.norm"
PRIMEKG_EDGES  = BASE / "data/primekg/edges.norm/"
ROBOKOP_EDGES  = BASE / "data/robokop/edges.norm/"
RTXKG2_EDGES   = BASE / "data/rtx_kg2/edges.norm/"
OUT_DIR        = BASE / "visualizations/mechanistic_pairs"

DRUG_ID     = "CHEBI:52717"    # Bortezomib
DISEASE_ID  = "MONDO:0015758"  # Primary cutaneous T-cell lymphoma
SOP_KEY     = f"{DRUG_ID}|{DISEASE_ID}"

# ── Project-wide color palette ─────────────────────────────────────────────
# KG edge colors — UPSTREAM_SOURCE_COLORS (same as all other scripts)
KG_TO_COLOR = {
    "PrimeKG": "#FF7F0E",
    "Robokop":  "#17BECF",   # notebook uses 'Robokop' (mixed case)
    "RTX-KG2": "#1F77B4",
}

# Node category colors — GROUP_COLORS semantic palette
CATEGORY_TO_COLOR = {
    "biolink:SmallMolecule": "#009E73",   # Chemical / Drug
    "biolink:Drug":          "#009E73",   # Chemical / Drug
    "biolink:Protein":       "#0072B2",   # Molecular / Genetic
    "biolink:Disease":       "#D55E00",   # Disease / Phenotype
}
BACKGROUND_NODE_COLOR = "#DDDDDD"
FALLBACK_NODE_COLOR   = "#AAAAAA"

# ── Label clean-up ─────────────────────────────────────────────────────────
LABEL_MAPPING = {
    "CDKN2A protein, human":               "CDKN2A",
    "Primary cutaneous t-cell lymphoma":   "CTCL",
}


def clean_predicate(pred: str) -> str:
    """Shorten a biolink predicate string for edge label display."""
    s = pred.replace("biolink:", "").replace("_", " ")
    s = s.replace("genetically associated with", "associated with")
    if len(s) > 28:
        words, lines, line = s.split(), [], ""
        for w in words:
            if len(line) + len(w) + 1 > 22:
                lines.append(line.strip())
                line = ""
            line += " " + w
        lines.append(line.strip())
        return "\n".join(lines)
    return s


# ── Data loading ────────────────────────────────────────────────────────────

def load_edges_df() -> polars.DataFrame:
    """Stream the integrated KG SOP for the Bortezomib–CTCL pair and join node metadata."""
    with open(SOP_PATH, "rb") as f:
        for k, v in ijson.kvitems(f, ""):
            if k == SOP_KEY:
                objects = v
                break

    rows = []
    for meta in objects.get("paths_metadata", []):
        nodes = meta["nodes"]
        for i, preds in enumerate(meta["edge_predicates"]):
            for pred in preds:
                rows.append({"subject": nodes[i], "predicate": pred, "object": nodes[i + 1]})

    df = polars.DataFrame(rows)
    nodes_df = polars.read_parquet(str(NODES_PATH))[["id", "category", "name"]]

    df = df.join(
        nodes_df.rename({"id": "subject", "category": "subject_category", "name": "subject_name"}),
        on="subject", how="left",
    ).join(
        nodes_df.rename({"id": "object", "category": "object_category", "name": "object_name"}),
        on="object", how="left",
    )
    return df


def load_kg_edge_sets() -> dict:
    """Load edge sets from each upstream KG for membership testing."""
    sets = {}
    for name, path in [
        ("PrimeKG", PRIMEKG_EDGES),
        ("Robokop",  ROBOKOP_EDGES),
        ("RTX-KG2", RTXKG2_EDGES),
    ]:
        df = polars.read_parquet(str(path))[["subject", "predicate", "object"]]
        sets[name] = set(zip(df["subject"], df["predicate"], df["object"]))
    return sets


def build_example_edges(edges_df: polars.DataFrame, kg_sets: dict) -> polars.DataFrame:
    """Filter to the CDKN2A sub-path and add per-KG membership flags."""
    ex = edges_df.filter(
        ((polars.col("subject") == DRUG_ID)
         & polars.col("object_name").str.contains("CDKN2A"))
        | ((polars.col("object") == DISEASE_ID)
           & polars.col("subject_name").str.contains("CDKN2A"))
    )

    def _in_kg(kg_set):
        return polars.struct(["subject", "predicate", "object"]).map_elements(
            lambda r: (r["subject"], r["predicate"], r["object"]) in kg_set,
            return_dtype=polars.Boolean,
        )

    return ex.with_columns([
        _in_kg(kg_sets["PrimeKG"]).alias("is_primekg"),
        _in_kg(kg_sets["Robokop"]).alias("is_robokop"),
        _in_kg(kg_sets["RTX-KG2"]).alias("is_rtxkg2"),
    ])


# ── Graph construction ──────────────────────────────────────────────────────

def build_graph(edges_df: polars.DataFrame, ex_edges_df: polars.DataFrame) -> tuple:
    G = nx.DiGraph()
    main_path_nodes: set = set()

    for node_name, node_cat in set(
        list(zip(ex_edges_df["subject_name"].to_list(), ex_edges_df["subject_category"].to_list()))
        + list(zip(ex_edges_df["object_name"].to_list(), ex_edges_df["object_category"].to_list()))
    ):
        if not G.has_node(node_name):
            G.add_node(node_name, category=node_cat, is_main=True)
            main_path_nodes.add(node_name)

    for row in ex_edges_df.iter_rows(named=True):
        sources = (
            (["PrimeKG"] if row["is_primekg"] else [])
            + (["Robokop"] if row["is_robokop"] else [])
            + (["RTX-KG2"] if row["is_rtxkg2"] else [])
        )
        G.add_edge(row["subject_name"], row["object_name"],
                   predicate=row["predicate"], sources=sources, is_main=True)

    # Sample background 2-hop paths
    drug_nodes    = {n for n in G.nodes if G.nodes[n].get("category", "") in CATEGORY_TO_COLOR
                     and "Drug" in G.nodes[n].get("category", "")}
    disease_nodes = {n for n in G.nodes if "Disease" in G.nodes[n].get("category", "")}

    edges_by_subject: dict = {}
    for row in edges_df.iter_rows(named=True):
        edges_by_subject.setdefault(row["subject_name"], []).append(row)

    additional_paths = []
    random.seed(42)
    for drug in drug_nodes:
        for e1 in edges_by_subject.get(drug, [])[:10]:
            inter = e1["object_name"]
            for e2 in edges_by_subject.get(inter, [])[:5]:
                if e2["object_name"] in disease_nodes:
                    additional_paths.append((e1, e2, inter, e1["object_category"]))
                    if not G.has_node(inter):
                        G.add_node(inter, category=e1["object_category"], is_main=False)

    background_edges = []
    for e1, e2, _, _ in random.sample(additional_paths, min(8, len(additional_paths))):
        G.add_edge(e1["subject_name"], e1["object_name"],
                   predicate=e1["predicate"], sources=[], is_main=False)
        G.add_edge(e2["subject_name"], e2["object_name"],
                   predicate=e2["predicate"], sources=[], is_main=False)
        background_edges += [(e1["subject_name"], e1["object_name"]),
                              (e2["subject_name"], e2["object_name"])]

    G.remove_nodes_from([n for n in G.nodes if G.degree(n) == 0])
    return G, main_path_nodes, background_edges


# ── Plotting ────────────────────────────────────────────────────────────────

def draw_network(G: nx.DiGraph, main_path_nodes: set, background_edges: list) -> None:
    apply_style()

    pos = nx.circular_layout(G)
    label_pos = {n: (x, y + 0.12) for n, (x, y) in pos.items()}
    display_labels = {n: LABEL_MAPPING.get(n, n) for n in G.nodes}

    main_edges, main_edge_colors = [], []
    for u, v in G.edges:
        if G.edges[u, v].get("is_main", False):
            main_edges.append((u, v))
            srcs = G.edges[u, v]["sources"]
            main_edge_colors.append(KG_TO_COLOR.get(srcs[0], "#666666") if srcs else "#666666")

    fig, ax = plt.subplots(figsize=figsize(PAGE_WIDTH_IN, 6.5))

    background_nodes = [n for n in G.nodes if n not in main_path_nodes]
    if background_nodes:
        nx.draw_networkx_nodes(G, pos, nodelist=background_nodes,
                               node_color=BACKGROUND_NODE_COLOR, node_size=800,
                               edgecolors="k", linewidths=1.0, ax=ax)

    if main_path_nodes:
        nx.draw_networkx_nodes(
            G, pos, nodelist=list(main_path_nodes),
            node_color=[CATEGORY_TO_COLOR.get(G.nodes[n].get("category", ""), FALLBACK_NODE_COLOR)
                        for n in main_path_nodes],
            node_size=800, edgecolors="k", linewidths=1.0, ax=ax,
        )

    if background_edges:
        nx.draw_networkx_edges(G, pos, edgelist=background_edges,
                               arrows=True, arrowstyle="-|>", arrowsize=14, ax=ax,
                               width=1.0, edge_color="#CCCCCC", alpha=0.3,
                               min_source_margin=20, min_target_margin=18,
                               connectionstyle="arc3,rad=0.1")

    if main_edges:
        nx.draw_networkx_edges(G, pos, edgelist=main_edges,
                               arrows=True, arrowstyle="-|>", arrowsize=14, ax=ax,
                               width=1.5, edge_color=main_edge_colors, alpha=1.0,
                               min_source_margin=20, min_target_margin=18,
                               connectionstyle="arc3,rad=0.1")

    nx.draw_networkx_labels(G, label_pos, labels=display_labels,
                            font_size=AXIS_LABEL_SIZE, font_weight="bold", ax=ax,
                            verticalalignment="bottom", horizontalalignment="center")

    main_edge_labels = {(u, v): clean_predicate(G.edges[u, v]["predicate"]) for u, v in main_edges}
    for (u, v), lbl in main_edge_labels.items():
        nx.draw_networkx_edge_labels(
            G, pos, edge_labels={(u, v): lbl},
            font_color="#333333",
            font_size=TICK_LABEL_SIZE if "\n" not in lbl else TICK_LABEL_SIZE - 1,
            ax=ax, label_pos=0.55,
            bbox=dict(boxstyle="round,pad=0.0", facecolor="none", edgecolor="none", alpha=0),
        )

    _lkw = {**LEGEND_KWARGS, "title_fontsize": LEGEND_SIZE}

    node_legend = ax.legend(
        handles=[
            Patch(facecolor=CATEGORY_TO_COLOR["biolink:Drug"],    edgecolor="k", linewidth=0.5, label="Drug"),
            Patch(facecolor=CATEGORY_TO_COLOR["biolink:Protein"], edgecolor="k", linewidth=0.5, label="Protein"),
            Patch(facecolor=CATEGORY_TO_COLOR["biolink:Disease"], edgecolor="k", linewidth=0.5, label="Disease"),
        ],
        loc="upper left", bbox_to_anchor=(1.02, 1.0),
        title="Node type", **_lkw,
    )

    edge_legend = ax.legend(
        handles=[
            Line2D([0], [0], color=KG_TO_COLOR["PrimeKG"], linewidth=2, label="PrimeKG"),
            Line2D([0], [0], color=KG_TO_COLOR["Robokop"],  linewidth=2, label="Robokop"),
            Line2D([0], [0], color=KG_TO_COLOR["RTX-KG2"], linewidth=2, label="RTX-KG2"),
        ],
        loc="upper left", bbox_to_anchor=(1.02, 0.62),
        title="Edge source", **_lkw,
    )
    ax.add_artist(node_legend)

    ax.margins(0.15)
    ax.axis("off")
    plt.subplots_adjust(right=0.78)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "bortezomib_cdkn2a_ctcl_network"
    save_fig(fig, str(out.with_suffix(".pdf")))
    fig.savefig(str(out.with_suffix(".png")), dpi=SAVE_DPI, bbox_inches="tight")
    plt.close(fig)


# ── Entry point ─────────────────────────────────────────────────────────────

def main():
    print("Loading SOP edge data...")
    edges_df = load_edges_df()
    print("Loading upstream KG edge sets...")
    kg_sets = load_kg_edge_sets()
    print("Building example edges...")
    ex_edges_df = build_example_edges(edges_df, kg_sets)
    print("Building graph...")
    G, main_path_nodes, background_edges = build_graph(edges_df, ex_edges_df)
    print("Drawing network...")
    draw_network(G, main_path_nodes, background_edges)
    print("Done.")


if __name__ == "__main__":
    main()
