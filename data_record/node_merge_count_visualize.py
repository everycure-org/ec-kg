import sys
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

sys.path.append(str(Path(__file__).parent.parent / "technical_validation" / "ml_validation"))
from fig_style import (
    apply_style,
    figsize,
    style_title, clean_spines, grid_y,
    LEGEND_KWARGS,
    AXIS_LABEL_SIZE, TICK_LABEL_SIZE, ANNOTATION_SIZE,
    PAGE_WIDTH_IN,
    savefig as save_fig,
)

apply_style()

# ── Colors — consistent with KG_COLORS in analyse_output.py ─────────────────
NETWORK_COLORS = {
    "RTX-KG2": "#1F77B4",
    "ROBOKOP":  "#17BECF",
    "PrimeKG":  "#FF7F0E",
}

# ── Data ─────────────────────────────────────────────────────────────────────
networks = ["RTX-KG2", "ROBOKOP", "PrimeKG"]
colors   = [NETWORK_COLORS[n] for n in networks]

nodes = [4109861, 4648640, 132090]
edges = [44510560, 25516629, 9372210]

normalized = [3130573, 4641236, 124857]
merged     = [2119056, 2111717, 124857]

unique_rtx     = [55.88, 58.21, 27.52]
unique_robokop = [14.12,  6.14, 17.59]
unique_primekg = [ 0.03,  0.01,  0.03]

x     = np.arange(len(networks))
width = 0.35

total_nodes   = sum(nodes)
total_edges   = sum(edges)
nodes_pct     = [v / total_nodes * 100 for v in nodes]
edges_pct     = [v / total_edges * 100 for v in edges]
normalized_pct = [n / r * 100 for n, r in zip(normalized, nodes)]
merged_pct     = [m / r * 100 for m, r in zip(merged,     nodes)]


# ── Helpers ──────────────────────────────────────────────────────────────────
def add_bar_labels(
    ax, bars, values, fmt_fn,
    offset_frac: float = 0.015,
    rotation: int = 0,
    min_height: float = 0.0,
) -> None:
    """
    Draw value labels centred above each bar.

    - Bars shorter than `min_height` (axis units) are skipped — avoids
      clutter near zero for tiny values.
    - When a label would overflow the top of the y-axis it is placed inside
      the bar (top-anchored, white text) so the axis scale stays at 100%.
    - `rotation=90` is useful for narrow panels with many bars.
    """
    ylim_top = ax.get_ylim()[1]
    offset   = ylim_top * offset_frac
    for bar, v in zip(bars, values):
        h = bar.get_height()
        if h < min_height:
            continue
        if h + offset > ylim_top:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h - offset,
                fmt_fn(v),
                ha="center", va="top",
                fontsize=ANNOTATION_SIZE, fontweight="bold",
                color="white", rotation=rotation,
            )
        else:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + offset,
                fmt_fn(v),
                ha="center", va="bottom",
                fontsize=ANNOTATION_SIZE, fontweight="bold",
                rotation=rotation,
            )


# ── Figure ───────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=figsize(PAGE_WIDTH_IN, 3.5))

# Shared label style applied to every add_bar_labels call
_LBL = dict(rotation=90, min_height=0.5)

# ── Subplot 1: Network Scale Metrics ─────────────────────────────────────────
ax = axes[0]
b1a = ax.bar(x - width / 2, nodes_pct, width,
             color=colors, alpha=0.9, edgecolor="black", linewidth=0.5, zorder=2)
b1b = ax.bar(x + width / 2, edges_pct, width,
             color=colors, alpha=0.7, edgecolor="black", linewidth=0.5,
             hatch="////", zorder=2)

