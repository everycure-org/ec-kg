import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

sns.set_theme(style="whitegrid")
plt.rcParams.update(
    {
        "font.size": 11,
        "axes.labelsize": 12,
        "axes.titlesize": 13,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "figure.titlesize": 14,
    }
)

# Load Data

# --- Data Configuration ---
networks = ["RTX-KG2", "ROBOKOP", "PrimeKG"]
colors = ["#1f77b4", "#17becf", "#ff7f0e"]  # Deep Blue, Cyan, Orange

# 1. Total Scale Metrics
nodes = [4109861, 4648640, 132090]
edges = [44510560, 25516629, 9372210]

# 2. Pipeline Metrics
normalized = [3130573, 4641236, 124857]
merged = [2119056, 2111717, 124857]

# 3. Unique Domain Contributions (%)
unique_rtx = [55.88, 58.21, 27.52]
unique_robokop = [14.12, 6.14, 17.59]
unique_primekg = [0.03, 0.01, 0.03]

x = np.arange(len(networks))
width = 0.35

# Convert subplot 1 to % of total across all KGs
total_nodes = sum(nodes)
total_edges = sum(edges)
nodes_pct = [v / total_nodes * 100 for v in nodes]
edges_pct = [v / total_edges * 100 for v in edges]

# Convert subplot 2 to % of original (raw) node count per KG
normalized_pct = [n / r * 100 for n, r in zip(normalized, nodes)]
merged_pct = [m / r * 100 for m, r in zip(merged, nodes)]

def fmt_large(v):
    """Human-readable label for raw counts."""
    if v >= 1_000_000:
        return f"{v/1e6:.2f}M"
    if v >= 1_000:
        return f"{v/1e3:.0f}K"
    return str(v)

def add_bar_labels(ax, bars, raw_values, fmt_fn, offset_frac=0.01):
    """Draw value labels centred above each bar."""
    ylim_top = ax.get_ylim()[1]
    offset = ylim_top * offset_frac
    for bar, raw in zip(bars, raw_values):
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            h + offset,
            fmt_fn(raw),
            ha="center", va="bottom",
            fontsize=9, fontweight="bold",
        )

# Initialize 3-panel subplot layout
fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))

# Helper: Add bold lowercase panel label in upper left
def add_panel_label(ax, label):
    ax.annotate(
        f"{label}",
        xy=(-0.08, 1.12),
        xycoords="axes fraction",
        ha="left", va="top",
        fontsize=15, fontweight='bold',
        annotation_clip=False
    )

# ==============================================================================
# SUBPLOT 1: Node and Edge Shares (% of total across KGs)
# ==============================================================================
b1a = axes[0].bar(x - width / 2, nodes_pct, width, label="Nodes", color=colors, alpha=0.9, edgecolor="black")
b1b = axes[0].bar(x + width / 2, edges_pct, width, label="Edges", color=colors, alpha=0.5, edgecolor="black", hatch="//")
axes[0].set_title("Network Scale Metrics", fontweight="bold")
axes[0].set_xticks(x)
axes[0].set_xticklabels(networks)
axes[0].set_ylabel("Total share (%)", fontweight="bold")
axes[0].yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
axes[0].set_ylim(0, axes[0].get_ylim()[1] * 1.15)
# Manual legend: solid = Nodes, hatched = Edges
from matplotlib.patches import Patch
axes[0].legend(handles=[Patch(facecolor="grey", alpha=0.9, label="Nodes"),
                         Patch(facecolor="grey", alpha=0.5, label="Edges", hatch="//")], frameon=True)
add_bar_labels(axes[0], b1a, nodes_pct, lambda v: f"{v:.1f}%")
add_bar_labels(axes[0], b1b, edges_pct, lambda v: f"{v:.1f}%")
add_panel_label(axes[0], "a")

# ==============================================================================
# SUBPLOT 2: Normalization and Merge Retention (% of raw node count)
# ==============================================================================
b2a = axes[1].bar(
    x - width / 2, normalized_pct, width, label="Normalized", color=colors, alpha=0.9, edgecolor="black"
)
b2b = axes[1].bar(x + width / 2, merged_pct, width, label="Merged", color=colors, alpha=0.5, edgecolor="black", hatch="//")
axes[1].set_title("Normalization Metrics", fontweight="bold")
axes[1].set_xticks(x)
axes[1].set_xticklabels(networks)
axes[1].set_ylabel("Normalization rate (%)", fontweight="bold")
axes[1].yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
axes[1].set_ylim(0, axes[1].get_ylim()[1])
axes[1].legend(handles=[Patch(facecolor="grey", alpha=0.9, label="Normalised"),
                          Patch(facecolor="grey", alpha=0.5, hatch="//", label="Merged")], frameon=True)
add_bar_labels(axes[1], b2a, normalized_pct, lambda v: f"{v:.1f}%")
add_bar_labels(axes[1], b2b, merged_pct,     lambda v: f"{v:.1f}%")
add_panel_label(axes[1], "b")

# ==============================================================================
# SUBPLOT 3: Domain-Specific Unique Content Footprint (already %)
# ==============================================================================
domain_width = 0.25
domains_x = np.arange(3)

b3a = axes[2].bar(
    domains_x - domain_width, unique_rtx, domain_width,
    label="RTX-KG2", color=colors[0], edgecolor="black", alpha=0.9,
)
b3b = axes[2].bar(
    domains_x, unique_robokop, domain_width,
    label="ROBOKOP", color=colors[1], alpha=0.9, edgecolor="black",
)
b3c = axes[2].bar(
    domains_x + domain_width, unique_primekg, domain_width,
    label="PrimeKG", color=colors[2], edgecolor="black", alpha=0.9,
)
axes[2].set_title("Unique Domain Contributions", fontweight="bold")
axes[2].set_xticks(domains_x)
axes[2].set_xticklabels(["Unique Drugs", "Unique Diseases", "Unique Proteins"])
axes[2].set_ylabel("Contribution Ratio (%)", fontweight="bold")
axes[2].yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
axes[2].set_ylim(0, axes[2].get_ylim()[1] * 1.15)
axes[2].legend(frameon=True)
add_bar_labels(axes[2], b3a, unique_rtx,     lambda v: f"{v:.1f}%")
add_bar_labels(axes[2], b3b, unique_robokop, lambda v: f"{v:.1f}%")
add_bar_labels(axes[2], b3c, unique_primekg, lambda v: f"{v:.1f}%")
add_panel_label(axes[2], "c")

# Set suptitle in bold (optional/for overall figure, not present originally)
# Uncomment the next line if you want an overall title:
# fig.suptitle("Knowledge Graph Metrics Overview", fontsize=16, fontweight="bold", y=1.08)

# Tight layout optimization for publication figures
plt.tight_layout()

# Save options standard for journal submission formats (300 DPI TIF or PDF)
plt.savefig("knowledge_graph_metrics.pdf", bbox_inches='tight', dpi=300)
plt.show()