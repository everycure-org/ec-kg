"""
UpSet-style replacement for the count-based/set-based Venn diagrams in
upstream_venn.py: node ID overlap, edge triple overlap, and primary
knowledge source overlap across the three upstream sources (ROBOKOP,
RTX-KG2, PrimeKG). One 3-panel figure, each panel a classic UpSet plot
(bar per source-combination + membership matrix below) instead of a
3-circle Venn diagram.

Unlike distribution/upstream_upset.py — which shows individual items and
so can't collapse them into per-combination bars without hiding which
item dominates — all three datasets here are already region-level counts
with no per-item detail to lose: node IDs and edge triples are counted
directly per region by BigQuery, and PKS identifiers are counted from
fixed set membership. The classic aggregate UpSet form fits these as-is.

Matrix dots use each source's own color from
eckg.colors.UPSTREAM_SOURCE_COLORS when that source is part of the
combination (light gray otherwise), so a given source reads the same
color here as everywhere else in the paper.

Reuses upstream_venn.py's caching (node_id_venn_counts.csv,
edge_triple_venn_counts.csv, and — via load_sets — distribution's
upstream_cache/), so run upstream_venn.py / upstream_distribution.py
first, or just run this — it calls the same cached loaders.
"""
import os

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from eckg.colors import UPSTREAM_SOURCE_COLORS
from upstream_venn import (
    SOURCE_NAMES,
    _REGION_MAP,
    load_edge_triple_counts,
    load_node_id_counts,
    load_sets,
)

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

DOT_OFF    = "#dddddd"
LINE_COLOR = "#999999"
DOT_SIZE   = 34
LINE_WIDTH = 1.2
BAR_COLOR  = "#455a64"


def region_counts_from_raw(raw_counts: dict) -> dict:
    """raw_counts keyed by venn3 letter code (e.g. 'Abc') -> a dict keyed by
    bool tuple (in SOURCE_NAMES order), empty regions dropped."""
    counts = {combo: raw_counts.get(letter, 0) for combo, letter in _REGION_MAP.items()}
    return {combo: n for combo, n in counts.items() if n > 0}


def pks_region_counts() -> dict:
    """Distinct primary_knowledge_source identifiers per source combination."""
    sets = load_sets("pks", "primary_knowledge_source")
    A, B, C = (sets[s] for s in SOURCE_NAMES)
    regions = {
        (True,  False, False): A - B - C,
        (False, True,  False): B - A - C,
        (False, False, True):  C - A - B,
        (True,  True,  False): (A & B) - C,
        (True,  False, True):  (A & C) - B,
        (False, True,  True):  (B & C) - A,
        (True,  True,  True):  A & B & C,
    }
    return {combo: len(items) for combo, items in regions.items() if items}


def draw_upset_panel(ax_bar, ax_matrix, counts: dict, title: str, ylabel: str):
    combos = sorted(counts, key=lambda c: counts[c], reverse=True)
    sizes  = [counts[c] for c in combos]
    n      = len(combos)
    n_src  = len(SOURCE_NAMES)
    x      = np.arange(n)

    # ── Bar panel: count per source-combination ──
    ax_bar.bar(x, sizes, width=0.6, color=BAR_COLOR, zorder=2)
    ax_bar.set_yscale("log")
    ax_bar.set_xlim(-0.6, n - 0.4)
    ax_bar.set_ylim(top=max(sizes) * 4)   # headroom so value labels clear the title
    ax_bar.set_xticks([])
    ax_bar.set_ylabel(ylabel, fontsize=6.5, labelpad=3)
    ax_bar.set_title(title, fontsize=9, fontweight="bold", loc="left", pad=4)
    ax_bar.yaxis.set_major_formatter(
        mticker.FuncFormatter(
            lambda v, _: f"{v/1e6:.1f}M" if v >= 1e6 else
                          f"{v/1e3:.0f}k" if v >= 1e3 else f"{v:.0f}"))
    ax_bar.grid(axis="y", which="major", color="#e0e0e0", lw=0.4, zorder=0)
    ax_bar.set_axisbelow(True)
    for sp in ("top", "right"):
        ax_bar.spines[sp].set_visible(False)

    for xi, v in zip(x, sizes):
        ax_bar.text(xi, v * 1.3, f"{v:,.0f}", ha="center", va="bottom",
                    fontsize=4.3, color="#333333")

    # ── Matrix panel: which sources make up each combination ──
    for xi, combo in enumerate(combos):
        included = [j for j, present in enumerate(combo) if present]
        if len(included) > 1:
            ax_matrix.plot([xi, xi], [min(included), max(included)],
                           color=LINE_COLOR, lw=LINE_WIDTH, zorder=1)
        for j, present in enumerate(combo):
            color = UPSTREAM_SOURCE_COLORS[SOURCE_NAMES[j]] if present else DOT_OFF
            ax_matrix.scatter(xi, j, s=DOT_SIZE, color=color, zorder=2, edgecolor="none")

    ax_matrix.set_xlim(-0.6, n - 0.4)
    ax_matrix.set_ylim(-0.7, n_src - 0.3)
    ax_matrix.invert_yaxis()
    ax_matrix.set_yticks(range(n_src))
    ax_matrix.set_yticklabels(SOURCE_NAMES, fontsize=6.5)
    ax_matrix.set_xticks([])
    ax_matrix.tick_params(axis="y", length=0)
    for sp in ax_matrix.spines.values():
        sp.set_visible(False)


def main():
    plt.rcParams.update(RCPARAMS)

    print("Node IDs:")
    node_id_counts = region_counts_from_raw(load_node_id_counts())

    print("Edge triples (unique subject, predicate, object):")
    edge_triple_counts = region_counts_from_raw(load_edge_triple_counts())

    print("Primary knowledge sources:")
    pks_counts = pks_region_counts()

    fig = plt.figure(figsize=(8.5, 10))
    gs = fig.add_gridspec(3, 1, hspace=0.4, left=0.10, right=0.97, top=0.96, bottom=0.04)

    panels = [
        (node_id_counts, "Node overlap by ID across upstream sources", "Number of nodes"),
        (edge_triple_counts, "Edge overlap by unique triple across upstream sources", "Number of edges"),
        (pks_counts, "Primary knowledge source overlap across upstream sources",
         "Number of primary\nknowledge sources"),
    ]
    for i, (counts, title, ylabel) in enumerate(panels):
        gs_panel  = gs[i].subgridspec(2, 1, height_ratios=[2.4, 1.0], hspace=0.08)
        ax_bar    = fig.add_subplot(gs_panel[0])
        ax_matrix = fig.add_subplot(gs_panel[1], sharex=ax_bar)
        draw_upset_panel(ax_bar, ax_matrix, counts, title, ylabel)

    out = os.path.join(SCRIPT_DIR, "upstream_upset.pdf")
    fig.savefig(out, dpi=300)
    print(f"Saved → {out}")


if __name__ == "__main__":
    main()
