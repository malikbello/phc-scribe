"""Speech-to-text adapters for /v1/transcribe: the official N-ATLaS ASR models.

Whisper-Small fine-tunes by NCAIR1, one per language; Nigerian Pidgin has no model of its
own, so it goes through the Nigerian-accented English model. The models take 30-second
windows, so longer audio is chunked by the pipeline. Heavy imports stay inside the class
so the API (and CI) never need them unless ASR is switched on.
"""

from __future__ import annotations

import io
import wave
from typing import Protocol

from phc_scribe.asr_guard import guard

ASR_MODELS = {
    "yo": "NCAIR1/Yoruba-ASR",
    "ha": "NCAIR1/Hausa-ASR",
    "ig": "NCAIR1/Igbo-ASR",
    "en": "NCAIR1/NigerianAccentedEnglish",
    "pcm": "NCAIR1/NigerianAccentedEnglish",
}
# Whisper language token for each model. The NCAIR1 generation configs leave the language
# unset, so Whisper detects it per 30-second window; forcing the model's own language stops
# a window being decoded as another language (Pidgin has no Whisper language: English).
WHISPER_LANGUAGE = {"yo": "yoruba", "ha": "hausa", "ig": "igbo", "en": "english", "pcm": "english"}
SAMPLE_RATE = 16_000


# Less speech than this (seconds) and the clip is treated as having none (ADR-0031). A
# one-word answer ("yes", "bẹ́ẹ̀ni") is about 0.3-0.5 s; the gate is for silence and noise.
MIN_SPEECH_S = 0.25
# Clips shorter than this are always transcribed: a lone word is too short for the VAD to be
# sure of (FLEURS dev check: 48/60 one-word clips passed), and a visit recording is minutes
# long, so the gate's job is the long silent or noisy recording (results/asr/vad-gate.*.json).
GATE_MIN_CLIP_S = 2.0


class SpeechGate(Protocol):
    def speech_seconds(self, samples: list[float]) -> float: ...


class SileroGate:
    """Silero VAD (MIT; the model ships inside the `silero-vad` wheel, so it works offline).

    Whisper-family models write fluent text for silence and noise ("hallucination"); a VAD in
    front of them is the standard remedy (faster-whisper's vad_filter, WhisperX). Here it only
    decides whether a clip has speech at all: clips with speech go to Whisper unchanged.
    """

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
        self._model = None

    def speech_spans(self, samples: list[float]) -> list[tuple[int, int]]:
        """(start, end) sample offsets of the speech in a clip."""
        import torch  # pyright: ignore[reportMissingImports]
        from silero_vad import (  # pyright: ignore[reportMissingImports]
            get_speech_timestamps,
            load_silero_vad,
        )

        if self._model is None:
            self._model = load_silero_vad()
        spans = get_speech_timestamps(
            torch.tensor(samples, dtype=torch.float32),
            self._model,
            threshold=self.threshold,
            sampling_rate=SAMPLE_RATE,
        )
        return [(int(s["start"]), int(s["end"])) for s in spans]

    def speech_seconds(self, samples: list[float]) -> float:
        return sum(b - a for a, b in self.speech_spans(samples)) / SAMPLE_RATE


class AudioError(ValueError):
    """The upload is not audio we can read."""


class Transcriber(Protocol):
    def model_for(self, language: str) -> str: ...

    def transcribe(self, samples: list[float], language: str) -> str: ...


def read_wav(data: bytes) -> tuple[list[float], float]:
    """Mono float samples at 16 kHz and the duration in seconds, from a PCM WAV file."""
    try:
        with wave.open(io.BytesIO(data)) as w:
            rate, width, channels = w.getframerate(), w.getsampwidth(), w.getnchannels()
            frames = w.readframes(w.getnframes())
    except (wave.Error, EOFError) as e:
        raise AudioError("send PCM WAV audio (16- or 32-bit)") from e
    if width not in (2, 4):
        raise AudioError("send PCM WAV audio (16- or 32-bit)")
    import numpy as np

    pcm = np.frombuffer(frames, dtype="<i2" if width == 2 else "<i4").astype(np.float64)
    pcm /= 32768.0 if width == 2 else 2147483648.0
    if channels > 1:  # average the channels
        pcm = pcm[: len(pcm) - len(pcm) % channels].reshape(-1, channels).mean(axis=1)
    if rate != SAMPLE_RATE:  # linear interpolation is enough for speech recognition
        n = int(len(pcm) * SAMPLE_RATE / rate)
        pcm = np.interp(np.arange(n) * (rate / SAMPLE_RATE), np.arange(len(pcm)), pcm)
    samples = pcm.tolist()
    if not samples:
        raise AudioError("the audio is empty")
    return samples, len(samples) / SAMPLE_RATE


