# Generates the top-N unique-to-EC-KG drug-disease metapaths figure, matching paper_vis.ipynb.

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from matplotlib.patches import Patch

plt.rcParams.update({
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "font.size": 10,
    "font.family": "sans-serif",
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.labelweight": "bold",
    "xtick.labelsize": 9,
    "ytick.labelsize": 8.5,
})

BAR_COLOR_TRUE = "#386cb0"
BAR_COLOR_FALSE = "#e6842a"
TOP_N = 15

IRRELEVANT_ENTITIES = [
    "Food", "OrganismTaxon", "IndividualOrganism", "Device", "NamedThing",
    "Behavior", "Publication", "InformationContentEntity", "Cohort", "Human",
    "PopulationOfIndividualOrganisms", "Event", "Activity", "Behavior",
    "Agent", "Phenomenon", "Procedure",
]


def trim_drug_disease_endpoints(metapath: str) -> str:
    """Drop leading Drug and trailing Disease from display labels; rename Protein to Gene/Protein."""
    parts = metapath.split(" → ")
    inner = parts[1:-1] if len(parts) > 2 else parts
    inner = [p.replace("Protein", "Gene/Protein") for p in inner]
    return " → ".join(inner)


def main():
    parser = argparse.ArgumentParser(
        description="Visualize top unique-to-EC-KG drug-disease metapaths."
    )
    parser.add_argument("--input", type=str, default=None, help="Path to metapath_diversity.csv")
    parser.add_argument(
        "--output_stem",
        type=str,
        default=None,
        help="Prefix for output figure files (default: unique_bio_metapath_distribution beside the input CSV)",
    )
    args = parser.parse_args()

    if args.input is None:
        print("Error: --input is required (path to metapath_diversity.csv)", file=sys.stderr)
        sys.exit(1)
    input_csv = Path(args.input)
    if not input_csv.exists():
        print(f"Error: input file {input_csv} does not exist.", file=sys.stderr)
        sys.exit(1)

    output_stem = Path(args.output_stem) if args.output_stem else input_csv.parent / "unique_bio_metapath_distribution"

    metapaths = pl.read_csv(str(input_csv))

    irrelevant_pattern = "|".join(IRRELEVANT_ENTITIES)
    filtered = (
        metapaths
        .filter(
            (pl.col("present_in_source_kgs") == "Unique-to-Integrated")
            & pl.col("is_unique_to_integrated")
        )
        .with_columns(
            pl.when(pl.col("metapath").str.contains(irrelevant_pattern))
            .then(False)
            .otherwise(True)
            .alias("biomedical_relevance")
        )
        .sort("count", descending=True)
        .head(TOP_N)
    )

    counts = filtered["count"].to_numpy()
    metapath_labels = [trim_drug_disease_endpoints(m) for m in filtered["metapath"].to_list()]
    biomedical_relevance = filtered["biomedical_relevance"].to_numpy()
    bar_colors = np.where(biomedical_relevance, BAR_COLOR_TRUE, BAR_COLOR_FALSE)

    fig_h = 0.40 * TOP_N + 1.2
    fig, ax = plt.subplots(figsize=(7.2, fig_h))
    fig.subplots_adjust(left=0.32, right=0.96, top=0.92, bottom=0.10)

    ax.set_title(
        f"Top {TOP_N} drug-disease metapaths unique to EC-KG\n",
        loc="left",
        pad=4,
        fontsize=10,
        fontweight="bold",
    )

    y_pos = np.arange(len(metapath_labels))
    bars = ax.barh(
        y_pos,
        counts,
        color=bar_colors,
        alpha=0.85,
        edgecolor="black",
        linewidth=0.6,
        height=0.72,
        zorder=3,
    )

    for bar, count in zip(bars, counts):
        ax.text(
            bar.get_width() + (counts.max() * 0.01 if counts.size > 0 else 0),
            bar.get_y() + bar.get_height() / 2,
            f"{count:,}  ",
            va="center",
            ha="left",
            fontsize=8.5,
            fontweight="bold",
            color="#333333",
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(metapath_labels)
    ax.invert_yaxis()
    ax.set_xlabel("3-hop path count")
    ax.set_xlim(0, counts.max() * 1.14 if counts.size > 0 else 1)

    ax.xaxis.grid(True, linestyle="-", linewidth=0.5, color="#dddddd", zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    legend_handles = [
        Patch(facecolor=BAR_COLOR_TRUE, edgecolor="black", label="TRUE"),
        Patch(facecolor=BAR_COLOR_FALSE, edgecolor="black", label="FALSE"),
    ]
    ax.legend(handles=legend_handles, loc="lower right", fontsize=8, frameon=True, title="Biomedical Relevance")

    for ext in ("png", "svg"):
        fig.savefig(f"{output_stem}.{ext}", dpi=300, bbox_inches="tight", pad_inches=0.04, facecolor="white")
    print(f"✓ Figure saved to {output_stem}.png and .svg")
    plt.close(fig)


if __name__ == "__main__":
    main()
