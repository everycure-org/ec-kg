import json
import os

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from eckg.colors import CATEGORY_COLORS, _FALLBACK_COLOR, GROUPS

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CAT_JSON   = os.path.join(SCRIPT_DIR, "..", "sankey", "category_counts.json")
OUT_PDF    = os.path.join(SCRIPT_DIR, "node_distribution.pdf")



def main():
    with open(CAT_JSON) as f:
        raw = json.load(f)

    df = (pd.DataFrame(list(raw.items()), columns=["category", "count"])
          .sort_values("count", ascending=True)
          .reset_index(drop=True))
    df["label"] = df["category"].str.replace("biolink:", "", regex=False)
    df["color"] = df["category"].map(lambda c: CATEGORY_COLORS.get(c, _FALLBACK_COLOR))

    plt.rcParams.update({
        "font.family":     "Helvetica",
        "pdf.fonttype":    42,
        "ps.fonttype":     42,
        "font.size":       7,
        "axes.linewidth":  0.5,
        "xtick.major.width": 0.4,
        "xtick.major.size":  2.5,
    })

    fig, ax = plt.subplots(figsize=(6.5, 8.5))
    fig.subplots_adjust(left=0.26, right=0.97, top=0.95, bottom=0.07)

    y = np.arange(len(df))
    ax.barh(y, df["count"], height=0.72, color=df["color"], edgecolor="none")

    ax.set_xscale("log")
    ax.set_xlim(left=1)
    ax.set_ylim(-0.5, len(df) - 0.5)
    ax.set_yticks(y)
    ax.set_yticklabels(df["label"], fontsize=6.5)
    ax.set_xlabel("Number of nodes (log scale)", fontsize=8, labelpad=4)
    ax.set_title("Node type distribution", fontsize=10, fontweight="bold",
                 loc="left", pad=6)
    ax.tick_params(axis="y", length=0, pad=3)
    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(
            lambda x, _: f"{x/1e6:.1f}M" if x >= 1e6 else
                          f"{x/1e3:.0f}k"  if x >= 1e3 else f"{x:.0f}"))
    ax.grid(axis="x", which="major", color="#e0e0e0", lw=0.5, zorder=0)
    ax.grid(axis="x", which="minor", color="#f0f0f0", lw=0.3, zorder=0)
    ax.set_axisbelow(True)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)

    # Count labels on largest bars
    threshold = df["count"].max() / 1000
    for _, row in df[df["count"] >= threshold].iterrows():
        ax.text(row["count"] * 1.15, row.name,
                f"{row['count']:,.0f}", va="center", fontsize=5.0, color="#333333")

    patches = [plt.Rectangle((0,0),1,1, fc=c, ec="none", label=l) for l, c in GROUPS]
    ax.legend(handles=patches, loc="lower right", fontsize=5.5,
              frameon=True, framealpha=0.92, edgecolor="#cccccc",
              handlelength=1.0, handleheight=1.0, borderpad=0.6,
              labelspacing=0.3, title="Biolink category group", title_fontsize=5.5)

    fig.savefig(OUT_PDF, dpi=300, bbox_inches="tight")
    print(f"Saved → {OUT_PDF}")


if __name__ == "__main__":
    main()
