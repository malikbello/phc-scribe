# ruff: noqa: E501  (the model card is a Markdown template; its lines are prose)
"""Upload the fine-tuned N-ATLaS ASR models (ADR-0026) to PRIVATE Hugging Face model repos.

    python scripts/publish_asr.py --models data/private/models/asrft-20261003/asr-ft

Creates (if missing) one private repo per language and uploads the model, processor,
training summary and a model card. The repos stay private (visible only to the owner's
account) until Malik switches them to gated on submission day (ADR-0015, ADR-0026). Names
carry the N-ATLaS Terms' "Powered by Awarri" suffix. Prints repo ids and commit hashes,
never the token. Needs HF_TOKEN with write access.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPOS = {
    "yo": "N-ATLaS-ASR-Health-Yoruba-Powered-by-Awarri",
    "pcm": "N-ATLaS-ASR-Health-Pidgin-Powered-by-Awarri",
}
BASE = {"yo": "NCAIR1/Yoruba-ASR", "pcm": "NCAIR1/NigerianAccentedEnglish"}
NAME = {"yo": "Yoruba", "pcm": "Nigerian Pidgin"}
RESULTS = Path(__file__).resolve().parents[1] / "results" / "asr" / "ft-vs-base.20261003.json"


def pct(x: float) -> str:
    """Percent, rounding halves up (0.5105 -> 51.1%), as everywhere else in the reports."""
    return f"{x * 100 + 1e-9:.1f}%"


def card(lang: str, summary: dict, result: dict) -> str:
    r = result["languages"][lang]
    d = r["wer_diff"]
    return f"""---
license: other
license_name: n-atlas-terms-of-use
base_model: {BASE[lang]}
language: [{"yo" if lang == "yo" else "pcm"}]
tags: [automatic-speech-recognition, whisper, n-atlas, health, nigeria]
---

# N-ATLaS ASR Health · {NAME[lang]} · Powered by Awarri

A fine-tune of [{BASE[lang]}](https://huggingface.co/{BASE[lang]}) (Whisper-Small) on
{NAME[lang]} speech from WazobiaSpeech (`train` split, CC-BY-4.0), built for PHC Scribe, an
offline antenatal-care scribe for Nigerian primary health care (NAIC 2026).

## Results (test pool, speakers never seen in training)
| | Base | This model | Difference [95% CI, paired bootstrap over speakers] |
|---|---|---|---|
| WER | {pct(r["base_wer"])} | **{pct(r["candidate_wer"])}** | {d["point"] * 100:+.1f} points [{d["low"] * 100:+.1f}, {d["high"] * 100:+.1f}] |
| CER | {pct(r["base_cer"])} | **{pct(r["candidate_cer"])}** | |

{r["clips"]} clips, {r["speakers"]} speakers (WazobiaSpeech `dev` + `dev_test`), language forced for both models, text folded (case, punctuation, tone marks) before scoring.

## Training
- {summary["train_clips"]:,} clips ({summary["train_hours"]} h) from 30 evenly spaced `train` shards, all domains; 5% of speakers held out as dev; the LLM's two-view training clips excluded.
- 2 epochs, learning rate 1e-5 (10% warm-up, linear decay), AdamW, batch 16, fp16, SpecAugment (time masking p = 0.05), {summary["steps"]} steps on one T4.
- Held-out speakers (dev, base -> fine-tuned): all {pct(summary["dev_base"]["wer_all"])} -> {pct(summary["dev_finetuned"]["wer_all"])}; health {pct(summary["dev_base"]["wer_health"])} -> {pct(summary["dev_finetuned"]["wer_health"])}; other domains {pct(summary["dev_base"]["wer_other"])} -> {pct(summary["dev_finetuned"]["wer_other"])}.

## Use and limits
- Decode with `language="{"yoruba" if lang == "yo" else "english"}"`, `task="transcribe"`.
- Trained on read and spontaneous speech, not clinic recordings; a health worker confirms every record made from its output.
- Licence: the N-ATLaS Terms of Use apply to this derivative (including the "Powered by Awarri" naming and the active-user limit without a commercial licence). WazobiaSpeech data: CC-BY-4.0, EqualyzAI / Data Science Nigeria.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--owner", default="malikbello")
    args = parser.parse_args()
    from huggingface_hub import HfApi

    api = HfApi()
    result = json.loads(RESULTS.read_text(encoding="utf-8"))
    for lang, name in REPOS.items():
        folder = args.models / lang
        summary = json.loads((folder / "asrft-summary.json").read_text(encoding="utf-8"))
        repo = f"{args.owner}/{name}"
        api.create_repo(repo, private=True, exist_ok=True, repo_type="model")
        if not api.model_info(repo).private:
            raise SystemExit(f"{repo} exists and is not private: refusing to upload")
        (folder / "README.md").write_text(card(lang, summary, result), encoding="utf-8")
        info = api.upload_folder(
            repo_id=repo,
            folder_path=str(folder),
            commit_message=f"ADR-0026 fine-tune ({summary['steps']} steps)",
        )
        print(f"{repo}: private, commit {info.oid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
