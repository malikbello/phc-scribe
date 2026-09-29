"""Per-item scoring and metric definitions for PHC-Scribe-Bench (docs/eval-plan.md, section 5).

Definitions (draft; fixed at the pre-registration freeze):
- danger-sign recall: over gold (concept, positive) danger findings, where positive
  means ``present`` or ``possible``; a hit needs the same concept predicted positive.
- micro-F1: over (concept, assertion) pairs, ``not_mentioned`` excluded.
- false-alarm rate: share of items with no gold danger sign where the system
  predicts at least one.
- item danger detection (for McNemar): an item with at least one gold danger sign
  counts as detected only if every one of its gold danger signs is detected.
- numeric exact match: BP (both numbers) and gestational age (weeks), over items
  whose gold record has the value.
- schema-valid rate and ungrounded-field rate: from the pipeline's validation and
  grounding steps.
- rule-flag recall (secondary, not pre-registered yet): rules engine run on gold vs
  predicted records; share of gold flags (rule ids) that the prediction also raises.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from bench.stats import Interval, Ratio, bootstrap_ci
from phc_scribe.encounter import POSITIVE_ASSERTIONS, Assertion, Encounter
from phc_scribe.grounding import GroundingResult
from phc_scribe.rules import check
from phc_scribe.vocab import load_vocabulary


def danger_positives(record: Encounter, danger_ids: frozenset[str]) -> set[str]:
    return {
        str(f.concept)
        for f in record.findings
        if str(f.concept) in danger_ids and f.assertion in POSITIVE_ASSERTIONS
    }


def assertion_pairs(record: Encounter) -> set[tuple[str, str]]:
    return {
        (str(f.concept), str(f.assertion))
        for f in record.findings
        if f.assertion != Assertion.not_mentioned
    }


def rule_flags(record: Encounter) -> set[str]:
    return {f.rule_id for f in check(record)}


@dataclass(frozen=True)
class ItemScore:
    item_id: str
    group_id: str
    schema_valid: bool
    danger_tp: int
    danger_fn: int
    danger_fp: int
    gold_has_danger: bool
    pred_has_danger: bool
    pair_tp: int
    pair_fp: int
    pair_fn: int
    bp_gold: bool
    bp_exact: bool
    ga_gold: bool
    ga_exact: bool
    flags_gold: int
    flags_hit: int
    fields_total: int
    fields_ungrounded: int

    @property
    def all_danger_detected(self) -> bool:
        return self.gold_has_danger and self.danger_fn == 0


def score_item(
    item_id: str,
    group_id: str,
    gold: Encounter,
    pred: Encounter | None,
    grounding: GroundingResult | None = None,
) -> ItemScore:
    """Score one prediction. ``pred`` is None when the output failed schema validation."""
    danger_ids = load_vocabulary().danger_sign_ids
    gold_danger = danger_positives(gold, danger_ids)
    gold_pairs = assertion_pairs(gold)
    gold_flags = rule_flags(gold)
    gold_bp = gold.vitals.blood_pressure
    gold_ga = gold.anc.gestational_age

    if pred is None:
        pred_danger: set[str] = set()
        pred_pairs: set[tuple[str, str]] = set()
        pred_flags: set[str] = set()
        bp_exact = ga_exact = False
    else:
        pred_danger = danger_positives(pred, danger_ids)
        pred_pairs = assertion_pairs(pred)
        pred_flags = rule_flags(pred)
        pbp, pga = pred.vitals.blood_pressure, pred.anc.gestational_age
        bp_exact = bool(
            gold_bp
            and pbp
            and (pbp.systolic, pbp.diastolic) == (gold_bp.systolic, gold_bp.diastolic)
        )
        ga_exact = bool(gold_ga and pga and pga.weeks == gold_ga.weeks)

    return ItemScore(
        item_id=item_id,
        group_id=group_id,
        schema_valid=pred is not None,
        danger_tp=len(gold_danger & pred_danger),
        danger_fn=len(gold_danger - pred_danger),
        danger_fp=len(pred_danger - gold_danger),
        gold_has_danger=bool(gold_danger),
        pred_has_danger=bool(pred_danger),
        pair_tp=len(gold_pairs & pred_pairs),
        pair_fp=len(pred_pairs - gold_pairs),
        pair_fn=len(gold_pairs - pred_pairs),
        bp_gold=gold_bp is not None,
        bp_exact=bp_exact,
        ga_gold=gold_ga is not None,
        ga_exact=ga_exact,
        flags_gold=len(gold_flags),
        flags_hit=len(gold_flags & pred_flags),
        fields_total=grounding.fields_total if grounding else 0,
        fields_ungrounded=grounding.ungrounded if grounding else 0,
    )


def metric_ratios(scores: Sequence[ItemScore]) -> dict[str, Ratio]:
    """Every reported metric as a ratio of per-item sums (see bench.stats)."""

    def r(num: Iterable[float], den: Iterable[float]) -> Ratio:
        return Ratio.of(list(num), list(den))

    return {
        "danger_recall": r(
            (s.danger_tp for s in scores), (s.danger_tp + s.danger_fn for s in scores)
        ),
        "micro_f1": r(
            (2 * s.pair_tp for s in scores),
            (2 * s.pair_tp + s.pair_fp + s.pair_fn for s in scores),
        ),
        "false_alarm_rate": r(
            (float(s.pred_has_danger and not s.gold_has_danger) for s in scores),
            (float(not s.gold_has_danger) for s in scores),
        ),
        "item_danger_detection": r(
            (float(s.all_danger_detected) for s in scores),
            (float(s.gold_has_danger) for s in scores),
        ),
        "bp_exact": r((float(s.bp_exact) for s in scores), (float(s.bp_gold) for s in scores)),
        "ga_exact": r((float(s.ga_exact) for s in scores), (float(s.ga_gold) for s in scores)),
        "schema_valid_rate": r((float(s.schema_valid) for s in scores), (1.0 for _ in scores)),
        "ungrounded_rate": r(
            (s.fields_ungrounded for s in scores), (s.fields_total for s in scores)
        ),
        "rule_flag_recall": r((s.flags_hit for s in scores), (s.flags_gold for s in scores)),
    }


def summarise(scores: Sequence[ItemScore], *, seed: int = 0) -> dict[str, Interval]:
    groups = [s.group_id for s in scores]
    return {
        name: bootstrap_ci(ratio, groups=groups, seed=seed)
        for name, ratio in metric_ratios(scores).items()
    }
