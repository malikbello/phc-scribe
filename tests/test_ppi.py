import random

import numpy as np

from bench.metrics import ItemScore, metric_ratios
from bench.ppi import Design, clopper_pearson_upper, ppi_ci, ppi_paired_diff, safety_stop


def _score(item_id: str, gold_danger: bool, pred_danger: bool, group: str = "g") -> ItemScore:
    """One item with at most one danger sign (recall and false-alarm rate depend on it)."""
    return ItemScore(
        item_id=item_id,
        group_id=group,
        schema_valid=True,
        danger_tp=int(gold_danger and pred_danger),
        danger_fn=int(gold_danger and not pred_danger),
        danger_fp=int(pred_danger and not gold_danger),
        gold_has_danger=gold_danger,
        pred_has_danger=pred_danger,
        pair_tp=0,
        pair_fp=0,
        pair_fn=0,
        bp_gold=False,
        bp_exact=False,
        ga_gold=False,
        ga_exact=False,
        flags_gold=0,
        flags_hit=0,
        fields_total=0,
        fields_ungrounded=0,
    )


def _world(seed: int = 0, n: int = 400):
    """Half the items in A (hard), half in B. Truth: 40% of A and 5% of B have a danger sign.
    The system detects 80% of them. The committee misses the hard ones: in A, 60% of the
    danger signs the system also misses, which inflates the system's recall under committee
    gold (the realistic failure: hard items are hard for every model)."""
    rng = random.Random(seed)  # noqa: S311 (simulation, not security)
    ids = [f"i{i:03d}" for i in range(n)]
    strata = {i: ("A" if k < n // 2 else "B") for k, i in enumerate(ids)}
    groups = {i: f"s{k % 20}" for k, i in enumerate(ids)}
    truth = {i: rng.random() < (0.4 if strata[i] == "A" else 0.05) for i in ids}
    pred = {i: truth[i] and rng.random() < 0.8 for i in ids}
    committee_gold = {
        i: truth[i] and not (strata[i] == "A" and not pred[i] and rng.random() < 0.6) for i in ids
    }
    return ids, strata, groups, truth, committee_gold, pred


def _scores(ids, gold, pred, groups):
    return {i: _score(i, gold[i], pred[i], groups[i]) for i in ids}


def test_all_labelled_equals_the_human_metric_and_no_correction_equals_committee():
    ids, strata, groups, truth, cgold, pred = _world()
    committee = _scores(ids, cgold, pred, groups)
    human = _scores(ids, truth, pred, groups)
    design = Design.of(ids, strata, groups, human)
    est = ppi_ci(design, committee, human, "danger_recall", n_resamples=200)
    true = metric_ratios(list(human.values()))["danger_recall"].value()
    assert abs(est.point - true) < 1e-12
    agree = {i: committee[i] for i in ids[:50]}  # humans agree with the committee
    design = Design.of(ids, strata, groups, agree)
    est = ppi_ci(design, committee, agree, "danger_recall", n_resamples=200)
    assert abs(est.point - metric_ratios(list(committee.values()))["danger_recall"].value()) < 1e-12


def test_ppi_removes_the_committee_bias_on_average():
    ids, strata, groups, truth, cgold, pred = _world(seed=1)
    committee = _scores(ids, cgold, pred, groups)
    full_human = _scores(ids, truth, pred, groups)
    true = metric_ratios(list(full_human.values()))["danger_recall"].value()
    naive = metric_ratios(list(committee.values()))["danger_recall"].value()
    rng = random.Random(2)  # noqa: S311 (simulation, not security)
    estimates = []
    for _ in range(300):
        sample = rng.sample(ids[:200], 60) + rng.sample(ids[200:], 30)
        human = {i: full_human[i] for i in sample}
        design = Design.of(ids, strata, groups, human)
        estimates.append(ppi_ci(design, committee, human, "danger_recall", n_resamples=1).point)
    assert abs(naive - true) > 0.02  # the committee alone is biased
    assert abs(float(np.mean(estimates)) - true) < 0.01  # PPI is not, on average


def test_paired_difference_of_identical_systems_is_zero():
    ids, strata, groups, truth, cgold, pred = _world(seed=3)
    committee = _scores(ids, cgold, pred, groups)
    human = {i: _score(i, truth[i], pred[i], groups[i]) for i in ids[::5]}
    design = Design.of(ids, strata, groups, human)
    diff = ppi_paired_diff(
        design, (committee, human), (committee, human), "danger_recall", n_resamples=300
    )
    assert diff.point == 0 and diff.low == 0 and diff.high == 0


def test_safety_stop_bounds():
    assert abs(clopper_pearson_upper(0, 60) - (1 - 0.05 ** (1 / 60))) < 1e-6
    assert not safety_stop(0, 60).triggered
    one = safety_stop(1, 60)
    assert one.triggered and 0.07 < one.upper_bound < 0.08
