"""Paired disease-clustered statistical tests for Figure 8.

Runs three EC-KG comparisons for each endpoint. Classification uses F1; the off-label
ranking panel uses Hit@10 and AUC(Hit@1..100). A paired permutation test exchanges
model outcomes within diseases, and a disease bootstrap estimates a 95% CI.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import polars as pl

EC_KG = "EC-KG"
COMPARATORS = ("PrimeKG", "ROBOKOP KG", "RTX-KG2")


def f1_from_counts(counts: np.ndarray) -> np.ndarray:
    """Calculate F1 from TP, FP, FN counts; supports a final length-three axis."""
    true_positive, false_positive, false_negative = (counts[..., index] for index in range(3))
    return 2 * true_positive / np.maximum(2 * true_positive + false_positive + false_negative, 1)


def holm_adjust(p_values: list[float]) -> list[float]:
    """Return family-wise Holm-adjusted p-values in original order."""
    order = np.argsort(p_values)
    adjusted = np.empty(len(p_values))
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, p_values[index] * (len(p_values) - rank)))
        adjusted[index] = running
    return adjusted.tolist()


def paired_scalar_test(
    ec_values: np.ndarray,
    other_values: np.ndarray,
    *,
    seed: int,
    permutations: int = 100_000,
    bootstraps: int = 20_000,
) -> tuple[float, float, float, float]:
    """Return paired mean effect, bootstrap CI, and two-sided swap-test p-value."""
    if ec_values.shape != other_values.shape or ec_values.ndim != 1:
        raise ValueError("Expected aligned one-dimensional disease-level outcomes.")
    rng = np.random.default_rng(seed)
    observed = float(np.mean(ec_values - other_values))
    indices = rng.integers(0, len(ec_values), size=(bootstraps, len(ec_values)))
    bootstrap = np.mean(ec_values[indices] - other_values[indices], axis=1)

    extreme = 0
    for start in range(0, permutations, 1_000):
        count = min(1_000, permutations - start)
        swap = rng.integers(0, 2, size=(count, len(ec_values)), dtype=np.int8).astype(bool)
        null_difference = np.mean(np.where(swap, other_values, ec_values) - np.where(swap, ec_values, other_values), axis=1)
        extreme += int(np.count_nonzero(np.abs(null_difference) >= abs(observed)))
    return observed, float(np.quantile(bootstrap, 0.025)), float(np.quantile(bootstrap, 0.975)), (extreme + 1) / (permutations + 1)


def paired_f1_test(
    ec_counts: np.ndarray,
    other_counts: np.ndarray,
    *,
    seed: int,
    permutations: int = 100_000,
    bootstraps: int = 20_000,
) -> tuple[float, float, float, float, float, float]:
    """Return EC/other F1, difference CI, and paired disease-swap p-value."""
    if ec_counts.shape != other_counts.shape or ec_counts.ndim != 2 or ec_counts.shape[1] != 3:
        raise ValueError("Expected aligned disease x (TP, FP, FN) count matrices.")
    rng = np.random.default_rng(seed)
    ec_f1 = float(f1_from_counts(ec_counts.sum(axis=0)))
    other_f1 = float(f1_from_counts(other_counts.sum(axis=0)))
    observed = ec_f1 - other_f1
    indices = rng.integers(0, len(ec_counts), size=(bootstraps, len(ec_counts)))
    bootstrap = f1_from_counts(ec_counts[indices].sum(axis=1)) - f1_from_counts(other_counts[indices].sum(axis=1))

    extreme = 0
    for start in range(0, permutations, 1_000):
        count = min(1_000, permutations - start)
        swap = rng.integers(0, 2, size=(count, len(ec_counts)), dtype=np.int8).astype(bool)
        first = np.where(swap[..., None], other_counts, ec_counts).sum(axis=1)
        second = np.where(swap[..., None], ec_counts, other_counts).sum(axis=1)
        null_difference = f1_from_counts(first) - f1_from_counts(second)
        extreme += int(np.count_nonzero(np.abs(null_difference) >= abs(observed)))
    return ec_f1, other_f1, observed, float(np.quantile(bootstrap, 0.025)), float(np.quantile(bootstrap, 0.975)), (extreme + 1) / (permutations + 1)


def f1_counts(frame: pl.DataFrame, score_column: str) -> pl.DataFrame:
    """Aggregate thresholded classifier outcomes to the disease test unit."""
    return (
        frame.with_columns((pl.col(score_column) > 0.5).alias("prediction"))
        .group_by("target")
        .agg(
            (pl.col("label") & pl.col("prediction")).sum().alias("tp"),
            ((~pl.col("label")) & pl.col("prediction")).sum().alias("fp"),
            (pl.col("label") & (~pl.col("prediction"))).sum().alias("fn"),
        )
        .sort("target")
    )


def collapsed_classification(frame: pl.DataFrame, evaluation_set: str, model: str) -> pl.DataFrame:
    """Average repeated held-out scores for a pair, notably off-label positives."""
    return (
        frame.filter((pl.col("evaluation_set") == evaluation_set) & (pl.col("model") == model))
        .group_by("source", "target")
        .agg(pl.col("label").max().alias("label"), pl.col("treat score").mean().alias("score"))
    )


def collapsed_ranks(frame: pl.DataFrame, model: str) -> pl.DataFrame:
    """Average a positive pair's held-out rank over its eligible folds."""
    return frame.filter(pl.col("model") == model).group_by("source", "target").agg(pl.col("rank").mean().alias("rank"))


