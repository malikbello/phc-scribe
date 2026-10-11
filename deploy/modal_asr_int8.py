"""Tier 2 speech (ADR-0032): int8 CTranslate2 against fp32 transformers, same decoding.

    modal run --detach deploy/modal_asr_int8.py::dev_spawn --model yo    # then pcm, en
    modal run --detach deploy/modal_asr_int8.py::test_spawn --model yo   # once, after dev

Each model is converted once (int8, CTranslate2) into /runs/_asr_int8/<model>/ct2, then both
versions transcribe the same clips one at a time on the same CPU, as the hub does: greedy,
language forced, no timestamps, the H4 loop guard on both.

- **Dev check (chooses):** public Nigerian speech that no model here was fine-tuned on and that
  is not the test pool: FLEURS Yoruba dev for the Yoruba model, AfriSpeech-200 dev (Yoruba,
  Igbo and Hausa accents) for the English and Pidgin models.
- **Test check (confirms, run once):** the ADR-0026 test pool (gated WazobiaSpeech).

The rule (ADR-0032, 11 Oct): the upper bound of the clustered bootstrap interval of int8 minus
fp32 WER is at most +3 points. Writes /runs/_asr_int8/<model>/<stage>.json (numbers only);
transcripts stay on the volume (<stage>.preds.jsonl).
"""

from __future__ import annotations

import modal

APP_DIR = "/app"

# Converting needs transformers 4.x (CTranslate2's converter); evaluating uses the hub's
# versions, so fp32 here decodes as the hub does.
convert_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch==2.8.0", index_url="https://download.pytorch.org/whl/cpu")
    .pip_install("transformers==4.57.1", "ctranslate2>=4.5,<5", "huggingface_hub>=0.34")
)
eval_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("libsndfile1")
    .pip_install("torch==2.14.1", index_url="https://download.pytorch.org/whl/cpu")
    .pip_install(
        "transformers==5.19.0",
        "ctranslate2>=4.5,<5",
        "huggingface_hub>=0.34",
        "pyarrow>=17",
        "soundfile>=0.12",
        "scipy>=1.11",  # bench.asr_run.resample
        "numpy>=1.26",
        "pydantic>=2.8,<3",
        "pyyaml>=6.0",
    )
    .env({"PYTHONPATH": f"{APP_DIR}/serve:{APP_DIR}", "HF_HOME": "/cache/hf"})
    .add_local_dir("serve", f"{APP_DIR}/serve", ignore=["**/__pycache__"])
    .add_local_dir("bench", f"{APP_DIR}/bench", ignore=["**/__pycache__"])
    .add_local_dir("schema", f"{APP_DIR}/schema")  # the vocabulary (imported by bench.wer)
    .add_local_dir("rules", f"{APP_DIR}/rules")
    .add_local_file(
        "data/asr/targets.v1.jsonl", f"{APP_DIR}/data/asr/targets.v1.jsonl"
    )  # test-pool ids
)

app = modal.App("phc-scribe-asr-int8")
runs = modal.Volume.from_name("phc-scribe-runs", create_if_missing=True)
hf_cache = modal.Volume.from_name("phc-scribe-hf-cache", create_if_missing=True)
SECRETS = [modal.Secret.from_name("phc-scribe-api")]  # HF_TOKEN (private fine-tunes, gated NCAIR1)
VOLUMES = {"/runs": runs, "/cache": hf_cache}

OWNER = "malikbello"
# The models the hub serves (serve/phc_scribe/fetch_models.py): repo, dev clips, language token.
MODELS = {
    "yo": (f"{OWNER}/N-ATLaS-ASR-Health-Yoruba-Powered-by-Awarri", "fleurs-yo", "yo"),
    "pcm": (f"{OWNER}/N-ATLaS-ASR-Health-Pidgin-Powered-by-Awarri", "afrispeech-ng", "en"),
    "en": ("NCAIR1/NigerianAccentedEnglish", "afrispeech-ng", "en"),
}
AFRISPEECH = "intronhealth/afrispeech-200"  # CC BY-NC-SA 4.0: evaluation only
NIGERIAN_ACCENTS = ("yoruba", "igbo", "hausa")
# Same vocabulary as each model; used only to convert (see convert()).
BASE_TOKENIZER = {
    "yo": "NCAIR1/Yoruba-ASR",
    "pcm": "NCAIR1/NigerianAccentedEnglish",
    "en": "NCAIR1/NigerianAccentedEnglish",
}
OUT = "/runs/_asr_int8"
CPU = 8.0


