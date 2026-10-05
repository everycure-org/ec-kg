# Figure 8a — F1 validation

This directory reproduces the F1 bars in manuscript Figure 8a and adds uncertainty
and paired comparisons across diseases. The analysis is intentionally limited to
panel 8a; it makes no inferential claims about the Hit@k curves in panels 8b–c.

The generated panel is [`figure_8a_f1_bootstrap.pdf`](figure_8a_f1_bootstrap.pdf).
See [`RESULTS.md`](RESULTS.md) for readable tables.

## What changed from the draft figure

The original bars showed mean F1 across five cross-validation folds with ±1 fold
standard deviation. Fold SD is descriptive, not an inferential confidence interval,
because the folds share most training data.

The revised panel keeps the same mean-fold F1 point estimates and replaces fold SD
with disease-cluster bootstrap 95% confidence intervals. Significance markers use
paired, disease-clustered permutation tests comparing EC-KG with each upstream KG.

## Reproduce from committed outcomes

The figure is generated with **Python, Polars, NumPy, and Matplotlib**. From the
repository root, run:

```bash
make figure_8a
```

This command:

1. runs 20,000 disease-bootstrap resamples and 100,000 paired permutations;
2. writes the estimates and comparison tables under `outcomes/`;
3. renders `figure_8a_f1_bootstrap.pdf` with Matplotlib.

For a faster development check, call the analysis script with smaller
`--bootstraps` and `--permutations` values. The committed results use the defaults.

## Data provenance

The compact committed artifact
[`outcomes/figure_8_classification_outcomes.parquet`](outcomes/figure_8_classification_outcomes.parquet)
was extracted from the exact five-fold manuscript runs:

| Model | GCS run prefix |
| --- | --- |
| EC-KG | `gs://mtrx-us-central1-hub-dev-storage/kedro/data/releases/v0.15.19/features_ec_kg/runs/ec-kg-rf-manuscript-0480a1c4/` |
| PrimeKG | `gs://mtrx-us-central1-hub-dev-storage/kedro/data/releases/v0.15.19/features/runs/prime-rf-manuscript-99910688/` |
| ROBOKOP KG | `gs://mtrx-us-central1-hub-dev-storage/kedro/data/releases/v0.15.19/features_robokop/runs/robokop-rf-manuscript-1c29853c/` |
| RTX-KG2 | `gs://mtrx-us-central1-hub-dev-storage/kedro/data/releases/v0.15.19/features_rtx/runs/rtx-rf-manuscript-f8ba5c90/` |

The 20 source matrices total roughly 15 GB compressed. With authenticated `gcloud`,
download each run into the layout expected by the extractor:

```bash
ROOT=/path/to/raw-root
for spec in \
  "ec gs://mtrx-us-central1-hub-dev-storage/kedro/data/releases/v0.15.19/features_ec_kg/runs/ec-kg-rf-manuscript-0480a1c4" \
  "prime gs://mtrx-us-central1-hub-dev-storage/kedro/data/releases/v0.15.19/features/runs/prime-rf-manuscript-99910688" \
  "robokop gs://mtrx-us-central1-hub-dev-storage/kedro/data/releases/v0.15.19/features_robokop/runs/robokop-rf-manuscript-1c29853c" \
  "rtx gs://mtrx-us-central1-hub-dev-storage/kedro/data/releases/v0.15.19/features_rtx/runs/rtx-rf-manuscript-f8ba5c90"
do
  set -- $spec
  model=$1; run=$2
  for fold in 0 1 2 3 4; do
    mkdir -p "$ROOT/$model/fold_$fold"
    gcloud storage cp --recursive \
      "$run/datasets/matrix_generation/model_output/fold_$fold/matrix_predictions" \
      "$ROOT/$model/fold_$fold/"
  done
done

MATRIX_ROOT="$ROOT" make figure_8_extract figure_8a
```

Committed compact-Parquet SHA-256:
`7a28e06cc35bd9e9cb940666de8b504d8d31f1ebfe63fb675db1f3f196e76a1b`.

## Statistical method

- F1 uses the manuscript's fixed score threshold of `> 0.5`.
- The displayed statistic is calculated exactly as in the draft figure: calculate F1
  within each fold, then average the five fold F1 values.
- A bootstrap draw samples whole diseases with replacement. All drug–disease pairs
  and fold outcomes for a sampled disease move together. Recalculating the displayed
  statistic over 20,000 draws gives each bar's 95% interval.
- A two-sided paired permutation test swaps the complete EC-KG and comparator outcome
  tensors within diseases and recalculates the same mean-fold F1 difference.
- Holm adjustment covers the six panel-8a comparisons: three upstream graphs on each
  of the standard and off-label cohorts.

The inference is conditional on the existing fitted-model runs and quantifies
robustness to the sampled diseases. It does not isolate KG choice from every source
of training variation.

## Limitation

PrimeKG used a different fold assignment from the other stored runs. All four models
share the same overall evaluation pairs, and the analysis compares the complete
five-fold pipeline outcomes, but a future causal comparison of KG choice should use
one shared split manifest and matched random seeds.
