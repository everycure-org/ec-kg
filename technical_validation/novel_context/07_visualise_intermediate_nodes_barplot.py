"""
Unique EC-KG metapath diversity barplot.

Standalone: draws top-N metapaths unique to EC-KG as a horizontal bar chart
and saves it as a PDF.

Combined: creates a two-panel figure with the intermediate-node grouped barplot
from '06_visualize_intermediate_nodes copy.py' as the second panel, saved as PDF.

Usage
-----
python 07_visualise_intermediate_nodes_barplot.py

The combined figure requires
  visualizations/metapath_analysis/intermediate_node_2v3hop.parquet
to exist (produced by running '06_visualize_intermediate_nodes copy.py' first).
"""

import importlib.util
import sys
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

sys.path.append(str(Path(__file__).parent.parent / "ml_validation"))
from fig_style import (
    apply_style,
    figsize,
    style_title, clean_spines, grid_x,
    LEGEND_KWARGS,
    AXIS_LABEL_SIZE, TICK_LABEL_SIZE, ANNOTATION_SIZE,
    PAGE_WIDTH_IN, MAX_HEIGHT_IN, SAVE_DPI,
    savefig as save_fig,
)

# ── Paths ──────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
BASE  = "/Users/piotrkaniewski/work/ec-kg-analysis"
VIZ_DIR = Path(f"{BASE}/visualizations/metapath_analysis")

DATA_2HOP = _HERE.parent / "metapath_diversity.csv"

TOP_N = 15

# ── Colors ─────────────────────────────────────────────────────────────────
# Colors already claimed elsewhere in the project:
#   KGs      → EC-KG #009E73 · ROBOKOP #17BECF · RTX-KG2 #1F77B4 · PrimeKG #FF7F0E
#   Node cat → Gene/Protein #0072B2 · BiologicalProcess #E69F00 · CellularComponent #CC79A7
#
# Tol bright green (#228833) and light grey (#BBBBBB) are unused → used here.
BAR_COLOR_TRUE  = "#228833"   # biologically relevant metapaths
BAR_COLOR_FALSE = "#BBBBBB"   # not biologically relevant

# ── Data loading ────────────────────────────────────────────────────────────
IRRELEVANT = [
    "Food", "OrganismTaxon", "IndividualOrganism", "Device", "NamedThing",
    "Behavior", "Publication", "InformationContentEntity", "Cohort", "Human",
    "PopulationOfIndividualOrganisms", "Event", "Activity", "Agent",
    "Phenomenon", "Procedure",
]
IRRELEVANT_PATTERN = "|".join(IRRELEVANT)


def trim_drug_disease_endpoints(metapath: str) -> str:
    """Drop leading Drug / trailing Disease from display labels; Protein -> Gene/Protein.

    Uses ' > ' as separator: Helvetica (set by fig_style) lacks the U+2192 arrow glyph.
    """
    parts = metapath.split(" → ")
    inner = parts[1:-1] if len(parts) > 2 else parts
    return " > ".join(p.replace("Protein", "Gene/Protein") for p in inner)


def prepare_panel_data(csv_path: Path):
    """
    Read a metapath_diversity CSV, filter to EC-KG-unique metapaths,
    classify biomedical relevance, and return the top-N rows.

    Returns
    -------
    labels   : list[str]
    counts   : np.ndarray
    relevant : np.ndarray[bool]
    """
    raw = pl.read_csv(csv_path)
    filtered = (
        raw
        .filter(
            (pl.col("present_in_source_kgs") == "Unique-to-Integrated")
            & pl.col("is_unique_to_integrated")
        )
        .with_columns(
            pl.when(pl.col("metapath").str.contains(IRRELEVANT_PATTERN))
            .then(False).otherwise(True)
            .alias("biomedical_relevance")
        )
    )
    top      = filtered.sort("count", descending=True).head(TOP_N)
    labels   = [trim_drug_disease_endpoints(m) for m in top["metapath"].to_list()]
    counts   = top["count"].to_numpy()
    relevant = top["biomedical_relevance"].to_numpy()
    return labels, counts, relevant


# ── Plotting ────────────────────────────────────────────────────────────────

def draw_barh_panel(
    ax: plt.Axes,
    labels: list,
    counts: np.ndarray,
    relevant: np.ndarray,
    xlabel: str,
    title: str,
    show_legend: bool = True,
) -> None:
    """
    Draw a horizontal barplot of EC-KG-unique metapath counts on *ax*.

    Bars are coloured by biomedical relevance (green = relevant, grey = not).
    Count labels are appended to the right of each bar.
    """
    bar_colors = np.where(relevant, BAR_COLOR_TRUE, BAR_COLOR_FALSE)
    y_pos      = np.arange(len(labels))
    max_count  = counts.max() if counts.size else 1

    bars = ax.barh(
        y_pos, counts,
        color=bar_colors, alpha=0.9,
        edgecolor="black", linewidth=0.5,
        height=0.72, zorder=3,
    )

    for bar, count in zip(bars, counts):
        ax.text(
            bar.get_width() + max_count * 0.012,
            bar.get_y() + bar.get_height() / 2,
            f"{count:,}",
            va="center", ha="left",
            fontsize=ANNOTATION_SIZE, color="#333333",
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=TICK_LABEL_SIZE)
    ax.invert_yaxis()
    ax.set_xlabel(xlabel, fontsize=AXIS_LABEL_SIZE)
    ax.set_xlim(0, max_count * 1.18)
    ax.tick_params(axis="x", labelsize=TICK_LABEL_SIZE)
    style_title(ax, title)
    grid_x(ax)
    clean_spines(ax)

    if show_legend:
        legend_handles = [
            mpatches.Patch(facecolor=BAR_COLOR_TRUE,  edgecolor="black",
                           linewidth=0.5, label="Biologically relevant"),
            mpatches.Patch(facecolor=BAR_COLOR_FALSE, edgecolor="black",
                           linewidth=0.5, label="Not relevant"),
        ]
        ax.legend(handles=legend_handles, loc="lower right", **LEGEND_KWARGS)


