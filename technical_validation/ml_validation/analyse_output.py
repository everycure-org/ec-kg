import sys
from pathlib import Path
import polars as pl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from typing import List, Tuple, Optional, Dict
from sklearn.metrics import f1_score

# Importing experimental evaluation suite
sys.path.append('/Users/piotrkaniewski/work/lab-notebooks/alexei/5_experimental_evaluation_suite_v0_1/src/')
sys.path.append(str(Path(__file__).parent))
from fig_style import (
    apply_style,
    figsize, grid_figsize,
    style_title, clean_spines, grid_y,
    LEGEND_KWARGS,
    TITLE_SIZE, AXIS_LABEL_SIZE, TICK_LABEL_SIZE, ANNOTATION_SIZE,
    PAGE_WIDTH_IN,
    savefig as save_fig,
)

BUCKET_NAME = 'mtrx-us-central1-hub-dev-storage'

# Okabe-Ito bluish-green (#009E73) chosen for EC-KG: maximally distinct from the
# Tableau cyan/blue/orange used by the three source KGs, and a standard member of
# both the Okabe-Ito and Tol colorblind-safe palettes.
KG_COLORS: Dict[str, str] = {
    "EC-KG":     "#009E73",
    "PrimeKG":   "#FF7F0E",
    "RobokopKG": "#17BECF",
    "RTX-KG":    "#1F77B4",
}

# Note: pathways are pointing to GCS as thats the data lake underlying MATRIX platform; modify if needed
KG_CONFIGS = {
    "EC-KG": {
        "run_path": "gs://mtrx-us-central1-hub-dev-storage/kedro/data/releases/v0.15.19/features_ec_kg/runs/ec-kg-rf-manuscript-0480a1c4/",
    },
    "PrimeKG": {
        "run_path": "gs://mtrx-us-central1-hub-dev-storage/kedro/data/releases/v0.15.19/features/runs/prime-rf-manuscript-99910688/",
    },
    "RobokopKG": {
        "run_path": "gs://mtrx-us-central1-hub-dev-storage/kedro/data/releases/v0.15.19/features_robokop/runs/robokop-rf-manuscript-1c29853c/",
    },
    "RTX-KG": {
        "run_path": "gs://mtrx-us-central1-hub-dev-storage/kedro/data/releases/v0.15.19/features_rtx/runs/rtx-rf-manuscript-f8ba5c90/",
    },
}


CACHE_DIR = Path(__file__).parent / ".matrix_cache"


def load_kg_matrices(run_path: str, n_folds: int = 5, cache: bool = True) -> List[pl.DataFrame]:
    """
    Load matrix predictions for all folds of a single KG run.

    On first call the data is downloaded from GCS and written to
    CACHE_DIR/<slug>/fold_<n>.parquet.  Subsequent calls read from disk,
    skipping the remote download entirely.

    Args:
        run_path: GCS prefix for the run (used both as download source and to
                  derive a stable cache key).
        n_folds:  Number of CV folds to load.
        cache:    Set to False to force a fresh download regardless of cache.
    """
    slug = run_path.rstrip("/").split("/")[-1]
    run_cache = CACHE_DIR / slug
    matrices = []

    for fold in range(n_folds):
        local_path = run_cache / f"fold_{fold}.parquet"

        if cache and local_path.exists():
            matrices.append(pl.read_parquet(local_path))
        else:
            remote_path = run_path + f"datasets/matrix_generation/model_output/fold_{fold}/matrix_predictions/"
            df = pl.read_parquet(remote_path)
            if cache:
                run_cache.mkdir(parents=True, exist_ok=True)
                df.write_parquet(local_path)
                print(f"  cached fold {fold} → {local_path}")
            matrices.append(df)

    return matrices

