"""Generate the revised Figure 8a F1 panel with disease-bootstrap intervals."""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from eckg.colors import ML_VALIDATION_MODEL_COLORS
from eckg.style import (
    ANNOTATION_SIZE,
    AXIS_LABEL_SIZE,
    PAGE_WIDTH_IN,
    TICK_LABEL_SIZE,
    apply_style,
    clean_spines,
    figsize,
    grid_y,
    savefig,
    style_title,
)

MODELS = ("EC-KG", "PrimeKG", "ROBOKOP KG", "RTX-KG2")
PANELS = (("standard", "Standard evaluation"), ("off_label", "Off-label evaluation"))


def significance_marker(p_value: float) -> str:
    if p_value < 0.001:
        return "***"
    if p_value < 0.01:
        return "**"
    if p_value < 0.05:
        return "*"
    return "ns"


def plot_figure(estimates: pl.DataFrame, comparisons: pl.DataFrame, output: Path) -> None:
    """Plot mean-fold F1 with disease-bootstrap 95% CIs and adjusted tests."""
    apply_style()
    fig, axes = plt.subplots(1, 2, figsize=figsize(PAGE_WIDTH_IN, 3.4), sharey=True)

    for ax, (evaluation_set, title) in zip(axes, PANELS, strict=True):
        panel = estimates.filter(pl.col("evaluation_set") == evaluation_set)
        rows = {row["model"]: row for row in panel.to_dicts()}
        values = np.array([rows[model]["f1"] for model in MODELS])
        lower = np.array([rows[model]["ci_95_low"] for model in MODELS])
        upper = np.array([rows[model]["ci_95_high"] for model in MODELS])
        errors = np.vstack((values - lower, upper - values))
        x = np.arange(len(MODELS))

        bars = ax.bar(
            x,
            values,
            yerr=errors,
            capsize=3,
            color=[ML_VALIDATION_MODEL_COLORS[model] for model in MODELS],
            edgecolor="black",
            linewidth=0.5,
            error_kw={"elinewidth": 0.7, "capthick": 0.7},
            zorder=2,
        )
        test_rows = {
            row["comparator"]: row
            for row in comparisons.filter(pl.col("evaluation_set") == evaluation_set).to_dicts()
        }
        for index, (model, bar, value, high) in enumerate(zip(MODELS, bars, values, upper, strict=True)):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                max(value - 0.06, 0.02),
                f"{value:.3f}",
                ha="center",
                va="center",
                color="white" if value > 0.18 else "black",
                fontsize=ANNOTATION_SIZE + 0.5,
                fontweight="bold",
            )
            if model != "EC-KG":
                ax.text(
                    index,
                    high + 0.035,
                    significance_marker(float(test_rows[model]["holm_p_value"])),
                    ha="center",
                    va="bottom",
                    fontsize=AXIS_LABEL_SIZE,
                    fontweight="bold",
                )

        style_title(ax, title)
        ax.set_xticks(x)
        ax.set_xticklabels(MODELS, rotation=25, ha="right", fontsize=TICK_LABEL_SIZE)
        ax.set_ylim(0, 1.0)
        ax.tick_params(axis="y", labelsize=TICK_LABEL_SIZE)
        grid_y(ax)
        clean_spines(ax)

    axes[0].set_ylabel("F1 score", fontsize=AXIS_LABEL_SIZE)
    fig.text(
        0.5,
        0.015,
        "Bars: mean F1 across five CV folds; error bars: disease-bootstrap 95% CI. "
        "Asterisks: Holm-adjusted paired disease permutation test vs EC-KG "
        "(* p<0.05, ** p<0.01, *** p<0.001; six comparisons).",
        ha="center",
        va="bottom",
        fontsize=ANNOTATION_SIZE,
    )
    fig.subplots_adjust(bottom=0.28, wspace=0.22)
    output.parent.mkdir(parents=True, exist_ok=True)
    savefig(fig, str(output))
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--estimates", type=Path, required=True)
    parser.add_argument("--comparisons", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plot_figure(pl.read_csv(args.estimates), pl.read_csv(args.comparisons), args.output)


if __name__ == "__main__":
    main()
