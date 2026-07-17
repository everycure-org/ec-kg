import math
import os

import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
from google.cloud import bigquery
from matplotlib.path import Path

from eckg.colors import CATEGORY_COLORS, _FALLBACK_COLOR, GROUPS, NODE_TO_GROUP
from eckg.grouping import group_sorted

GROUP_COLOR = dict(GROUPS)

# ── Cache files ────────────────────────────────────────────────────────────────
_DIR      = os.path.dirname(os.path.abspath(__file__))
LEFT_CSV  = os.path.join(_DIR, "disease_sankey_left.csv")
RIGHT_CSV = os.path.join(_DIR, "disease_sankey_right.csv")

# ── Figure dimensions (inches) — landscape half-page panel ────────────────────
FIG_W  = 3.5
FIG_H  = 3.0

M_LEFT   = 0.55
M_RIGHT  = 0.55
M_TOP    = 0.30
M_BOTTOM = 0.15
AVAIL_H  = FIG_H - M_TOP - M_BOTTOM   # 2.55

# All three bars the same width
SRC_BAR_W    = 0.06
CENTER_BAR_W = 0.06
TGT_BAR_W    = 0.06

SRC_X = M_LEFT
TGT_X = FIG_W - M_RIGHT - TGT_BAR_W

_inner_w = TGT_X - (SRC_X + SRC_BAR_W)
CENTER_X = SRC_X + SRC_BAR_W + (_inner_w - CENTER_BAR_W) / 2

# Center bar: half the figure height, centred vertically
CENTER_H   = FIG_H / 2
CENTER_TOP = FIG_H / 2 + CENTER_H / 2   # = 3/4 of FIG_H

GAP_SRC_TGT  = 0.010
MIN_RIBBON_H = 0.002

FONT_OUTER  = 2.0
FONT_CENTER = 5.0

CENTER_COLOR = "#c62828"   # Disease / Phenotype red

EDGE_ALPHA_MIN = 0.06
EDGE_ALPHA_MAX = 0.35
EDGE_LIGHTEN   = 0.55


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_cat_color(category):
    return CATEGORY_COLORS.get(category, _FALLBACK_COLOR)


def lighten(rgba, amount=EDGE_LIGHTEN):
    r, g, b, a = mcolors.to_rgba(rgba)
    return (r + (1-r)*amount, g + (1-g)*amount, b + (1-b)*amount, a)


def darken(rgba, amount=0.30):
    r, g, b, a = mcolors.to_rgba(rgba)
    f = 1 - amount
    return (r*f, g*f, b*f, a)


def flow_alpha(flow, log_min, log_max):
    if log_max <= log_min:
        return EDGE_ALPHA_MIN
    t = (math.log1p(flow) - log_min) / (log_max - log_min)
    return EDGE_ALPHA_MIN + t * (EDGE_ALPHA_MAX - EDGE_ALPHA_MIN)


def clean(s):
    return s.replace("biolink:", "")


# ── Data loading ───────────────────────────────────────────────────────────────

def load_data():
    if os.path.exists(LEFT_CSV) and os.path.exists(RIGHT_CSV):
        print("Loading cached data...")
        left_df  = pd.read_csv(LEFT_CSV)
        right_df = pd.read_csv(RIGHT_CSV)
        return left_df, right_df

    print("Fetching from BigQuery...")
    client = bigquery.Client(project="mtrx-hub-dev-3of")

    combined = client.query("""
        WITH diseases AS (
            SELECT id FROM `mtrx-hub-dev-3of.release_v0_15_19.disease_list_nodes_normalized`
        )
        SELECT 'left'        AS side,
               n.category    AS node_type,
               COUNT(*)      AS edge_count
        FROM `mtrx-hub-dev-3of.release_v0_15_19.edges_unified` e
        JOIN diseases                                                       ON e.object  = diseases.id
        JOIN `mtrx-hub-dev-3of.release_v0_15_19.nodes_unified` n           ON e.subject = n.id
        GROUP BY node_type

        UNION ALL

        SELECT 'right'       AS side,
               n.category    AS node_type,
               COUNT(*)      AS edge_count
        FROM `mtrx-hub-dev-3of.release_v0_15_19.edges_unified` e
        JOIN diseases                                                       ON e.subject = diseases.id
        JOIN `mtrx-hub-dev-3of.release_v0_15_19.nodes_unified` n           ON e.object  = n.id
        GROUP BY node_type
    """).to_dataframe()

    left_df  = (combined[combined["side"] == "left"]
                .rename(columns={"node_type": "source_type"})
                [["source_type", "edge_count"]]
                .reset_index(drop=True))
    right_df = (combined[combined["side"] == "right"]
                .rename(columns={"node_type": "target_type"})
                [["target_type", "edge_count"]]
                .reset_index(drop=True))

    left_df.to_csv(LEFT_CSV,   index=False)
    right_df.to_csv(RIGHT_CSV, index=False)

    print(f"  {left_df['edge_count'].sum():,.0f} left edges, "
          f"{right_df['edge_count'].sum():,.0f} right edges")
    return left_df, right_df