def give_hit_at_k(
        matrix : pl.DataFrame, k_max : int, bool_test_col : str = "is_known_positive", score_col : str = "treat score",
        ) -> pl.DataFrame:
    """
    Returns the hit@k score for a list of k values.

    Args:   
        matrix: Dataframe of drug-disease pairs with treat scores.
            Training set should have been taken out of the matrices.
        k_max: Maximum k value to compute hit@k for
        bool_test_col: Boolean column in the matrix indicating the known positive test set 
        score_col: Column in the matrix containing the treat scores.
    Returns:
        A dataframe with the hit@k scores and the k values.
    """
    # Restrict to test diseases
    test_diseases = matrix.group_by("target").agg(pl.col(bool_test_col).sum().alias("num_known_positives")).filter(pl.col("num_known_positives") > 0).select(pl.col("target")).to_series().to_list()
    matrix = matrix.filter(pl.col("target").is_in(test_diseases))

    # Add disease-specific ranks
    matrix = matrix.with_columns(disease_rank=pl.col(score_col).rank(descending=True, method="random").over("target"))

    #  Remove other positives from ranking
    matrix = matrix.filter(pl.col(bool_test_col)).with_columns(disease_rank_among_positives=pl.col(score_col).rank(descending=True, method="dense").over("target"))
    matrix = matrix.with_columns(disease_rank_against_negatives= pl.col("disease_rank") - pl.col("disease_rank_among_positives") + 1)

    # Count number of positives at each rank and cumulative sum
    ranks_for_test_set  = matrix.filter(pl.col(bool_test_col)).group_by("disease_rank_against_negatives").len().sort("disease_rank_against_negatives")
    ranks_for_test_set = ranks_for_test_set.with_columns(pl.col("len").cum_sum().alias("cumulative_len"))

    # Compute hit@k for each k
    df_hit_at_k = pl.DataFrame(
        {
            "k": ranks_for_test_set["disease_rank_against_negatives"], 
            "hit_at_k": ranks_for_test_set["cumulative_len"] / len(matrix.filter(pl.col(bool_test_col)))
        }
    )
    
    return df_hit_at_k.filter(pl.col("k") <= k_max)


def give_hit_at_k_folds(
        matrix_folds : List[pl.DataFrame], 
        k_max : int, 
        bool_test_col : str = "is_known_positive", 
        score_col : str = "treat score",
        ) -> Tuple[np.ndarray, np.ndarray]:
    """
    Returns the hit@k score for a list of k values over a list of folds.

    Args:
        matrix_folds: List of drug-disease treat score matrix dataframes for each fold
            Training set should have been taken out of the matrices.
        k_max: Maximum k value to compute hit@k for
        bool_test_col: Boolean column in the matrix indicating the known positive test set 
        score_col: Column in the matrix containing the treat scores.

    Returns:
        Tuple of two arrays:
            1. A 2d numpy array of the hit@k scores for the list of k values over the folds.
                The first dimension is the fold, the second is the k value.
            2. A numpy array of the k values.
    """
    # Compute Hit@k
    hit_at_k_folds = [give_hit_at_k(fold, k_max, bool_test_col=bool_test_col, score_col=score_col) for fold in matrix_folds]

    # Prepend value 0 for k=0
    hit_at_k_folds = [
        pl.concat([
            pl.DataFrame({"k": [0], "hit_at_k": [0]}).cast({"k": pl.UInt32, "hit_at_k": pl.Float64}),
            fold
        ])
        for fold in hit_at_k_folds
    ]
    # Join to fill missing k values
    hit_at_k_folds = [
        fold.join(pl.DataFrame({"k": list(range(0, k_max + 1))}).cast(pl.UInt32), on="k", how="right").fill_null(strategy="forward") 
        for fold in hit_at_k_folds
        ]
    
    k_lst = hit_at_k_folds[0]["k"].to_numpy()

    return np.array([fold["hit_at_k"].to_numpy() for fold in hit_at_k_folds]), k_lst
    

