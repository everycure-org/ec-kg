"""Disease-clustered inference for the F1 bars in Figure 8a.

The displayed statistic is the original mean F1 across five cross-validation folds.
Bootstrap samples resample whole diseases and recalculate that same statistic.
Paired permutation tests swap complete disease outcome tensors between EC-KG and
one comparator, then recalculate the same mean-fold F1 difference.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import polars as pl

EC_KG = "EC-KG"
MODELS = (EC_KG, "PrimeKG", "ROBOKOP KG", "RTX-KG2")
COMPARATORS = MODELS[1:]
EVALUATION_SETS = ("standard", "off_label")
N_FOLDS = 5
THRESHOLD = 0.5


def f1_from_counts(counts: np.ndarray) -> np.ndarray:
    """Calculate F1 from TP, FP, FN counts on the final axis."""
    true_positive, false_positive, false_negative = (counts[..., index] for index in range(3))
    denominator = 2 * true_positive + false_positive + false_negative
    return np.divide(2 * true_positive, denominator, out=np.zeros_like(denominator, dtype=float), where=denominator != 0)


def mean_fold_f1(total_counts: np.ndarray) -> np.ndarray:
    """Calculate mean F1 over the fold axis of (..., fold, outcome) counts."""
    return f1_from_counts(total_counts).mean(axis=-1)


def holm_adjust(p_values: list[float]) -> list[float]:
    """Return family-wise Holm-adjusted p-values in original order."""
    order = np.argsort(p_values)
    adjusted = np.empty(len(p_values))
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, p_values[index] * (len(p_values) - rank)))
        adjusted[index] = running
    return adjusted.tolist()


def disease_fold_counts(frame: pl.DataFrame, diseases: list[str]) -> np.ndarray:
    """Return disease x fold x (TP, FP, FN) counts at the fixed threshold."""
    grouped = (
        frame.with_columns((pl.col("treat score") > THRESHOLD).alias("prediction"))
        .group_by("target", "fold")
        .agg(
            (pl.col("label") & pl.col("prediction")).sum().alias("tp"),
            ((~pl.col("label")) & pl.col("prediction")).sum().alias("fp"),
            (pl.col("label") & (~pl.col("prediction"))).sum().alias("fn"),
        )
    )
    disease_index = {disease: index for index, disease in enumerate(diseases)}
    counts = np.zeros((len(diseases), N_FOLDS, 3), dtype=np.int64)
    for target, fold, tp, fp, fn in grouped.iter_rows():
        counts[disease_index[target], int(fold)] = (tp, fp, fn)
    return counts


def bootstrap_statistics(
    tensors: dict[str, np.ndarray],
    *,
    seed: int,
    bootstraps: int,
    batch_size: int = 500,
) -> dict[str, np.ndarray]:
    """Recalculate each model's mean-fold F1 over shared disease bootstrap draws."""
    disease_count = next(iter(tensors.values())).shape[0]
    if any(tensor.shape != next(iter(tensors.values())).shape for tensor in tensors.values()):
        raise ValueError("All models must have aligned disease/fold tensors.")
    rng = np.random.default_rng(seed)
    values = {model: np.empty(bootstraps, dtype=float) for model in tensors}
    probabilities = np.full(disease_count, 1 / disease_count)
    for start in range(0, bootstraps, batch_size):
        stop = min(start + batch_size, bootstraps)
        weights = rng.multinomial(disease_count, probabilities, size=stop - start)
        for model, tensor in tensors.items():
            totals = np.einsum("bd,dfc->bfc", weights, tensor, optimize=True)
            values[model][start:stop] = mean_fold_f1(totals)
    return values


def paired_permutation_p_value(
    ec_counts: np.ndarray,
    other_counts: np.ndarray,
    *,
    seed: int,
    permutations: int,
    batch_size: int = 1_000,
) -> float:
    """Two-sided disease-level graph-label swap test for mean-fold F1 difference."""
    if ec_counts.shape != other_counts.shape or ec_counts.ndim != 3:
        raise ValueError("Expected aligned disease x fold x outcome tensors.")
    observed = float(mean_fold_f1(ec_counts.sum(axis=0)) - mean_fold_f1(other_counts.sum(axis=0)))
    ec_total = ec_counts.sum(axis=0)
    other_total = other_counts.sum(axis=0)
    delta = other_counts - ec_counts
    rng = np.random.default_rng(seed)
    extreme = 0
    for start in range(0, permutations, batch_size):
        count = min(batch_size, permutations - start)
        swaps = rng.integers(0, 2, size=(count, len(ec_counts)), dtype=np.int8)
        swapped_delta = np.einsum("bd,dfc->bfc", swaps, delta, optimize=True)
        first = ec_total + swapped_delta
        second = other_total - swapped_delta
        null_difference = mean_fold_f1(first) - mean_fold_f1(second)
        extreme += int(np.count_nonzero(np.abs(null_difference) >= abs(observed)))
    return (extreme + 1) / (permutations + 1)