# ── Layout helpers ─────────────────────────────────────────────────────────────

def compute_heights(flows, avail_h, gap, min_h):
    n = len(flows)
    if n == 0:
        return []
    total_gap   = gap * max(n - 1, 0)
    avail_nodes = avail_h - total_gap
    total_flow  = sum(flows)
    heights     = [f / total_flow * avail_nodes for f in flows]

    for _ in range(200):
        small = [i for i, h in enumerate(heights) if h < min_h - 1e-9]
        if not small:
            break
        large = [i for i in range(n) if i not in set(small)]
        for i in small:
            heights[i] = min_h
        remaining = avail_nodes - len(small) * min_h
        if not large or remaining <= 0:
            heights = [avail_nodes / n] * n
            break
        large_sum = sum(heights[i] for i in large)
        for i in large:
            heights[i] = heights[i] / large_sum * remaining

    return heights


def node_tops(heights, gap):
    tops = []
    y = M_BOTTOM + AVAIL_H
    for h in heights:
        tops.append(y)
        y -= h + gap
    return tops


def draw_ribbon(ax, x0, y0t, y0b, x1, y1t, y1b, color, alpha):
    def enforce_min(top, bot):
        h = top - bot
        if h < MIN_RIBBON_H:
            mid = (top + bot) / 2
            return mid + MIN_RIBBON_H/2, mid - MIN_RIBBON_H/2
        return top, bot

    y0t, y0b = enforce_min(y0t, y0b)
    y1t, y1b = enforce_min(y1t, y1b)
    xm = (x0 + x1) / 2
    verts = [
        (x0, y0t), (xm, y0t), (xm, y1t), (x1, y1t),
        (x1, y1b), (xm, y1b), (xm, y0b), (x0, y0b),
        (x0, y0t),
    ]
    codes = [
        Path.MOVETO,
        Path.CURVE4, Path.CURVE4, Path.CURVE4,
        Path.LINETO,
        Path.CURVE4, Path.CURVE4, Path.CURVE4,
        Path.CLOSEPOLY,
    ]
    ax.add_patch(mpatches.PathPatch(
        Path(verts, codes),
        facecolor=color, edgecolor="none", alpha=alpha, zorder=1,
    ))


# ── Main sankey builder ────────────────────────────────────────────────────────

