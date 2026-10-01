from bench.belebele import build_prompt, gold_letter, score

ROW = {
    "link": "x",
    "question_number": "1",
    "flores_passage": "Ìtàn kúkúrú.",
    "question": "Kí ni?",
    "mc_answer1": "a",
    "mc_answer2": "b",
    "mc_answer3": "c",
    "mc_answer4": "d",
    "correct_answer_num": "3",
}


def test_prompt_and_gold():
    p = build_prompt(ROW)
    assert "A. a\nB. b\nC. c\nD. d" in p and p.endswith("Answer:")
    assert gold_letter(ROW) == "C"


def test_score_picks_the_highest_letter():
    res = score(
        [ROW, {**ROW, "question_number": "2", "correct_answer_num": "1"}],
        lambda _: [0.1, 0.2, 0.9, 0.3],
    )
    assert res["n_items"] == 2 and res["accuracy"] == 0.5
    assert [i["pred"] for i in res["items"]] == ["C", "C"]
