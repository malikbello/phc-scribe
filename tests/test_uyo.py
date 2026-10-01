from bench.uyo import (
    SYMPTOM_FINDINGS,
    Proportion,
    UyoRecord,
    clopper_pearson,
    evaluate,
    to_encounter,
)
from phc_scribe.vocab import load_vocabulary


def _rec(symptom="Cough", diagnosis="Malaria", bp="110/70", temp="36.5"):
    return UyoRecord(patient="p", symptom=symptom, diagnosis=diagnosis, bp=bp, temperature=temp)


def test_every_mapped_concept_exists_in_the_vocabulary():
    known = {c.id for c in load_vocabulary().concepts}
    assert {c for cs in SYMPTOM_FINDINGS.values() for c in cs} <= known


def test_to_encounter_maps_vitals_findings_and_urine_protein():
    r = to_encounter(_rec(symptom=" Bleeding  per vaginam ", bp="150/100", temp="38.2"))
    assert r.vitals.blood_pressure and (
        r.vitals.blood_pressure.systolic,
        r.vitals.blood_pressure.diastolic,
    ) == (150, 100)
    assert r.vitals.temperature and r.vitals.temperature.value == 38.2
    assert [f.concept for f in r.findings] == ["vaginal_bleeding"]
    p = to_encounter(_rec(symptom="Protein in Urine"))
    assert [t.test for t in p.anc.tests] == ["urine_protein"]
    assert to_encounter(_rec(symptom="Sugar in urine", bp="n/a")).findings == []


def test_clopper_pearson_matches_known_values():
    lo, hi = clopper_pearson(5, 10)
    assert abs(lo - 0.1871) < 1e-3 and abs(hi - 0.8129) < 1e-3
    assert clopper_pearson(0, 10)[0] == 0.0 and abs(clopper_pearson(0, 10)[1] - 0.3085) < 1e-3
    assert clopper_pearson(10, 10)[1] == 1.0


def test_evaluate_counts_against_diagnoses():
    res = evaluate(
        [
            _rec(diagnosis="Eclampsia", bp="170/115"),  # severe BP: flagged
            _rec(diagnosis="Hypertension", bp="120/80"),  # normal BP: missed
            _rec(diagnosis="Normal scan result", bp="110/70"),  # not flagged
            _rec(diagnosis="Normal scan result", symptom="Bleeding per vaginam"),  # flagged
        ]
    )
    assert res["danger_diagnosis_flagged"] == Proportion(1, 2)
    assert res["hypertensive_diagnosis_bp_flag"] == Proportion(1, 2)
    assert res["normal_scan_flagged"] == Proportion(1, 2)
    assert "VS-001" in res["flags_per_rule"]
