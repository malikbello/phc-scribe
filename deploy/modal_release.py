# ruff: noqa: E501  (model cards are Markdown; their lines are prose)
"""Release the models for judging: gated Hugging Face repos with automatic approval (ADR-0015;
Malik chose "Gated" on 11 Oct 2026).

    modal run deploy/modal_release.py            # check only: prints what it would change
    modal run deploy/modal_release.py --apply    # update cards, upload int8, then gate

Order, so a repo is never visible half-finished:
1. update each card (the GGUF card from docs/cards/model-card.md) and add the access form:
   the N-ATLaS Terms checkbox and an affiliation field;
2. upload the int8 speech builds (ADR-0032): `ct2-int8/` in the Yoruba and Pidgin repos, and
   a new repo for the English model;
3. check that every repo holds model files only (refuse anything else, such as data);
4. only then switch each repo from private to gated with automatic approval.
Prints repo ids and states, never the token.
"""

from __future__ import annotations

from pathlib import Path

import modal

app = modal.App("phc-scribe-release")
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "huggingface_hub[hf_xet]>=0.32", "pyyaml>=6.0"
)
runs = modal.Volume.from_name("phc-scribe-runs")
SECRETS = [modal.Secret.from_name("phc-scribe-hf-write")]  # HF_TOKEN with write access

GGUF = "N-ATLaS-Health-ANC-Scribe-GGUF-Powered-by-Awarri"
ASR = {
    "yo": "N-ATLaS-ASR-Health-Yoruba-Powered-by-Awarri",
    "pcm": "N-ATLaS-ASR-Health-Pidgin-Powered-by-Awarri",
}
EN_INT8 = "N-ATLaS-ASR-NigerianAccentedEnglish-int8-Powered-by-Awarri"

GATE = {
    "extra_gated_prompt": (
        "This model is a derivative of N-ATLaS and is governed by the N-ATLaS Terms of Use "
        '(Open-Source Research and Innovation License v1.0): it keeps the "Powered by Awarri" '
        "name, and deployments are limited to 1,000 active end-users per rolling 30 days without "
        "a commercial licence from Awarri Technologies. It drafts antenatal records for a health "
        "worker to check and confirm; it is not a diagnostic device. Access is approved automatically."
    ),
    "extra_gated_fields": {
        "I agree to the N-ATLaS Terms of Use": "checkbox",
        "Affiliation": "text",
    },
}
# Files a released model repo may hold. Anything else stops the release.
ALLOWED = (
    "README.md",
    ".gitattributes",
    "config.json",
    "generation_config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
    "merges.txt",
    "normalizer.json",
    "processor_config.json",
    "preprocessor_config.json",
    "special_tokens_map.json",
    "added_tokens.json",
    "asrft-summary.json",
    "model.bin",
    "vocabulary.json",
)

INT8_SECTION = """
## int8 build for CPUs (CTranslate2), in `ct2-int8/`
The same model converted to int8 with CTranslate2 (PHC Scribe ADR-0032, Tier 2): 242 MB instead of 967 MB, and several times faster on a laptop CPU. Checked before release against a pre-registered rule (int8 may not be more than 3 points worse in word error rate, upper bound of the 95% CI), on public dev speech, with the decoding PHC Scribe serves (greedy, language forced, windows of at most 20 s):

| Dev clips | fp32 WER | int8 WER | Difference [95% CI] |
|---|---|---|---|
| {dev} | {fp32}% | {int8}% | {diff:+.2f} [{lo:+.2f}, {hi:+.2f}] |

Serve it with PHC Scribe (`PHC_ASR=ct2`, `PHC_ASR_INT8_MODELS=<lang>=<folder>`).
"""

