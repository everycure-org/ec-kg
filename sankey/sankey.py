"""
Full EC-KG edge-flow Sankey diagram (source category -> predicate -> target
category).

Source/target categories are grouped adjacent to each other by biolink
category group (see eckg.colors.NODE_TO_GROUP), with a small buffer gap at
each group boundary to leave room for post-hoc group-section labels, and a
legend for the 8 groups at the bottom of the figure.

Every category already classified as Miscellaneous, plus any category —
regardless of its usual group — that contributes less than
SMALL_CONTRIB_THRESHOLD of edges as BOTH a source and a target, is merged
into a single "Miscellaneous" bar (their rows are summed together). A
category significant in either role keeps its own bar, color, and flow on
both sides.

Predicate labels have underscores replaced with spaces
("acts_upstream_of" -> "acts upstream of").
"""
import json
import math
import os

import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
from google.cloud import bigquery
from matplotlib.path import Path

from eckg.colors import CATEGORY_COLORS, _FALLBACK_COLOR, GROUPS, NODE_TO_GROUP
from eckg.grouping import group_gaps, group_sorted

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AGG_CSV    = os.path.join(SCRIPT_DIR, "sankey_agg.csv")
CAT_JSON   = os.path.join(SCRIPT_DIR, "category_counts.json")

# Categories contributing less than this share of edges (as both source
# and target) get folded into the Miscellaneous bar.
SMALL_CONTRIB_THRESHOLD = 0.005

# Pseudo-category label for the merged bar, and its uniform color.
MISC_LABEL = "biolink:Miscellaneous"
MISC_COLOR = "#666666"

# Figure dimensions (inches)
FIG_W  = 8.0
FIG_H  = 10.0

# Margins (room for labels outside the bars)
M_LEFT   = 1.30
M_RIGHT  = 1.30
M_TOP    = 0.55
M_BOTTOM = 0.25

AVAIL_H = FIG_H - M_TOP - M_BOTTOM   # height available for all node columns

#  Column geometry (inches)
SRC_BAR_W  = 0.10
PRED_BAR_W = 1.50   # wide enough to hold the longest predicate label
TGT_BAR_W  = 0.10

SRC_X  = M_LEFT
TGT_X  = FIG_W - M_RIGHT - TGT_BAR_W

# Centre the predicate column in the space between source and target
_inner_w = TGT_X - (SRC_X + SRC_BAR_W)
PRED_X   = SRC_X + SRC_BAR_W + (_inner_w - PRED_BAR_W) / 2

# Gap between nodes in each column (inches)
GAP_SRC_TGT = 0.028
GAP_PRED    = 0.010

# Extra gap inserted at group boundaries in the source/target columns, on
# top of GAP_SRC_TGT — leaves room to post-hoc add group-section labels.
GROUP_BUFFER = 0.05

# Minimum visible ribbon width — ensures every connection draws something
MIN_RIBBON_H = 0.004   # inches

# Group legend, drawn below the diagram (inches)
LEGEND_H      = 0.55   # vertical space reserved for the legend
LEGEND_MARGIN = 0.30   # left/right margin for the legend row
LEGEND_COLS   = 4
LEGEND_SWATCH = 0.09
LEGEND_FONT   = 5.5

#  Font sizes
FONT_OUTER    = 4.5    # source / target labels (pt) — slightly smaller
FONT_PRED_MAX = 6.0    # predicate labels inside bars – may be reduced automatically

#  Colors
# Predicate column is a unified light band — no individual boxes
COL_PRED_BG   = "#f0f0f0"   # background behind entire predicate column
COL_PRED_SEP  = "#cccccc"   # thin separator between predicates
COL_PRED_TEXT = "black"

# Edge opacity: log-scaled between these bounds so dominant flows dominate
EDGE_ALPHA_MIN = 0.06
EDGE_ALPHA_MAX = 0.35
EDGE_LIGHTEN   = 0.55   # how much to lighten node color for ribbons

def get_cat_color(category):
    if category == MISC_LABEL:
        return MISC_COLOR
    return CATEGORY_COLORS.get(category, _FALLBACK_COLOR)


def lighten(rgba, amount=EDGE_LIGHTEN):
    """Blend an RGBA colour towards white (amount 0=original, 1=white)."""
    r, g, b, a = mcolors.to_rgba(rgba)
    return (r + (1 - r) * amount,
            g + (1 - g) * amount,
            b + (1 - b) * amount,
            a)


