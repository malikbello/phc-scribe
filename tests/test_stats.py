import math

import pytest

from bench.stats import Ratio, bootstrap_ci, mcnemar_exact, paired_bootstrap_diff


def test_ratio_value_and_empty_denominator():
    assert Ratio.of([1, 2], [2, 2]).value() == 0.75
    assert math.isnan(Ratio.of([0, 0], [0, 0]).value())


def test_bootstrap_ci_brackets_point_and_is_seeded():
    r = Ratio.of([1] * 70 + [0] * 30, [1] * 100)
    a = bootstrap_ci(r, n_resamples=2000, seed=1)
    b = bootstrap_ci(r, n_resamples=2000, seed=1)
    assert a == b
    assert a.low <= a.point == 0.7 <= a.high
    assert 0.55 < a.low < 0.7 < a.high < 0.85


def test_constant_metric_has_zero_width_ci():
    ci = bootstrap_ci(Ratio.of([1] * 10, [1] * 10), n_resamples=500)
    assert ci.low == ci.high == ci.point == 1.0


def test_groups_are_resampled_together():
    # Pairs of identical items: grouping halves the effective sample size.
    num = [1, 1, 0, 0] * 10
    den = [1] * 40
    groups = [f"g{i // 2}" for i in range(40)]
    ungrouped = bootstrap_ci(Ratio.of(num, den), n_resamples=4000, seed=3)
    grouped = bootstrap_ci(Ratio.of(num, den), groups=groups, n_resamples=4000, seed=3)
    assert grouped.n_groups == 20
    assert (grouped.high - grouped.low) > (ungrouped.high - ungrouped.low)


def test_paired_diff_detects_a_clear_improvement():
    base = Ratio.of([1] * 50 + [0] * 50, [1] * 100)
    cand = Ratio.of([1] * 90 + [0] * 10, [1] * 100)
    diff = paired_bootstrap_diff(base, cand, n_resamples=2000)
    assert diff.point == pytest.approx(0.4)
    assert diff.excludes_zero_above()


def test_paired_diff_of_identical_systems_is_zero():
    r = Ratio.of([1, 0, 1, 1], [1, 1, 1, 1])
    diff = paired_bootstrap_diff(r, r, n_resamples=500)
    assert diff.low == diff.high == diff.point == 0


def test_mcnemar_exact_known_values():
    # 0 vs 6 discordant pairs: two-sided exact p = 2 * 0.5**6
    res = mcnemar_exact([False] * 6 + [True] * 4, [True] * 6 + [True] * 4)
    assert (res.only_baseline, res.only_candidate) == (0, 6)
    assert res.p_value == pytest.approx(2 * 0.5**6)
    assert mcnemar_exact([True, False], [True, False]).p_value == 1.0


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        mcnemar_exact([True], [True, False])
    with pytest.raises(ValueError):
        paired_bootstrap_diff(Ratio.of([1], [1]), Ratio.of([1, 1], [1, 1]))
