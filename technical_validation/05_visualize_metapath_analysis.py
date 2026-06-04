"""
Visualization Script for Metapath Analysis

Creates publication-quality figures demonstrating:
1. Metapath diversity across KGs
2. Cross-source path breakdown
3. Example cross-source paths for selected drug-disease pairs
"""

import io
import os
import polars as pl
import json
import ijson
import gcsfs
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from matplotlib.ticker import EngFormatter
from pathlib import Path
from tqdm import tqdm

# Set publication-quality style
sns.set_style("whitegrid")
plt.rcParams['figure.dpi'] = 300
plt.rcParams['font.size'] = 10
plt.rcParams['font.family'] = 'sans-serif'

# Paths (local or gs://)
OUTPUT_DIR = '/Users/piotrkaniewski/work/ec-kg-analysis/data/sop_no_filtered_kg/output'
SOP_PATH = '/Users/piotrkaniewski/work/ec-kg-analysis/data/sop_no_filtered_kg/prm/'
VIZ_DIR = '/Users/piotrkaniewski/work/ec-kg-analysis/visualizations/metapath_analysis'

KG_FILES = {
    'PrimeKG': 'primekg_sop.json',
    'Robokop': 'robokop_sop.json',
    'RTX-KG2': 'rtx_kg2_sop.json',
    'EC-KG': 'integrated_kg_sop.json',
}

_gcs_fs = None


def is_gcs_path(path):
    return isinstance(path, str) and path.startswith('gs://')


def get_gcs_fs():
    global _gcs_fs
    if _gcs_fs is None:
        _gcs_fs = gcsfs.GCSFileSystem()
    return _gcs_fs


def open_binary(path, mode='rb'):
    if is_gcs_path(path):
        return get_gcs_fs().open(path, mode)
    return open(path, mode)


def open_text(path, mode='r', encoding='utf-8'):
    if is_gcs_path(path):
        return get_gcs_fs().open(path, mode, encoding=encoding)
    return open(path, mode, encoding=encoding)


def join_storage_path(base, *parts):
    if is_gcs_path(base):
        return '/'.join([base.rstrip('/'), *parts])
    return os.path.join(base, *parts)


def ensure_viz_dir():
    if not is_gcs_path(VIZ_DIR):
        Path(VIZ_DIR).mkdir(parents=True, exist_ok=True)


def save_figure(filename, dpi=300, bbox_inches='tight', **kwargs):
    """Save current matplotlib figure to local path or GCS."""
    path = join_storage_path(VIZ_DIR, filename)
    if is_gcs_path(path):
        buf = io.BytesIO()
        fmt = Path(filename).suffix.lstrip('.') or 'png'
        plt.savefig(buf, format=fmt, dpi=dpi, bbox_inches=bbox_inches, **kwargs)
        buf.seek(0)
        with get_gcs_fs().open(path, 'wb') as f:
            f.write(buf.getvalue())
    else:
        plt.savefig(path, dpi=dpi, bbox_inches=bbox_inches, **kwargs)


def get_sop_path(kg_name):
    return join_storage_path(SOP_PATH, KG_FILES[kg_name])


def iter_sop_pairs(sop_path):
    with open_binary(sop_path, 'rb') as f:
        for pair_key, pair_data in ijson.kvitems(f, ''):
            yield pair_key, pair_data


def load_data():
    """Load analysis results from local path or GCS."""
    metapath_df = pl.read_csv(join_storage_path(OUTPUT_DIR, 'metapath_diversity.csv'))
    cross_source_df = pl.read_csv(join_storage_path(OUTPUT_DIR, 'cross_source_pair_stats.csv'))

    with open_text(join_storage_path(OUTPUT_DIR, 'metapath_analysis_summary.json'), 'r') as f:
        summary = json.load(f)

    return metapath_df, cross_source_df, summary


def _normalize_intermediate_category(cat):
    if isinstance(cat, list):
        cat_str = cat[0] if cat else 'Unknown'
    elif cat is None:
        cat_str = 'Unknown'
    else:
        cat_str = cat
    return cat_str.replace('biolink:', '')


