"""Stratified prediction-powered inference for the counted benchmark (ADR-0025, section 5).

Every item has a committee label; a seeded random sample within each stratum also has a
human label. For a ratio-of-sums metric R = sum(num) / sum(den), each total is estimated as

    T = sum_k [ sum_{i in k} x_c(i) + (N_k / n_k) * sum_{j in S_k} (x_h(j) - x_c(j)) ]

(x_c from committee gold, x_h from human gold, S_k the human sample in stratum k, N_k and
n_k their sizes), and R_hat = T_num / T_den. The correction term removes the committee's
bias in expectation whatever the committee gets wrong (Angelopoulos et al., Science 2023;
the stratified form, Fisch et al., NeurIPS 2024).

Uncertainty: a cluster bootstrap within strata. Each resample draws speakers (groups) with
replacement inside each stratum; a drawn group brings all its items (committee term) and its
human-labelled items (correction term), and N_k / n_k is recomputed from the resample. Paired
comparisons (fine-tuned - base) use the same resamples for both systems, as the eval plan's
paired bootstrap does.

Also here: the ADR-0025 safety stop (missed danger signs in the stratum-B audit).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from bench.metrics import ItemScore, metric_ratios
from bench.stats import DEFAULT_RESAMPLES, Interval, _percentiles

SAFETY_MISS_LIMIT = 0.05  # ADR-0025 §6: upper 95% bound of the stratum-B miss rate


@dataclass(frozen=True)
class Design:
    """Which stratum and speaker each item belongs to, and whether a human labelled it."""

    item_ids: list[str]
    strata: NDArray[np.intp]
    groups: NDArray[np.intp]
    sampled: NDArray[np.bool_]

    @classmethod
    def of(
        cls,
        item_ids: Sequence[str],
        strata: Mapping[str, str],
        groups: Mapping[str, str],
        human: Mapping[str, object],
    ) -> Design:
        ids = list(item_ids)
        _, s = np.unique([strata[i] for i in ids], return_inverse=True)
        _, g = np.unique([f"{strata[i]}|{groups[i]}" for i in ids], return_inverse=True)
        return cls(ids, s.astype(np.intp), g.astype(np.intp), np.array([i in human for i in ids]))


def _columns(
    design: Design,
    committee: Mapping[str, ItemScore],
    human: Mapping[str, ItemScore],
    metric: str,
) -> tuple[NDArray[np.float64], ...]:
    """Per-item committee num/den and human-minus-committee differences (0 if unlabelled)."""
    c_scores = [committee[i] for i in design.item_ids]
    rc = metric_ratios(c_scores)[metric]
    h_scores = [human.get(i, committee[i]) for i in design.item_ids]
    rh = metric_ratios(h_scores)[metric]
    mask = design.sampled.astype(np.float64)
    return rc.num, rc.den, (rh.num - rc.num) * mask, (rh.den - rc.den) * mask


def _totals(design: Design, cols: tuple[NDArray[np.float64], ...], weights: NDArray[np.float64]):
    """PPI numerator and denominator totals for each row of group weights (R x G)."""
    c_num, c_den, d_num, d_den = cols
    n_groups = int(design.groups.max()) + 1

    def per_group(x: NDArray[np.float64]) -> NDArray[np.float64]:
        return np.bincount(design.groups, weights=x, minlength=n_groups)

    group_stratum = np.zeros(n_groups, dtype=np.intp)
    group_stratum[design.groups] = design.strata
    count = per_group(np.ones(len(design.item_ids)))
    labelled = per_group(design.sampled.astype(np.float64))
    t_num = np.zeros(weights.shape[0])
    t_den = np.zeros(weights.shape[0])
    for k in np.unique(design.strata):
        cols_k = group_stratum == k
        w = weights[:, cols_k]
        n_all = w @ count[cols_k]
        n_lab = w @ labelled[cols_k]
        scale = np.where(n_lab > 0, n_all / np.where(n_lab > 0, n_lab, 1), 0.0)
        t_num += w @ per_group(c_num)[cols_k] + scale * (w @ per_group(d_num)[cols_k])
        t_den += w @ per_group(c_den)[cols_k] + scale * (w @ per_group(d_den)[cols_k])
    return t_num, t_den


def _ratio(t_num: NDArray[np.float64], t_den: NDArray[np.float64]) -> NDArray[np.float64]:
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(t_den > 0, t_num / np.where(t_den > 0, t_den, 1), np.nan)


def _weights(design: Design, n_resamples: int, seed: int) -> NDArray[np.float64]:
    """Cluster-bootstrap weights: groups drawn with replacement within each stratum."""
    rng = np.random.default_rng(seed)
    n_groups = int(design.groups.max()) + 1
    group_stratum = np.zeros(n_groups, dtype=np.intp)
    group_stratum[design.groups] = design.strata
    w = np.zeros((n_resamples, n_groups))
    for k in np.unique(design.strata):
        cols = np.flatnonzero(group_stratum == k)
        w[:, cols] = rng.multinomial(len(cols), np.full(len(cols), 1 / len(cols)), n_resamples)
    return w


def ppi_ci(
    design: Design,
    committee: Mapping[str, ItemScore],
    human: Mapping[str, ItemScore],
    metric: str,
    *,
    n_resamples: int = DEFAULT_RESAMPLES,
    alpha: float = 0.05,
    seed: int = 0,
) -> Interval:
    """PPI point estimate and cluster-bootstrap CI for one system's metric."""
    cols = _columns(design, committee, human, metric)
    point = float(_ratio(*_totals(design, cols, np.ones((1, int(design.groups.max()) + 1))))[0])
    boot = _ratio(*_totals(design, cols, _weights(design, n_resamples, seed)))
    low, high = _percentiles(boot, alpha)
    return Interval(point, low, high, len(design.item_ids), int(design.groups.max()) + 1)