# ── Standalone figure ───────────────────────────────────────────────────────

def plot_metapath_barplot(csv_path: Path = DATA_2HOP) -> None:
    """Save a standalone PDF of the top-N unique EC-KG metapath barplot."""
    apply_style()
    labels, counts, relevant = prepare_panel_data(csv_path)

    fig_h = min(0.35 * TOP_N + 1.0, 9.5)
    fig, ax = plt.subplots(figsize=figsize(PAGE_WIDTH_IN, fig_h))

    draw_barh_panel(
        ax, labels, counts, relevant,
        xlabel="Path count",
        title=f"Top {TOP_N} drug–disease metapaths unique to EC-KG",
        show_legend=True,
    )

    fig.tight_layout()
    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    save_fig(fig, str(VIZ_DIR / "unique_bio_metapath_distribution.pdf"))
    fig.savefig(str(VIZ_DIR / "unique_bio_metapath_distribution.png"),
                dpi=SAVE_DPI, bbox_inches="tight")
    plt.close(fig)


# ── Combined figure ─────────────────────────────────────────────────────────

def _load_intermediate_nodes_module():
    """Import plot_barplot_ax and load_figure_data from the copy script."""
    copy_path = _HERE / "06_visualize_intermediate_nodes copy.py"
    spec = importlib.util.spec_from_file_location("intermediate_nodes", copy_path)
    mod  = importlib.util.module_from_spec(spec)
    sys.modules["intermediate_nodes"] = mod
    spec.loader.exec_module(mod)
    return mod


def plot_combined_figure(csv_path: Path = DATA_2HOP) -> None:
    """
    Two-row stacked figure:
      Row 1 (full width): top-N unique EC-KG metapath horizontal barplot
      Row 2 (two panels side by side):
        Left  — key biological nodes as intermediate entities, 2-hop
        Right — key biological nodes as intermediate entities, 3-hop

    Both rows are laid out horizontally (stacked top-to-bottom).
    Requires visualizations/metapath_analysis/intermediate_node_2v3hop.parquet.
    """
    labels, counts, relevant = prepare_panel_data(csv_path)

    int_mod = _load_intermediate_nodes_module()
    stats_2hop, stats_3hop = int_mod.load_figure_data(str(VIZ_DIR))

    apply_style()
    fig = plt.figure(figsize=figsize(PAGE_WIDTH_IN, MAX_HEIGHT_IN))

    # Row 1 taller (horizontal barh needs room for TOP_N labels),
    # Row 2 shorter (vertical grouped barplot).
    gs = fig.add_gridspec(2, 2, height_ratios=[3, 2], hspace=0.45, wspace=0.35)

    ax_top = fig.add_subplot(gs[0, :])   # spans both columns
    ax_bl  = fig.add_subplot(gs[1, 0])
    ax_br  = fig.add_subplot(gs[1, 1])

    draw_barh_panel(
        ax_top, labels, counts, relevant,
        xlabel="Path count",
        title=f"Top {TOP_N} drug–disease metapaths unique to EC-KG",
        show_legend=True,
    )

    int_mod.plot_barplot_ax(
        ax_bl, stats_2hop,
        title="Key biological nodes as intermediate entities — 2-hop paths",
        legend=True,
        show_ylabel=True,
    )

    int_mod.plot_barplot_ax(
        ax_br, stats_3hop,
        title="Key biological nodes as intermediate entities — 3-hop paths",
        legend=False,
        show_ylabel=False,
    )

    fig.tight_layout()

    # Snap row-2 axes to exactly the same horizontal extent as ax_top's
    # plot area. tight_layout doesn't guarantee this when ax_top has long
    # y-tick labels that push its left edge to the right.
    fig.canvas.draw()
    top  = ax_top.get_position()
    bl   = ax_bl.get_position()
    br   = ax_br.get_position()
    gap  = br.x0 - bl.x1           # preserve the inter-panel gap
    pw   = (top.width - gap) / 2   # width of each row-2 panel

    ax_bl.set_position([top.x0,            bl.y0, pw, bl.height])
    ax_br.set_position([top.x0 + pw + gap, br.y0, pw, br.height])

    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    out_stem = VIZ_DIR / "metapath_intermediate_combined"
    save_fig(fig, str(out_stem.with_suffix(".pdf")))
    fig.savefig(str(out_stem.with_suffix(".png")), dpi=SAVE_DPI, bbox_inches="tight")
    plt.close(fig)


# ── Entry point ─────────────────────────────────────────────────────────────

def main():
    plot_metapath_barplot()
    plot_combined_figure()


if __name__ == "__main__":
    main()