def analyze_intermediate_nodes_for_kg(kg_name, sop_path=None):
    """Stream SOP JSON for one KG and count intermediate node categories."""
    from collections import Counter

    sop_path = sop_path or get_sop_path(kg_name)
    print(f"  Processing {kg_name} from {sop_path}...")
    all_intermediates = []

    for _pair_key, pair_data in tqdm(iter_sop_pairs(sop_path), desc=f"  {kg_name} pairs"):
        for path_meta in pair_data.get('paths_metadata', []):
            node_cats = path_meta.get('node_categories', [])
            if len(node_cats) < 3:
                continue
            for cat in node_cats[1:-1]:
                all_intermediates.append(_normalize_intermediate_category(cat))

    intermediate_counts = Counter(all_intermediates)
    print(f"    Total intermediate nodes: {len(all_intermediates):,}")
    print(f"    Unique node types: {len(intermediate_counts)}")

    return {
        'counts': dict(intermediate_counts),
        'total': len(all_intermediates),
        'unique_types': len(intermediate_counts),
    }


def analyze_intermediate_nodes():
    """
    Analyze intermediate node categories across all paths in each KG.
    Intermediate nodes are all nodes except the first (drug) and last (disease).
    """
    print("\nAnalyzing intermediate node distributions...")
    intermediate_stats = {}
    for kg_name in KG_FILES:
        intermediate_stats[kg_name] = analyze_intermediate_nodes_for_kg(kg_name)
    return intermediate_stats