def ppi_paired_diff(
    design: Design,
    base: tuple[Mapping[str, ItemScore], Mapping[str, ItemScore]],
    candidate: tuple[Mapping[str, ItemScore], Mapping[str, ItemScore]],
    metric: str,
    *,
    n_resamples: int = DEFAULT_RESAMPLES,
    alpha: float = 0.05,
    seed: int = 0,
) -> Interval:
    """CI for candidate - base (each a (committee-gold scores, human-gold scores) pair)."""
    ones = np.ones((1, int(design.groups.max()) + 1))
    w = _weights(design, n_resamples, seed)
    cb = _columns(design, *base, metric)
    cc = _columns(design, *candidate, metric)
    point = float(_ratio(*_totals(design, cc, ones))[0] - _ratio(*_totals(design, cb, ones))[0])
    diff = _ratio(*_totals(design, cc, w)) - _ratio(*_totals(design, cb, w))
    low, high = _percentiles(diff, alpha)
    return Interval(point, low, high, len(design.item_ids), int(design.groups.max()) + 1)


def clopper_pearson_upper(k: int, n: int, alpha: float = 0.05) -> float:
    """Exact one-sided upper (1 - alpha) bound for a binomial proportion, by bisection on
    the binomial CDF: the largest p with P(X <= k | n, p) >= alpha."""
    if n <= 0 or k >= n:
        return 1.0

    def cdf(p: float) -> float:
        return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))

    lo, hi = k / n, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if cdf(mid) > alpha else (lo, mid)
    return (lo + hi) / 2


@dataclass(frozen=True)
class SafetyStop:
    audited: int
    missed: int
    upper_bound: float
    triggered: bool


def safety_stop(missed: int, audited: int, limit: float = SAFETY_MISS_LIMIT) -> SafetyStop:
    """ADR-0025 section 6: if the stratum-B audit finds danger signs the committee missed, and
    the upper 95% bound of that miss rate is above `limit`, humans label all of stratum B."""
    upper = clopper_pearson_upper(missed, audited)
    return SafetyStop(audited, missed, upper, missed > 0 and upper > limit)
