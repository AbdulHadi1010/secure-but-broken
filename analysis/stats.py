"""Statistics used for every number in the paper (CLAUDE.md §8). Pure functions, unit-tested.

- Wilson score interval for proportions (e.g. SAFE_FIX rate per model/condition)
- Fisher's exact test (2x2) / chi-square (r x c) for rates across models or types
- Exact McNemar for paired conditions (same case, model, repeat under C0 vs C2)
- Holm-Bonferroni correction across a family of tests
- Effect sizes: risk difference with Wilson-based CI (Newcombe), odds ratio
"""

from __future__ import annotations

import math

from scipy import stats

Z95 = 1.959963984540054


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float, float]:
    """(p, low, high). n=0 -> (nan, 0, 1)."""
    if n == 0:
        return float("nan"), 0.0, 1.0
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, centre - half), min(1.0, centre + half)


def newcombe_diff(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float, float]:
    """Risk difference p1 - p2 with Newcombe's hybrid score interval (method 10)."""
    p1, l1, u1 = wilson(k1, n1)
    p2, l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


def fisher_2x2(a: int, b: int, c: int, d: int, alternative: str = "two-sided") -> dict:
    """Table [[a, b], [c, d]] (rows: groups, cols: success/failure). alternative 'greater' = row 1 has higher odds."""
    odds, p = stats.fisher_exact([[a, b], [c, d]], alternative=alternative)
    return {"odds_ratio": odds, "p": p, "alternative": alternative}


def chi_square(table: list[list[int]]) -> dict:
    chi2, p, dof, expected = stats.chi2_contingency(table)
    return {"chi2": chi2, "dof": dof, "p": p, "min_expected": float(expected.min())}


def rxc_exact(table: list[list[int]], n_resamples: int = 100_000, seed: int = 20261016) -> dict:
    """Monte Carlo permutation test of independence for an r x c table (Fisher-Freeman-Halton style, chi-square
    statistic, margins fixed): used instead of chi-square when an expected count is < 5 (protocol RQ3).
    Fixed seed, so the p-value is reproducible."""
    import numpy as np

    tab = np.asarray(table, dtype=int)
    rows = np.repeat(np.arange(tab.shape[0]), tab.sum(axis=1))
    cols = np.repeat(np.arange(tab.shape[1]), tab.sum(axis=0))
    expected = np.outer(tab.sum(axis=1), tab.sum(axis=0)) / tab.sum()

    def stat(t):
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.nansum((t - expected) ** 2 / np.where(expected == 0, np.nan, expected))

    observed = stat(tab)
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(n_resamples):
        perm = np.zeros_like(tab)
        np.add.at(perm, (rows, rng.permutation(cols)), 1)
        hits += stat(perm) >= observed - 1e-12
    return {"chi2": float(observed), "p": (hits + 1) / (n_resamples + 1), "n_resamples": n_resamples, "seed": seed}


def mcnemar_exact(pairs: list[tuple[bool, bool]]) -> dict:
    """pairs: (success under A, success under B) for the same unit. Exact binomial test on discordant pairs."""
    b = sum(1 for x, y in pairs if x and not y)  # A only
    c = sum(1 for x, y in pairs if y and not x)  # B only
    n = b + c
    p = 1.0 if n == 0 else stats.binomtest(b, n, 0.5).pvalue
    return {"a_only": b, "b_only": c, "discordant": n, "p": p}


def holm(pvalues: dict[str, float], alpha: float = 0.05) -> dict[str, dict]:
    """Holm-Bonferroni step-down. Returns adjusted p and reject flag per test."""
    order = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(order)
    out, running = {}, 0.0
    for i, (name, p) in enumerate(order):
        adj = min(1.0, max(running, (m - i) * p))
        running = adj
        out[name] = {"p": p, "p_holm": adj, "reject": adj < alpha}
    return out
