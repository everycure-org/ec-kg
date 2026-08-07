"""Unit tests for Figure 8 statistical helpers."""
from __future__ import annotations

import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "technical_validation" / "ml_validation" / "figure_8_ml_validation"))
from statistical_analysis import (  # noqa: E402
    f1_from_counts,
    holm_adjust,
    paired_f1_test,
    paired_scalar_test,
    rank_endpoint_by_disease,
)


class Figure8StatisticsTest(unittest.TestCase):
    def test_f1_from_counts(self) -> None:
        self.assertAlmostEqual(float(f1_from_counts(np.array([8, 2, 2]))), 0.8)

    def test_holm_adjustment_preserves_order_and_monotonicity(self) -> None:
        adjusted = holm_adjust([0.04, 0.001, 0.02])
        self.assertEqual(adjusted, [0.04, 0.003, 0.04])

    def test_paired_scalar_test_finds_consistent_positive_effect(self) -> None:
        ec = np.array([0.8, 0.7, 0.9, 0.6, 0.75])
        other = np.array([0.2, 0.1, 0.3, 0.0, 0.15])
        effect, lower, upper, p_value = paired_scalar_test(ec, other, seed=1, permutations=5_000, bootstraps=2_000)
        self.assertGreater(effect, 0)
        self.assertGreater(lower, 0)
        self.assertGreater(upper, lower)
        self.assertLess(p_value, 0.1)

    def test_paired_f1_test_finds_consistent_positive_effect(self) -> None:
        ec = np.array([[8, 1, 1], [9, 1, 1], [7, 1, 2], [8, 0, 2], [9, 1, 0]])
        other = np.array([[4, 4, 5], [5, 3, 4], [4, 4, 4], [3, 5, 4], [4, 4, 4]])
        ec_f1, other_f1, effect, lower, upper, p_value = paired_f1_test(ec, other, seed=1, permutations=5_000, bootstraps=2_000)
        self.assertGreater(ec_f1, other_f1)
        self.assertGreater(effect, 0)
        self.assertGreater(lower, 0)
        self.assertGreater(upper, lower)
        self.assertLess(p_value, 0.1)

    def test_rank_endpoints_are_calculated_per_disease(self) -> None:
        import polars as pl

        ranks = pl.DataFrame({"target": ["d1", "d1", "d2"], "rank": [1, 20, 10]})
        hit_at_ten = rank_endpoint_by_disease(ranks, "rank", "Hit@10")
        auc = rank_endpoint_by_disease(ranks, "rank", "AUC Hit@1-100")
        self.assertEqual(hit_at_ten["value"].to_list(), [0.5, 1.0])
        self.assertAlmostEqual(auc["value"][0], (1.0 + 0.81) / 2)
        self.assertAlmostEqual(auc["value"][1], 0.91)


if __name__ == "__main__":
    unittest.main()