def darken(rgba, amount=0.30):
    """Multiply RGB channels down (amount 0=original, 1=black)."""
    r, g, b, a = mcolors.to_rgba(rgba)
    f = 1 - amount
    return (r * f, g * f, b * f, a)


def flow_alpha(flow, log_min, log_max):
    if log_max <= log_min:
        return EDGE_ALPHA_MIN
    t = (math.log1p(flow) - log_min) / (log_max - log_min)
    return EDGE_ALPHA_MIN + t * (EDGE_ALPHA_MAX - EDGE_ALPHA_MIN)


def load_data():
    if os.path.exists(AGG_CSV) and os.path.exists(CAT_JSON):
        print("Loading cached data...")
        df = pd.read_csv(AGG_CSV)
        with open(CAT_JSON) as f:
            cat_counts = json.load(f)
        print(f"  {len(df):,} triples, {len(cat_counts)} categories")
        return df, cat_counts

    print("Fetching from BigQuery (will cache locally)...")
    client = bigquery.Client(project="mtrx-hub-dev-3of")

    nodes_df = client.query(
        "SELECT id, category FROM `mtrx-hub-dev-3of.release_v0_15_19.nodes_unified`"
    ).to_dataframe()
    cat_counts = nodes_df.groupby("category").size().to_dict()
    id_to_cat  = dict(zip(nodes_df["id"], nodes_df["category"]))
    del nodes_df

    edges_df = client.query(
        "SELECT subject, predicate, object FROM `mtrx-hub-dev-3of.release_v0_15_19.edges_unified`"
    ).to_dataframe()

    edges_df["source_type"] = edges_df["subject"].map(id_to_cat)
    edges_df["target_type"] = edges_df["object"].map(id_to_cat)
    edges_df = edges_df.dropna(subset=["source_type", "target_type"])

    df = (
        edges_df.groupby(["source_type", "predicate", "target_type"])
        .size()
        .reset_index(name="edge_count")
        .sort_values("edge_count", ascending=False)
    )
    df.to_csv(AGG_CSV, index=False)
    with open(CAT_JSON, "w") as f:
        json.dump(cat_counts, f)
    return df, cat_counts


def collapse_miscellaneous(df, threshold=SMALL_CONTRIB_THRESHOLD):
    """
    Fold every category already classified as Miscellaneous, plus any
    category contributing less than `threshold` of edges as BOTH a source
    and a target, into a single Miscellaneous row. A category significant
    in either role keeps its own row (and thus its own bar) on both sides.
    """
    src_flow = df.groupby("source_type")["edge_count"].sum()
    tgt_flow = df.groupby("target_type")["edge_count"].sum()
    total    = df["edge_count"].sum()

    all_cats = set(src_flow.index) | set(tgt_flow.index)

    def is_small(cat):
        if NODE_TO_GROUP.get(cat, "Miscellaneous") == "Miscellaneous":
            return True
        src_share = src_flow.get(cat, 0) / total
        tgt_share = tgt_flow.get(cat, 0) / total
        return src_share < threshold and tgt_share < threshold

    folded = sorted(
        c for c in all_cats
        if is_small(c) and NODE_TO_GROUP.get(c, "Miscellaneous") != "Miscellaneous"
    )
    print(f"  Folding {len(folded)} additional categories into Miscellaneous "
          f"(< {threshold:.1%} of edges as both source AND target):")
    for c in folded:
        s = src_flow.get(c, 0) / total
        t = tgt_flow.get(c, 0) / total
        print(f"    {clean(c):35s} src {s:6.3%}  tgt {t:6.3%}")

    remap = {cat: (MISC_LABEL if is_small(cat) else cat) for cat in all_cats}

    out = df.copy()
    out["source_type"] = out["source_type"].map(remap)
    out["target_type"] = out["target_type"].map(remap)
    out = (
        out.groupby(["source_type", "predicate", "target_type"])["edge_count"]
        .sum()
        .reset_index()
    )
    return out


def _gap_list(gap, n):
    """Accept either a uniform scalar gap or a pre-built list of n-1 gaps
    (e.g. from eckg.grouping.group_gaps, for extra space at group boundaries)."""
    if isinstance(gap, (int, float)):
        return [gap] * max(n - 1, 0)
    return list(gap)