ax.set_ylim(0, 100)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax.set_xticks(x)
ax.set_xticklabels(networks, fontsize=TICK_LABEL_SIZE, rotation=30, ha="right")
ax.set_ylabel("Total share (%)", fontsize=AXIS_LABEL_SIZE)
style_title(ax, "Network Scale Metrics")
grid_y(ax)
clean_spines(ax)
ax.legend(
    handles=[
        mpatches.Patch(facecolor="grey", alpha=0.9, edgecolor="black",
                       linewidth=0.5, label="Nodes"),
        mpatches.Patch(facecolor="grey", alpha=0.7, edgecolor="black",
                       linewidth=0.5, hatch="////", label="Edges"),
    ],
    **LEGEND_KWARGS,
)
add_bar_labels(ax, b1a, nodes_pct, lambda v: f"{v:.1f}%", **_LBL)
add_bar_labels(ax, b1b, edges_pct, lambda v: f"{v:.1f}%", **_LBL)

# ── Subplot 2: Normalization Metrics ─────────────────────────────────────────
ax = axes[1]
b2a = ax.bar(x - width / 2, normalized_pct, width,
             color=colors, alpha=0.9, edgecolor="black", linewidth=0.5, zorder=2)
b2b = ax.bar(x + width / 2, merged_pct, width,
             color=colors, alpha=0.7, edgecolor="black", linewidth=0.5,
             hatch="////", zorder=2)

ax.set_ylim(0, 100)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax.set_xticks(x)
ax.set_xticklabels(networks, fontsize=TICK_LABEL_SIZE, rotation=30, ha="right")
ax.set_ylabel("Normalization rate (%)", fontsize=AXIS_LABEL_SIZE)
style_title(ax, "Normalization Metrics")
grid_y(ax)
clean_spines(ax)
ax.legend(
    handles=[
        mpatches.Patch(facecolor="grey", alpha=0.9, edgecolor="black",
                       linewidth=0.5, label="Normalised"),
        mpatches.Patch(facecolor="grey", alpha=0.7, edgecolor="black",
                       linewidth=0.5, hatch="////", label="Merged"),
    ],
    bbox_to_anchor=(0.5, -0.18), loc="upper center", ncol=2,
    **LEGEND_KWARGS,
)
add_bar_labels(ax, b2a, normalized_pct, lambda v: f"{v:.1f}%", **_LBL)
add_bar_labels(ax, b2b, merged_pct,     lambda v: f"{v:.1f}%", **_LBL)

# ── Subplot 3: Unique Domain Contributions ───────────────────────────────────
ax      = axes[2]
dw      = 0.25
dx      = np.arange(3)

b3a = ax.bar(dx - dw, unique_rtx,     dw, label="RTX-KG2",
             color=NETWORK_COLORS["RTX-KG2"], alpha=0.9,
             edgecolor="black", linewidth=0.5, zorder=2)
b3b = ax.bar(dx,      unique_robokop, dw, label="ROBOKOP",
             color=NETWORK_COLORS["ROBOKOP"],  alpha=0.9,
             edgecolor="black", linewidth=0.5, zorder=2)
b3c = ax.bar(dx + dw, unique_primekg, dw, label="PrimeKG",
             color=NETWORK_COLORS["PrimeKG"],  alpha=0.9,
             edgecolor="black", linewidth=0.5, zorder=2)

ax.set_ylim(0, 100)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax.set_xticks(dx)
ax.set_xticklabels(["Unique Drugs", "Unique Diseases", "Unique Proteins"],
                   fontsize=TICK_LABEL_SIZE, rotation=30, ha="right")
ax.set_ylabel("Contribution ratio (%)", fontsize=AXIS_LABEL_SIZE)
style_title(ax, "Unique Domain Contributions")
grid_y(ax)
clean_spines(ax)
ax.legend(**LEGEND_KWARGS)
add_bar_labels(ax, b3a, unique_rtx,     lambda v: f"{v:.1f}%", **_LBL)
add_bar_labels(ax, b3b, unique_robokop, lambda v: f"{v:.1f}%", **_LBL)
add_bar_labels(ax, b3c, unique_primekg, lambda v: f"{v:.1f}%", **_LBL)

# ── Save ─────────────────────────────────────────────────────────────────────
# rect bottom=0.1 reserves space below subplot 2's external legend
fig.tight_layout(rect=[0, 0.1, 1, 1])
save_fig(fig, "knowledge_graph_metrics.pdf")
plt.show()