class HfWhisperTranscriber:
    """The NCAIR1 models through the transformers speech-recognition pipeline (CPU or GPU)."""

    def __init__(self, models: dict[str, str] | None = None, force_language: bool = False):
        self.models = models or ASR_MODELS
        self.force_language = force_language
        self._pipes: dict[str, object] = {}

    def model_for(self, language: str) -> str:
        return self.models[language]

    def _pipe(self, model_id: str):
        if model_id not in self._pipes:
            import torch  # pyright: ignore[reportMissingImports]
            from transformers import pipeline  # pyright: ignore[reportMissingImports]

            self._pipes[model_id] = pipeline(
                "automatic-speech-recognition",
                model=model_id,
                chunk_length_s=30,
                device=0 if torch.cuda.is_available() else -1,
            )
        return self._pipes[model_id]

    def transcribe(self, samples: list[float], language: str, force: bool | None = None) -> str:
        """`force` overrides the instance setting for one call (used to compare the two)."""
        import numpy as np

        pipe = self._pipe(self.model_for(language))
        audio = {"raw": np.asarray(samples, dtype=np.float32), "sampling_rate": SAMPLE_RATE}
        forced = self.force_language if force is None else force
        kwargs = (
            {"generate_kwargs": {"language": WHISPER_LANGUAGE[language], "task": "transcribe"}}
            if forced
            else {}
        )
        out = pipe(audio, **kwargs)  # pyright: ignore[reportCallIssue]
        text = str(out["text"]).strip()  # pyright: ignore[reportIndexIssue, reportArgumentType]
        return guard(text)[0]  # audit H4: cut a decoding loop before it reaches the record


# Whisper reads 30 seconds at a time.
WINDOW_S = 30.0
# Whisper's own language codes for the language tokens.
WHISPER_CODE = {"yoruba": "yo", "hausa": "ha", "igbo": "ig", "english": "en"}


def speech_windows(
    spans: list[tuple[int, int]],
    total: int,
    max_s: float = WINDOW_S,
    pad_s: float = 0.2,
    rate: int = SAMPLE_RATE,
) -> list[tuple[int, int]]:
    """Cut a recording into windows of at most `max_s` seconds at pauses.

    Speech spans (from the VAD) are padded a little and grouped while they fit in one window,
    so a window ends in a pause and no word is cut in two (the approach of WhisperX). A span
    longer than a window is split evenly. With no spans, fixed windows cover the whole clip.
    """
    limit, pad = int(max_s * rate), int(pad_s * rate)
    if not spans:
        return [(s, min(s + limit, total)) for s in range(0, total, limit)]
    pieces: list[tuple[int, int]] = []
    for a, b in sorted(spans):
        a, b = max(0, a - pad), min(total, b + pad)
        while b - a > limit:
            pieces.append((a, a + limit))
            a += limit
        pieces.append((a, b))
    out: list[tuple[int, int]] = []
    for a, b in pieces:
        if out and max(out[-1][1], b) - out[-1][0] <= limit:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


class Ct2WhisperTranscriber:
    """The same models converted to int8 for CTranslate2 (ADR-0032, Tier 2).

    About a quarter of the memory of fp32 and faster on a laptop CPU. Decoding is the
    evaluated one (ADR-0032): greedy, the language forced, no timestamps, each window on its
    own, then the H4 loop guard. A recording longer than one window is cut at pauses
    (`speech_windows`). Languages without an int8 build use `fallback` (the fp32 models).
    """

    def __init__(
        self,
        models: dict[str, str],
        gate: SileroGate | None = None,
        fallback: Transcriber | None = None,
        threads: int = 0,
    ):
        self.models = models
        self.gate = gate
        self.fallback = fallback
        self.threads = threads
        self._loaded: dict[str, tuple[object, object]] = {}

    def model_for(self, language: str) -> str:
        if language in self.models:
            return self.models[language]
        if self.fallback is None:
            raise KeyError(f"no int8 speech model for {language!r}")
        return self.fallback.model_for(language)

    def _load(self, path: str):
        if path not in self._loaded:
            import ctranslate2  # pyright: ignore[reportMissingImports]
            from transformers import WhisperProcessor  # pyright: ignore[reportMissingImports]

            model = ctranslate2.models.Whisper(
                path, device="cpu", compute_type="int8", intra_threads=self.threads
            )
            self._loaded[path] = (model, WhisperProcessor.from_pretrained(path))
        return self._loaded[path]

    def transcribe(self, samples: list[float], language: str) -> str:
        if language not in self.models:
            if self.fallback is None:
                raise KeyError(f"no int8 speech model for {language!r}")
            return self.fallback.transcribe(samples, language)
        import ctranslate2  # pyright: ignore[reportMissingImports]
        import numpy as np

        model, proc = self._load(self.models[language])
        x = np.asarray(samples, dtype=np.float32)
        long = len(x) > WINDOW_S * SAMPLE_RATE
        spans = self.gate.speech_spans(samples) if long and self.gate is not None else []
        windows = speech_windows(spans, len(x)) if long else [(0, len(x))]
        code = WHISPER_CODE[WHISPER_LANGUAGE[language]]
        tok = proc.tokenizer  # pyright: ignore[reportAttributeAccessIssue]
        prompt = tok.convert_tokens_to_ids(
            ["<|startoftranscript|>", f"<|{code}|>", "<|transcribe|>", "<|notimestamps|>"]
        )
        feats = proc.feature_extractor(  # pyright: ignore[reportAttributeAccessIssue]
            [x[a:b] for a, b in windows], sampling_rate=SAMPLE_RATE, return_tensors="np"
        ).input_features
        results = model.generate(  # pyright: ignore[reportAttributeAccessIssue]
            ctranslate2.StorageView.from_array(np.ascontiguousarray(feats, dtype=np.float32)),
            [prompt] * len(windows),
            beam_size=1,
            max_length=448,
        )
        parts = [tok.decode(r.sequences_ids[0], skip_special_tokens=True).strip() for r in results]
        return guard(" ".join(" ".join(parts).split()))[0]
