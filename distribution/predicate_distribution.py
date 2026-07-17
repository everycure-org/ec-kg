import json
import os
from collections import defaultdict

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AGG_CSV    = os.path.join(SCRIPT_DIR, "..", "sankey", "sankey_agg.csv")
OUT_PDF    = os.path.join(SCRIPT_DIR, "predicate_distribution.pdf")

# ── Biolink predicate hierarchy (DFS preorder) ─────────────────────────────────
# (key, depth, is_phantom, display_label)
# Phantom nodes are structural intermediates not present in EC-KG edge data.
TREE_NODES = [
    ("related_to",                              0, False, "related to"),
      ("_related_to_at_concept_level",          1, True,  "related to at concept level"),
        ("close_match",                         2, False, "close match"),
          ("same_as",                           3, False, "same as"),
        ("has_member",                          2, False, "has member"),
        ("subclass_of",                         2, False, "subclass of"),
        ("superclass_of",                       2, False, "superclass of"),
      ("disease_has_location",                  1, False, "disease has location"),
      ("_related_to_at_instance_level",         1, True,  "related to at instance level"),
        ("active_in",                           2, False, "active in"),
        ("affected_by",                         2, False, "affected by"),
        ("affects",                             2, False, "affects"),
          ("ameliorates_condition",             3, False, "ameliorates condition"),
          ("disrupts",                          3, False, "disrupts"),
          ("exacerbates_condition",             3, False, "exacerbates condition"),
          ("has_adverse_event",                 3, False, "has adverse event"),
          ("has_side_effect",                   3, False, "has side effect"),
          ("regulates",                         3, False, "regulates"),
        ("_affects_likelihood_of",              2, True,  "affects likelihood of"),
          ("predisposes_to_condition",          3, False, "predisposes to condition"),
          ("preventative_for_condition",        3, False, "preventative for condition"),
        ("applied_to_treat",                    2, False, "applied to treat"),
        ("associated_with",                     2, False, "associated with"),
          ("correlated_with",                   3, False, "correlated with"),
            ("biomarker_for",                   4, False, "biomarker for"),
            ("coexpressed_with",                4, False, "coexpressed with"),
            ("negatively_correlated_with",      4, False, "negatively correlated with"),
            ("positively_correlated_with",      4, False, "positively correlated with"),
          ("genetically_associated_with",       3, False, "genetically associated with"),
            ("gene_associated_with_condition",  4, False, "gene associated with condition"),
        ("acts_upstream_of",                    2, False, "acts upstream of"),
          ("acts_upstream_of_negative_effect",  3, False, "acts upstream of negative effect"),
          ("_acts_upstream_of_or_within",       3, True,  "acts upstream of or within"),
            ("acts_upstream_of_or_within_negative_effect", 4, False,
             "acts upstream of or within negative effect"),
            ("acts_upstream_of_or_within_positive_effect", 4, False,
             "acts upstream of or within positive effect"),
          ("acts_upstream_of_positive_effect",  3, False, "acts upstream of positive effect"),
        ("coexists_with",                       2, False, "coexists with"),
          ("colocalizes_with",                  3, False, "colocalizes with"),
          ("in_complex_with",                   3, False, "in complex with"),
        ("contraindicated_in",                  2, False, "contraindicated in"),
        ("contributes_to",                      2, False, "contributes to"),
          ("causes",                            3, False, "causes"),
        ("derives_from",                        2, False, "derives from"),
        ("_derives_into",                       2, True,  "derives into"),
          ("has_metabolite",                    3, False, "has metabolite"),
        ("develops_from",                       2, False, "develops from"),
        ("diagnoses",                           2, False, "diagnoses"),
        ("disease_has_basis_in",                2, False, "disease has basis in"),
        ("gene_product_of",                     2, False, "gene product of"),
        ("has_decreased_amount",                2, False, "has decreased amount"),
        ("has_increased_amount",                2, False, "has increased amount"),
        ("has_molecular_consequence",           2, False, "has molecular consequence"),
        ("has_not_completed",                   2, False, "has not completed"),
        ("has_participant",                     2, False, "has participant"),
          ("has_input",                         3, False, "has input"),
          ("has_output",                        3, False, "has output"),
        ("has_phenotype",                       2, False, "has phenotype"),
        ("in_taxon",                            2, False, "in taxon"),
        ("interacts_with",                      2, False, "interacts with"),
          ("genetically_interacts_with",        3, False, "genetically interacts with"),
          ("physically_interacts_with",         3, False, "physically interacts with"),
            ("directly_physically_interacts_with",   4, False,
             "directly physically interacts with"),
            ("indirectly_physically_interacts_with", 4, False,
             "indirectly physically interacts with"),
        ("is_sequence_variant_of",              2, False, "is sequence variant of"),
        ("lacks_part",                          2, False, "lacks part"),
        ("located_in",                          2, False, "located in"),
          ("expressed_in",                      3, False, "expressed in"),
        ("manifestation_of",                    2, False, "manifestation of"),
        ("mentions",                            2, False, "mentions"),
        ("model_of",                            2, False, "model of"),
        ("occurs_in",                           2, False, "occurs in"),
        ("overlaps",                            2, False, "overlaps"),
          ("has_part",                          3, False, "has part"),
            ("has_active_ingredient",           4, False, "has active ingredient"),
            ("has_plasma_membrane_part",        4, False, "has plasma membrane part"),
          ("composed_primarily_of",             3, False, "composed primarily of"),
        ("_participates_in",                    2, True,  "participates in"),
          ("actively_involved_in",              3, False, "actively involved in"),
            ("capable_of",                      4, False, "capable of"),
          ("catalyzes",                         3, False, "catalyzes"),
          ("enables",                           3, False, "enables"),
        ("produces",                            2, False, "produces"),
        ("similar_to",                          2, False, "similar to"),
          ("chemically_similar_to",             3, False, "chemically similar to"),
          ("homologous_to",                     3, False, "homologous to"),
        ("target_for",                          2, False, "target for"),
        ("temporally_related_to",               2, False, "temporally related to"),
          ("precedes",                          3, False, "precedes"),
        ("transcribed_from",                    2, False, "transcribed from"),
        ("translates_to",                       2, False, "translates to"),
        ("treats_or_applied_or_studied_to_treat", 2, False,
         "treats or applied or studied to treat"),
          ("treats",                            3, False, "treats"),
          ("beneficial_in_models_for",          3, False, "beneficial in models for"),
        # Position unresolved in installed schema version — semantically grouped here
        ("affects_response_to",                 2, False, "affects response to"),
        ("decreases_response_to",               2, False, "decreases response to"),
        ("increases_response_to",               2, False, "increases response to"),
    ("drug_regulatory_status_world_wide",       0, False, "drug regulatory status world wide"),
]