EN_CARD = """---
license: other
license_name: n-atlas-terms-of-use
base_model: NCAIR1/NigerianAccentedEnglish
language: [en, pcm]
tags: [ctranslate2, int8, whisper, n-atlas, nigeria, speech-recognition]
---

# N-ATLaS ASR Nigerian-accented English · int8 (CTranslate2) · Powered by Awarri

[NCAIR1/NigerianAccentedEnglish](https://huggingface.co/NCAIR1/NigerianAccentedEnglish), unchanged except for its number format: converted to int8 with CTranslate2 for laptop CPUs, as used by the PHC Scribe clinic hub for English visits (ADR-0032, Tier 2). 242 MB instead of 967 MB.

**Checked before release** against a pre-registered rule (int8 no more than 3 points worse in word error rate, upper bound of the 95% CI), with PHC Scribe's decoding (greedy, English forced, windows of at most 20 s):

| Dev clips | fp32 WER | int8 WER | Difference [95% CI] |
|---|---|---|---|
| AfriSpeech-200 dev, Yoruba/Igbo/Hausa accents, 300 clips (84 speakers) | 16.78% | 16.97% | +0.20 [−0.48, +0.89] |

On the reference clinic laptop (i7-8665U), a 20 s recording takes about 6 s instead of 56 s.

**Use:** `ctranslate2.models.Whisper(path, device="cpu", compute_type="int8")`, with the tokenizer and feature extractor files in this folder; or PHC Scribe with `PHC_ASR=ct2`.

**Licence:** the N-ATLaS Terms of Use apply ("Powered by Awarri"; 1,000 active end-users per rolling 30 days without a commercial licence from Awarri Technologies). N-ATLaS is an initiative of the Federal Ministry of Communications, Innovation and Digital Economy, powered by Awarri Technologies.
"""

# Dev results with the shipped windows (results/asr/int8-dev-recheck.20261011.json).
DEV = {
    "yo": ("FLEURS Yoruba dev, 300 clips", 29.30, 29.33, 0.03, -0.60, 0.67),
    "pcm": ("AfriSpeech-200 dev, Nigerian accents, 300 clips", 30.57, 30.23, -0.35, -1.05, 0.28),
}


def _with_gate(card: str) -> str:
    import yaml

    if card.startswith("---\n"):
        _, head, body = card.split("---\n", 2)
        meta = yaml.safe_load(head) or {}
    else:
        meta, body = {}, card
    meta.update(GATE)
    return (
        "---\n"
        + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=1000)
        + "---\n"
        + body.lstrip("\n")
    )


def _check_files(api, repo: str) -> list[str]:
    files = api.list_repo_files(repo)
    bad = [
        f
        for f in files
        if not (
            f in ALLOWED or f.endswith((".gguf", ".manifest.json")) or f.startswith("ct2-int8/")
        )
    ]
    return bad


@app.function(image=image, secrets=SECRETS, volumes={"/runs": runs}, timeout=3600)
def release(owner: str, gguf_card: str, apply: bool) -> list[str]:
    from huggingface_hub import HfApi, hf_hub_download

    api = HfApi()
    log: list[str] = []
    repos = [f"{owner}/{GGUF}", *(f"{owner}/{r}" for r in ASR.values())]
    en_repo = f"{owner}/{EN_INT8}"

    # 1-2. Cards, access form, int8 builds (repos are still private).
    if apply:
        api.upload_file(
            path_or_fileobj=_with_gate(gguf_card).encode(),
            path_in_repo="README.md",
            repo_id=repos[0],
            commit_message="Model card and access form for release",
        )
        for lang, name in ASR.items():
            repo = f"{owner}/{name}"
            card = Path(hf_hub_download(repo, "README.md")).read_text(encoding="utf-8")
            if "## int8 build for CPUs" not in card:
                dev, fp32, int8, diff, lo, hi = DEV[lang]
                card = (
                    card.rstrip()
                    + "\n"
                    + INT8_SECTION.format(dev=dev, fp32=fp32, int8=int8, diff=diff, lo=lo, hi=hi)
                )
            api.upload_file(
                path_or_fileobj=_with_gate(card).encode(),
                path_in_repo="README.md",
                repo_id=repo,
                commit_message="Model card and access form for release",
            )
            api.upload_folder(
                folder_path=f"/runs/_asr_int8/{lang}/ct2",
                path_in_repo="ct2-int8",
                repo_id=repo,
                commit_message="int8 CTranslate2 build (ADR-0032)",
            )
        api.create_repo(en_repo, private=True, exist_ok=True)
        api.upload_folder(
            folder_path="/runs/_asr_int8/en/ct2",
            repo_id=en_repo,
            commit_message="int8 CTranslate2 build of NCAIR1/NigerianAccentedEnglish (ADR-0032)",
        )
        api.upload_file(
            path_or_fileobj=_with_gate(EN_CARD).encode(),
            path_in_repo="README.md",
            repo_id=en_repo,
            commit_message="Model card and access form",
        )
    all_repos = repos + ([en_repo] if apply or api.repo_exists(en_repo) else [])

    # 3. Model files only.
    for repo in all_repos:
        bad = _check_files(api, repo)
        if bad:
            raise SystemExit(
                f"{repo} holds files that are not model files: {bad}; nothing was gated"
            )
        log.append(f"{repo}: {len(api.list_repo_files(repo))} files, all model files")

    # 4. Gate with automatic approval (private -> public behind the access form).
    for repo in all_repos:
        if apply:
            api.update_repo_settings(repo, private=False, gated="auto")
        info = api.model_info(repo)
        log.append(f"{repo}: private={info.private}, gated={info.gated}")
    return log


