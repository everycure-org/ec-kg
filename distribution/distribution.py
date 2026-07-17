import json
import os

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from eckg.colors import CATEGORY_COLORS, _FALLBACK_COLOR, GROUPS

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
SANKEY_DIR   = os.path.join(SCRIPT_DIR, "..", "sankey")
CAT_JSON     = os.path.join(SANKEY_DIR, "category_counts.json")
AGG_CSV      = os.path.join(SANKEY_DIR, "sankey_agg.csv")
OUT_NODES    = os.path.join(SCRIPT_DIR, "distribution_nodes.pdf")
OUT_EDGES    = os.path.join(SCRIPT_DIR, "distribution_edges.pdf")

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

# ── Helpers ────────────────────────────────────────────────────────────────────

def strip_prefix(name: str) -> str:
    return name.replace("biolink:", "")


def load_data():
    with open(CAT_JSON) as f:
        cat_counts = json.load(f)
    df = pd.read_csv(AGG_CSV)
    pred_counts = df.groupby("predicate")["edge_count"].sum()
    return cat_counts, pred_counts


# ── Figure builders ────────────────────────────────────────────────────────────

def build_nodes_figure(cat_counts: dict):
    nodes = (
        pd.DataFrame(list(cat_counts.items()), columns=["category", "count"])
        .sort_values("count", ascending=True)
        .reset_index(drop=True)
    )
    nodes["label"] = nodes["category"].apply(strip_prefix)
    nodes["color"] = nodes["category"].map(
        lambda c: CATEGORY_COLORS.get(c, _FALLBACK_COLOR))

    plt.rcParams.update(RCPARAMS)

    fig, ax = plt.subplots(figsize=(3.5, 8.5))
    fig.subplots_adjust(left=0.26, right=0.97, top=0.95, bottom=0.07)

    n = len(nodes)
    y = np.arange(n)
    ax.barh(y, nodes["count"], height=0.72, color=nodes["color"], edgecolor="none")

    ax.set_xscale("log")
    ax.set_xlim(left=1)
    ax.set_ylim(-0.5, n - 0.5)
    ax.set_yticks(y)
    ax.set_yticklabels(nodes["label"], fontsize=5.2)
    ax.set_xlabel("Number of nodes", fontsize=8, labelpad=3)
    ax.set_title("Node type distribution", fontsize=9,
                 fontweight="bold", loc="left", pad=5)
    ax.tick_params(axis="y", length=0, pad=2)
    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(
            lambda x, _: f"{x/1e6:.1f}M" if x >= 1e6 else f"{x:,.0f}"))
    ax.grid(axis="x", which="major", color="#e0e0e0", lw=0.4, zorder=0)
    ax.set_axisbelow(True)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)

    # Count labels for top 50 node types
    top50 = nodes.nlargest(50, "count")
    for idx, row in top50.iterrows():
        ax.text(row["count"] * 1.08, idx,
                f"{row['count']:,.0f}",
                va="center", fontsize=4.5, color="#333333")

    patches = [plt.Rectangle((0,0),1,1, fc=c, ec="none", label=l) for l, c in GROUPS]
    ax.legend(handles=patches, loc="lower right", fontsize=5.0,
              frameon=True, framealpha=0.9, edgecolor="#cccccc",
              handlelength=0.9, handleheight=0.9, borderpad=0.5,
              labelspacing=0.25, title="Category group", title_fontsize=5.0)

    return fig


def build_edges_figure(pred_counts: pd.Series):
    preds = (
        pred_counts
        .reset_index()
        .rename(columns={"edge_count": "count"})
        .sort_values("count", ascending=True)
        .reset_index(drop=True)
    )
    preds["label"] = preds["predicate"].str.replace("biolink:", "", regex=False)

    plt.rcParams.update(RCPARAMS)

    fig, ax = plt.subplots(figsize=(3.5, 8.5))
    fig.subplots_adjust(left=0.26, right=0.97, top=0.95, bottom=0.07)

    n = len(preds)
    y = np.arange(n)
    ax.barh(y, preds["count"], height=0.72, color="#455a64", edgecolor="none")

    ax.set_xscale("log")
    ax.set_xlim(left=1)
    ax.set_ylim(-0.5, n - 0.5)
    ax.set_yticks(y)
    ax.set_yticklabels(preds["label"], fontsize=5.2)
    ax.set_xlabel("Number of edges", fontsize=8, labelpad=3)
    ax.set_title("Predicate distribution", fontsize=9,
                 fontweight="bold", loc="left", pad=5)
    ax.tick_params(axis="y", length=0, pad=2)
    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(
            lambda x, _: f"{x/1e6:.0f}M" if x >= 1e6 else
                          f"{x/1e3:.0f}k" if x >= 1e3 else f"{x:.0f}"))
    ax.grid(axis="x", which="major", color="#e0e0e0", lw=0.4, zorder=0)
    ax.set_axisbelow(True)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)

    # Count labels for top 50 predicates
    top50 = preds.nlargest(50, "count")
    for idx, row in top50.iterrows():
        ax.text(row["count"] * 1.08, idx,
                f"{row['count']:,.0f}",
                va="center", fontsize=4.5, color="#333333")

    return fig


def main():
    cat_counts, pred_counts = load_data()

    fig_nodes = build_nodes_figure(cat_counts)
    fig_nodes.savefig(OUT_NODES, dpi=300, bbox_inches="tight")
    print(f"Saved → {OUT_NODES}")

    fig_edges = build_edges_figure(pred_counts)
    fig_edges.savefig(OUT_EDGES, dpi=300, bbox_inches="tight")
    print(f"Saved → {OUT_EDGES}")


if __name__ == "__main__":
    main()