def build_sankey(left_df, right_df):
    src_flow = left_df.set_index("source_type")["edge_count"]
    tgt_flow = right_df.set_index("target_type")["edge_count"]

    # Group categories that share a biolink category group (see
    # eckg.colors.NODE_TO_GROUP) adjacent to each other, in canonical group order.
    sources = group_sorted(src_flow.index.tolist(), src_flow.to_dict())
    targets = group_sorted(tgt_flow.index.tolist(), tgt_flow.to_dict())

    total_left  = int(src_flow.sum())
    total_right = int(tgt_flow.sum())

    print(f"  {len(sources)} source types | EC Disease List | {len(targets)} target types")

    cat_color = {c: get_cat_color(c) for c in set(sources) | set(targets)}

    all_flows = left_df["edge_count"].tolist() + right_df["edge_count"].tolist()
    log_min   = math.log1p(min(all_flows))
    log_max   = math.log1p(max(all_flows))

    min_h_st    = 0.010
    src_heights = compute_heights(src_flow[sources].tolist(), AVAIL_H, GAP_SRC_TGT, min_h_st)
    tgt_heights = compute_heights(tgt_flow[targets].tolist(), AVAIL_H, GAP_SRC_TGT, min_h_st)

    src_tops = node_tops(src_heights, GAP_SRC_TGT)
    tgt_tops = node_tops(tgt_heights, GAP_SRC_TGT)

    center_top = CENTER_TOP
    center_h   = CENTER_H

    SI = {s: {"top": t, "h": h, "flow": int(src_flow[s])}
          for s, t, h in zip(sources, src_tops, src_heights)}
    TI = {t_: {"top": t, "h": h, "flow": int(tgt_flow[t_])}
          for t_, t, h in zip(targets, tgt_tops, tgt_heights)}

    src_out    = {s: SI[s]["top"] for s in sources}
    center_in  = center_top
    center_out = center_top
    tgt_in     = {t_: TI[t_]["top"] for t_ in targets}

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    ax.set_xlim(0, FIG_W)
    ax.set_ylim(0, FIG_H)
    ax.axis("off")

    # Left ribbons: source_type → center block
    for s in sources:
        cnt  = SI[s]["flow"]
        rh_s = SI[s]["h"]
        rh_c = (cnt / total_left) * center_h
        y0t, y0b = src_out[s], src_out[s] - rh_s
        y1t, y1b = center_in, center_in - rh_c
        center_in -= rh_c
        draw_ribbon(ax, SRC_X + SRC_BAR_W, y0t, y0b,
                        CENTER_X,          y1t, y1b,
                    lighten(cat_color[s]), flow_alpha(cnt, log_min, log_max))

    # Right ribbons: center block → target_type
    for t_ in targets:
        cnt  = TI[t_]["flow"]
        rh_c = (cnt / total_right) * center_h
        rh_t = TI[t_]["h"]
        y0t, y0b = center_out, center_out - rh_c
        center_out -= rh_c
        y1t, y1b = tgt_in[t_], tgt_in[t_] - rh_t
        tgt_in[t_] -= rh_t
        draw_ribbon(ax, CENTER_X + CENTER_BAR_W, y0t, y0b,
                        TGT_X,                   y1t, y1b,
                    lighten(cat_color[t_]), flow_alpha(cnt, log_min, log_max))

    # Source bars
    for s, d in SI.items():
        fc = cat_color[s]
        ax.add_patch(mpatches.Rectangle(
            (SRC_X, d["top"] - d["h"]), SRC_BAR_W, d["h"],
            facecolor=fc, edgecolor=darken(fc), linewidth=0.3, zorder=2,
        ))

    # Center block
    ax.add_patch(mpatches.Rectangle(
        (CENTER_X, center_top - center_h), CENTER_BAR_W, center_h,
        facecolor=CENTER_COLOR, edgecolor=darken(CENTER_COLOR), linewidth=0.5, zorder=2,
    ))
    ax.text(
        CENTER_X + CENTER_BAR_W / 2, center_top + 0.06,
        "EC Disease List",
        ha="center", va="bottom",
        fontsize=FONT_CENTER, fontfamily="Helvetica",
        color=CENTER_COLOR, fontweight="bold", zorder=3,
    )

    # Target bars
    for t_, d in TI.items():
        fc = cat_color[t_]
        ax.add_patch(mpatches.Rectangle(
            (TGT_X, d["top"] - d["h"]), TGT_BAR_W, d["h"],
            facecolor=fc, edgecolor=darken(fc), linewidth=0.3, zorder=2,
        ))

    # Outer labels
    label_gap = 0.04
    for s, d in SI.items():
        ax.text(SRC_X - label_gap, d["top"] - d["h"] / 2,
                clean(s), ha="right", va="center",
                fontsize=FONT_OUTER, fontfamily="Helvetica", color="black")
    for t_, d in TI.items():
        ax.text(TGT_X + TGT_BAR_W + label_gap, d["top"] - d["h"] / 2,
                clean(t_), ha="left", va="center",
                fontsize=FONT_OUTER, fontfamily="Helvetica", color="black")

    return fig