def give_average_hit_at_k_folds(
        matrix_folds : List[pl.DataFrame], 
        k_max : int, 
        bool_test_col : str = "is_known_positive", 
        score_col : str = "treat score"
    ) -> dict[str, np.ndarray]:
    """
    Returns the average and std (over folds) of the hit@k score for a list of k values.

    Args:
        matrix_folds: List of drug-disease treat score matrix dataframes for each fold
            Training set should have been taken out of the matrices.
        k_max: Maximum k value to compute hit@k for
        bool_test_col: Boolean column in the matrix indicating the known positive test set 
        score_col: Column in the matrix containing the treat scores.
    Returns:
        A dictionary with the average and std (over folds) of the hit@k scores and the k values.
    """
    all_hit_at_k_arr, k_lst = give_hit_at_k_folds(matrix_folds, k_max, bool_test_col=bool_test_col, score_col=score_col)
    # Compute average Hit@k
    return {
        "hit_at_k_mean": all_hit_at_k_arr.mean(axis=0),
        "hit_at_k_std": all_hit_at_k_arr.std(axis=0),
        "k": k_lst
    }

def give_f1_score(
    matrix: pl.DataFrame,
    bool_test_col_pos: str = "is_known_positive",
    bool_test_col_neg: str = "is_known_negative",
    score_col: str = "treat score",
    threshold: float = 0.5,
) -> float:
    """Return the F1 score for a single fold matrix."""
    ground_truth = matrix.filter(
        pl.col(bool_test_col_pos) | pl.col(bool_test_col_neg)
    ).select(bool_test_col_pos, score_col)
    return f1_score(ground_truth[bool_test_col_pos], ground_truth[score_col] > threshold)


def compute_f1_across_folds(
    matrices: List[pl.DataFrame],
    bool_test_col_pos: str = "is_known_positive",
) -> Dict:
    """Compute mean/std F1 score across all folds for a single KG."""
    scores = [give_f1_score(m, bool_test_col_pos=bool_test_col_pos) for m in matrices]
    return {"mean": np.mean(scores), "std": np.std(scores), "f1_scores": scores}


def save_f1_csv(results: Dict, label: str, suffix: str = "") -> None:
    """Persist per-fold F1 scores to CSV."""
    fname = f"f1_scores_{label.lower().replace('-', '')}{suffix}.csv"
    pd.DataFrame({"fold": range(len(results["f1_scores"])), "f1_score": results["f1_scores"]}).to_csv(fname, index=False)


def plot_f1_comparison(
    results: Dict[str, Dict],
    results_off: Dict[str, Dict],
    save_path: Optional[str] = None,
) -> None:
    """
    Barplot comparing standard vs off-label F1 scores across KGs.

    Each KG gets its own colour from KG_COLORS.  Standard bars are solid;
    off-label bars carry a hatch pattern so the two sets remain distinguishable
    in greyscale / for colour-blind readers.

    Args:
        results:     Per-KG F1 result dicts for the standard test set.
        results_off: Per-KG F1 result dicts for the off-label test set.
        save_path:   If set, save figure to this path (PDF).
    """
    apply_style()
    labels = list(results.keys())
    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=figsize(PAGE_WIDTH_IN, 4.5))

    for i, kg in enumerate(labels):
        color = KG_COLORS.get(kg, "#888888")
        m1, s1 = results[kg]["mean"],     results[kg]["std"]
        m2, s2 = results_off[kg]["mean"], results_off[kg]["std"]

        bar1 = ax.bar(i - width / 2, m1, width, yerr=s1,
                      color=color, edgecolor="black", linewidth=0.5,
                      capsize=4, zorder=2)
        bar2 = ax.bar(i + width / 2, m2, width, yerr=s2,
                      color=color, edgecolor="black", linewidth=0.5,
                      capsize=4, zorder=2, hatch="////", alpha=0.7)
        bar1[0].set_zorder(2)
        bar2[0].set_zorder(2)

        ax.text(i - width / 2, m1 + s1 + 0.02, f"{m1:.2f}±{s1:.2f}",
                ha="center", va="bottom", fontsize=ANNOTATION_SIZE)
        ax.text(i + width / 2, m2 + s2 + 0.02, f"{m2:.2f}±{s2:.2f}",
                ha="center", va="bottom", fontsize=ANNOTATION_SIZE)

    kg_handles = [
        mpatches.Patch(facecolor=KG_COLORS.get(kg, "#888888"), edgecolor="black",
                       linewidth=0.5, label=kg)
        for kg in labels
    ]
    style_handles = [
        mpatches.Patch(facecolor="white", edgecolor="black", linewidth=0.5, label="Standard"),
        mpatches.Patch(facecolor="white", edgecolor="black", linewidth=0.5,
                       hatch="////", label="Off-label"),
    ]
    ax.legend(handles=kg_handles + style_handles, ncol=2, **LEGEND_KWARGS)

    style_title(ax, "Standard vs Off-label Test Set Evaluation by KG")
    ax.set_ylabel("F1 Score", fontsize=AXIS_LABEL_SIZE)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Knowledge Graph", fontsize=AXIS_LABEL_SIZE)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=TICK_LABEL_SIZE)
    grid_y(ax)
    clean_spines(ax)
    fig.tight_layout()

    if save_path is not None:
        save_fig(fig, save_path)
    else:
        plt.show()
    plt.close(fig)


