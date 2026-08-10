# Figure 8 — machine-learning validation

This directory contains the computation and statistical inference for the manuscript
asset `figure8_combined_figure_ml_validation` (Figure 8). See [`RESULTS.md`](RESULTS.md)
for the readable statistical-results tables; the underlying full-precision output is
in [`outcomes/figure_8_statistical_tests.csv`](outcomes/figure_8_statistical_tests.csv).

## Scope

Figure 8 compares random-forest models trained on embeddings from EC-KG, PrimeKG,
ROBOKOP KG, and RTX-KG2. It has three panels:

- **8a:** F1 on standard and off-label evaluation sets.
- **8b:** standard-set Hit@k curves.
- **8c:** off-label Hit@k curves.

`generate_figure.py` is retained as the historical plotting implementation. The
new scripts below make the **inferential analysis** reproducible rather than inferring
significance from plotted cross-validation ranges. They do not replace the raw-matrix
workflow needed to regenerate panels 8b and 8c.

## Data provenance

The source matrices are GCS outputs from five manuscript runs:

| Model | Run ID |
| --- | --- |
| EC-KG | `ec-kg-rf-manuscript-0480a1c4` |
| PrimeKG | `prime-rf-manuscript-99910688` |
| ROBOKOP KG | `robokop-rf-manuscript-1c29853c` |
| RTX-KG2 | `rtx-rf-manuscript-f8ba5c90` |

They live under `gs://mtrx-us-central1-hub-dev-storage/kedro/data/releases/v0.15.19/`.
The 20 raw fold matrices total roughly 15 GB compressed, so they are **not**
committed. Download them with authenticated `gcloud storage cp --recursive` into a
local directory shaped as:

```text
<raw-root>/{ec,prime,robokop,rtx}/fold_{0..4}/matrix_predictions/*.parquet
```

## Reproduce

First extract compact outcomes from the raw matrices:

```bash
uv run python technical_validation/ml_validation/figure_8_ml_validation/extract_outcomes.py \
  --matrix-root /path/to/raw-root \
  --output-dir /path/to/figure-8-outcomes
```

This writes two compact Parquet artifacts:

- `figure_8_classification_outcomes.parquet`: held-out labels and scores for panel 8a.
- `figure_8_off_label_ranks.parquet`: held-out off-label positive ranks for panel 8c.

The extracted artifacts and the resulting table are versioned in `outcomes/`, so a
reader can reproduce the statistical table without GCS access. Re-extract them only
when the upstream manuscript runs intentionally change.

Then calculate the statistical table:

```bash
uv run python technical_validation/ml_validation/figure_8_ml_validation/statistical_analysis.py \
  --classification-outcomes /path/to/figure-8-outcomes/figure_8_classification_outcomes.parquet \
  --off-label-ranks /path/to/figure-8-outcomes/figure_8_off_label_ranks.parquet \
  --output technical_validation/ml_validation/figure_8_ml_validation/outcomes/figure_8_statistical_tests.csv
```

## Statistical plan

All comparisons are EC-KG against one upstream graph: PrimeKG, ROBOKOP KG, and
RTX-KG2.

- **Panel 8a:** F1, separately for the standard and off-label cohorts.
- **Panel 8c:** both **Hit@10** and normalized **AUC(Hit@1..100)**, calculated per
  disease then averaged. Hit@10 is an interpretable decision threshold; AUC preserves
  the full ranking-curve information.
- Each outcome uses a two-sided paired permutation test that swaps EC-KG and
  comparator outcomes **within diseases**. This keeps correlated pairs from the same
  disease together.
- A disease-cluster bootstrap provides a 95% confidence interval for the effect.
- Holm adjustment is applied across the complete predeclared family of 12 tests:
  6 F1 comparisons plus 6 off-label ranking comparisons.

The five CV fold means and standard deviations in the figure are descriptive—not
confidence intervals and not suitable independent samples for a conventional t-test.

### Deterministic ties

`generate_figure.py` historically used random rank tie-breaking without a seed. The
extraction script resolves equal scores deterministically by source identifier, making
Hit@k endpoints reproducible. This should be used for new inference and documented if
results are added to the manuscript.

## Important limitation

The stored PrimeKG run assigns some pairs to different CV folds from the other runs.
The scripts therefore align held-out outcomes by normalized drug–disease pair after
combining folds; scores for a pair evaluated in multiple eligible folds are averaged.
A future rerun should use one shared split manifest for all four KGs.
