import os

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from google.cloud import bigquery

from eckg.colors import UPSTREAM_SOURCE_COLORS

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR  = os.path.join(SCRIPT_DIR, "upstream_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# ── Source definitions ─────────────────────────────────────────────────────────
PROJECT = "mtrx-hub-dev-3of"
DATASET = "release_v0_15_19"

SOURCES = {
    "ROBOKOP": {
        "nodes_table": f"{PROJECT}.{DATASET}.robokop_nodes_normalized",
        "edges_table": f"{PROJECT}.{DATASET}.robokop_edges_normalized",
        "color": UPSTREAM_SOURCE_COLORS["ROBOKOP"],
    },
    "RTX-KG2": {
        "nodes_table": f"{PROJECT}.{DATASET}.rtx_kg2_nodes_normalized",
        "edges_table": f"{PROJECT}.{DATASET}.rtx_kg2_edges_normalized",
        "color": UPSTREAM_SOURCE_COLORS["RTX-KG2"],
    },
    "PrimeKG": {
        "nodes_table": f"{PROJECT}.{DATASET}.primekg_nodes_normalized",
        "edges_table": f"{PROJECT}.{DATASET}.primekg_edges_normalized",
        "color": UPSTREAM_SOURCE_COLORS["PrimeKG"],
    },
}

SOURCE_NAMES = list(SOURCES.keys())

RCPARAMS = {
    "font.family":     "Helvetica",
    "pdf.fonttype":    42,
    "ps.fonttype":     42,
    "font.size":       7,
    "axes.linewidth":  0.5,
    "xtick.major.width": 0.4,
    "ytick.major.width": 0.4,
    "xtick.major.size":  2.0,
    "ytick.major.size":  2.0,
}


# ── Data loading ───────────────────────────────────────────────────────────────

def _bq_client():
    return bigquery.Client(project=PROJECT)


def _cached_query(cache_path: str, sql: str) -> pd.DataFrame:
    if os.path.exists(cache_path):
        return pd.read_csv(cache_path)
    client = _bq_client()
    df = client.query(sql).to_dataframe()
    df.to_csv(cache_path, index=False)
    return df


def _cache_name(source: str, kind: str) -> str:
    return os.path.join(CACHE_DIR, f"{source.lower().replace('-', '_')}_{kind}.csv")


def load_node_counts(source: str, table: str) -> pd.Series:
    cache = _cache_name(source, "nodes")
    print(f"  {'[cache]' if os.path.exists(cache) else '[BQ]'} {source} nodes")
    df = _cached_query(cache, f"""
        SELECT category, COUNT(*) AS count
        FROM `{table}`
        GROUP BY category
    """)
    return df.set_index("category")["count"]


def load_edge_counts(source: str, table: str) -> pd.Series:
    cache = _cache_name(source, "edges")
    print(f"  {'[cache]' if os.path.exists(cache) else '[BQ]'} {source} edges")
    df = _cached_query(cache, f"""
        SELECT predicate, COUNT(*) AS count
        FROM `{table}`
        GROUP BY predicate
    """)
    return df.set_index("predicate")["count"]


def load_pks_counts(source: str, table: str) -> pd.Series:
    cache = _cache_name(source, "pks")
    print(f"  {'[cache]' if os.path.exists(cache) else '[BQ]'} {source} primary_knowledge_source")
    df = _cached_query(cache, f"""
        SELECT primary_knowledge_source, COUNT(*) AS count
        FROM `{table}`
        WHERE primary_knowledge_source IS NOT NULL
        GROUP BY primary_knowledge_source
    """)
    return df.set_index("primary_knowledge_source")["count"]


def load_all_data():
    node_counts, edge_counts, pks_counts = {}, {}, {}
    for name, info in SOURCES.items():
        node_counts[name] = load_node_counts(name, info["nodes_table"])
        edge_counts[name] = load_edge_counts(name, info["edges_table"])
        pks_counts[name]  = load_pks_counts(name, info["edges_table"])
    return node_counts, edge_counts, pks_counts


# ── Figure builder ─────────────────────────────────────────────────────────────

def build_grouped_bar(
    counts_by_source: dict,
    xlabel: str,
    title: str,
    strip_prefix: str = "biolink:",
) -> plt.Figure:
    """
    Grouped horizontal bar chart: one row per label, one bar per upstream source.
    Rows sorted ascending by total count so the largest label appears at top.
    """
    plt.rcParams.update(RCPARAMS)

    # Union of labels across all sources, sorted ascending by total
    all_labels = set()
    for s in counts_by_source.values():
        all_labels |= set(s.index)

    totals = {
        lbl: sum(int(counts_by_source[src].get(lbl, 0)) for src in SOURCE_NAMES)
        for lbl in all_labels
    }
    labels  = sorted(all_labels, key=lambda l: totals[l])   # ascending → top at end
    display = [l.replace(strip_prefix, "", 1) if l.startswith(strip_prefix) else l
               for l in labels]

    n     = len(labels)
    n_src = len(SOURCE_NAMES)

    # Vertical geometry within each group row
    group_h = 0.72
    bar_h   = group_h / n_src * 0.82
    offsets = np.linspace(
        (group_h - bar_h) / 2,
        -(group_h - bar_h) / 2,
        n_src,
    )

    fig_h = max(3.5, n * (group_h * 0.14) + 1.2)
    fig, ax = plt.subplots(figsize=(5.0, fig_h))
    fig.subplots_adjust(left=0.30, right=0.94, top=0.95, bottom=0.06)

    for si, src_name in enumerate(SOURCE_NAMES):
        color  = SOURCES[src_name]["color"]
        series = counts_by_source[src_name]
        y_pos  = np.arange(n, dtype=float) + offsets[si]
        x_vals = np.array([series.get(lbl, 0) for lbl in labels], dtype=float)
        mask   = x_vals > 0
        if mask.any():
            ax.barh(y_pos[mask], x_vals[mask], height=bar_h,
                    color=color, edgecolor="none", zorder=2)

    ax.set_xscale("log")
    ax.set_xlim(left=0.9)
    ax.set_ylim(-0.5, n - 0.5)
    ax.set_yticks(range(n))
    ax.set_yticklabels(display, fontsize=5.2)
    ax.set_xlabel(xlabel, fontsize=8, labelpad=3)
    ax.set_title(title, fontsize=9, fontweight="bold", loc="left", pad=5)
    ax.tick_params(axis="y", length=0, pad=2)
    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(
            lambda x, _: f"{x/1e6:.1f}M" if x >= 1e6 else
                          f"{x/1e3:.0f}k"  if x >= 1e3 else f"{x:.0f}"))
    ax.grid(axis="x", which="major", color="#e0e0e0", lw=0.4, zorder=0)
    ax.set_axisbelow(True)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)

    handles = [
        mpatches.Rectangle((0, 0), 1, 1, fc=SOURCES[s]["color"], ec="none", label=s)
        for s in SOURCE_NAMES
    ]
    ax.legend(
        handles=handles,
        loc="lower right",
        fontsize=6.0,
        frameon=True, framealpha=0.9, edgecolor="#cccccc",
        handlelength=1.0, handleheight=0.9, borderpad=0.5,
        labelspacing=0.3,
        title="Upstream source", title_fontsize=6.0,
    )

    return fig


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("Loading data...")
    node_counts, edge_counts, pks_counts = load_all_data()

    print("Building node type figure...")
    fig = build_grouped_bar(
        node_counts,
        xlabel="Number of nodes",
        title="Node type distribution by upstream source",
        strip_prefix="biolink:",
    )
    out = os.path.join(SCRIPT_DIR, "upstream_nodes.pdf")
    fig.savefig(out, dpi=300, bbox_inches="tight")
    print(f"Saved → {out}")

    print("Building predicate figure...")
    fig = build_grouped_bar(
        edge_counts,
        xlabel="Number of edges",
        title="Predicate distribution by upstream source",
        strip_prefix="biolink:",
    )
    out = os.path.join(SCRIPT_DIR, "upstream_edges.pdf")
    fig.savefig(out, dpi=300, bbox_inches="tight")
    print(f"Saved → {out}")

    print("Building primary knowledge source figure...")
    fig = build_grouped_bar(
        pks_counts,
        xlabel="Number of edges",
        title="Primary knowledge source distribution by upstream source",
        strip_prefix="infores:",
    )
    out = os.path.join(SCRIPT_DIR, "upstream_pks.pdf")
    fig.savefig(out, dpi=300, bbox_inches="tight")
    print(f"Saved → {out}")

    print("Done.")


if __name__ == "__main__":
    main()
