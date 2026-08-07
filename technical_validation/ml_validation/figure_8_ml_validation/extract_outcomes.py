"""Extract compact, reproducible Figure 8 outcomes from manuscript matrix runs.

The full matrices are intentionally not committed: all 20 folds total about 15 GB
compressed. This script retains only held-out classification outcomes and off-label
positive ranks needed to reproduce Figure 8 inference.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

MODELS = {
    "EC-KG": "ec",
    "PrimeKG": "prime",
    "ROBOKOP KG": "robokop",
    "RTX-KG2": "rtx",
}
N_FOLDS = 5
SCORE = "treat score"
NEGATIVE = "is_known_negative"
OFF_LABEL = "ec_indications_list_off_label"
STANDARD = "is_known_positive"


def matrix_path(matrix_root: Path, model_directory: str, fold: int) -> str:
    """Return the local parquet glob for one model and CV fold."""
    return str(matrix_root / model_directory / f"fold_{fold}" / "matrix_predictions" / "*.parquet")


def classification_outcomes(matrix_glob: str, model: str, fold: int) -> pl.DataFrame:
    """Extract held-out classification rows for the standard and off-label cohorts."""
    rows = (
        pl.scan_parquet(matrix_glob)
        .filter(pl.col(STANDARD) | pl.col(OFF_LABEL) | pl.col(NEGATIVE))
        .select("source", "target", STANDARD, OFF_LABEL, NEGATIVE, SCORE)
        .collect(engine="streaming")
    )
    standard = (
        rows.filter(pl.col(STANDARD) | pl.col(NEGATIVE))
        .select("source", "target", pl.col(STANDARD).alias("label"), SCORE)
        .with_columns(pl.lit("standard").alias("evaluation_set"))
    )
    off_label = (
        rows.filter(pl.col(OFF_LABEL) | pl.col(NEGATIVE))
        .select("source", "target", pl.col(OFF_LABEL).alias("label"), SCORE)
        .with_columns(pl.lit("off_label").alias("evaluation_set"))
    )
    return pl.concat([standard, off_label]).with_columns(
        pl.lit(model).alias("model"),
        pl.lit(fold).alias("fold"),
        pl.col("label").cast(pl.Boolean),
    )


def off_label_ranking_outcomes(matrix_glob: str, model: str, fold: int) -> pl.DataFrame:
    """Extract deterministic ranks for held-out off-label positives.

    Ties are resolved by source identifier after descending score. This is deliberate:
    the historical Figure 8 script used random tie-breaking, which makes its curves
    non-reproducible. Rank is then adjusted to remove other off-label positives above
    the evaluated positive, matching the intent of the published Hit@k calculation.
    """
    scan = pl.scan_parquet(matrix_glob)
    positives = scan.filter(pl.col(OFF_LABEL)).select("target").unique().collect(engine="streaming")
    targets = positives["target"].to_list()
    if not targets:
        return pl.DataFrame(schema={"source": pl.String, "target": pl.String, "rank": pl.Int64, "model": pl.String, "fold": pl.Int64})

    candidates = (
        scan.filter(pl.col("target").is_in(targets))
        .select("source", "target", OFF_LABEL, SCORE)
        .collect(engine="streaming")
        .sort(["target", SCORE, "source"], descending=[False, True, False])
        .with_columns(pl.col("source").cum_count().over("target").alias("_raw_rank"))
        .with_columns(
            pl.when(pl.col(OFF_LABEL)).then(1).otherwise(0).cum_sum().over("target").alias("_positive_count")
        )
    )
    return (
        candidates.filter(pl.col(OFF_LABEL))
        .select("source", "target", (pl.col("_raw_rank") - pl.col("_positive_count") + 1).alias("rank"))
        .with_columns(pl.lit(model).alias("model"), pl.lit(fold).alias("fold"))
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, required=True, help="Directory containing ec/, prime/, robokop/, and rtx/ fold directories.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for compact parquet artifacts.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    classifications: list[pl.DataFrame] = []
    rankings: list[pl.DataFrame] = []
    for model, directory in MODELS.items():
        for fold in range(N_FOLDS):
            path = matrix_path(args.matrix_root, directory, fold)
            print(f"Extracting {model}, fold {fold}", flush=True)
            classifications.append(classification_outcomes(path, model, fold))
            rankings.append(off_label_ranking_outcomes(path, model, fold))

    pl.concat(classifications).write_parquet(args.output_dir / "figure_8_classification_outcomes.parquet")
    pl.concat(rankings).write_parquet(args.output_dir / "figure_8_off_label_ranks.parquet")


if __name__ == "__main__":
    main()
