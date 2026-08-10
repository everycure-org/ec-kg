# Figure 8 statistical-validation results

This is a readable rendering of [`outcomes/figure_8_statistical_tests.csv`](outcomes/figure_8_statistical_tests.csv), generated from the held-out outcomes committed in this directory.

**Method.** Two-sided, disease-clustered paired permutation tests (100,000 permutations) compare EC-KG to each upstream KG. Disease-cluster bootstrap confidence intervals use 20,000 resamples. Holm correction covers all 12 predeclared tests: standard and off-label F1 (six comparisons), plus off-label Hit@10 and AUC(Hit@1–100) (six comparisons).

## Panel 8a — F1

| Test set | Comparison | EC-KG F1 | Comparator F1 | Difference (95% CI) | Holm-adjusted p |
| --- | --- | ---: | ---: | --- | ---: |
| Standard | PrimeKG | 0.808 | 0.570 | +0.238 (+0.217, +0.262) | <0.001 |
| Standard | ROBOKOP KG | 0.808 | 0.733 | +0.075 (+0.066, +0.084) | <0.001 |
| Standard | RTX-KG2 | 0.808 | 0.780 | +0.028 (+0.023, +0.034) | <0.001 |
| Off-label | PrimeKG | 0.442 | 0.154 | +0.287 (+0.225, +0.350) | <0.001 |
| Off-label | ROBOKOP KG | 0.442 | 0.379 | +0.062 (+0.029, +0.098) | 0.0031 |
| Off-label | RTX-KG2 | 0.442 | 0.408 | +0.034 (+0.016, +0.053) | 0.0013 |

EC-KG has higher F1 than every comparator in both cohorts; every adjusted 95% CI excludes zero.

## Panel 8c — off-label disease-specific ranking

| Endpoint | Comparison | EC-KG | Comparator | Difference (95% CI) | Holm-adjusted p |
| --- | --- | ---: | ---: | --- | ---: |
| Hit@10 | PrimeKG | 0.163 | 0.119 | +0.044 (+0.014, +0.074) | 0.0065 |
| Hit@10 | ROBOKOP KG | 0.163 | 0.118 | +0.045 (+0.023, +0.069) | <0.001 |
| Hit@10 | RTX-KG2 | 0.163 | 0.158 | +0.005 (−0.018, +0.027) | 0.676 |
| AUC(Hit@1–100) | PrimeKG | 0.311 | 0.261 | +0.050 (+0.021, +0.078) | 0.0031 |
| AUC(Hit@1–100) | ROBOKOP KG | 0.311 | 0.250 | +0.061 (+0.035, +0.086) | <0.001 |
| AUC(Hit@1–100) | RTX-KG2 | 0.311 | 0.271 | +0.040 (+0.019, +0.061) | 0.0010 |

EC-KG outperforms PrimeKG and ROBOKOP KG for both ranking endpoints. Compared with RTX-KG2, EC-KG has a higher complete Hit@k curve (AUC), but its Hit@10 difference is not statistically significant.

## Interpretation for the manuscript

The primary conclusion supported by Figure 8 is not that EC-KG dominates at every arbitrary rank cutoff. Rather, EC-KG has significantly higher F1 in both cohorts and significantly better overall off-label ranking performance than all three upstream KGs. The top-ten off-label result against RTX-KG2 is inconclusive.
