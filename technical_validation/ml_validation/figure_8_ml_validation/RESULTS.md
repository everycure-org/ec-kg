# Figure 8a statistical results

The bars retain the manuscript draft's mean F1 across five cross-validation folds.
Intervals are disease-cluster bootstrap 95% confidence intervals from 20,000
resamples.

## F1 estimates

| Evaluation set | Model | Mean F1 | Disease-bootstrap 95% CI |
| --- | --- | ---: | ---: |
| Standard | EC-KG | 0.808 | 0.789–0.826 |
| Standard | PrimeKG | 0.570 | 0.535–0.602 |
| Standard | ROBOKOP KG | 0.733 | 0.712–0.753 |
| Standard | RTX-KG2 | 0.780 | 0.759–0.799 |
| Off-label | EC-KG | 0.553 | 0.493–0.607 |
| Off-label | PrimeKG | 0.123 | 0.085–0.163 |
| Off-label | ROBOKOP KG | 0.414 | 0.356–0.468 |
| Off-label | RTX-KG2 | 0.509 | 0.450–0.563 |

## Paired EC-KG comparisons

Two-sided paired disease permutation tests use 100,000 permutations. Holm correction
covers all six Figure 8a comparisons.

| Evaluation set | Comparison | F1 difference | Disease-bootstrap 95% CI | Holm-adjusted p |
| --- | --- | ---: | ---: | ---: |
| Standard | EC-KG vs PrimeKG | +0.238 | +0.216–+0.262 | 0.00006† |
| Standard | EC-KG vs ROBOKOP KG | +0.075 | +0.066–+0.084 | 0.00006† |
| Standard | EC-KG vs RTX-KG2 | +0.028 | +0.023–+0.034 | 0.00006† |
| Off-label | EC-KG vs PrimeKG | +0.430 | +0.370–+0.487 | 0.00006† |
| Off-label | EC-KG vs ROBOKOP KG | +0.139 | +0.098–+0.182 | 0.00006† |
| Off-label | EC-KG vs RTX-KG2 | +0.044 | +0.029–+0.060 | 0.00006† |

† All six tests reached the 100,000-permutation simulation floor: no permuted
difference was as extreme as the observed difference. The reported adjusted bound is
six times the add-one raw Monte Carlo bound (`1 / 100,001`).

Within these existing model runs, EC-KG has higher mean-fold F1 than each comparator
on both evaluation sets, and all six differences are robust to disease resampling.
The analysis is retrospective and conditional on the fitted runs; PrimeKG used a
different fold assignment, so these results do not isolate KG choice as the sole
cause of every difference.
