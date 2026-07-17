"""
Stacked-bar replacement for the upstream_nodes / upstream_edges / upstream_pks
grouped bar charts (see upstream_distribution.py). One 3-panel figure
showing, for node types, predicates, and primary knowledge sources, the top
individual items ranked by total count — same as the original bar charts —
but as a single stacked bar per item instead of one grouped bar per source.

Each bar is segmented by upstream source (ROBOKOP / RTX-KG2 / PrimeKG,
eckg.colors.UPSTREAM_SOURCE_COLORS), with segment length equal to that
source's own count for the item — so both the total and the per-source
breakdown are visible directly, with no blended "combination" colors to
decode against a legend.

Uses a LINEAR x-axis rather than this project's usual log scale: stacked
segments only read correctly on a linear axis (segment pixel width must be
proportional to its own value, not to log of the cumulative sum before it —
on a log axis a segment's apparent size depends on where the preceding
stack lands, which misrepresents it).

Reuses upstream_distribution.py's BigQuery caching, so run that first (or
just run this — it calls the same cached loaders).
"""
import os

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from eckg.colors import UPSTREAM_SOURCE_COLORS
from upstream_distribution import SOURCE_NAMES, load_all_data

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

RCPARAMS = {
    "font.family":       "Helvetica",
    "pdf.fonttype":      42,
    "ps.fonttype":       42,
    "font.size":         7,
    "axes.linewidth":    0.5,
    "xtick.major.width": 0.4,
    "ytick.major.width": 0.4,
    "xtick.major.size":  2.0,
    "ytick.major.size":  2.0,
}

TOP_N = 15   # items shown per panel


def item_table(counts_by_source: dict) -> pd.DataFrame:
    """
    One row per item (union of labels across sources): its count from each
    source and the total across all three. Sorted descending by total.
    """
    all_labels = set()
    for s in counts_by_source.values():
        all_labels |= set(s.index)

    rows = []
    for lbl in all_labels:
        per_source = {src: int(counts_by_source[src].get(lbl, 0)) for src in SOURCE_NAMES}
        total = sum(per_source.values())
        if total > 0:
            rows.append({"label": lbl, "total": total, **per_source})

    df = pd.DataFrame(rows)
    return df.sort_values("total", ascending=False).reset_index(drop=True)


def draw_stacked_bar_panel(ax, counts_by_source: dict, title: str, xlabel: str,
                            strip_prefix: str = "biolink:", top_n: int = TOP_N):
    df = item_table(counts_by_source).head(top_n)
    df = df.iloc[::-1].reset_index(drop=True)   # largest ends up at the top

    n = len(df)
    y = np.arange(n)

    left = np.zeros(n)
    for src in SOURCE_NAMES:
        vals = df[src].to_numpy()
        ax.barh(y, vals, left=left, height=0.7,
                color=UPSTREAM_SOURCE_COLORS[src], edgecolor="none", zorder=2)
        left = left + vals

    labels = [l.replace(strip_prefix, "", 1) if l.startswith(strip_prefix) else l
              for l in df["label"]]
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=5.5)
    ax.set_ylim(-0.6, n - 0.4)
    ax.tick_params(axis="y", length=0, pad=2)

    ax.set_xlim(left=0, right=df["total"].max() * 1.22)   # headroom for value labels
    ax.set_xlabel(xlabel, fontsize=6.5, labelpad=3)
    ax.set_title(title, fontsize=9, fontweight="bold", loc="left", pad=4)
    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(
            lambda v, _: f"{v/1e6:.1f}M" if v >= 1e6 else
                          f"{v/1e3:.0f}k" if v >= 1e3 else f"{v:.0f}"))
    ax.grid(axis="x", which="major", color="#e0e0e0", lw=0.4, zorder=0)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)

    for yi, v in zip(y, df["total"]):
        ax.text(v * 1.02, yi, f"{v:,.0f}", va="center", fontsize=4.2, color="#333333")

    handles = [
        mpatches.Rectangle((0, 0), 1, 1, fc=UPSTREAM_SOURCE_COLORS[src], ec="none", label=src)
        for src in SOURCE_NAMES
    ]
    # Placed above the axes, right-aligned with the title row.
    ax.legend(handles=handles, loc="lower right", bbox_to_anchor=(1, 1.01),
              fontsize=4.8, ncol=3, frameon=False,
              handlelength=1.0, handleheight=0.9, borderpad=0.2,
              labelspacing=0.25, columnspacing=0.8)


def main():
    plt.rcParams.update(RCPARAMS)
    print("Loading data...")
    node_counts, edge_counts, pks_counts = load_all_data()

    fig, axes = plt.subplots(3, 1, figsize=(4.5, 10))
    fig.subplots_adjust(left=0.22, right=0.97, top=0.94, bottom=0.05, hspace=0.55)

    print("Building node type panel...")
    draw_stacked_bar_panel(axes[0], node_counts,
                            "Node type distribution by upstream source", "Number of nodes",
                            strip_prefix="biolink:")

    print("Building predicate panel...")
    draw_stacked_bar_panel(axes[1], edge_counts,
                            "Predicate distribution by upstream source", "Number of edges",
                            strip_prefix="biolink:")

    print("Building primary knowledge source panel...")
    draw_stacked_bar_panel(axes[2], pks_counts,
                            "Primary knowledge source distribution by upstream source", "Number of edges",
                            strip_prefix="infores:")

    out = os.path.join(SCRIPT_DIR, "upstream_stacked_bar.pdf")
    fig.savefig(out, dpi=300)
    print(f"Saved → {out}")


if __name__ == "__main__":
    main()
