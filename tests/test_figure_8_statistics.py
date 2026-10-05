"""Unit tests for Figure 8a statistical helpers."""
from __future__ import annotations

import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "technical_validation" / "ml_validation" / "figure_8_ml_validation"))
from statistical_analysis import (  # noqa: E402
    bootstrap_statistics,
    f1_from_counts,
    holm_adjust,
    mean_fold_f1,
    paired_permutation_p_value,
)


class Figure8StatisticsTest(unittest.TestCase):
    def test_f1_from_counts(self) -> None:
        self.assertAlmostEqual(float(f1_from_counts(np.array([8, 2, 2]))), 0.8)

    def test_mean_fold_f1_matches_original_statistic(self) -> None:
        totals = np.array([[8, 2, 2], [3, 1, 1]])
        expected = (0.8 + 0.75) / 2
        self.assertAlmostEqual(float(mean_fold_f1(totals)), expected)

    def test_committed_outcomes_reproduce_original_figure_8a_bars(self) -> None:
        import polars as pl
        from sklearn.metrics import f1_score

        outcomes = pl.read_parquet(
            Path(__file__).parents[1]
            / "technical_validation/ml_validation/figure_8_ml_validation/outcomes/figure_8_classification_outcomes.parquet"
        )
        expected = {
            ("standard", "EC-KG"): 0.8082367703861747,
            ("standard", "PrimeKG"): 0.5697518913148452,
            ("standard", "ROBOKOP KG"): 0.733462855576703,
            ("standard", "RTX-KG2"): 0.77999442044856,
            ("off_label", "EC-KG"): 0.5527894848981838,
            ("off_label", "PrimeKG"): 0.1226091276550326,
            ("off_label", "ROBOKOP KG"): 0.4137308863556742,
            ("off_label", "RTX-KG2"): 0.5086908506637935,
        }
        observed: dict[tuple[str, str], list[float]] = {}
        for key, group in outcomes.group_by("evaluation_set", "model", "fold"):
            evaluation_set, model, _fold = key
            observed.setdefault((evaluation_set, model), []).append(
                f1_score(group["label"].to_numpy(), group["treat score"].to_numpy() > 0.5)
            )
        for key, value in expected.items():
            self.assertAlmostEqual(float(np.mean(observed[key])), value)

    def test_holm_adjustment_preserves_order_and_monotonicity(self) -> None:
        adjusted = holm_adjust([0.04, 0.001, 0.02])
        self.assertEqual(adjusted, [0.04, 0.003, 0.04])

    def test_shared_bootstrap_draws_match_for_identical_models(self) -> None:
        tensor = np.array(
            [
                [[4, 0, 1], [3, 1, 1]],
                [[5, 1, 0], [4, 0, 1]],
                [[3, 0, 2], [5, 1, 0]],
            ]
        )
        values = bootstrap_statistics({"first": tensor, "second": tensor.copy()}, seed=1, bootstraps=200)
        np.testing.assert_array_equal(values["first"], values["second"])

    def test_paired_permutation_finds_consistent_f1_advantage(self) -> None:
        ec = np.tile(np.array([[[8, 1, 1]]]), (8, 1, 1))
        other = np.tile(np.array([[[3, 5, 5]]]), (8, 1, 1))
        p_value = paired_permutation_p_value(ec, other, seed=1, permutations=5_000)
        self.assertLess(p_value, 0.05)


if __name__ == "__main__":
    unittest.main()