def rank_endpoint_by_disease(frame: pl.DataFrame, rank_column: str, endpoint: str) -> pl.DataFrame:
    """Compute one disease-level Hit@10 or normalized AUC(Hit@1..100) outcome."""
    if endpoint == "Hit@10":
        value = (pl.col(rank_column) <= 10).cast(pl.Float64)
    elif endpoint == "AUC Hit@1-100":
        value = (101 - pl.col(rank_column).clip(upper_bound=101)).clip(lower_bound=0) / 100
    else:
        raise ValueError(f"Unknown endpoint: {endpoint}")
    return frame.with_columns(value.alias("value")).group_by("target").agg(pl.col("value").mean().alias("value")).sort("target")


def classification_results(frame: pl.DataFrame) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for evaluation_set in ("standard", "off_label"):
        ec = collapsed_classification(frame, evaluation_set, EC_KG).rename({"score": "ec_score"})
        for offset, comparator in enumerate(COMPARATORS):
            other = collapsed_classification(frame, evaluation_set, comparator).rename({"label": "other_label", "score": "other_score"})
            paired = ec.join(other, on=["source", "target"], how="inner").filter(pl.col("label") == pl.col("other_label"))
            ec_counts = f1_counts(paired, "ec_score")
            other_counts = f1_counts(paired, "other_score").rename({"tp": "other_tp", "fp": "other_fp", "fn": "other_fn"})
            counts = ec_counts.join(other_counts, on="target", how="inner").sort("target")
            first = counts.select("tp", "fp", "fn").to_numpy().astype(int)
            second = counts.select("other_tp", "other_fp", "other_fn").to_numpy().astype(int)
            ec_f1, other_f1, effect, lower, upper, p_value = paired_f1_test(first, second, seed=20260806 + offset)
            results.append({"panel": "8a", "evaluation_set": evaluation_set, "endpoint": "F1", "comparison": f"EC-KG vs {comparator}", "n_pairs": paired.height, "n_diseases": counts.height, "ec_kg_value": ec_f1, "comparator_value": other_f1, "effect": effect, "ci_95_low": lower, "ci_95_high": upper, "p_value": p_value})
    return results


def ranking_results(frame: pl.DataFrame) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    ec = collapsed_ranks(frame, EC_KG).rename({"rank": "ec_rank"})
    for endpoint_index, endpoint in enumerate(("Hit@10", "AUC Hit@1-100")):
        for comparison_index, comparator in enumerate(COMPARATORS):
            other = collapsed_ranks(frame, comparator).rename({"rank": "other_rank"})
            paired = ec.join(other, on=["source", "target"], how="inner")
            first = rank_endpoint_by_disease(paired, "ec_rank", endpoint)
            second = rank_endpoint_by_disease(paired, "other_rank", endpoint).rename({"value": "other_value"})
            values = first.join(second, on="target", how="inner").sort("target")
            effect, lower, upper, p_value = paired_scalar_test(values["value"].to_numpy(), values["other_value"].to_numpy(), seed=20260816 + endpoint_index * 10 + comparison_index)
            results.append({"panel": "8c", "evaluation_set": "off_label", "endpoint": endpoint, "comparison": f"EC-KG vs {comparator}", "n_pairs": paired.height, "n_diseases": values.height, "ec_kg_value": float(values["value"].mean()), "comparator_value": float(values["other_value"].mean()), "effect": effect, "ci_95_low": lower, "ci_95_high": upper, "p_value": p_value})
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classification-outcomes", type=Path, required=True)
    parser.add_argument("--off-label-ranks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = classification_results(pl.read_parquet(args.classification_outcomes)) + ranking_results(pl.read_parquet(args.off_label_ranks))
    adjusted = holm_adjust([float(row["p_value"]) for row in results])
    for row, adjusted_p_value in zip(results, adjusted, strict=True):
        row["holm_p_value"] = adjusted_p_value
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(results).write_csv(args.output)


if __name__ == "__main__":
    main()