def plot_av_hit_at_k_horizontal_subplots(
    matrices_all: Tuple[List[pl.DataFrame], ...],
    model_names: Tuple[str, ...],
    bool_test_cols: Tuple[str, str] = ("ec_indications_list_off_label", "is_known_positive"),
    panel_titles: Tuple[str, str] = ("Off-label Set Evaluation", "Standard Test Set Evaluation"),
    ylabel: str = "Average disease-specific Hit@k",
    xlabel: str = "k",
    sup_title: Optional[str] = "Average Disease-Specific Hit@k vs k",
    k_max: int = 100,
    is_average_folds: bool = True,
    plot_error_bars: bool = True,
    force_full_y_axis: bool = True,
    save_path: Optional[str] = None,
    save_pdf_each_panel: bool = False
) -> None:
    """
    Two horizontal subplots of average Hit@k across folds for each model and label set.

    Args:
        matrices_all:        Tuple of per-fold matrix lists, one entry per model.
        model_names:         Model display names, aligned with matrices_all.
        bool_test_cols:      Boolean columns used for the two subplots.
        panel_titles:        Subplot titles aligned with bool_test_cols.
        ylabel:              Shared y-axis label.
        xlabel:              Shared x-axis label.
        sup_title:           Figure suptitle.
        k_max:               Maximum k for Hit@k curve.
        is_average_folds:    Average curves over CV folds.
        plot_error_bars:     Shade ±1 std around the mean curve.
        force_full_y_axis:   Fix y-axis to [0, 1].
        save_path:           If set, save figure to this path.
        save_pdf_each_panel: If True, also save each panel as a separate PDF.
    """
    assert len(bool_test_cols) == 2, "bool_test_cols must contain exactly two column names"
    assert len(panel_titles) == 2, "panel_titles must contain exactly two titles"
    number_of_drugs = min(
        len(matrix["source"].unique())
        for matrix_folds in matrices_all
        for matrix in (matrix_folds if is_average_folds else [matrix_folds])
    )

    apply_style()
    fig, axes = plt.subplots(1, 2, figsize=grid_figsize(1, 2), sharey=True)
    for idx, (ax, bool_test_col, panel_title) in enumerate(zip(axes, bool_test_cols, panel_titles)):
        for model_name, matrix_folds in zip(model_names, matrices_all):
            color = KG_COLORS.get(model_name, "#888888")
            if is_average_folds:
                d = give_average_hit_at_k_folds(matrix_folds, k_max, bool_test_col=bool_test_col)
                ax.plot(d["k"], d["hit_at_k_mean"], color=color, label=model_name)
                if plot_error_bars:
                    ax.fill_between(
                        d["k"], d["hit_at_k_mean"] - d["hit_at_k_std"],
                        d["hit_at_k_mean"] + d["hit_at_k_std"], color=color, alpha=0.2
                    )
            else:
                d = give_hit_at_k(matrix_folds, k_max, bool_test_col=bool_test_col)
                ax.plot(d["k"], d["hit_at_k"], color=color, label=model_name)

        ax.plot([0, number_of_drugs], [0, 1], "k--", label="Random classifier", alpha=0.5)
        style_title(ax, panel_title)
        ax.set_xlabel(xlabel, fontsize=AXIS_LABEL_SIZE)
        ax.set_xlim(0, k_max)
        if force_full_y_axis:
            ax.set_ylim(0, 1)
        grid_y(ax)
        clean_spines(ax)

        # Save individual panel as PDF if requested
        if save_pdf_each_panel:
            panel_pdf_name = f"{panel_title.lower().replace(' ', '_').replace('/', '_')}_hitatk_panel.pdf"
            panel_fig, panel_ax = plt.subplots(figsize=figsize(PAGE_WIDTH_IN, 4.5))
            for model_name, matrix_folds in zip(model_names, matrices_all):
                color = KG_COLORS.get(model_name, "#888888")
                if is_average_folds:
                    d = give_average_hit_at_k_folds(matrix_folds, k_max, bool_test_col=bool_test_col)
                    panel_ax.plot(d["k"], d["hit_at_k_mean"], color=color, label=model_name)
                    if plot_error_bars:
                        panel_ax.fill_between(
                            d["k"], d["hit_at_k_mean"] - d["hit_at_k_std"],
                            d["hit_at_k_mean"] + d["hit_at_k_std"], color=color, alpha=0.2
                        )
                else:
                    d = give_hit_at_k(matrix_folds, k_max, bool_test_col=bool_test_col)
                    panel_ax.plot(d["k"], d["hit_at_k"], color=color, label=model_name)
            panel_ax.plot([0, number_of_drugs], [0, 1], "k--", label="Random classifier", alpha=0.5)
            style_title(panel_ax, panel_title)
            panel_ax.set_xlabel(xlabel, fontsize=AXIS_LABEL_SIZE)
            if idx == 0:
                panel_ax.set_ylabel(ylabel, fontsize=AXIS_LABEL_SIZE)
            panel_ax.set_xlim(0, k_max)
            if force_full_y_axis:
                panel_ax.set_ylim(0, 1)
            grid_y(panel_ax)
            clean_spines(panel_ax)
            panel_ax.legend(loc="lower right", **LEGEND_KWARGS)
            panel_fig.tight_layout()
            save_fig(panel_fig, panel_pdf_name)
            plt.close(panel_fig)

    axes[0].set_ylabel(ylabel, fontsize=AXIS_LABEL_SIZE)
    axes[1].legend(loc="lower right", **LEGEND_KWARGS)
    plt.suptitle(sup_title, fontsize=TITLE_SIZE)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    if save_path is not None:
        save_fig(fig, save_path)
    plt.show()
    plt.close(fig)


