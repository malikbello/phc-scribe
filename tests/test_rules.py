import pytest

from phc_scribe.encounter import Encounter
from phc_scribe.rules import Facts, check, load_rules, parse_rules, validate_condition

RULES = load_rules()
GOLDEN = [(rule, test) for rule in RULES.rules for test in rule.tests]


@pytest.mark.parametrize(("rule", "case"), GOLDEN, ids=[f"{r.id}: {t.name}" for r, t in GOLDEN])
def test_golden_cases(rule, case):
    assert rule.fires(case.facts) is case.fires


def test_every_danger_sign_concept_has_a_rule():
    from phc_scribe.vocab import load_vocabulary

    covered = set()

    def walk(cond):
        ((kind, spec),) = cond.items()
        if kind in ("any", "all"):
            for c in spec:
                walk(c)
        elif kind == "finding":
            covered.add(spec if isinstance(spec, str) else spec["concept"])

    for rule in RULES.rules:
        walk(rule.when)
    assert load_vocabulary().danger_sign_ids <= covered


def test_superseded_flags_are_hidden_and_most_severe_first():
    facts = Facts.from_dict(
        {"vitals": {"bp_systolic": 170, "bp_diastolic": 100}, "findings": {"fever": ["present"]}}
    )
    ids = [f.rule_id for f in RULES.evaluate(facts)]
    assert "VS-002" not in ids
    assert ids == ["VS-001", "DS-005"]


def test_check_from_a_record():
    record = Encounter.model_validate(
        {
            "findings": [
                {"concept": "severe_headache", "assertion": "possible", "evidence": {"text": "x y"}}
            ],
            "vitals": {
                "blood_pressure": {
                    "systolic": 145,
                    "diastolic": 95,
                    "evidence": {"text": "145/95"},
                },
                "temperature": {"value": 100.8, "unit": "[degF]", "evidence": {"text": "100.8"}},
            },
            "anc": {
                "tests": [
                    {
                        "test": "haemoglobin",
                        "value": 6.8,
                        "unit": "g/dL",
                        "evidence": {"text": "Hb 6.8"},
                    }
                ]
            },
        }
    )
    ids = [f.rule_id for f in check(record)]
    assert {"CB-001", "DS-003", "LB-001", "DS-005"} <= set(ids)
    assert "VS-002" not in ids


def test_no_findings_no_flags():
    assert check(Encounter()) == []


@pytest.mark.parametrize(
    "cond",
    [
        {"finding": "headache_ish"},
        {"vital": {"name": "bp", "gte": 140}},
        {"vital": {"name": "bp_systolic"}},
        {"test": {"name": "ferritin", "lt": 10}},
        {"any": []},
        {"not": {"finding": "fever"}},
        {"finding": "fever", "vital": {"name": "pulse", "gt": 100}},
    ],
)
def test_malformed_conditions_fail_loudly(cond):
    with pytest.raises(ValueError):
        validate_condition(cond, "test")


def test_rule_without_golden_test_is_rejected():
    data = {
        "version": "0",
        "sources": {"S": {"title": "t"}},
        "severities": {"urgent_referral": "", "refer": ""},
        "rules": [
            {
                "id": "X",
                "name": "x",
                "severity": "refer",
                "when": {"finding": "fever"},
                "message_en": "m",
                "source": {"ref": "S"},
            }
        ],
    }
    with pytest.raises(ValueError, match="golden test"):
        parse_rules(data)