def plot_metapath_diversity(metapath_df, summary):
    """
    Create bar chart showing unique metapath types per KG.
    Highlights metapaths unique to Integrated-KG.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # Plot 1: Total unique metapaths per KG
    kg_names = ['PrimeKG', 'Robokop', 'RTX-KG2', 'Integrated-KG']
    unique_counts = []
    
    for kg in kg_names:
        count = metapath_df.filter(pl.col('kg') == kg)['metapath'].n_unique()
        unique_counts.append(count)
    
    colors = ['#7fc97f', '#beaed4', '#fdc086', '#386cb0']
    bars = ax1.bar(kg_names, unique_counts, color=colors, alpha=0.8, edgecolor='black')
    
    # Add value labels on bars
    for bar, count in zip(bars, unique_counts):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(count):,}',
                ha='center', va='bottom', fontweight='bold')
    
    ax1.set_ylabel('Number of Unique Metapath Types', fontsize=11, fontweight='bold')
    ax1.set_xlabel('Knowledge Graph', fontsize=11, fontweight='bold')
    ax1.set_title('A. Metapath Diversity Across KGs', fontsize=12, fontweight='bold', pad=15)
    ax1.tick_params(axis='x', rotation=45)
    
    # Plot 2: Metapath uniqueness breakdown for Integrated-KG
    integrated_stats = summary['metapath_diversity']['integrated_kg']
    unique_to_integrated = integrated_stats['metapaths_unique_to_integrated']
    shared_with_sources = integrated_stats['metapaths_shared_with_sources']
    
    labels = ['Unique to\nIntegrated-KG', 'Shared with\nSource KGs']
    sizes = [unique_to_integrated, shared_with_sources]
    colors_pie = ['#d62728', '#2ca02c']
    explode = (0.1, 0)
    
    wedges, texts, autotexts = ax2.pie(
        sizes, 
        explode=explode, 
        labels=labels,
        colors=colors_pie,
        autopct='%1.1f%%',
        startangle=90,
        textprops={'fontsize': 10, 'fontweight': 'bold'}
    )
    
    # Make percentage text white for better visibility
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(11)
    
    ax2.set_title('B. Integrated-KG Metapath Composition', 
                  fontsize=12, fontweight='bold', pad=15)
    
    plt.tight_layout()
    save_figure('metapath_diversity.png', dpi=300, bbox_inches='tight')
    save_figure('metapath_diversity.svg', bbox_inches='tight')
    print(f"✓ Saved metapath diversity plot")
    plt.close()


def plot_cross_source_breakdown(summary):
    """
    Create detailed breakdown of cross-source vs. single-source paths.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    cross_source_data = summary['cross_source_analysis']
    total = cross_source_data['total_paths']
    cross = cross_source_data['cross_source_paths']
    single = cross_source_data['single_source_paths']
    
    # Plot 1: Overall cross-source fraction
    labels = ['Cross-Source\n(≥2 KGs)', 'Single-Source\n(1 KG)']
    sizes = [cross, single]
    colors = ['#ff7f0e', '#1f77b4']
    explode = (0.05, 0)
    
    wedges, texts, autotexts = ax1.pie(
        sizes,
        explode=explode,
        labels=labels,
        colors=colors,
        autopct=lambda pct: f'{pct:.1f}%\n({int(pct*total/100):,} paths)',
        startangle=90,
        textprops={'fontsize': 9, 'fontweight': 'bold'}
    )
    
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(10)
    
    ax1.set_title('A. Path Source Distribution', 
                  fontsize=12, fontweight='bold', pad=15)
    
    # Plot 2: Source combination breakdown (top 10)
    source_combos = cross_source_data['source_combinations']
    
    # Separate single-source and cross-source
    single_combos = {k: v for k, v in source_combos.items() if k.startswith('Single:')}
    cross_combos = {k: v for k, v in source_combos.items() if k.startswith('Cross:')}
    
    # Get top combinations
    all_combos = sorted(source_combos.items(), key=lambda x: x[1], reverse=True)[:10]
    combo_labels = [k.replace('Single:', '').replace('Cross:', '') for k, v in all_combos]
    combo_counts = [v for k, v in all_combos]
    
    # Color by type
    combo_colors = ['#1f77b4' if k.startswith('Single:') else '#ff7f0e' 
                    for k, v in all_combos]
    
    bars = ax2.barh(range(len(combo_labels)), combo_counts, color=combo_colors, alpha=0.8, edgecolor='black')
    
    # Add value labels
    for i, (bar, count) in enumerate(zip(bars, combo_counts)):
        width = bar.get_width()
        pct = 100 * count / total
        ax2.text(width, bar.get_y() + bar.get_height()/2.,
                f' {count:,} ({pct:.1f}%)',
                ha='left', va='center', fontsize=9, fontweight='bold')
    
    ax2.set_yticks(range(len(combo_labels)))
    ax2.set_yticklabels(combo_labels, fontsize=9)
    ax2.set_xlabel('Number of Paths', fontsize=11, fontweight='bold')
    ax2.set_title('B. Top Source Combinations', fontsize=12, fontweight='bold', pad=15)
    ax2.invert_yaxis()
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#1f77b4', alpha=0.8, edgecolor='black', label='Single Source'),
        Patch(facecolor='#ff7f0e', alpha=0.8, edgecolor='black', label='Cross-Source')
    ]
    ax2.legend(handles=legend_elements, loc='lower right', fontsize=9)
    
    plt.tight_layout()
    save_figure('cross_source_breakdown.png', dpi=300, bbox_inches='tight')
    save_figure('cross_source_breakdown.svg', bbox_inches='tight')
    print(f"✓ Saved cross-source breakdown plot")
    plt.close()


