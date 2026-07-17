"""
Demo of eckg.style usage — NOT part of the real figure pipeline.

Two synthetic figures (random data, no BigQuery needed) showing the intended
pattern for a multi-panel figure built on the shared style guide:

  1. test_bar_panels.pdf  — 8 panels (4 rows x 2 cols), grouped bar chart
                             per panel, bars colored by UPSTREAM_SOURCE_COLORS.
                             Panels alternate log/linear y-scale — use log
                             when values span multiple orders of magnitude,
                             linear when they sit within one.
  2. test_line_panels.pdf — 3 panels (3 rows x 1 col), line chart per panel,
                             lines colored by the 8 category GROUPS colors

Run: python test_figures.py
"""
import os

import matplotlib.pyplot as plt
import numpy as np

from eckg import style
from eckg.colors import GROUPS, UPSTREAM_SOURCE_COLORS

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RNG = np.random.default_rng(7)

SOURCE_NAMES = list(UPSTREAM_SOURCE_COLORS.keys())
PANEL_CATEGORIES = ["Drug", "Disease", "Gene", "Protein", "Pathway"]

N_ROWS, N_COLS = 4, 2
# Alternates log/linear per panel — log scale for values spanning several
# orders of magnitude (the common case for real KG counts), linear for
# values that sit within a single order of magnitude and would otherwise
# read as visually flat on a log axis.
LOG_PANELS = [True, False, True, False, True, False, True, False]


# ── Figure 1: 8-panel grouped bar chart ─────────────────────────────────────

def build_bar_panels() -> plt.Figure:
    style.apply_style()

    fig, axes = plt.subplots(
        N_ROWS, N_COLS,
        figsize=style.grid_figsize(N_ROWS, N_COLS),
    )
    fig.subplots_adjust(left=0.08, right=0.98, top=0.91, bottom=0.06,
                         hspace=0.85, wspace=0.28)

    n_cat = len(PANEL_CATEGORIES)
    n_src = len(SOURCE_NAMES)
    x = np.arange(n_cat)
    bar_w = 0.8 / n_src

    for panel_idx, ax in enumerate(axes.flat):
        use_log = LOG_PANELS[panel_idx]
        if use_log:
            # Wide, log-distributed counts — mirrors real KG data spanning
            # several orders of magnitude.
            counts = {
                src: (10 ** RNG.uniform(2, 6, size=n_cat)).astype(int)
                for src in SOURCE_NAMES
            }
        else:
            # Narrow-range counts — linear scale reads better within a
            # single order of magnitude.
            counts = {
                src: RNG.uniform(10, 100, size=n_cat).astype(int)
                for src in SOURCE_NAMES
            }

        for si, src in enumerate(SOURCE_NAMES):
            offset = (si - (n_src - 1) / 2) * bar_w
            ax.bar(x + offset, counts[src], width=bar_w * 0.9,
                   color=UPSTREAM_SOURCE_COLORS[src], edgecolor="none", zorder=2)

        if use_log:
            ax.set_yscale("log")
            ax.yaxis.set_major_formatter(style.count_formatter())
        ax.set_xticks(x)
        ax.set_xticklabels(PANEL_CATEGORIES, fontsize=style.TICK_LABEL_SIZE, rotation=30, ha="right")
        ax.tick_params(axis="y", labelsize=style.TICK_LABEL_SIZE)
        scale_note = "log scale" if use_log else "linear scale"
        style.style_title(ax, f"Panel {panel_idx + 1} ({scale_note})", fontsize=style.AXIS_LABEL_SIZE)
        style.grid_y(ax)
        style.clean_spines(ax)

    handles = [
        plt.Rectangle((0, 0), 1, 1, fc=UPSTREAM_SOURCE_COLORS[s], ec="none", label=s)
        for s in SOURCE_NAMES
    ]
    fig.legend(handles=handles, loc="upper center", ncol=n_src,
               bbox_to_anchor=(0.5, 0.975), **{**style.LEGEND_KWARGS, "frameon": False})

    return fig


# ── Figure 2: 3-panel line chart, group colors ──────────────────────────────

def build_line_panels() -> plt.Figure:
    style.apply_style()

    fig, axes = plt.subplots(
        3, 1,
        figsize=style.grid_figsize(3, 1),
    )
    fig.subplots_adjust(left=0.16, right=0.96, top=0.96, bottom=0.07, hspace=0.5)

    x = np.arange(1, 11)  # e.g. "hops" or some ordinal axis

    for panel_idx, ax in enumerate(axes.flat):
        for label, color in GROUPS:
            # Synthetic monotonic-ish trend with noise, one line per group
            base = RNG.uniform(0.3, 0.9)
            y = base * np.log1p(x) / np.log1p(x.max()) + RNG.normal(0, 0.03, size=x.size)
            ax.plot(x, y, color=color, lw=1.0, marker="o", ms=2.0, label=label, zorder=2)

        ax.set_xlim(x.min(), x.max())
        ax.set_ylim(0, 1)
        ax.tick_params(axis="both", labelsize=style.TICK_LABEL_SIZE)
        ax.set_xlabel("k", fontsize=style.AXIS_LABEL_SIZE, labelpad=3)
        style.style_title(ax, f"Panel {panel_idx + 1}", fontsize=style.AXIS_LABEL_SIZE)
        style.grid_y(ax)
        style.clean_spines(ax)

    axes.flat[0].legend(
        loc="lower right", ncol=2,
        **{**style.LEGEND_KWARGS, "fontsize": style.ANNOTATION_SIZE + 0.5},
    )

    return fig


def main():
    fig1 = build_bar_panels()
    style.savefig(fig1, os.path.join(SCRIPT_DIR, "test_bar_panels.pdf"))

    fig2 = build_line_panels()
    style.savefig(fig2, os.path.join(SCRIPT_DIR, "test_line_panels.pdf"))


if __name__ == "__main__":
    main()