MAX_DEPTH = 4

# ── Tree helpers ───────────────────────────────────────────────────────────────

def build_relations(nodes):
    parent_map   = {}
    children_map = defaultdict(list)
    depth_map    = {}
    stack = []
    for key, depth, *_ in nodes:
        while stack and stack[-1][1] >= depth:
            stack.pop()
        depth_map[key] = depth
        if stack:
            par = stack[-1][0]
            parent_map[key]  = par
            children_map[par].append(key)
        else:
            parent_map[key] = None
        stack.append((key, depth))
    return parent_map, children_map, depth_map


def draw_tree(ax, tree_nodes, y_of, children_map, parent_map, depth_map):
    lc = "#555555"
    lw = 0.6
    for key, depth, *_ in tree_nodes:
        y  = y_of[key]
        x  = float(depth)
        # Bracket: vertical line at this node's x spanning direct children
        if children_map[key]:
            cy = [y_of[c] for c in children_map[key]]
            ax.plot([x, x], [min(cy), max(cy)],
                    color=lc, lw=lw, solid_capstyle="butt", zorder=2)
        # Horizontal: connect this node back to its parent's x
        par = parent_map[key]
        if par is not None:
            px = float(depth_map[par])
            ax.plot([px, x], [y, y],
                    color=lc, lw=lw, solid_capstyle="butt", zorder=2)
        else:
            ax.plot([x - 0.3, x], [y, y],
                    color=lc, lw=lw, solid_capstyle="butt", zorder=2)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    df_edges   = pd.read_csv(AGG_CSV)
    pred_total = df_edges.groupby("predicate")["edge_count"].sum()

    parent_map, children_map, depth_map = build_relations(TREE_NODES)

    n = len(TREE_NODES)
    # y=0 is bottom; index 0 → top row → highest y value
    y_of = {k: (n - 1 - i) for i, (k, *_) in enumerate(TREE_NODES)}

    plt.rcParams.update({
        "font.family":     "Helvetica",
        "pdf.fonttype":    42,
        "ps.fonttype":     42,
        "font.size":       7,
        "axes.linewidth":  0.5,
        "xtick.major.width": 0.4,
        "xtick.major.size":  2.5,
    })

    fig = plt.figure(figsize=(10.0, 12.0))
    # Two panels sharing y: tree (left) | bars (right)
    gs = fig.add_gridspec(
        1, 2,
        width_ratios=[28, 72],
        left=0.01, right=0.98,
        top=0.96, bottom=0.04,
        wspace=0.01,
    )
    ax_tree = fig.add_subplot(gs[0])
    ax_bar  = fig.add_subplot(gs[1])
    ax_bar.sharey(ax_tree)

    # ── Tree panel ─────────────────────────────────────────────────────────────
    ax_tree.set_xlim(-0.4, MAX_DEPTH + 3.2)
    ax_tree.set_ylim(-0.5, n - 0.5)
    ax_tree.set_axis_off()
    ax_tree.set_title("Predicate distribution", fontsize=11,
                       fontweight="bold", loc="left", pad=6)

    draw_tree(ax_tree, TREE_NODES, y_of, children_map, parent_map, depth_map)

    for key, depth, is_phantom, label in TREE_NODES:
        y  = y_of[key]
        col   = "#aaaaaa" if is_phantom else "#222222"
        fs    = 4.8       if is_phantom else 5.5
        style = "italic"  if is_phantom else "normal"
        ax_tree.plot(depth, y, "o", ms=2.0, color="#555555", zorder=3)
        ax_tree.text(MAX_DEPTH + 0.2, y, label,
                     va="center", ha="left", fontsize=fs,
                     color=col, fontstyle=style)

    # ── Bar panel ──────────────────────────────────────────────────────────────
    ax_bar.set_xscale("log")
    ax_bar.set_ylim(-0.5, n - 0.5)
    ax_bar.tick_params(axis="y", left=False, labelleft=False)
    ax_bar.set_xlabel("Number of edges (log scale)", fontsize=9, labelpad=4)
    ax_bar.grid(axis="x", which="major", color="#e0e0e0", lw=0.5, zorder=0)
    ax_bar.grid(axis="x", which="minor", color="#f2f2f2", lw=0.3, zorder=0)
    ax_bar.set_axisbelow(True)
    for sp in ["top", "right", "left"]:
        ax_bar.spines[sp].set_visible(False)

    BAR_COLOR = "#455a64"

    for key, depth, is_phantom, label in TREE_NODES:
        if is_phantom:
            continue
        y        = y_of[key]
        pred_key = "biolink:" + key
        count    = pred_total.get(pred_key, 0)
        if count > 0:
            ax_bar.barh(y, count, height=0.65,
                        color=BAR_COLOR, edgecolor="none", zorder=2)
            # Inline count label
            ax_bar.text(count * 1.08, y, f"{count:,.0f}",
                        va="center", ha="left", fontsize=4.2, color="#444444")

    ax_bar.xaxis.set_major_formatter(
        mticker.FuncFormatter(
            lambda x, _: f"{x/1e6:.0f}M" if x >= 1e6 else
                          f"{x/1e3:.0f}k"  if x >= 1e3 else f"{x:.0f}"))

    fig.savefig(OUT_PDF, dpi=300, bbox_inches="tight")
    print(f"Saved → {OUT_PDF}")


if __name__ == "__main__":
    main()