def validate_and_build_tensors(frame: pl.DataFrame, evaluation_set: str) -> tuple[list[str], dict[str, np.ndarray], int]:
    """Validate the common cohort and build aligned model outcome tensors."""
    cohort = frame.filter(pl.col("evaluation_set") == evaluation_set)
    labels_per_pair = cohort.group_by("source", "target").agg(pl.col("label").n_unique().alias("n"))
    if labels_per_pair["n"].max() != 1:
        raise ValueError(f"Inconsistent labels across models/folds for {evaluation_set}.")

    pair_sets: dict[str, set[tuple[str, str]]] = {}
    disease_sets: dict[str, set[str]] = {}
    for model in MODELS:
        model_frame = cohort.filter(pl.col("model") == model)
        pair_sets[model] = set(model_frame.select("source", "target").unique().iter_rows())
        disease_sets[model] = set(model_frame["target"].unique())
    if len({frozenset(values) for values in pair_sets.values()}) != 1:
        raise ValueError(f"Models do not share one drug-disease evaluation universe for {evaluation_set}.")
    if len({frozenset(values) for values in disease_sets.values()}) != 1:
        raise ValueError(f"Models do not share one disease evaluation universe for {evaluation_set}.")

    diseases = sorted(disease_sets[EC_KG])
    tensors = {
        model: disease_fold_counts(cohort.filter(pl.col("model") == model), diseases)
        for model in MODELS
    }
    return diseases, tensors, len(pair_sets[EC_KG])


def analyze(
    frame: pl.DataFrame,
    *,
    bootstraps: int = 20_000,
    permutations: int = 100_000,
    seed: int = 20260826,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Return per-model F1 estimates and EC-KG paired comparisons for Figure 8a."""
    required_columns = {"source", "target", "label", "treat score", "evaluation_set", "model", "fold"}
    missing_columns = required_columns - set(frame.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {sorted(missing_columns)}")
    null_columns = [column for column in required_columns if frame[column].null_count()]
    if null_columns:
        raise ValueError(f"Null values in required columns: {sorted(null_columns)}")
    if set(frame["model"].unique()) != set(MODELS):
        raise ValueError("Classification outcomes must contain exactly the four Figure 8 models.")
    if set(frame["evaluation_set"].unique()) != set(EVALUATION_SETS):
        raise ValueError("Classification outcomes must contain standard and off-label cohorts.")
    if frame.unique(subset=["source", "target", "evaluation_set", "model", "fold"]).height != frame.height:
        raise ValueError("Duplicate model/fold outcomes found for a drug-disease pair.")
    expected_folds = set(range(N_FOLDS))
    coverage = frame.group_by("model", "evaluation_set").agg(pl.col("fold").unique())
    if any(set(folds) != expected_folds for folds in coverage["fold"]):
        raise ValueError("Every model and evaluation cohort must contain folds 0 through 4.")

    estimates: list[dict[str, object]] = []
    comparisons: list[dict[str, object]] = []

    for evaluation_index, evaluation_set in enumerate(EVALUATION_SETS):
        diseases, tensors, pair_count = validate_and_build_tensors(frame, evaluation_set)
        bootstrap = bootstrap_statistics(
            tensors,
            seed=seed + evaluation_index,
            bootstraps=bootstraps,
        )
        points = {
            model: float(mean_fold_f1(tensor.sum(axis=0)))
            for model, tensor in tensors.items()
        }
        for model in MODELS:
            lower, upper = np.quantile(bootstrap[model], [0.025, 0.975])
            estimates.append(
                {
                    "evaluation_set": evaluation_set,
                    "model": model,
                    "f1": points[model],
                    "ci_95_low": float(lower),
                    "ci_95_high": float(upper),
                    "n_pairs": pair_count,
                    "n_diseases": len(diseases),
                    "folds": N_FOLDS,
                    "bootstrap_resamples": bootstraps,
                }
            )

        for comparator_index, comparator in enumerate(COMPARATORS):
            effect_distribution = bootstrap[EC_KG] - bootstrap[comparator]
            lower, upper = np.quantile(effect_distribution, [0.025, 0.975])
            p_value = paired_permutation_p_value(
                tensors[EC_KG],
                tensors[comparator],
                seed=seed + 100 + evaluation_index * 10 + comparator_index,
                permutations=permutations,
            )
            comparisons.append(
                {
                    "evaluation_set": evaluation_set,
                    "comparison": f"EC-KG vs {comparator}",
                    "comparator": comparator,
                    "ec_kg_f1": points[EC_KG],
                    "comparator_f1": points[comparator],
                    "effect": points[EC_KG] - points[comparator],
                    "ci_95_low": float(lower),
                    "ci_95_high": float(upper),
                    "p_value": p_value,
                    "n_pairs": pair_count,
                    "n_diseases": len(diseases),
                    "permutations": permutations,
                }
            )

    adjusted = holm_adjust([float(row["p_value"]) for row in comparisons])
    for row, adjusted_p_value in zip(comparisons, adjusted, strict=True):
        row["holm_p_value"] = adjusted_p_value
    return pl.DataFrame(estimates), pl.DataFrame(comparisons)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classification-outcomes", type=Path, required=True)
    parser.add_argument("--estimates-output", type=Path, required=True)
    parser.add_argument("--comparisons-output", type=Path, required=True)
    parser.add_argument("--bootstraps", type=int, default=20_000)
    parser.add_argument("--permutations", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=20260826)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    estimates, comparisons = analyze(
        pl.read_parquet(args.classification_outcomes),
        bootstraps=args.bootstraps,
        permutations=args.permutations,
        seed=args.seed,
    )
    args.estimates_output.parent.mkdir(parents=True, exist_ok=True)
    args.comparisons_output.parent.mkdir(parents=True, exist_ok=True)
    estimates.write_csv(args.estimates_output)
    comparisons.write_csv(args.comparisons_output)


if __name__ == "__main__":
    main()
