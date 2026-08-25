import sys
import polars as pl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typing import List, Tuple, Optional, Dict
from sklearn.metrics import f1_score

# Importing experimental evaluation suite
sys.path.append('/Users/piotrkaniewski/work/lab-notebooks/alexei/5_experimental_evaluation_suite_v0_1/src/')

BUCKET_NAME = 'mtrx-us-central1-hub-dev-storage'

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


def load_kg_matrices(run_path: str, cache_base: str, bucket, n_folds: int = 5) -> List[pl.DataFrame]:
    """Load matrix predictions for all folds of a single KG run."""
    matrices = []
    for fold in range(n_folds):
        matrix_path = run_path + f"datasets/matrix_generation/model_output/fold_{fold}/matrix_predictions/"
        matrices.append(pl.read_parquet(matrix_path, cache_base + f"_fold_{fold}", bucket))
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

    Args:
        results:     Per-KG F1 result dicts for the standard test set.
        results_off: Per-KG F1 result dicts for the off-label test set.
        save_path:   If set, save figure to this path instead of showing it.
    """
    labels = list(results.keys())
    x = np.arange(len(labels))
    width = 0.4

    means     = [results[kg]["mean"]     for kg in labels]
    stds      = [results[kg]["std"]      for kg in labels]
    means_off = [results_off[kg]["mean"] for kg in labels]
    stds_off  = [results_off[kg]["std"]  for kg in labels]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width / 2, means,     width, yerr=stds,     label="Standard",  capsize=10, edgecolor="black")
    bars2 = ax.bar(x + width / 2, means_off, width, yerr=stds_off, label="Off-label", capsize=10, edgecolor="black", alpha=0.8)

    for bar in [*bars1, *bars2]:
        bar.set_zorder(2)

    for i, (m1, s1, m2, s2) in enumerate(zip(means, stds, means_off, stds_off)):
        ax.text(i - width / 2, m1 + s1 + 0.02, f"{m1:.2f}±{s1:.2f}", ha="center", va="bottom", fontsize=11)
        ax.text(i + width / 2, m2 + s2 + 0.02, f"{m2:.2f}±{s2:.2f}", ha="center", va="bottom", fontsize=11)

    ax.set_ylabel("F1 Score")
    ax.set_title("Standard vs Off-label Test Set Evaluation by KG")
    ax.set_ylim(0, 1)
    ax.set_xlabel("KG")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.grid(True, alpha=0.7, axis="y")
    ax.legend()
    plt.tight_layout()

    if save_path is not None:
        plt.savefig(save_path)
    plt.show()


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
    """
    assert len(bool_test_cols) == 2, "bool_test_cols must contain exactly two column names"
    assert len(panel_titles) == 2, "panel_titles must contain exactly two titles"
    number_of_drugs = min(
        len(matrix["source"].unique())
        for matrix_folds in matrices_all
        for matrix in (matrix_folds if is_average_folds else [matrix_folds])
    )

    fig, axes = plt.subplots(1, 2, figsize=(16, 5), sharey=True)
    for ax, bool_test_col, panel_title in zip(axes, bool_test_cols, panel_titles):
        for model_name, matrix_folds in zip(model_names, matrices_all):
            if is_average_folds:
                d = give_average_hit_at_k_folds(matrix_folds, k_max, bool_test_col=bool_test_col)
                ax.plot(d["k"], d["hit_at_k_mean"], label=model_name)
                if plot_error_bars:
                    ax.fill_between(d["k"], d["hit_at_k_mean"] - d["hit_at_k_std"],
                                    d["hit_at_k_mean"] + d["hit_at_k_std"], alpha=0.2)
            else:
                d = give_hit_at_k(matrix_folds, k_max, bool_test_col=bool_test_col)
                ax.plot(d["k"], d["hit_at_k"], label=model_name)

        ax.plot([0, number_of_drugs], [0, 1], "k--", label="Random classifier", alpha=0.5)
        ax.set_title(panel_title)
        ax.set_xlabel(xlabel)
        ax.set_xlim(0, k_max)
        if force_full_y_axis:
            ax.set_ylim(0, 1)
        ax.grid(True)

    axes[0].set_ylabel(ylabel)
    axes[1].legend(loc="lower right")
    plt.suptitle(sup_title)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    if save_path is not None:
        plt.savefig(save_path)
    plt.show()


def main():
    # Load all KG matrices
    all_matrices = {
        name: load_kg_matrices(cfg["run_path"], cfg["cache_base"])
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

    plot_f1_comparison(results, results_off)

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
    )

if __name__ == "__main__":
    main()