def plot_pair_level_stats(cross_source_df):
    """
    Plot distribution of cross-source fractions at pair level.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    fractions = cross_source_df['fraction_cross_source'].to_numpy()
    
    # Plot 1: Histogram
    ax1.hist(fractions, bins=30, color='#2ca02c', alpha=0.7, edgecolor='black')
    ax1.axvline(np.mean(fractions), color='red', linestyle='--', linewidth=2, label=f'Mean: {np.mean(fractions):.3f}')
    ax1.axvline(np.median(fractions), color='blue', linestyle='--', linewidth=2, label=f'Median: {np.median(fractions):.3f}')
    
    ax1.set_xlabel('Fraction Cross-Source Paths', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Number of Drug-Disease Pairs', fontsize=11, fontweight='bold')
    ax1.set_title('A. Distribution of Cross-Source Fractions', fontsize=12, fontweight='bold', pad=15)
    ax1.legend(loc='upper left', fontsize=9)
    ax1.grid(axis='y', alpha=0.3)
    
    # Plot 2: CDF
    sorted_fractions = np.sort(fractions)
    cumulative = np.arange(1, len(sorted_fractions) + 1) / len(sorted_fractions)
    
    ax2.plot(sorted_fractions, cumulative, linewidth=2, color='#9467bd')
    ax2.fill_between(sorted_fractions, 0, cumulative, alpha=0.3, color='#9467bd')
    
    # Add reference lines
    ax2.axvline(0.5, color='red', linestyle='--', alpha=0.5, linewidth=1.5, label='50% cross-source')
    
    # Calculate percentage of pairs above 50%
    pct_above_50 = 100 * np.sum(fractions >= 0.5) / len(fractions)
    ax2.text(0.5, 0.05, f'{pct_above_50:.1f}% of pairs\n≥50% cross-source',
             fontsize=9, fontweight='bold', ha='center',
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, edgecolor='red'))
    
    ax2.set_xlabel('Fraction Cross-Source Paths', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Cumulative Fraction of Pairs', fontsize=11, fontweight='bold')
    ax2.set_title('B. Cumulative Distribution', fontsize=12, fontweight='bold', pad=15)
    ax2.legend(loc='lower right', fontsize=9)
    ax2.grid(alpha=0.3)
    
    plt.tight_layout()
    save_figure('pair_level_cross_source_distribution.png', dpi=300, bbox_inches='tight')
    save_figure('pair_level_cross_source_distribution.svg', bbox_inches='tight')
    print(f"✓ Saved pair-level statistics plot")
    plt.close()


def plot_top_metapaths(metapath_df):
    """
    Show top metapaths for each KG, highlighting uniqueness.
    """
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()
    
    kg_names = ['PrimeKG', 'Robokop', 'RTX-KG2', 'Integrated-KG']
    
    for i, kg in enumerate(kg_names):
        ax = axes[i]
        
        # Get top 15 metapaths for this KG
        kg_data = metapath_df.filter(pl.col('kg') == kg)
        top_metapaths = (kg_data
                        .group_by('metapath')
                        .agg(pl.col('count').sum())
                        .sort('count', descending=True)
                        .head(15))
        
        metapaths = top_metapaths['metapath'].to_list()
        counts = top_metapaths['count'].to_list()
        
        # For Integrated-KG, color by uniqueness
        if kg == 'Integrated-KG':
            colors = []
            for mp in metapaths:
                is_unique = kg_data.filter(pl.col('metapath') == mp)['is_unique_to_integrated'].max()
                colors.append('#d62728' if is_unique else '#2ca02c')
        else:
            colors = ['#7fc97f'] * len(metapaths)
        
        # Truncate long metapath names
        display_names = [mp[:60] + '...' if len(mp) > 60 else mp for mp in metapaths]
        
        bars = ax.barh(range(len(display_names)), counts, color=colors, alpha=0.8, edgecolor='black')
        
        # Add value labels
        for j, (bar, count) in enumerate(zip(bars, counts)):
            width = bar.get_width()
            ax.text(width, bar.get_y() + bar.get_height()/2.,
                   f' {count:,}',
                   ha='left', va='center', fontsize=7, fontweight='bold')
        
        ax.set_yticks(range(len(display_names)))
        ax.set_yticklabels(display_names, fontsize=7)
        ax.set_xlabel('Path Count', fontsize=9, fontweight='bold')
        ax.set_title(f'{kg} - Top 15 Metapaths', fontsize=10, fontweight='bold', pad=10)
        ax.invert_yaxis()
        
        # Add legend for Integrated-KG
        if kg == 'Integrated-KG':
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor='#d62728', alpha=0.8, edgecolor='black', label='Unique to Integrated'),
                Patch(facecolor='#2ca02c', alpha=0.8, edgecolor='black', label='Shared with Sources')
            ]
            ax.legend(handles=legend_elements, loc='lower right', fontsize=7)
    
    plt.tight_layout()
    save_figure('top_metapaths_per_kg.png', dpi=300, bbox_inches='tight')
    save_figure('top_metapaths_per_kg.svg', bbox_inches='tight')
    print(f"✓ Saved top metapaths plot")
    plt.close()


def create_summary_figure(summary):
    """
    Create a single comprehensive summary figure with key metrics.
    """
    fig = plt.figure(figsize=(14, 8))
    gs = fig.add_gridspec(3, 3, hspace=0.4, wspace=0.4)
    
    # Title
    fig.suptitle('Integrated Knowledge Graph: Quality and Novelty Metrics', 
                 fontsize=16, fontweight='bold', y=0.98)
    
    # Metric 1: Total Metapaths
    ax1 = fig.add_subplot(gs[0, 0])
    integrated_metapaths = summary['metapath_diversity']['integrated_kg']['unique_metapaths']
    ax1.text(0.5, 0.5, f"{integrated_metapaths:,}", 
            ha='center', va='center', fontsize=36, fontweight='bold', color='#386cb0')
    ax1.text(0.5, 0.15, "Unique Metapath\nTypes in Integrated-KG",
            ha='center', va='center', fontsize=10, fontweight='bold')
    ax1.axis('off')
    
    # Metric 2: Unique to Integrated
    ax2 = fig.add_subplot(gs[0, 1])
    unique_metapaths = summary['metapath_diversity']['integrated_kg']['metapaths_unique_to_integrated']
    ax2.text(0.5, 0.5, f"{unique_metapaths:,}",
            ha='center', va='center', fontsize=36, fontweight='bold', color='#d62728')
    ax2.text(0.5, 0.15, "Metapaths Unique to\nIntegrated-KG",
            ha='center', va='center', fontsize=10, fontweight='bold')
    ax2.axis('off')
    
    # Metric 3: Cross-Source Fraction
    ax3 = fig.add_subplot(gs[0, 2])
    cross_frac = summary['cross_source_analysis']['cross_source_fraction']
    ax3.text(0.5, 0.5, f"{100*cross_frac:.1f}%",
            ha='center', va='center', fontsize=36, fontweight='bold', color='#ff7f0e')
    ax3.text(0.5, 0.15, "Paths Requiring\nMultiple Source KGs",
            ha='center', va='center', fontsize=10, fontweight='bold')
    ax3.axis('off')
    
    # Metric 4: Total Paths
    ax4 = fig.add_subplot(gs[1, :])
    kg_names = ['PrimeKG', 'Robokop', 'RTX-KG2', 'Integrated-KG']
    path_counts = []
    for kg in kg_names:
        if kg == 'Integrated-KG':
            count = summary['cross_source_analysis']['total_paths']
        else:
            count = summary['metapath_diversity']['source_kgs'][kg]['total_paths']
        path_counts.append(count)
    
    colors = ['#7fc97f', '#beaed4', '#fdc086', '#386cb0']
    bars = ax4.bar(kg_names, path_counts, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
    
    for bar, count in zip(bars, path_counts):
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., height,
                f'{count:,}',
                ha='center', va='bottom', fontweight='bold', fontsize=11)
    
    ax4.set_ylabel('Total Number of Paths', fontsize=12, fontweight='bold')
    ax4.set_title('Total Path Count by Knowledge Graph', fontsize=13, fontweight='bold', pad=15)
    ax4.tick_params(axis='x', rotation=45)
    ax4.grid(axis='y', alpha=0.3)
    
    # Bottom panel: Key takeaways
    ax5 = fig.add_subplot(gs[2, :])
    ax5.axis('off')
    
    takeaways = [
        f"✓ Integration creates {unique_metapaths} new metapath types not present in any source KG",
        f"✓ {100*cross_frac:.1f}% of paths genuinely integrate multiple sources (cross-source paths)",
        f"✓ Integrated-KG supports {integrated_metapaths:,} distinct metapath types"
    ]
    
    takeaway_text = "\n".join(takeaways)
    ax5.text(0.5, 0.5, takeaway_text,
            ha='center', va='center', fontsize=11, fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.3, pad=1))
    
    save_figure('summary_figure.png', dpi=300, bbox_inches='tight')
    save_figure('summary_figure.svg', bbox_inches='tight')
    print(f"✓ Saved summary figure")
    plt.close()


def plot_intermediate_node_distribution(intermediate_stats):
    """
    Create visualizations showing intermediate node type distributions across KGs.
    """
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    kg_names = ['PrimeKG', 'Robokop', 'RTX-KG2', 'Integrated-KG']
    colors_kg = ['#7fc97f', '#beaed4', '#fdc086', '#386cb0']
    
    # Get all unique node types across all KGs
    all_node_types = set()
    for stats in intermediate_stats.values():
        all_node_types.update(stats['counts'].keys())
    
    # Get top node types by total count across all KGs
    type_totals = {}
    for node_type in all_node_types:
        total = sum(stats['counts'].get(node_type, 0) for stats in intermediate_stats.values())
        type_totals[node_type] = total
    
    top_types = sorted(type_totals.items(), key=lambda x: x[1], reverse=True)[:15]
    top_type_names = [t[0] for t in top_types]
    
    # Plot 1: Stacked bar chart (absolute counts)
    ax1 = axes[0, 0]
    
    # Prepare data for stacked bars
    data_matrix = []
    for node_type in top_type_names:
        row = [intermediate_stats[kg]['counts'].get(node_type, 0) for kg in kg_names]
        data_matrix.append(row)
    
    data_matrix = np.array(data_matrix)
    
    # Create stacked bars
    bottom = np.zeros(len(kg_names))
    
    # Use a colormap for node types
    cmap = plt.cm.get_cmap('tab20')
    node_colors = [cmap(i / len(top_type_names)) for i in range(len(top_type_names))]
    
    for i, node_type in enumerate(top_type_names):
        ax1.bar(kg_names, data_matrix[i], bottom=bottom, label=node_type, 
               color=node_colors[i], alpha=0.8, edgecolor='white', linewidth=0.5)
        bottom += data_matrix[i]
    
    ax1.set_ylabel('Number of Intermediate Nodes', fontsize=11, fontweight='bold')
    ax1.set_title('A. Intermediate Node Types by KG (Absolute Counts)', 
                  fontsize=12, fontweight='bold', pad=15)
    ax1.tick_params(axis='x', rotation=45)
    ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8, ncol=1)
    ax1.grid(axis='y', alpha=0.3)
    ax1.yaxis.set_major_formatter(EngFormatter())
    
    # Plot 2: Stacked bar chart (percentage)
    ax2 = axes[0, 1]
    
    # Calculate percentages
    totals = np.sum(data_matrix, axis=0)
    data_matrix_pct = (data_matrix / totals) * 100
    
    bottom = np.zeros(len(kg_names))
    for i, node_type in enumerate(top_type_names):
        ax2.bar(kg_names, data_matrix_pct[i], bottom=bottom, label=node_type,
               color=node_colors[i], alpha=0.8, edgecolor='white', linewidth=0.5)
        bottom += data_matrix_pct[i]
    
    ax2.set_ylabel('Percentage of Intermediate Nodes', fontsize=11, fontweight='bold')
    ax2.set_title('B. Intermediate Node Types by KG (Percentage)', 
                  fontsize=12, fontweight='bold', pad=15)
    ax2.tick_params(axis='x', rotation=45)
    ax2.set_ylim(0, 100)
    ax2.grid(axis='y', alpha=0.3)
    
    # Plot 3: Top node types comparison (horizontal bars)
    ax3 = axes[1, 0]
    
    # For each top node type, show count across KGs
    top_5_types = top_type_names[:5]
    x = np.arange(len(top_5_types))
    width = 0.2
    
    for i, kg in enumerate(kg_names):
        counts = [intermediate_stats[kg]['counts'].get(t, 0) for t in top_5_types]
        offset = (i - 1.5) * width
        ax3.bar(x + offset, counts, width, label=kg, color=colors_kg[i], 
               alpha=0.8, edgecolor='black', linewidth=0.5)
    
    ax3.set_xlabel('Node Type', fontsize=11, fontweight='bold')
    ax3.set_ylabel('Count', fontsize=11, fontweight='bold')
    ax3.set_title('C. Top 5 Intermediate Node Types Across KGs', 
                  fontsize=12, fontweight='bold', pad=15)
    ax3.set_xticks(x)
    ax3.set_xticklabels(top_5_types, rotation=45, ha='right', fontsize=9)
    ax3.legend(fontsize=9, loc='upper right')
    ax3.grid(axis='y', alpha=0.3)
    
    # Plot 4: Heatmap of top node types
    ax4 = axes[1, 1]
    
    # Create heatmap data
    heatmap_data = []
    for node_type in top_type_names[:12]:  # Top 12 for better visibility
        row = [intermediate_stats[kg]['counts'].get(node_type, 0) for kg in kg_names]
        heatmap_data.append(row)
    
    heatmap_data = np.array(heatmap_data)
    
    # Normalize by row for better color scale
    heatmap_data_norm = heatmap_data / (heatmap_data.max(axis=1, keepdims=True) + 1e-10)
    
    im = ax4.imshow(heatmap_data_norm, cmap='YlOrRd', aspect='auto')
    
    # Set ticks
    ax4.set_xticks(np.arange(len(kg_names)))
    ax4.set_yticks(np.arange(len(top_type_names[:12])))
    ax4.set_xticklabels(kg_names, rotation=45, ha='right', fontsize=9)
    ax4.set_yticklabels(top_type_names[:12], fontsize=8)
    
    # Add count annotations
    for i in range(len(top_type_names[:12])):
        for j in range(len(kg_names)):
            count = heatmap_data[i, j]
            if count > 0:
                text_color = 'white' if heatmap_data_norm[i, j] > 0.5 else 'black'
                ax4.text(j, i, f'{int(count):,}', ha='center', va='center',
                        color=text_color, fontsize=7, fontweight='bold')
    
    ax4.set_title('D. Heatmap: Node Type Usage Across KGs', 
                  fontsize=12, fontweight='bold', pad=15)
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax4, fraction=0.046, pad=0.04)
    cbar.set_label('Normalized Count', fontsize=9, fontweight='bold')
    
    plt.tight_layout()
    save_figure('intermediate_node_distribution.png', dpi=300, bbox_inches='tight')
    save_figure('intermediate_node_distribution.svg', bbox_inches='tight')
    print(f"✓ Saved intermediate node distribution plot")
    plt.close()


def plot_intermediate_node_comparison(intermediate_stats):
    """
    Create focused comparison of Gene/Protein usage as intermediate nodes.
    Gene and Protein are combined into a single category.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    kg_names = ['PrimeKG', 'Robokop', 'RTX-KG2', 'EC-KG']
    colors_kg = ['#7fc97f', '#beaed4', '#fdc086', '#386cb0']
    
    # Categories of interest - Gene/Protein combined
    categories_of_interest = ['Gene/Protein', 'BiologicalProcess', 'Pathway', 
                              'MolecularActivity', 'CellularComponent', 'Anatomy']
    
    # Plot 1: Absolute counts for key biological entities
    ax1_data = {}
    for cat in categories_of_interest:
        counts = []
        for kg in kg_names:
            if cat == 'Gene/Protein':
                # Combine Gene and Protein counts
                gene_count = intermediate_stats[kg]['counts'].get('Gene', 0)
                protein_count = intermediate_stats[kg]['counts'].get('Protein', 0)
                count = gene_count + protein_count
            else:
                count = intermediate_stats[kg]['counts'].get(cat, 0)
            counts.append(count)
        ax1_data[cat] = counts
    
    x = np.arange(len(kg_names))
    width = 0.14
    
    for i, cat in enumerate(categories_of_interest):
        offset = (i - len(categories_of_interest)/2) * width
        bars = ax1.bar(x + offset, ax1_data[cat], width, label=cat, alpha=0.8, edgecolor='black', linewidth=0.5)
    
    ax1.set_xlabel('Knowledge Graph', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Number of Intermediate Nodes', fontsize=11, fontweight='bold')
    ax1.set_title('A. Key Biological Entities as Intermediate Nodes', 
                  fontsize=12, fontweight='bold', pad=15)
    ax1.set_xticks(x)
    ax1.set_xticklabels(kg_names, rotation=45, ha='right')
    ax1.legend(fontsize=8, loc='upper left', ncol=2)
    ax1.grid(axis='y', alpha=0.3)
    ax1.yaxis.set_major_formatter(EngFormatter())
    
    # Plot 2: Gene/Protein dominance (combined)
    ax2_data = []
    labels = []
    
    for kg in kg_names:
        gene_count = intermediate_stats[kg]['counts'].get('Gene', 0)
        protein_count = intermediate_stats[kg]['counts'].get('Protein', 0)
        gene_protein_combined = gene_count + protein_count
        total = intermediate_stats[kg]['total']
        
        gene_protein_pct = 100 * gene_protein_combined / total if total > 0 else 0
        other_pct = 100 - gene_protein_pct
        
        ax2_data.append([gene_protein_pct, other_pct])
        labels.append(kg)
    
    ax2_data = np.array(ax2_data)
    
    bottom = np.zeros(len(kg_names))
    category_labels = ['Gene/Protein', 'Other']
    category_colors = ['#2ca02c', '#d3d3d3']
    
    for i, (cat_label, color) in enumerate(zip(category_labels, category_colors)):
        bars = ax2.bar(kg_names, ax2_data[:, i], bottom=bottom, label=cat_label,
                      color=color, alpha=0.8, edgecolor='black', linewidth=1)
        
        # Add percentage labels
        for j, (bar, val) in enumerate(zip(bars, ax2_data[:, i])):
            if val > 3:  # Only show if > 3%
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., bottom[j] + height/2.,
                        f'{val:.1f}%', ha='center', va='center', 
                        fontweight='bold', fontsize=9, color='white' if i < 1 else 'black')
        
        bottom += ax2_data[:, i]
    
    ax2.set_xlabel('Knowledge Graph', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Percentage of Intermediate Nodes', fontsize=11, fontweight='bold')
    ax2.set_title('B. Gene/Protein Dominance in Intermediate Nodes', 
                  fontsize=12, fontweight='bold', pad=15)
    ax2.tick_params(axis='x', rotation=45)
    ax2.set_ylim(0, 100)
    ax2.legend(fontsize=10, loc='upper right')
    ax2.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    save_figure('gene_protein_intermediate_comparison.png', dpi=300, bbox_inches='tight')
    save_figure('gene_protein_intermediate_comparison.svg', bbox_inches='tight')
    print(f"✓ Saved gene/protein intermediate comparison plot")
    plt.close()


def main():
    ensure_viz_dir()

    print("Loading analysis results...")
    print(f"  OUTPUT_DIR: {OUTPUT_DIR}")
    print(f"  SOP_PATH: {SOP_PATH}")
    print(f"  VIZ_DIR: {VIZ_DIR}")
    metapath_df, cross_source_df, summary = load_data()

    print("\nGenerating visualizations...")
    print("-" * 50)

    # plot_metapath_diversity(metapath_df, summary)
    # plot_cross_source_breakdown(summary)
    # plot_pair_level_stats(cross_source_df)
    # plot_top_metapaths(metapath_df)
    # create_summary_figure(summary)

    print("\nAnalyzing intermediate nodes...")
    intermediate_stats = analyze_intermediate_nodes()
    #plot_intermediate_node_distribution(intermediate_stats)
    plot_intermediate_node_comparison(intermediate_stats)
    
    print("-" * 50)
    print(f"\n✓ All visualizations saved to: {VIZ_DIR}")
    print("\nGenerated files:")
    print("  • metapath_diversity.png/.svg")
    print("  • cross_source_breakdown.png/.svg")
    print("  • pair_level_cross_source_distribution.png/.svg")
    print("  • top_metapaths_per_kg.png/.svg")
    print("  • summary_figure.png/.svg")
    print("  • intermediate_node_distribution.png/.svg")
    print("  • gene_protein_intermediate_comparison.png/.svg")


if __name__ == '__main__':
    main()
