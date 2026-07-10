"""
Intermediate Node Visualization — 2-hop vs 3-hop comparison.

Creates a single figure with two side-by-side barplots:
  Left  (A): key biological entities as intermediate nodes in 2-hop paths
  Right (B): key biological entities as intermediate nodes in 3-hop paths

Each SOP path directory must contain one JSON file per KG named according to
KG_FILES.  Paths within each JSON may span multiple hop counts; only paths
matching the target hop count are used for each panel.

Usage
-----
Set SOP_2HOP_PATH and SOP_3HOP_PATH to the directories containing the
processed SOP JSON files (the `prm/` output of 02_calculate_sop_4hop_thr.py).
Either path can be a local directory or a gs:// URI.
"""

import io
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

import ijson
import gcsfs
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import EngFormatter
from tqdm import tqdm

sys.path.append(str(Path(__file__).parent.parent / "ml_validation"))
from fig_style import (
    apply_style,
    figsize,
    style_title, clean_spines, grid_y,
    LEGEND_KWARGS,
    AXIS_LABEL_SIZE, TICK_LABEL_SIZE,
    PAGE_WIDTH_IN, SAVE_DPI,
    savefig as save_fig,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE = '/Users/piotrkaniewski/work/ec-kg-analysis/data'

SOP_2HOP_PATH = f'{BASE}/sop_no_filtered_kg/prm/'
SOP_3HOP_PATH = 'gs://mtrx-us-central1-wg2-modeling-dev-storage/Piotr/sop_4hop/prm' #f'{BASE}/sop_no_filtered_kg/prm/'   # update to gs:// when 3-hop data is ready

VIZ_DIR = '/Users/piotrkaniewski/work/ec-kg-analysis/visualizations/metapath_analysis'

KG_FILES = {
    'PrimeKG':  'primekg_sop_checkpoint_80.json',
    'Robokop':  'robokop_sop_checkpoint_80.json',
    'RTX-KG2':  'rtx_kg2_sop_checkpoint_80.json',
    'EC-KG':    'integrated_kg_sop_checkpoint_80.json',
}

KG_NAMES = list(KG_FILES.keys())

CATEGORIES_OF_INTEREST = [
    'Gene/Protein',
    'BiologicalProcess',
    'CellularComponent',
]

# ── Color mapping (Okabe-Ito / Tol colorblind-safe palette) ─────────────────
GROUPS = [
    ("Molecular / Genetic",  "#0072B2"),
    ("Chemical / Drug",      "#009E73"),
    ("Disease / Phenotype",  "#D55E00"),
    ("Anatomy / Cell",       "#CC79A7"),
    ("Biological Process",   "#E69F00"),
    ("Organism / Taxonomy",  "#6A3D9A"),
    ("Clinical",             "#56B4E9"),
    ("Miscellaneous",        "#666666"),
]
GROUP_COLORS = dict(GROUPS)

NODE_TO_GROUP = {
    "biolink:Gene":                              "Molecular / Genetic",
    "biolink:Protein":                           "Molecular / Genetic",
    "biolink:Transcript":                        "Molecular / Genetic",
    "biolink:GeneFamily":                        "Molecular / Genetic",
    "biolink:Polypeptide":                       "Molecular / Genetic",
    "biolink:MicroRNA":                          "Molecular / Genetic",
    "biolink:RNAProduct":                        "Molecular / Genetic",
    "biolink:NucleicAcidEntity":                 "Molecular / Genetic",
    "biolink:GenomicEntity":                     "Molecular / Genetic",
    "biolink:Exon":                              "Molecular / Genetic",
    "biolink:SmallMolecule":                     "Chemical / Drug",
    "biolink:ChemicalEntity":                    "Chemical / Drug",
    "biolink:Drug":                              "Chemical / Drug",
    "biolink:MolecularMixture":                  "Chemical / Drug",
    "biolink:ChemicalMixture":                   "Chemical / Drug",
    "biolink:ComplexMolecularMixture":           "Chemical / Drug",
    "biolink:ChemicalExposure":                  "Chemical / Drug",
    "biolink:Food":                              "Chemical / Drug",
    "biolink:MolecularEntity":                   "Chemical / Drug",
    "biolink:Treatment":                         "Chemical / Drug",
    "biolink:Disease":                           "Disease / Phenotype",
    "biolink:PhenotypicFeature":                 "Disease / Phenotype",
    "biolink:DiseaseOrPhenotypicFeature":        "Disease / Phenotype",
    "biolink:PathologicalProcess":               "Disease / Phenotype",
    "biolink:BehavioralFeature":                 "Disease / Phenotype",
    "biolink:AnatomicalEntity":                  "Anatomy / Cell",
    "biolink:GrossAnatomicalStructure":          "Anatomy / Cell",
    "biolink:Cell":                              "Anatomy / Cell",
    "biolink:CellLine":                          "Anatomy / Cell",
    "biolink:CellularComponent":                 "Anatomy / Cell",
    "biolink:BiologicalProcess":                 "Biological Process",
    "biolink:MolecularActivity":                 "Biological Process",
    "biolink:Pathway":                           "Biological Process",
    "biolink:PhysiologicalProcess":              "Biological Process",
    "biolink:EnvironmentalProcess":              "Biological Process",
    "biolink:Activity":                          "Biological Process",
    "biolink:BiologicalEntity":                  "Biological Process",
    "biolink:OrganismTaxon":                     "Organism / Taxonomy",
    "biolink:PopulationOfIndividualOrganisms":   "Organism / Taxonomy",
    "biolink:IndividualOrganism":                "Organism / Taxonomy",
    "biolink:Human":                             "Organism / Taxonomy",
    "biolink:MaterialSample":                    "Organism / Taxonomy",
    "biolink:LifeStage":                         "Organism / Taxonomy",
    "biolink:Cohort":                            "Organism / Taxonomy",
    "biolink:Behavior":                          "Organism / Taxonomy",
    "biolink:Procedure":                         "Clinical",
    "biolink:ClinicalAttribute":                 "Clinical",
    "biolink:ClinicalIntervention":              "Clinical",
    "biolink:NamedThing":                        "Miscellaneous",
    "biolink:PhysicalEntity":                    "Miscellaneous",
    "biolink:Agent":                             "Miscellaneous",
    "biolink:Publication":                       "Miscellaneous",
    "biolink:InformationContentEntity":          "Miscellaneous",
    "biolink:Device":                            "Miscellaneous",
    "biolink:GeographicLocation":                "Miscellaneous",
    "biolink:Phenomenon":                        "Miscellaneous",
    "biolink:Event":                             "Miscellaneous",
    "biolink:RetrievalSource":                   "Miscellaneous",
    "biolink:EnvironmentalFeature":              "Miscellaneous",
    "biolink:OrganismAttribute":                 "Miscellaneous",
}

_FALLBACK_COLOR = "#aaaaaa"

# Map each CATEGORIES_OF_INTEREST label → group colour via the biolink key
_CAT_TO_BIOLINK = {
    'Gene/Protein':      None,                       # merged Gene + Protein
    'BiologicalProcess': 'biolink:BiologicalProcess',
    'CellularComponent': 'biolink:CellularComponent',
}
CATEGORY_DISPLAY_COLORS = {
    cat: (
        GROUP_COLORS["Molecular / Genetic"] if bl is None
        else GROUP_COLORS.get(NODE_TO_GROUP.get(bl, "Miscellaneous"), _FALLBACK_COLOR)
    )
    for cat, bl in _CAT_TO_BIOLINK.items()
}


# ---------------------------------------------------------------------------
# GCS / local storage utilities
# ---------------------------------------------------------------------------

_gcs_fs = None


def is_gcs_path(path: str) -> bool:
    return isinstance(path, str) and path.startswith('gs://')


def get_gcs_fs() -> gcsfs.GCSFileSystem:
    global _gcs_fs
    if _gcs_fs is None:
        _gcs_fs = gcsfs.GCSFileSystem()
    return _gcs_fs


def open_binary(path: str, mode: str = 'rb'):
    """Open a file for binary reading from a local path or GCS URI."""
    if is_gcs_path(path):
        return get_gcs_fs().open(path, mode)
    return open(path, mode)


def join_path(base: str, *parts: str) -> str:
    """Join path segments correctly for both local and GCS paths."""
    if is_gcs_path(base):
        return '/'.join([base.rstrip('/'), *parts])
    return os.path.join(base, *parts)


def ensure_local_dir(path: str) -> None:
    if not is_gcs_path(path):
        Path(path).mkdir(parents=True, exist_ok=True)


def save_figure(fig: plt.Figure, path: str, dpi: int = SAVE_DPI, bbox_inches: str = 'tight', **kwargs) -> None:
    """Save a matplotlib figure to a local path or GCS URI."""
    if is_gcs_path(path):
        fmt = Path(path).suffix.lstrip('.') or 'png'
        buf = io.BytesIO()
        fig.savefig(buf, format=fmt, dpi=dpi, bbox_inches=bbox_inches, **kwargs)
        buf.seek(0)
        with get_gcs_fs().open(path, 'wb') as f:
            f.write(buf.getvalue())
    else:
        fig.savefig(path, dpi=dpi, bbox_inches=bbox_inches, **kwargs)
        print(f"Saved → {path}")


def save_parquet(df: pd.DataFrame, path: str) -> None:
    """Save a DataFrame as parquet to a local path or GCS URI."""
    if is_gcs_path(path):
        buf = io.BytesIO()
        df.to_parquet(buf, index=False)
        buf.seek(0)
        with get_gcs_fs().open(path, 'wb') as f:
            f.write(buf.getvalue())
    else:
        df.to_parquet(path, index=False)


# ---------------------------------------------------------------------------
# Streaming SOP data — works for both local and GCS
# ---------------------------------------------------------------------------

def iter_sop_pairs(sop_file_path: str):
    """Yield (pair_key, pair_data) by streaming a SOP JSON file with ijson."""
    with open_binary(sop_file_path, 'rb') as f:
        yield from ijson.kvitems(f, '')


def get_sop_file_path(sop_dir: str, kg_name: str) -> str:
    return join_path(sop_dir, KG_FILES[kg_name])


# ---------------------------------------------------------------------------
# Intermediate node analysis
# ---------------------------------------------------------------------------

def _normalise_category(cat) -> str:
    """Return a cleaned biolink category string."""
    if isinstance(cat, list):
        cat = cat[0] if cat else 'Unknown'
    if cat is None:
        return 'Unknown'
    return str(cat).replace('biolink:', '')


def analyze_intermediate_nodes_for_kg(
    kg_name: str,
    sop_dir: str,
    n_hops: Optional[int] = None,
) -> dict:
    """
    Stream the SOP JSON for one KG and count intermediate node categories.

    Args:
        kg_name:  KG display name (must be a key in KG_FILES).
        sop_dir:  directory (local or gs://) containing the KG JSON files.
        n_hops:   if given, only count paths with exactly this many hops
                  (N hops → N+1 nodes).  Pass None to include all lengths.

    Returns:
        {'counts': dict, 'total': int, 'unique_types': int}
    """
    node_length_filter = (n_hops + 1) if n_hops is not None else None
    sop_path = get_sop_file_path(sop_dir, kg_name)
    print(f'  Processing {kg_name} from {sop_path}...')

    intermediates = []
    for _pair_key, pair_data in tqdm(iter_sop_pairs(sop_path), desc=f'    {kg_name}'):
        for path_meta in pair_data.get('paths_metadata', []):
            node_cats = path_meta.get('node_categories', [])

            if node_length_filter is not None and len(node_cats) != node_length_filter:
                continue
            if len(node_cats) < 3:
                continue

            for cat in node_cats[1:-1]:
                intermediates.append(_normalise_category(cat))

    counts = Counter(intermediates)
    print(f'    {len(intermediates):,} intermediate nodes, {len(counts)} unique types')
    return {'counts': dict(counts), 'total': len(intermediates), 'unique_types': len(counts)}


def analyze_intermediate_nodes(sop_dir: str, n_hops: Optional[int] = None) -> dict:
    """
    Analyze intermediate node categories for all KGs in sop_dir.

    Args:
        sop_dir: directory (local or gs://) containing per-KG SOP JSON files.
        n_hops:  hop-count filter forwarded to analyze_intermediate_nodes_for_kg.

    Returns:
        dict mapping KG name → stats dict.
    """
    hop_label = f'{n_hops}-hop' if n_hops is not None else 'all hops'
    print(f'\nAnalyzing intermediate node distributions ({hop_label}, {sop_dir})...')
    return {
        kg_name: analyze_intermediate_nodes_for_kg(kg_name, sop_dir, n_hops)
        for kg_name in KG_NAMES
    }


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

def _build_ax_data(intermediate_stats: dict) -> dict:
    """
    Return per-category count lists (aligned to KG_NAMES).
    Gene and Protein are merged into 'Gene/Protein'.
    """
    ax_data = {}
    for cat in CATEGORIES_OF_INTEREST:
        counts = []
        for kg in KG_NAMES:
            kg_counts = intermediate_stats.get(kg, {}).get('counts', {})
            if cat == 'Gene/Protein':
                count = kg_counts.get('Gene', 0) + kg_counts.get('Protein', 0)
            else:
                count = kg_counts.get(cat, 0)
            counts.append(count)
        ax_data[cat] = counts
    return ax_data


def plot_barplot_ax(
    ax: plt.Axes,
    intermediate_stats: dict,
    title: str,
    legend: bool = True,
    show_ylabel: bool = True,
) -> None:
    """
    Draw a grouped barplot of key biological entity intermediate node counts
    on a logarithmic y-axis.

    Args:
        ax:                 Matplotlib axes to draw on.
        intermediate_stats: output of analyze_intermediate_nodes.
        title:              subplot title.
        legend:             whether to show the legend.
        show_ylabel:        whether to show the y-axis label.
    """
    ax_data = _build_ax_data(intermediate_stats)

    x = np.arange(len(KG_NAMES))
    n_cats = len(CATEGORIES_OF_INTEREST)
    width = 0.22

    for i, cat in enumerate(CATEGORIES_OF_INTEREST):
        offset = (i - n_cats / 2 + 0.5) * width
        color = CATEGORY_DISPLAY_COLORS.get(cat, _FALLBACK_COLOR)
        # Clip to 1 so zero-count bars don't break the log scale
        heights = [max(v, 1) for v in ax_data[cat]]
        ax.bar(x + offset, heights, width,
               label=cat, color=color, alpha=0.9,
               edgecolor='black', linewidth=0.5, zorder=2)

    ax.set_yscale('log')
    ax.set_xlabel('Knowledge Graph', fontsize=AXIS_LABEL_SIZE)
    if show_ylabel:
        ax.set_ylabel('Intermediate node count (log scale)', fontsize=AXIS_LABEL_SIZE)
    style_title(ax, title)
    ax.set_xticks(x)
    ax.set_xticklabels(KG_NAMES, rotation=30, ha='right', fontsize=TICK_LABEL_SIZE)
    ax.tick_params(axis='y', labelsize=TICK_LABEL_SIZE)
    ax.yaxis.set_major_formatter(EngFormatter(places=0))
    grid_y(ax)
    ax.grid(axis='y', which='minor', color='#e0e0e0', lw=0.2, zorder=0)
    clean_spines(ax)
    if legend:
        ax.legend(loc='upper left', **LEGEND_KWARGS)


# ---------------------------------------------------------------------------
# Parquet export
# ---------------------------------------------------------------------------

def stats_to_dataframe(stats_2hop: dict, stats_3hop: dict) -> pd.DataFrame:
    """
    Convert intermediate-node stats for both hop counts into a tidy DataFrame.

    Columns: kg_name, hop_count, category, count, total_intermediates, unique_types
    One row per (kg_name, hop_count, category) combination.
    """
    rows = []
    for hop_count, stats in [(2, stats_2hop), (3, stats_3hop)]:
        for kg_name, kg_stats in stats.items():
            all_counts = kg_stats.get('counts', {})
            total = kg_stats.get('total', 0)
            unique_types = kg_stats.get('unique_types', 0)
            for category, count in all_counts.items():
                rows.append({
                    'kg_name': kg_name,
                    'hop_count': hop_count,
                    'category': category,
                    'count': count,
                    'total_intermediates': total,
                    'unique_types': unique_types,
                })
    return pd.DataFrame(rows, columns=[
        'kg_name', 'hop_count', 'category', 'count',
        'total_intermediates', 'unique_types',
    ])


def save_figure_data(stats_2hop: dict, stats_3hop: dict, out_dir: str) -> None:
    """Save all data used for figure generation as a parquet file."""
    df = stats_to_dataframe(stats_2hop, stats_3hop)
    out_path = join_path(out_dir, 'intermediate_node_2v3hop.parquet')
    save_parquet(df, out_path)
    print(f'✓ Saved figure data ({len(df):,} rows) to {out_path}')


# ---------------------------------------------------------------------------
# Main figure
# ---------------------------------------------------------------------------

def plot_intermediate_node_comparison(
    stats_2hop: dict,
    stats_3hop: dict,
) -> None:
    """
    Create a two-panel figure comparing intermediate node distributions for
    2-hop and 3-hop paths side by side and save to VIZ_DIR.
    """
    apply_style()
    fig, (ax_left, ax_right) = plt.subplots(
        1, 2, figsize=figsize(PAGE_WIDTH_IN, 4.5)
    )

    plot_barplot_ax(
        ax_left, stats_2hop,
        'Key biological nodes as intermediate entities — 2-hop paths',
        legend=True,
        show_ylabel=True,
    )
    plot_barplot_ax(
        ax_right, stats_3hop,
        'Key biological nodes as intermediate entities — 3-hop paths',
        legend=False,
        show_ylabel=False,
    )

    fig.tight_layout()

    ensure_local_dir(VIZ_DIR)
    save_fig(fig, join_path(VIZ_DIR, 'intermediate_node_2v3hop.pdf'))
    save_figure(fig, join_path(VIZ_DIR, 'intermediate_node_2v3hop.png'))
    save_figure(fig, join_path(VIZ_DIR, 'intermediate_node_2v3hop.svg'))
    plt.close(fig)


def _df_to_stats(df: pd.DataFrame) -> dict:
    """
    Convert a tidy DataFrame (as saved by save_figure_data) for a single hop
    count into the stats dict expected by plot_barplot_ax.

    Input columns: kg_name, category, count, total_intermediates, unique_types
    Output: {kg_name: {'counts': {category: count, ...}, 'total': int, 'unique_types': int}}
    """
    stats = {}
    for kg_name, group in df.groupby('kg_name'):
        stats[kg_name] = {
            'counts': dict(zip(group['category'], group['count'])),
            'total': int(group['total_intermediates'].iloc[0]) if len(group) else 0,
            'unique_types': int(group['unique_types'].iloc[0]) if len(group) else 0,
        }
    return stats


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    ensure_local_dir(VIZ_DIR)

    stats_2hop = analyze_intermediate_nodes(SOP_2HOP_PATH, n_hops=2)
    stats_3hop = analyze_intermediate_nodes(SOP_3HOP_PATH, n_hops=3)

    save_figure_data(stats_2hop, stats_3hop, VIZ_DIR)
    plot_intermediate_node_comparison(stats_2hop, stats_3hop)

if __name__ == '__main__':
    main()