def compute_heights(flows, avail_h, gap, min_h):
    """
    Proportional heights with a minimum-height floor.
    Iteratively bumps small nodes up to min_h and rescales the rest.
    """
    n = len(flows)
    if n == 0:
        return []
    gaps        = _gap_list(gap, n)
    total_gap   = sum(gaps)
    avail_nodes = avail_h - total_gap
    total_flow  = sum(flows)

    heights = [f / total_flow * avail_nodes for f in flows]

    for _ in range(200):
        small  = [i for i, h in enumerate(heights) if h < min_h - 1e-9]
        if not small:
            break
        large  = [i for i, h in enumerate(heights) if i not in set(small)]
        for i in small:
            heights[i] = min_h
        remaining = avail_nodes - len(small) * min_h
        if not large or remaining <= 0:
            # Force all equal if no room
            equal = avail_nodes / n
            heights = [equal] * n
            break
        large_h_sum = sum(heights[i] for i in large)
        for i in large:
            heights[i] = heights[i] / large_h_sum * remaining

    return heights


def node_tops(heights, gap):
    """y-coordinates of the TOP of each node (matplotlib y-axis: 0=bottom, FIG_H=top)."""
    gaps = _gap_list(gap, len(heights))
    tops = []
    y = M_BOTTOM + AVAIL_H   # start at top of node area
    for i, h in enumerate(heights):
        tops.append(y)
        y -= h
        if i < len(gaps):
            y -= gaps[i]
    return tops


def clean(label):
    return label.replace("biolink:", "").replace("_", " ")


