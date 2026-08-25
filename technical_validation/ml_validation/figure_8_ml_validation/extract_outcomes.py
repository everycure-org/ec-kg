"""Extract compact Figure 8a classification outcomes from manuscript matrix runs.

The 20 full fold matrices total roughly 15 GB compressed and are intentionally not
committed. This script retains the labels, scores, folds, and disease identifiers
needed to reproduce the F1 bars and disease-clustered inference.
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, required=True, help="Directory containing ec/, prime/, robokop/, and rtx/ fold directories.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for the compact parquet artifact.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    classifications: list[pl.DataFrame] = []
    for model, directory in MODELS.items():
        for fold in range(N_FOLDS):
            path = matrix_path(args.matrix_root, directory, fold)
            print(f"Extracting {model}, fold {fold}", flush=True)
            classifications.append(classification_outcomes(path, model, fold))

    pl.concat(classifications).write_parquet(args.output_dir / "figure_8_classification_outcomes.parquet")


if __name__ == "__main__":
    main()