def plot_combined_figure(
    results: Dict[str, Dict],
    results_off: Dict[str, Dict],
    matrices_all: Tuple,
    model_names: Tuple[str, ...],
    k_max: int = 100,
    plot_error_bars: bool = True,
    save_path: Optional[str] = None,
) -> None:
    """
    Three-panel stacked figure (all panels horizontal / full-width):

      panel a (top)    – F1 barplot; per-KG colours, standard solid, off-label hatched
      panel b (middle) – Average disease-specific Hit@k, standard test set
      panel c (bottom) – Average disease-specific Hit@k, off-label test set

    Args:
        results:         Per-KG F1 result dicts for the standard test set.
        results_off:     Per-KG F1 result dicts for the off-label test set.
        matrices_all:    Tuple of per-fold matrix lists, one entry per model.
        model_names:     Model display names, aligned with matrices_all.
        k_max:           Maximum k for Hit@k curves.
        plot_error_bars: Shade ±1 std around each mean curve.
        save_path:       If set, save figure to this path.
    """
    labels = list(results.keys())
    x = np.arange(len(labels))
    width = 0.35

    number_of_drugs = min(
        len(matrix["source"].unique())
        for matrix_folds in matrices_all
        for matrix in matrix_folds
    )

    apply_style()
    fig, (ax_bar, ax_std, ax_off) = plt.subplots(
        3, 1, figsize=grid_figsize(3, 1),
        gridspec_kw={"hspace": 0.75},
    )

    # ── Panel a: F1 barplot ───────────────────────────────────────────────
    for i, kg in enumerate(labels):
        color = KG_COLORS.get(kg, "#888888")
        m1, s1 = results[kg]["mean"],     results[kg]["std"]
        m2, s2 = results_off[kg]["mean"], results_off[kg]["std"]

        bar1 = ax_bar.bar(i - width / 2, m1, width, yerr=s1,
                          color=color, edgecolor="black", linewidth=0.5,
                          capsize=4, zorder=2)
        bar2 = ax_bar.bar(i + width / 2, m2, width, yerr=s2,
                          color=color, edgecolor="black", linewidth=0.5,
                          capsize=4, zorder=2, hatch="////", alpha=0.7)
        bar1[0].set_zorder(2)
        bar2[0].set_zorder(2)

        ax_bar.text(i - width / 2, m1 + s1 + 0.02, f"{m1:.2f}±{s1:.2f}",
                    ha="center", va="bottom", fontsize=ANNOTATION_SIZE)
        ax_bar.text(i + width / 2, m2 + s2 + 0.02, f"{m2:.2f}±{s2:.2f}",
                    ha="center", va="bottom", fontsize=ANNOTATION_SIZE)

    kg_handles = [
        mpatches.Patch(facecolor=KG_COLORS.get(kg, "#888888"), edgecolor="black",
                       linewidth=0.5, label=kg)
        for kg in labels
    ]
    style_handles = [
        mpatches.Patch(facecolor="white", edgecolor="black", linewidth=0.5, label="Standard"),
        mpatches.Patch(facecolor="white", edgecolor="black", linewidth=0.5,
                       hatch="////", label="Off-label"),
    ]
    ax_bar.legend(handles=kg_handles + style_handles, ncol=3,
                  bbox_to_anchor=(0.5, -0.18), loc="upper center", **LEGEND_KWARGS)
    style_title(ax_bar, "Standard vs Off-label Test Set Evaluation")
    ax_bar.set_ylabel("F1 Score", fontsize=AXIS_LABEL_SIZE)
    ax_bar.set_ylim(0, 1)
    ax_bar.set_xlabel("Knowledge Graph", fontsize=AXIS_LABEL_SIZE)
    ax_bar.set_xticks(x)
    ax_bar.set_xticklabels(labels, fontsize=TICK_LABEL_SIZE)
    grid_y(ax_bar)
    clean_spines(ax_bar)

    # ── Panel b: Hit@k – standard test set ───────────────────────────────
    for model_name, matrix_folds in zip(model_names, matrices_all):
        color = KG_COLORS.get(model_name, "#888888")
        d = give_average_hit_at_k_folds(matrix_folds, k_max, bool_test_col="is_known_positive")
        ax_std.plot(d["k"], d["hit_at_k_mean"], color=color, label=model_name)
        if plot_error_bars:
            ax_std.fill_between(
                d["k"],
                d["hit_at_k_mean"] - d["hit_at_k_std"],
                d["hit_at_k_mean"] + d["hit_at_k_std"],
                color=color, alpha=0.2,
            )
    ax_std.plot([0, number_of_drugs], [0, 1], "k--", label="Random classifier", alpha=0.5)
    style_title(ax_std, "Average Disease-Specific Hit@k – Standard Test Set")
    ax_std.set_xlabel("k", fontsize=AXIS_LABEL_SIZE)
    ax_std.set_ylabel("Average disease-specific Hit@k", fontsize=AXIS_LABEL_SIZE)
    ax_std.set_xlim(0, k_max)
    ax_std.set_ylim(0, 1)
    grid_y(ax_std)
    clean_spines(ax_std)
    ax_std.legend(loc="lower right", **LEGEND_KWARGS)

    # ── Panel c: Hit@k – off-label test set ──────────────────────────────
    for model_name, matrix_folds in zip(model_names, matrices_all):
        color = KG_COLORS.get(model_name, "#888888")
        d = give_average_hit_at_k_folds(matrix_folds, k_max,
                                        bool_test_col="ec_indications_list_off_label")
        ax_off.plot(d["k"], d["hit_at_k_mean"], color=color, label=model_name)
        if plot_error_bars:
            ax_off.fill_between(
                d["k"],
                d["hit_at_k_mean"] - d["hit_at_k_std"],
                d["hit_at_k_mean"] + d["hit_at_k_std"],
                color=color, alpha=0.2,
            )
    ax_off.plot([0, number_of_drugs], [0, 1], "k--", label="Random classifier", alpha=0.5)
    style_title(ax_off, "Average Disease-Specific Hit@k – Off-label Test Set")
    ax_off.set_xlabel("k", fontsize=AXIS_LABEL_SIZE)
    ax_off.set_ylabel("Average disease-specific Hit@k", fontsize=AXIS_LABEL_SIZE)
    ax_off.set_xlim(0, k_max)
    ax_off.set_ylim(0, 1)
    grid_y(ax_off)
    clean_spines(ax_off)
    ax_off.legend(loc="upper right", **LEGEND_KWARGS)

    if save_path is not None:
        save_fig(fig, save_path)
    else:
        plt.show()
    plt.close(fig)