def draw_ribbon(ax, x0, y0_top, y0_bot, x1, y1_top, y1_bot, color, alpha):
    """Filled cubic-bezier ribbon between two vertical edges.
    Enforces a minimum visible height at each end so hairline connections show."""
    # Enforce minimum visible width at each end (centred on the midpoint)
    def enforce_min(top, bot):
        h = top - bot
        if h < MIN_RIBBON_H:
            mid = (top + bot) / 2
            return mid + MIN_RIBBON_H / 2, mid - MIN_RIBBON_H / 2
        return top, bot

    y0_top, y0_bot = enforce_min(y0_top, y0_bot)
    y1_top, y1_bot = enforce_min(y1_top, y1_bot)
    xm = (x0 + x1) / 2
    verts = [
        (x0, y0_top),
        (xm, y0_top), (xm, y1_top), (x1, y1_top),   # top curve
        (x1, y1_bot),
        (xm, y1_bot), (xm, y0_bot), (x0, y0_bot),   # bottom curve (reversed)
        (x0, y0_top),
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


def draw_group_legend(ax, fig_w, legend_h):
    """Swatch + label for each of the 8 category groups, in a grid below the
    diagram (y in [-legend_h, 0])."""
    n_rows = math.ceil(len(GROUPS) / LEGEND_COLS)
    col_w  = (fig_w - 2 * LEGEND_MARGIN) / LEGEND_COLS
    row_h  = legend_h / n_rows

    for i, (label, color) in enumerate(GROUPS):
        row, col = divmod(i, LEGEND_COLS)
        x0 = LEGEND_MARGIN + col * col_w
        y  = -row_h * row - row_h / 2
        ax.add_patch(mpatches.Rectangle(
            (x0, y - LEGEND_SWATCH / 2), LEGEND_SWATCH, LEGEND_SWATCH,
            facecolor=color, edgecolor=darken(color, 0.30), linewidth=0.3, zorder=3,
        ))
        ax.text(
            x0 + LEGEND_SWATCH + 0.04, y,
            label, ha="left", va="center",
            fontsize=LEGEND_FONT, fontfamily="Helvetica", color="black", zorder=3,
        )


def build_sankey(df, cat_counts):
    # Per-node total flows — this is what determines each bar's drawn height,
    # so it must also be what we sort by (sorting by cat_counts, the raw node
    # count, can disagree with edge flow and make same-group bars look
    # out of size order).
    src_flow  = df.groupby("source_type")["edge_count"].sum()
    pred_flow = df.groupby("predicate")["edge_count"].sum()
    tgt_flow  = df.groupby("target_type")["edge_count"].sum()

    #  Sort — group categories that share a biolink category group (see
    #  eckg.colors.NODE_TO_GROUP) adjacent to each other, e.g. Gene next to
    #  Protein, SmallMolecule next to Drug. The merged Miscellaneous bar
    #  isn't in NODE_TO_GROUP so it falls back to the Miscellaneous group.
    sources    = group_sorted(df["source_type"].unique().tolist(), src_flow.to_dict())
    targets    = group_sorted(df["target_type"].unique().tolist(), tgt_flow.to_dict())
    predicates = (
        pred_flow
        .sort_values(ascending=False)
        .index.tolist()
    )

    print(f"  {len(sources)} src | {len(predicates)} pred | {len(targets)} tgt")

    # Colour map: biologically grouped, shared between src & tgt columns
    all_cats  = list(dict.fromkeys(sources + targets))
    cat_color = {cat: get_cat_color(cat) for cat in all_cats}

    #  Log-scale bounds for edge alpha
    all_link_flows = (
        df.groupby(["source_type", "predicate"])["edge_count"].sum().tolist() +
        df.groupby(["predicate", "target_type"])["edge_count"].sum().tolist()
    )
    log_min = math.log1p(min(all_link_flows))
    log_max = math.log1p(max(all_link_flows))

    src_flows  = [int(src_flow[s])  for s in sources]
    pred_flows = [int(pred_flow[p]) for p in predicates]
    tgt_flows  = [int(tgt_flow[t])  for t in targets]

    # Auto-size predicate font to fit all bars
    n_pred      = len(predicates)
    total_gaps  = GAP_PRED * max(n_pred - 1, 0)
    avail_pred  = AVAIL_H - total_gaps
    # If all nodes equal, min height = avail / n
    auto_min_h  = avail_pred / n_pred
    # Font height that fits: font_pt = min_h_in * 72 * 0.75 (75% of bar for text)
    auto_font   = min(FONT_PRED_MAX, auto_min_h * 72 * 0.75)
    auto_font   = max(auto_font, 4.5)
    min_h_pred  = auto_font / 72 / 0.75   # reverse: ensure text fits

    print(f"  Predicate font: {auto_font:.1f}pt, min bar height: {min_h_pred*25.4:.1f}mm")

    # Minimum heights
    min_h_src_tgt = 0.018   # source/target: no text inside, just visible

    # Extra gap at group boundaries — leaves room to post-hoc add
    # group-section labels alongside the source/target columns.
    src_gaps = group_gaps(sources, GAP_SRC_TGT, GROUP_BUFFER)
    tgt_gaps = group_gaps(targets, GAP_SRC_TGT, GROUP_BUFFER)

    src_heights  = compute_heights(src_flows,  AVAIL_H, src_gaps, min_h_src_tgt)
    pred_heights = compute_heights(pred_flows, AVAIL_H, GAP_PRED, min_h_pred)
    tgt_heights  = compute_heights(tgt_flows,  AVAIL_H, tgt_gaps, min_h_src_tgt)

    #  Node top positions
    src_tops  = node_tops(src_heights,  src_gaps)
    pred_tops = node_tops(pred_heights, GAP_PRED)
    tgt_tops  = node_tops(tgt_heights,  tgt_gaps)

    # Lookup dicts
    SI = {s: {"top": t, "h": h, "flow": f}
          for s, t, h, f in zip(sources,    src_tops,  src_heights,  src_flows)}
    PI = {p: {"top": t, "h": h, "flow": f}
          for p, t, h, f in zip(predicates, pred_tops, pred_heights, pred_flows)}
    TI = {t_: {"top": t, "h": h, "flow": f}
          for t_, t, h, f in zip(targets,   tgt_tops,  tgt_heights,  tgt_flows)}

    # Link offsets (current fill position within each node)
    src_out  = {s: SI[s]["top"] for s in sources}
    pred_in  = {p: PI[p]["top"] for p in predicates}
    pred_out = {p: PI[p]["top"] for p in predicates}
    tgt_in   = {t_: TI[t_]["top"] for t_ in targets}

    pred_order = {p: i for i, p in enumerate(predicates)}
    tgt_order  = {t_: i for i, t_ in enumerate(targets)}

    # Figure — extra LEGEND_H of canvas below y=0 holds the group legend;
    # all existing geometry above is untouched (still relative to FIG_H).
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H + LEGEND_H))
    # Fill the entire figure — no automatic margins
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    ax.set_xlim(0, FIG_W)
    ax.set_ylim(-LEGEND_H, FIG_H)
    ax.axis("off")

    #  Draw ribbons: source → predicate
    sp = (
        df.groupby(["source_type", "predicate"])["edge_count"].sum()
        .reset_index()
        .assign(pred_order=lambda d: d["predicate"].map(pred_order))
        .sort_values(["source_type", "pred_order"])
    )
    for _, row in sp.iterrows():
        s, p, cnt = row["source_type"], row["predicate"], row["edge_count"]
        if s not in SI or p not in PI:
            continue
        rh_s = (cnt / SI[s]["flow"]) * SI[s]["h"]
        rh_p = (cnt / PI[p]["flow"]) * PI[p]["h"]

        y0t, y0b = src_out[s], src_out[s] - rh_s;  src_out[s]  -= rh_s
        y1t, y1b = pred_in[p], pred_in[p] - rh_p;  pred_in[p]  -= rh_p

        ribbon_col = lighten(cat_color[s])
        alpha      = flow_alpha(cnt, log_min, log_max)
        draw_ribbon(ax, SRC_X + SRC_BAR_W, y0t, y0b,
                        PRED_X,            y1t, y1b, ribbon_col, alpha)

    # Draw ribbons: predicate → target
    pt = (
        df.groupby(["predicate", "target_type"])["edge_count"].sum()
        .reset_index()
        .assign(tgt_order=lambda d: d["target_type"].map(tgt_order))
        .sort_values(["predicate", "tgt_order"])
    )
    for _, row in pt.iterrows():
        p, t_, cnt = row["predicate"], row["target_type"], row["edge_count"]
        if p not in PI or t_ not in TI:
            continue
        rh_p = (cnt / PI[p]["flow"]) * PI[p]["h"]
        rh_t = (cnt / TI[t_]["flow"]) * TI[t_]["h"]

        y0t, y0b = pred_out[p], pred_out[p] - rh_p;  pred_out[p] -= rh_p
        y1t, y1b = tgt_in[t_], tgt_in[t_]  - rh_t;  tgt_in[t_]  -= rh_t

        ribbon_col = lighten(cat_color[t_])
        alpha      = flow_alpha(cnt, log_min, log_max)
        draw_ribbon(ax, PRED_X + PRED_BAR_W, y0t, y0b,
                        TGT_X,               y1t, y1b, ribbon_col, alpha)

    #  Draw nodes
    for s, d in SI.items():
        fc = cat_color[s]
        ec = darken(fc, 0.30)
        ax.add_patch(mpatches.Rectangle(
            (SRC_X, d["top"] - d["h"]), SRC_BAR_W, d["h"],
            facecolor=fc, edgecolor=ec, linewidth=0.3, zorder=2,
        ))

    # Predicate column: single light background band, no individual boxes
    pred_col_top = PI[predicates[0]]["top"]
    pred_col_bot = PI[predicates[-1]]["top"] - PI[predicates[-1]]["h"]
    ax.add_patch(mpatches.Rectangle(
        (PRED_X, pred_col_bot), PRED_BAR_W, pred_col_top - pred_col_bot,
        facecolor=COL_PRED_BG, edgecolor="none", zorder=1.5,
    ))
    # Thin separator lines between predicate slots
    for p in predicates[:-1]:
        sep_y = PI[p]["top"] - PI[p]["h"] - GAP_PRED / 2
        ax.plot([PRED_X, PRED_X + PRED_BAR_W], [sep_y, sep_y],
                color=COL_PRED_SEP, linewidth=0.25, zorder=2.5)
    # Labels inside the band
    for p, d in PI.items():
        ax.text(
            PRED_X + PRED_BAR_W / 2, d["top"] - d["h"] / 2,
            clean(p),
            ha="center", va="center",
            fontsize=auto_font, fontfamily="Helvetica",
            color=COL_PRED_TEXT, clip_on=True, zorder=3,
        )

    for t_, d in TI.items():
        fc = cat_color[t_]
        ec = darken(fc, 0.30)
        ax.add_patch(mpatches.Rectangle(
            (TGT_X, d["top"] - d["h"]), TGT_BAR_W, d["h"],
            facecolor=fc, edgecolor=ec, linewidth=0.3, zorder=2,
        ))

    # Labels outside nodes
    label_gap = 0.06   # gap between bar edge and label

    for s, d in SI.items():
        ax.text(
            SRC_X - label_gap, d["top"] - d["h"] / 2,
            clean(s),
            ha="right", va="center",
            fontsize=FONT_OUTER, fontfamily="Helvetica", color="black",
        )

    for t_, d in TI.items():
        ax.text(
            TGT_X + TGT_BAR_W + label_gap, d["top"] - d["h"] / 2,
            clean(t_),
            ha="left", va="center",
            fontsize=FONT_OUTER, fontfamily="Helvetica", color="black",
        )

    draw_group_legend(ax, FIG_W, LEGEND_H)

    return fig


def main():
    plt.rcParams.update({
        "font.family":  "Helvetica",
        "pdf.fonttype": 42,
        "ps.fonttype":  42,
    })
    df, cat_counts = load_data()
    df = collapse_miscellaneous(df)
    fig = build_sankey(df, cat_counts)
    out = os.path.join(SCRIPT_DIR, "sankey.pdf")
    fig.savefig(out, format="pdf", dpi=300)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