@app.function(
    image=convert_image, secrets=SECRETS, volumes=VOLUMES, cpu=4.0, memory=8192, timeout=3600
)
def convert(model: str) -> str:
    import os
    import shutil
    import tempfile

    import ctranslate2
    from huggingface_hub import snapshot_download

    repo = MODELS[model][0]
    src = snapshot_download(repo, cache_dir="/cache/hf/hub", token=os.environ.get("HF_TOKEN"))
    # Everything WhisperProcessor needs, so the int8 folder loads on its own at the hub.
    wanted = (
        "tokenizer.json",
        "tokenizer_config.json",
        "preprocessor_config.json",
        "special_tokens_map.json",
        "added_tokens.json",
        "vocab.json",
        "merges.txt",
        "normalizer.json",
        "generation_config.json",
    )
    out = f"{OUT}/{model}/ct2"
    # A fine-tune saved by transformers 5 has a tokenizer config the 4.x converter cannot read.
    # The vocabulary is the base model's (fine-tuning adds no tokens), so the converter reads
    # the base model's tokenizer files beside the fine-tune's weights.
    work = tempfile.mkdtemp()
    for f in os.listdir(src):
        if f not in wanted:
            os.symlink(os.path.realpath(f"{src}/{f}"), f"{work}/{f}")
    base = snapshot_download(
        BASE_TOKENIZER[model],
        cache_dir="/cache/hf/hub",
        token=os.environ.get("HF_TOKEN"),
        allow_patterns=list(wanted),
    )
    for f in wanted:
        if os.path.exists(f"{base}/{f}"):
            shutil.copy(f"{base}/{f}", f"{work}/{f}")
    ctranslate2.converters.TransformersConverter(work).convert(out, quantization="int8", force=True)
    # The hub reads the tokenizer with its own transformers: ship the fine-tune's own files.
    for f in wanted:
        if os.path.exists(f"{src}/{f}"):
            shutil.copy(f"{src}/{f}", f"{out}/{f}")
    runs.commit()
    size = sum(os.path.getsize(f"{out}/{f}") for f in os.listdir(out))
    print(f"=== INT8 {model}: converted {repo} -> {out} ({size / 1e6:.0f} MB)", flush=True)
    return out


def _audio(raw: bytes):
    import io

    import numpy as np
    import soundfile as sf

    from bench.asr_run import resample

    x, rate = sf.read(io.BytesIO(raw))
    if x.ndim > 1:
        x = x.mean(axis=1)
    return np.clip(resample(x, rate), -1, 1).astype(np.float32)


def _dev_clips(source: str, want: int) -> list[dict]:
    """Up to `want` public dev clips of 0.5-30 s. `speaker` is the bootstrap cluster: the
    speaker for AfriSpeech, the sentence for FLEURS (it has no speaker ids; each sentence is
    read by a few people)."""
    import csv
    import random
    import tarfile
    from pathlib import PurePosixPath

    from huggingface_hub import HfApi, hf_hub_download

    from bench.asr_finetune import MAX_SECONDS, MIN_SECONDS, SEED

    get = lambda repo, f: hf_hub_download(repo, f, repo_type="dataset", cache_dir="/cache/hf/hub")  # noqa: E731
    clips: list[dict] = []

    def keep(audio_id, cluster, health, raw, text):
        x = _audio(raw)
        if text.strip() and MIN_SECONDS <= len(x) / 16_000 <= MAX_SECONDS:
            clips.append(
                {
                    "audio_id": audio_id,
                    "speaker": cluster,
                    "health": health,
                    "audio": x,
                    "text": text.strip(),
                }
            )

    if source == "fleurs-yo":
        rows = {}
        with open(get("google/fleurs", "data/yo_ng/dev.tsv"), encoding="utf-8") as fh:
            for line in fh:
                p = line.rstrip("\n").split("\t")
                rows[p[1]] = (p[0], p[2])  # file -> (sentence id, raw transcription)
        with tarfile.open(get("google/fleurs", "data/yo_ng/audio/dev.tar.gz")) as tar:
            for m in tar:
                name = PurePosixPath(m.name).name
                if m.isfile() and name in rows:
                    keep(name, rows[name][0], False, tar.extractfile(m).read(), rows[name][1])  # pyright: ignore[reportOptionalMemberAccess]
    elif source == "afrispeech-ng":
        files = HfApi().list_repo_files(AFRISPEECH, repo_type="dataset")
        for accent in NIGERIAN_ACCENTS:
            with open(get(AFRISPEECH, f"transcripts/{accent}/dev.csv"), encoding="utf-8") as fh:
                meta = {PurePosixPath(r["audio_paths"]).name: r for r in csv.DictReader(fh)}
            for part in sorted(f for f in files if f.startswith(f"audio/{accent}/dev/")):
                with tarfile.open(get(AFRISPEECH, part)) as tar:
                    for m in tar:
                        r = meta.get(PurePosixPath(m.name).name)
                        if m.isfile() and r:
                            keep(
                                r["audio_ids"],
                                r["user_ids"],
                                r.get("domain") == "clinical",
                                tar.extractfile(m).read(),
                                r["transcript"],
                            )  # pyright: ignore[reportOptionalMemberAccess]
    else:
        raise ValueError(f"unknown dev source {source!r}")
    random.Random(SEED).shuffle(clips)  # noqa: S311
    return clips[:want]


