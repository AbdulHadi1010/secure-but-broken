import math

import pytest

from analysis.stats import chi_square, fisher_2x2, holm, mcnemar_exact, newcombe_diff, rxc_exact, wilson


def test_wilson_known_values():
    # Reference: Newcombe (1998) / Brown, Cai & DasGupta (2001): 81/263 -> (0.2553, 0.3662) approx
    p, lo, hi = wilson(81, 263)
    assert p == pytest.approx(0.30798, abs=1e-4)
    assert lo == pytest.approx(0.2553, abs=1e-3) and hi == pytest.approx(0.3662, abs=1e-3)
    assert wilson(0, 10)[1] == pytest.approx(0.0, abs=1e-12) and wilson(10, 10)[2] == pytest.approx(1.0)
    assert math.isnan(wilson(0, 0)[0])


def test_newcombe_contains_point_and_is_ordered():
    d, lo, hi = newcombe_diff(56, 70, 48, 80)
    assert lo < d < hi and d == pytest.approx(0.2)


def test_fisher_and_chi_square_detect_obvious_difference():
    assert fisher_2x2(20, 0, 0, 20)["p"] < 1e-6
    assert chi_square([[20, 0], [0, 20], [10, 10]])["p"] < 1e-6
    assert fisher_2x2(5, 5, 5, 5)["p"] == pytest.approx(1.0)


def test_mcnemar_uses_only_discordant_pairs():
    pairs = [(True, True)] * 30 + [(False, False)] * 30 + [(False, True)] * 10
    r = mcnemar_exact(pairs)
    assert r["discordant"] == 10 and r["b_only"] == 10 and r["p"] < 0.01
    assert mcnemar_exact([(True, True)] * 5)["p"] == 1.0


def test_holm_monotone_and_correct():
    r = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert r["a"]["p_holm"] == pytest.approx(0.03)
    assert r["c"]["p_holm"] == pytest.approx(0.06) and r["b"]["p_holm"] == pytest.approx(0.06)
    assert r["a"]["reject"] and not r["b"]["reject"]


def test_fisher_one_sided():
    two = fisher_2x2(8, 2, 2, 8)
    one = fisher_2x2(8, 2, 2, 8, alternative="greater")
    assert one["p"] < two["p"] and abs(one["p"] - two["p"] / 2) < 1e-9


def test_rxc_exact_matches_fisher_on_2x2_and_is_reproducible():
    r1 = rxc_exact([[8, 2], [2, 8]], n_resamples=20_000)
    r2 = rxc_exact([[8, 2], [2, 8]], n_resamples=20_000)
    assert r1["p"] == r2["p"]
    assert abs(r1["p"] - fisher_2x2(8, 2, 2, 8)["p"]) < 0.01
    assert rxc_exact([[5, 5], [5, 5], [5, 5]], n_resamples=2_000)["p"] > 0.9