@app.local_entrypoint()
def main(owner: str = "malikbello", apply: bool = False) -> None:
    card = Path("docs/cards/model-card.md").read_text(encoding="utf-8")
    for line in release.remote(owner, card, apply):
        print(line)
    if not apply:
        print("check only: run again with --apply to release")


@app.function(image=image, secrets=SECRETS, timeout=1800)
def complete_int8(owner: str) -> list[str]:
    """Put the feature-extractor config beside each `ct2-int8/` build. The fine-tunes keep it
    as `processor_config.json` at the repo root, which the first conversion did not copy
    (found 11 Oct, before any download), and WhisperProcessor needs it to load the folder."""
    from huggingface_hub import HfApi, hf_hub_download

    api = HfApi()
    log = []
    for name in ASR.values():
        repo = f"{owner}/{name}"
        files = set(api.list_repo_files(repo))
        for f in ("processor_config.json", "preprocessor_config.json"):
            if f in files and f"ct2-int8/{f}" not in files:
                api.upload_file(
                    path_or_fileobj=hf_hub_download(repo, f),
                    path_in_repo=f"ct2-int8/{f}",
                    repo_id=repo,
                    commit_message=f"ct2-int8: add {f} (the feature-extractor config)",
                )
                log.append(f"{repo}: added ct2-int8/{f}")
        if not any(
            f"ct2-int8/{f}" in set(api.list_repo_files(repo))
            for f in ("processor_config.json", "preprocessor_config.json")
        ):
            raise SystemExit(f"{repo}: ct2-int8 still has no feature-extractor config")
        log.append(f"{repo}: ct2-int8 complete")
    return log


@app.local_entrypoint()
def complete(owner: str = "malikbello") -> None:
    for line in complete_int8.remote(owner):
        print(line)


# Confirming check on the ADR-0026 test pool (results/asr/int8-test.20261012.json).
TEST = {
    "yo": ("300 held-out test clips, 16 speakers", 28.90, 29.26, 0.36, -0.09, 0.99),
    "pcm": ("300 held-out test clips, 19 speakers", 18.30, 18.16, -0.14, -0.67, 0.30),
}


@app.function(image=image, secrets=SECRETS, timeout=1800)
def add_test_results(owner: str) -> list[str]:
    """Add the test-pool confirmation (run once, 12 Oct) to each int8 section of the cards."""
    from huggingface_hub import HfApi, hf_hub_download

    api = HfApi()
    log = []
    for lang, name in ASR.items():
        repo = f"{owner}/{name}"
        card = Path(hf_hub_download(repo, "README.md")).read_text(encoding="utf-8")
        if "Confirmed on the held-out test pool" in card:
            log.append(f"{repo}: already has the test-pool result")
            continue
        clips, fp32, int8, diff, lo, hi = TEST[lang]
        line = (
            f"\n**Confirmed on the held-out test pool** (run once, same rule and decoding): {clips}, "
            f"fp32 {fp32:.2f}% → int8 {int8:.2f}%, {diff:+.2f} points [{lo:+.2f}, {hi:+.2f}]: **pass**. "
            "PHC Scribe's clinic hub serves this int8 build.\n"
        )
        anchor = "Serve it with PHC Scribe"
        card = (
            card.replace(anchor, line.lstrip("\n") + "\n" + anchor, 1)
            if anchor in card
            else card.rstrip() + "\n" + line
        )
        api.upload_file(
            path_or_fileobj=card.encode(),
            path_in_repo="README.md",
            repo_id=repo,
            commit_message="int8: test-pool confirmation (ADR-0032)",
        )
        log.append(f"{repo}: test-pool result added")
    return log


@app.local_entrypoint()
def test_results(owner: str = "malikbello") -> None:
    for line in add_test_results.remote(owner):
        print(line)
