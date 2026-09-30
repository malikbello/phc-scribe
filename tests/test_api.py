import hashlib
import secrets

import pytest
from fastapi.testclient import TestClient

from phc_scribe.api.app import create_app
from phc_scribe.api.extractors import ExtractorError
from phc_scribe.api.settings import Settings
from phc_scribe.encounter import Encounter

KEY = secrets.token_urlsafe(16)  # generated per run: no key-like literal in the repo
AUTH = {"Authorization": f"Bearer {KEY}"}
NOTE = "G2P1 at 32 weeks. Complains of severe headache and blurred vision. BP 160/110. No bleeding."


def make(tmp_path, **kw) -> TestClient:
    s = Settings(
        api_key_hashes=frozenset({hashlib.sha256(KEY.encode()).hexdigest()}),
        db_path=str(tmp_path / "db.sqlite3"),
        **kw,
    )
    return TestClient(create_app(s))


def test_production_refuses_to_start_without_keys(tmp_path):
    with pytest.raises(RuntimeError, match="PHC_API_KEY_HASHES"):
        create_app(Settings(db_path=str(tmp_path / "db")))


def test_health_is_open_and_everything_else_needs_a_key(tmp_path):
    c = make(tmp_path)
    assert c.get("/v1/health").json() == {"status": "ok"}
    r = c.post("/v1/extract", json={"text": NOTE})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    assert r.json()["error"]["request_id"] == r.headers["X-Request-ID"]
    assert c.get("/v1/version", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_extract_grounds_and_flags(tmp_path):
    c = make(tmp_path)
    r = c.post("/v1/extract", json={"text": NOTE, "language": "en"}, headers=AUTH)
    assert r.status_code == 200, r.text
    body = r.json()
    concepts = {f["concept"] for f in body["record"]["findings"]}
    assert "severe_headache" in concepts or "headache" in concepts
    assert body["record"]["vitals"]["blood_pressure"]["systolic"] == 160
    assert any(f["severity"] for f in body["flags"])
    for f in body["record"]["findings"]:
        assert f["evidence"]["text"] in NOTE
    assert body["versions"]["schema_version"] == "0.1.0"


def test_request_id_is_echoed(tmp_path):
    r = make(tmp_path).get("/v1/version", headers={**AUTH, "X-Request-ID": "abc-123"})
    assert r.headers["X-Request-ID"] == "abc-123"


def test_validation_errors_use_the_envelope(tmp_path):
    r = make(tmp_path).post("/v1/extract", json={"text": ""}, headers=AUTH)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_request"


def test_backend_failure_is_a_502(tmp_path):
    class Broken:
        name = "broken"

        def extract(self, text: str) -> Encounter:
            raise ExtractorError("ConnectError")

    s = Settings(env="dev", db_path=str(tmp_path / "db"))
    r = TestClient(create_app(s, extractor=Broken())).post("/v1/extract", json={"text": NOTE})
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "model_unavailable"


def test_records_are_idempotent_and_append_only(tmp_path):
    c = make(tmp_path)
    draft = c.post("/v1/extract", json={"text": NOTE}, headers=AUTH).json()["record"]
    h = {**AUTH, "Idempotency-Key": "visit-0001-abcdef"}
    first = c.post("/v1/records", json={"record": draft, "actor": "hw-17"}, headers=h)
    assert first.status_code == 201
    rid = first.json()["id"]
    replay = c.post("/v1/records", json={"record": draft, "actor": "hw-17"}, headers=h)
    assert replay.status_code == 200
    assert replay.json()["id"] == rid
    clash = c.post("/v1/records", json={"record": draft, "actor": "hw-99"}, headers=h)
    assert clash.status_code == 409

    confirmed = c.post(f"/v1/records/{rid}/confirm", json={"actor": "hw-17"}, headers=AUTH)
    assert confirmed.json()["status"] == "confirmed"
    draft["findings"] = []
    amended = c.post(
        f"/v1/records/{rid}/amend",
        json={"record": draft, "actor": "hw-17", "reason": "headache was mild"},
        headers=AUTH,
    ).json()
    assert amended["status"] == "amended"
    assert [e["type"] for e in amended["events"]] == ["drafted", "confirmed", "amended"]
    assert amended["record"]["findings"] == []


def test_records_are_private_to_each_key(tmp_path):
    other = secrets.token_urlsafe(16)
    s = Settings(
        api_key_hashes=frozenset(hashlib.sha256(k.encode()).hexdigest() for k in (KEY, other)),
        db_path=str(tmp_path / "db"),
    )
    c = TestClient(create_app(s))
    draft = c.post("/v1/extract", json={"text": NOTE}, headers=AUTH).json()["record"]
    rid = c.post(
        "/v1/records", json={"record": draft}, headers={**AUTH, "Idempotency-Key": "k-12345678"}
    ).json()["id"]
    r = c.get(f"/v1/records/{rid}", headers={"Authorization": f"Bearer {other}"})
    assert r.status_code == 404


def test_rate_limit(tmp_path):
    c = make(tmp_path, rate_limit_per_minute=2)
    assert c.get("/v1/version", headers=AUTH).status_code == 200
    assert c.get("/v1/version", headers=AUTH).status_code == 200
    r = c.get("/v1/version", headers=AUTH)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"


def _wav(seconds: float = 1.0, rate: int = 8000, channels: int = 1) -> bytes:
    import io
    import math
    import struct
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        n = int(seconds * rate)
        tone = (int(8000 * math.sin(i / 10)) for i in range(n))
        w.writeframes(b"".join(struct.pack("<" + "h" * channels, *([t] * channels)) for t in tone))
    return buf.getvalue()


class FakeAsr:
    def __init__(self):
        self.calls: list[tuple[int, str]] = []

    def model_for(self, language: str) -> str:
        return {"yo": "NCAIR1/Yoruba-ASR"}.get(language, "NCAIR1/NigerianAccentedEnglish")

    def transcribe(self, samples: list[float], language: str) -> str:
        self.calls.append((len(samples), language))
        return "ori n fo mi gan"


def test_transcribe_is_off_by_default(tmp_path):
    r = make(tmp_path).post(
        "/v1/transcribe?language=yo", content=_wav(), headers={**AUTH, "Content-Type": "audio/wav"}
    )
    assert r.status_code == 501
    assert r.json()["error"]["code"] == "asr_not_enabled"


def test_transcribe_resamples_and_uses_the_language_model(tmp_path):
    asr = FakeAsr()
    s = Settings(env="dev", db_path=str(tmp_path / "db"))
    c = TestClient(create_app(s, transcriber=asr))
    r = c.post("/v1/transcribe?language=yo", content=_wav(2.0, rate=8000, channels=2))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["text"] == "ori n fo mi gan"
    assert body["model"] == "NCAIR1/Yoruba-ASR"
    assert body["duration_s"] == 2.0
    assert asr.calls == [(32000, "yo")]  # 2 s at 16 kHz, stereo averaged to mono


def test_transcribe_rejects_non_wav(tmp_path):
    s = Settings(env="dev", db_path=str(tmp_path / "db"))
    c = TestClient(create_app(s, transcriber=FakeAsr()))
    r = c.post("/v1/transcribe?language=en", content=b"not audio")
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "unsupported_audio"