def build_grouped_sankey(left_df, right_df):
    """Same as build_sankey but node types are collapsed into the 8 biolink groups."""

    def to_group(df, col):
        df = df.copy()
        df["group"] = df[col].map(NODE_TO_GROUP).fillna("Miscellaneous")
        return df.groupby("group")["edge_count"].sum()

    src_flow = to_group(left_df,  "source_type")
    tgt_flow = to_group(right_df, "target_type")

    group_names = [g for g, _ in GROUPS]
    sources = [g for g in group_names if g in src_flow.index]
    targets = [g for g in group_names if g in tgt_flow.index]

    total_left  = int(src_flow.sum())
    total_right = int(tgt_flow.sum())

    print(f"  {len(sources)} source groups | EC Disease List | {len(targets)} target groups")

    all_flows = src_flow.tolist() + tgt_flow.tolist()
    log_min   = math.log1p(min(all_flows))
    log_max   = math.log1p(max(all_flows))

    gap   = 0.030
    min_h = 0.080
    src_heights = compute_heights(src_flow[sources].tolist(), AVAIL_H, gap, min_h)
    tgt_heights = compute_heights(tgt_flow[targets].tolist(), AVAIL_H, gap, min_h)

    src_tops = node_tops(src_heights, gap)
    tgt_tops = node_tops(tgt_heights, gap)

    center_top = CENTER_TOP
    center_h   = CENTER_H

    SI = {s: {"top": t, "h": h, "flow": int(src_flow[s])}
          for s, t, h in zip(sources, src_tops, src_heights)}
    TI = {t_: {"top": t, "h": h, "flow": int(tgt_flow[t_])}
          for t_, t, h in zip(targets, tgt_tops, tgt_heights)}

    src_out    = {s: SI[s]["top"] for s in sources}
    center_in  = center_top
    center_out = center_top
    tgt_in     = {t_: TI[t_]["top"] for t_ in targets}

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    ax.set_xlim(0, FIG_W)
    ax.set_ylim(0, FIG_H)
    ax.axis("off")

    # Left ribbons
    for s in sources:
        cnt  = SI[s]["flow"]
        rh_s = SI[s]["h"]
        rh_c = (cnt / total_left) * center_h
        y0t, y0b = src_out[s], src_out[s] - rh_s
        y1t, y1b = center_in, center_in - rh_c
        center_in -= rh_c
        draw_ribbon(ax, SRC_X + SRC_BAR_W, y0t, y0b,
                        CENTER_X,          y1t, y1b,
                    lighten(GROUP_COLOR[s]), flow_alpha(cnt, log_min, log_max))

    # Right ribbons
    for t_ in targets:
        cnt  = TI[t_]["flow"]
        rh_c = (cnt / total_right) * center_h
        rh_t = TI[t_]["h"]
        y0t, y0b = center_out, center_out - rh_c
        center_out -= rh_c
        y1t, y1b = tgt_in[t_], tgt_in[t_] - rh_t
        tgt_in[t_] -= rh_t
        draw_ribbon(ax, CENTER_X + CENTER_BAR_W, y0t, y0b,
                        TGT_X,                   y1t, y1b,
                    lighten(GROUP_COLOR[t_]), flow_alpha(cnt, log_min, log_max))

    # Source bars
    for s, d in SI.items():
        fc = GROUP_COLOR[s]
        ax.add_patch(mpatches.Rectangle(
            (SRC_X, d["top"] - d["h"]), SRC_BAR_W, d["h"],
            facecolor=fc, edgecolor=darken(fc), linewidth=0.3, zorder=2,
        ))

    # Center block
    ax.add_patch(mpatches.Rectangle(
        (CENTER_X, center_top - center_h), CENTER_BAR_W, center_h,
        facecolor=CENTER_COLOR, edgecolor=darken(CENTER_COLOR), linewidth=0.5, zorder=2,
    ))
    ax.text(
        CENTER_X + CENTER_BAR_W / 2, center_top + 0.06,
        "EC Disease List",
        ha="center", va="bottom",
        fontsize=FONT_CENTER, fontfamily="Helvetica",
        color=CENTER_COLOR, fontweight="bold", zorder=3,
    )

    # Target bars
    for t_, d in TI.items():
        fc = GROUP_COLOR[t_]
        ax.add_patch(mpatches.Rectangle(
            (TGT_X, d["top"] - d["h"]), TGT_BAR_W, d["h"],
            facecolor=fc, edgecolor=darken(fc), linewidth=0.3, zorder=2,
        ))

    # Labels — larger font since only 8 groups
    label_gap = 0.04
    for s, d in SI.items():
        ax.text(SRC_X - label_gap, d["top"] - d["h"] / 2,
                s, ha="right", va="center",
                fontsize=5.5, fontfamily="Helvetica", color="black")
    for t_, d in TI.items():
        ax.text(TGT_X + TGT_BAR_W + label_gap, d["top"] - d["h"] / 2,
                t_, ha="left", va="center",
                fontsize=5.5, fontfamily="Helvetica", color="black")

    return fig


def main():
    plt.rcParams.update({
        "font.family":  "Helvetica",
        "pdf.fonttype": 42,
        "ps.fonttype":  42,
    })
    left_df, right_df = load_data()

    fig_full = build_sankey(left_df, right_df)
    out_full = os.path.join(_DIR, "disease_sankey_full.pdf")
    fig_full.savefig(out_full, format="pdf", dpi=300)
    print(f"Saved {out_full}")

    fig_grouped = build_grouped_sankey(left_df, right_df)
    out_grouped = os.path.join(_DIR, "disease_sankey_grouped.pdf")
    fig_grouped.savefig(out_grouped, format="pdf", dpi=300)
    print(f"Saved {out_grouped}")


if __name__ == "__main__":
    main()
