"""Uncertainty and significance for PHC-Scribe-Bench (docs/eval-plan.md, sections 5 and 6).

Every metric we report is a ratio of sums over items (recall = sum TP / sum (TP + FN),
micro-F1 = 2TP / (2TP + FP + FN), rates = count / count). Ratios of sums are additive
over groups, so the bootstrap resamples *groups* (a source note and its translation
share a group) by summing per-group numerators and denominators. That keeps pairs
together, as the eval plan requires, and is fast enough for 10,000 resamples.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

DEFAULT_RESAMPLES = 10_000


@dataclass(frozen=True)
class Ratio:
    """Per-item numerator and denominator of a ratio-of-sums metric."""

    num: NDArray[np.float64]
    den: NDArray[np.float64]

    @classmethod
    def of(cls, num: Sequence[float], den: Sequence[float]) -> Ratio:
        n, d = np.asarray(num, dtype=float), np.asarray(den, dtype=float)
        if n.shape != d.shape or n.ndim != 1:
            raise ValueError("num and den must be 1-D and the same length")
        return cls(n, d)

    def value(self) -> float:
        total = self.den.sum()
        return float(self.num.sum() / total) if total else math.nan

    def __len__(self) -> int:
        return len(self.num)


@dataclass(frozen=True)
class Interval:
    point: float
    low: float
    high: float
    n_items: int
    n_groups: int

    def excludes_zero_above(self) -> bool:
        """True if the whole interval is above zero (the P1/P2 success test)."""
        return self.low > 0


def _group_sums(
    ratio: Ratio, groups: Sequence[str] | None
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    if groups is None:
        return ratio.num, ratio.den
    if len(groups) != len(ratio):
        raise ValueError("groups must have one entry per item")
    _, inverse = np.unique(np.asarray(groups), return_inverse=True)
    k = int(inverse.max()) + 1 if len(inverse) else 0
    num = np.bincount(inverse, weights=ratio.num, minlength=k).astype(np.float64)
    den = np.bincount(inverse, weights=ratio.den, minlength=k).astype(np.float64)
    return num, den


def _resample_ratio(
    num: NDArray[np.float64], den: NDArray[np.float64], idx: NDArray[np.intp]
) -> NDArray[np.float64]:
    n, d = num[idx].sum(axis=1), den[idx].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(d > 0, n / np.where(d > 0, d, 1), np.nan)


def _percentiles(samples: NDArray[np.float64], alpha: float) -> tuple[float, float]:
    samples = samples[~np.isnan(samples)]
    if samples.size == 0:
        return math.nan, math.nan
    lo, hi = np.percentile(samples, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def bootstrap_ci(
    ratio: Ratio,
    *,
    groups: Sequence[str] | None = None,
    n_resamples: int = DEFAULT_RESAMPLES,
    alpha: float = 0.05,
    seed: int = 0,
) -> Interval:
    """Percentile bootstrap CI for a ratio-of-sums metric, resampling groups."""
    num, den = _group_sums(ratio, groups)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(num), size=(n_resamples, len(num)))
    low, high = _percentiles(_resample_ratio(num, den, idx), alpha)
    return Interval(ratio.value(), low, high, len(ratio), len(num))


def paired_bootstrap_diff(
    baseline: Ratio,
    candidate: Ratio,
    *,
    groups: Sequence[str] | None = None,
    n_resamples: int = DEFAULT_RESAMPLES,
    alpha: float = 0.05,
    seed: int = 0,
) -> Interval:
    """CI for ``candidate - baseline`` with both systems scored on the same items.

    The same resampled groups are used for both systems, so the interval reflects the
    paired design (eval plan P1/P2).
    """
    if len(baseline) != len(candidate):
        raise ValueError("paired comparison needs the same items for both systems")
    bn, bd = _group_sums(baseline, groups)
    cn, cd = _group_sums(candidate, groups)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(bn), size=(n_resamples, len(bn)))
    diff = _resample_ratio(cn, cd, idx) - _resample_ratio(bn, bd, idx)
    low, high = _percentiles(diff, alpha)
    return Interval(candidate.value() - baseline.value(), low, high, len(baseline), len(bn))


@dataclass(frozen=True)
class McNemar:
    only_baseline: int  # items the baseline got right and the candidate got wrong
    only_candidate: int  # items the candidate got right and the baseline got wrong
    p_value: float


def mcnemar_exact(baseline_ok: Sequence[bool], candidate_ok: Sequence[bool]) -> McNemar:
    """Exact (binomial) two-sided McNemar test on paired per-item outcomes."""
    if len(baseline_ok) != len(candidate_ok):
        raise ValueError("paired test needs the same items for both systems")
    b = sum(1 for x, y in zip(baseline_ok, candidate_ok, strict=True) if x and not y)
    c = sum(1 for x, y in zip(baseline_ok, candidate_ok, strict=True) if y and not x)
    n = b + c
    if n == 0:
        return McNemar(b, c, 1.0)
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n
    return McNemar(b, c, min(1.0, 2 * tail))
