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
