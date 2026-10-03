from bench.items import BenchItem
from bench.two_view import asr_views, audio_id, fold, relocate
from phc_scribe.encounter import Encounter


def teacher_item(aid: str, text: str, findings: list[tuple[str, str, str]]) -> BenchItem:
    record = Encounter.model_validate(
        {
            "findings": [
                {"concept": c, "assertion": a, "evidence": {"text": q}} for c, a, q in findings
            ]
        }
    )
    return BenchItem(
        item_id=f"t-pcm-{aid}",
        group_id="wazobia:spk1",
        stratum="T",
        language="pcm",
        origin="real",
        transcript=text,
        gold=record,
    )


def test_fold_strips_tone_marks_case_and_punctuation():
    assert fold("Ọmọ inú mi, KÒ mì!") == "omo inu mi ko mi"


def test_relocate_returns_verbatim_asr_words_for_a_close_match():
    asr = "since yesterday di baby no move at all o"
    assert relocate("the baby no move at all", asr) == "di baby no move at all"


def test_relocate_handles_tone_mark_differences():
    asr = "omo inu mi ko mi daadaa bi ti tele mo"
    assert relocate("Ọmọ inú mi kò mì dáadáa", asr) == "omo inu mi ko mi daadaa"


def test_relocate_refuses_a_distant_match():
    assert relocate("blood dey comot", "i dey go market tomorrow morning") is None


def test_asr_views_move_quotes_and_keep_the_group():
    item = teacher_item(
        "pcm_f_1_he_01",
        "Since yesterday the baby no move at all.",
        [("reduced_fetal_movement", "present", "the baby no move at all")],
    )
    assert audio_id(item) == "pcm_f_1_he_01"
    views, rep = asr_views([item], {"pcm_f_1_he_01": "since yesterday di baby no move at all"})
    [v] = views
    assert v.item_id.endswith("-asr") and v.group_id == item.group_id
    assert v.transcript == "since yesterday di baby no move at all"
    evidence = v.gold.findings[0].evidence
    assert evidence is not None and evidence.text == "di baby no move at all"
    assert rep.added == 1


def test_asr_view_dropped_when_any_quote_is_lost():
    item = teacher_item(
        "x",
        "Blood dey comot and my head dey pain.",
        [("vaginal_bleeding", "present", "Blood dey comot")],
    )
    views, rep = asr_views([item], {"x": "i dey go market tomorrow"})
    assert views == [] and rep.quote_not_found == 1


def test_items_without_asr_are_counted_not_invented():
    item = teacher_item("y", "general talk", [])
    views, rep = asr_views([item], {})
    assert views == [] and rep.no_asr == 1


def test_relocate_keeps_a_leading_negation_cue():
    assert relocate("no be blood", "e nor be blood wey i see") == "nor be blood"


def test_wer_counts_edits_over_folded_words():
    from bench.wer import corpus_wer, edit_errors

    assert edit_errors("Ọmọ inú mi kò mì", "omo inu mi ko mi") == (0, 5)  # tone marks folded
    assert edit_errors("the baby no move", "di baby move") == (2, 4)  # 1 substitution, 1 deletion
    assert corpus_wer([("a b c d", "a b c d"), ("a b", "x b")]) == 1 / 6  # pooled, not averaged