def _bootstrap(
    per_speaker: dict[str, list[int]], n: int = 2000, seed: int = 0
) -> tuple[float, float]:
    """95% interval of (int8 - fp32) WER in points, resampling speakers."""
    import random

    rng = random.Random(seed)  # noqa: S311
    speakers = list(per_speaker)
    diffs = []
    for _ in range(n):
        e32 = e8 = w = 0
        for s in (rng.choice(speakers) for _ in speakers):
            a, b, c = per_speaker[s]
            e32, e8, w = e32 + a, e8 + b, w + c
        diffs.append(100 * (e8 - e32) / w)
    diffs.sort()
    return diffs[int(0.025 * n)], diffs[int(0.975 * n) - 1]


def _compare(model: str, clips: list[dict], stage: str, source: str) -> dict:
    """fp32 and int8 on the same clips, one at a time; writes <stage>.json and its preds."""
    import json
    import os
    import time

    import ctranslate2
    import numpy as np
    import torch
    from huggingface_hub import snapshot_download
    from transformers import WhisperForConditionalGeneration, WhisperProcessor

    from bench.wer import edit_errors
    from phc_scribe.api.asr import WHISPER_LANGUAGE
    from phc_scribe.asr_guard import guard

    repo, _, lang = MODELS[model]
    torch.set_num_threads(int(CPU))
    src = snapshot_download(repo, cache_dir="/cache/hf/hub", token=os.environ.get("HF_TOKEN"))
    proc = WhisperProcessor.from_pretrained(src)
    fp32 = WhisperForConditionalGeneration.from_pretrained(src, torch_dtype=torch.float32).eval()
    int8 = ctranslate2.models.Whisper(
        f"{OUT}/{model}/ct2", device="cpu", compute_type="int8", intra_threads=int(CPU)
    )
    code = "yo" if WHISPER_LANGUAGE[lang] == "yoruba" else "en"
    prompt = proc.tokenizer.convert_tokens_to_ids(
        ["<|startoftranscript|>", f"<|{code}|>", "<|transcribe|>", "<|notimestamps|>"]
    )
    window = 30 * 16_000  # a clip longer than one window is cut the same way for both

    rows, secs = [], {"fp32": 0.0, "int8": 0.0}
    for c in clips:
        parts32, parts8 = [], []
        for i in range(0, len(c["audio"]), window):
            f = proc.feature_extractor(
                c["audio"][i : i + window], sampling_rate=16_000, return_tensors="np"
            ).input_features
            t = time.time()
            with torch.no_grad():
                ids = fp32.generate(
                    torch.from_numpy(f),
                    language=WHISPER_LANGUAGE[lang],
                    task="transcribe",
                    max_new_tokens=440,
                )
            parts32.append(proc.batch_decode(ids, skip_special_tokens=True)[0].strip())
            secs["fp32"] += time.time() - t
            t = time.time()
            res = int8.generate(
                ctranslate2.StorageView.from_array(f.astype(np.float32)),
                [prompt],
                beam_size=1,
                max_length=448,
            )
            parts8.append(
                proc.tokenizer.decode(res[0].sequences_ids[0], skip_special_tokens=True).strip()
            )
            secs["int8"] += time.time() - t
        h32, h8 = guard(" ".join(parts32))[0], guard(" ".join(parts8))[0]
        rows.append(
            {
                "audio_id": c["audio_id"],
                "speaker": c["speaker"],
                "health": c["health"],
                "ref": c["text"],
                "fp32": h32,
                "int8": h8,
            }
        )

    per_speaker: dict[str, list[int]] = {}
    for r in rows:
        e32, n = edit_errors(r["ref"], r["fp32"])
        e8, _ = edit_errors(r["ref"], r["int8"])
        a = per_speaker.setdefault(r["speaker"], [0, 0, 0])
        a[0], a[1], a[2] = a[0] + e32, a[1] + e8, a[2] + n
    tot = [sum(v[i] for v in per_speaker.values()) for i in range(3)]
    low, high = _bootstrap(per_speaker)
    out = {
        "model": model,
        "repo": repo,
        "stage": stage,
        "source": source,
        "clips": len(rows),
        "speakers": len(per_speaker),
        "health_clips": sum(r["health"] for r in rows),
        "wer_fp32": round(100 * tot[0] / tot[2], 2),
        "wer_int8": round(100 * tot[1] / tot[2], 2),
        "diff_points": round(100 * (tot[1] - tot[0]) / tot[2], 2),
        "diff_ci95": [round(low, 2), round(high, 2)],
        "rule": "upper bound <= +3.0 points, clustered bootstrap (ADR-0032, 11 Oct)",
        "passes": high <= 3.0,
        "identical_outputs": sum(r["fp32"] == r["int8"] for r in rows),
        "seconds_per_clip": {k: round(v / max(1, len(rows)), 3) for k, v in secs.items()},
        "audio_seconds": round(sum(len(c["audio"]) for c in clips) / 16_000, 1),
        "cpu": CPU,
    }
    os.makedirs(f"{OUT}/{model}", exist_ok=True)
    with open(f"{OUT}/{model}/{stage}.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    with open(f"{OUT}/{model}/{stage}.preds.jsonl", "w", encoding="utf-8") as fh:
        fh.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    runs.commit()
    print("=== INT8 RESULT " + json.dumps(out), flush=True)
    return out


@app.function(
    image=eval_image, secrets=SECRETS, volumes=VOLUMES, cpu=CPU, memory=16384, timeout=4 * 3600
)
def dev_check(model: str, want: int = 300) -> dict:
    import time

    source = MODELS[model][1]
    t0 = time.time()
    clips = _dev_clips(source, want)
    clusters = len({c["speaker"] for c in clips})
    print(
        f"=== INT8 {model}: {len(clips)} dev clips, {clusters} clusters, {time.time() - t0:.0f}s",
        flush=True,
    )
    return _compare(model, clips, "dev", source)


@app.function(
    image=eval_image, secrets=SECRETS, volumes=VOLUMES, cpu=CPU, memory=16384, timeout=4 * 3600
)
def test_check(model: str, speakers: dict[str, str]) -> dict:
    """The confirming check, run once: the ADR-0026 test pool (WazobiaSpeech dev + dev_test,
    300 clips per language; gated). `speakers` maps clip id to speaker (the label queue)."""
    import json

    from huggingface_hub import HfFileSystem

    from bench.asr_run import SPLITS, shard_hits_retrying
    from bench.wazobia import DATASETS, _shards

    with open(f"{APP_DIR}/data/asr/targets.v1.jsonl", encoding="utf-8") as fh:
        targets = [json.loads(x) for x in fh if x.strip()]
    wanted = {t["audio_id"] for t in targets if t["language"] == model and t["split"] == "dev_pool"}
    repo, revision = DATASETS[model]  # pyright: ignore[reportArgumentType]
    fs = HfFileSystem()
    clips: list[dict] = []
    for split in SPLITS["dev_pool"]:
        for path in _shards(fs, repo, revision, split):
            left = wanted - {c["audio_id"] for c in clips}
            if not left:
                break
            for aid, raw, text in shard_hits_retrying(fs, path, left):
                clips.append(
                    {
                        "audio_id": aid,
                        "speaker": speakers.get(aid, aid),
                        "health": True,
                        "audio": _audio(raw),
                        "text": text,
                    }
                )
    print(f"=== INT8 {model}: {len(clips)} of {len(wanted)} test-pool clips", flush=True)
    return _compare(model, clips, "test", "wazobiaspeech-test-pool")


@app.function(image=eval_image, volumes=VOLUMES, timeout=6 * 3600)
def pipeline(model: str) -> dict:
    convert.remote(model)
    return dev_check.remote(model)


@app.local_entrypoint()
def dev_spawn(model: str):
    call = pipeline.spawn(model)
    print(f"{model}: started ({call.object_id}); results in {OUT}/{model}/dev.json")


@app.local_entrypoint()
def test_spawn(model: str, queue: str = "data/private/label_queue.s4w.jsonl"):
    """Run once per model, after its dev check passed. Speaker ids come from the label queue
    (clip id -> group id, as scripts/asr_compare.py groups them); no text leaves the laptop."""
    import json
    from pathlib import Path

    rows = [
        json.loads(x) for x in Path(queue).read_text(encoding="utf-8").splitlines() if x.strip()
    ]
    speakers = {r["source_id"]: r["group_id"] for r in rows if r.get("language") == model}
    call = test_check.spawn(model, speakers)
    print(f"{model}: test check started ({call.object_id}); results in {OUT}/{model}/test.json")