def main():
    # Load all KG matrices
    all_matrices = {
        name: load_kg_matrices(cfg["run_path"])
        for name, cfg in KG_CONFIGS.items()
    }

    # Compute F1 scores (standard + off-label) and persist CSVs
    results, results_off = {}, {}
    for label, matrices in all_matrices.items():
        results[label] = compute_f1_across_folds(matrices)
        results_off[label] = compute_f1_across_folds(matrices, bool_test_col_pos="ec_indications_list_off_label")
        save_f1_csv(results[label],     label)
        save_f1_csv(results_off[label], label, suffix="_offlabel")
        print(f"{label} standard:  {results[label]['mean']:.4f} ± {results[label]['std']:.4f}")
        print(f"{label} off-label: {results_off[label]['mean']:.4f} ± {results_off[label]['std']:.4f}")

    plot_f1_comparison(results, results_off, save_path="f1_comparison.pdf")

    plot_combined_figure(
        results=results,
        results_off=results_off,
        matrices_all=tuple(all_matrices.values()),
        model_names=tuple(all_matrices.keys()),
        k_max=100,
        plot_error_bars=True,
        save_path="combined_figure.pdf",
    )

    # Call the horizontal subplots function and save each panel as a PDF
    plot_av_hit_at_k_horizontal_subplots(
        matrices_all=tuple(all_matrices.values()),
        model_names=tuple(all_matrices.keys()),
        bool_test_cols=("ec_indications_list_off_label", "is_known_positive"),
        panel_titles=("Off-label Set Evaluation", "Standard Test Set Evaluation"),
        ylabel="Average disease-specific Hit@k",
        xlabel="k",
        sup_title="Average Disease-Specific Hit@k vs k",
        is_average_folds=True,
        k_max=100,
        plot_error_bars=True,
        force_full_y_axis=True,
        save_path="hitatk_horizontal_subplots.pdf",
        save_pdf_each_panel=True
    )

if __name__ == "__main__":
    main()
