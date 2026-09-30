from bench.items import BenchItem, read_jsonl
from bench.prompts import FEWSHOT_IDS, FEWSHOT_PATH, build_messages
from bench.runners.llm import parse_record, run


def _items():
    return [i for i in read_jsonl(FEWSHOT_PATH, BenchItem) if i.item_id not in FEWSHOT_IDS]


def test_messages_zero_and_few_shot():
    zero = build_messages("c/o headache", "zeroshot")
    few = build_messages("c/o headache", "fewshot")
    assert [m["role"] for m in zero] == ["system", "user"]
    assert len(few) == 2 + 2 * len(FEWSHOT_IDS)
    assert "vaginal_bleeding" in zero[0]["content"]  # vocabulary is listed
    assert '"start"' not in few[2]["content"]  # examples never show offsets


def test_parse_record_accepts_valid_and_rejects_invalid():
    fever = '{"concept": "fever", "assertion": "present", "evidence": {"text": "fever"}}'
    rec, err = parse_record('{"findings": [' + fever + "]}")
    assert rec is not None and err is None
    rec, err = parse_record('{"findings": [{"concept": "not_a_concept", "assertion": "present"}]}')
    assert rec is None and err
    rec, err = parse_record("not json")
    assert rec is None and err


def test_run_records_outputs_errors_and_tokens():
    items = _items()[:2]
    outputs = iter(['{"findings": []}', "broken"])
    preds = run(items, lambda msgs: (next(outputs), len(msgs)), "fake", "fewshot")
    assert preds[0].record is not None and preds[0].prompt_tokens == 2 + 2 * len(FEWSHOT_IDS)
    assert preds[1].record is None and preds[1].error and preds[1].raw_output == "broken"
