"""FastAPI app for /v1 (docs/api.md).

Every response carries X-Request-ID. Errors use one envelope:
{"error": {"code": ..., "message": ..., "request_id": ...}}. Clinical text is never
logged: log lines hold only the request id, route, status, latency and client.
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from collections import defaultdict, deque
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from phc_scribe import __version__
from phc_scribe.api.asr import ASR_MODELS, AudioError, HfWhisperTranscriber, Transcriber, read_wav
from phc_scribe.api.extractors import (
    Extractor,
    ExtractorError,
    KeywordExtractor,
    LlamaCppExtractor,
)
from phc_scribe.api.settings import Settings
from phc_scribe.api.store import IdempotencyConflict, RecordStore
from phc_scribe.encounter import SCHEMA_VERSION, Encounter
from phc_scribe.grounding import ground
from phc_scribe.polarity import check as polarity_check
from phc_scribe.rules import Flag, check, load_rules
from phc_scribe.vocab import load_vocabulary

log = logging.getLogger("phc_scribe.api")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


# ---------- response and request models ----------


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class FlagOut(BaseModel):
    rule_id: str
    name: str
    severity: str
    message_en: str
    source_ref: str
    source_section: str

    @classmethod
    def of(cls, f: Flag) -> FlagOut:
        return cls(**f.__dict__)


class Versions(BaseModel):
    api: str = "v1"
    service: str = __version__
    schema_version: str = SCHEMA_VERSION
    vocabulary: str
    rules: str
    model: str


class DroppedOut(BaseModel):
    path: str
    reason: str = Field(
        description="ungrounded, out_of_range, value_not_in_evidence, inconsistent, or"
        " schema_repair (removed so the model's output fits the schema; ADR-0029)."
    )
    detail: str = ""


class ReviewCheck(BaseModel):
    path: str
    reason: str = Field(
        description="polarity: the finding's own quote seems to say the opposite (ADR-0030)."
    )
    detail: str = ""


class Grounding(BaseModel):
    needs_review: bool = Field(
        description="True if any field was dropped or flagged by a check; a person must check."
    )
    fields_total: int
    dropped: list[DroppedOut]
    checks: list[ReviewCheck] = Field(
        default_factory=list,
        description="Fields kept but flagged for the health worker (nothing is changed).",
    )


class ExtractIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, description="What was said or written at the visit.")
    language: Literal["en", "yo", "pcm", "ha", "ig"] | None = None


class ExtractOut(BaseModel):
    record: Encounter = Field(description="Draft record; every value has verbatim evidence.")
    flags: list[FlagOut]
    grounding: Grounding
    versions: Versions
    latency_ms: float


class TranscribeOut(BaseModel):
    text: str = Field(description="The transcript. Send it to /v1/extract for a record.")
    language: str
    model: str = Field(description="The N-ATLaS ASR model used.")
    duration_s: float
    latency_ms: float


class CheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record: Encounter


class CheckOut(BaseModel):
    flags: list[FlagOut]
    rules_version: str


class RecordIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record: Encounter
    source: Literal["ai_draft", "manual"] = "ai_draft"
    model: str | None = Field(default=None, description="Model that drafted it, if any.")
    actor: str | None = Field(default=None, max_length=80, description="Worker id (not a name).")


class ConfirmIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str = Field(min_length=1, max_length=80)


class AmendIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record: Encounter
    actor: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=400)


class EventOut(BaseModel):
    seq: int
    type: Literal["drafted", "confirmed", "amended"]
    at: str
    actor: str | None
    reason: str | None


class RecordOut(BaseModel):
    id: str
    created_at: str
    status: Literal["draft", "confirmed", "amended"]
    record: Encounter
    flags: list[FlagOut]
    events: list[EventOut]


ERRORS: dict[int | str, dict[str, Any]] = {
    s: {"model": ErrorEnvelope} for s in (400, 401, 404, 409, 413, 415, 422, 429, 501, 502)
}


def client(request: Request, authorization: Annotated[str | None, Header()] = None) -> str:
    """The caller's id: the first 12 hex chars of their key's hash (never the key)."""
    settings: Settings = request.app.state.settings
    if not settings.api_key_hashes:  # dev only; Settings.validate() refuses this in production
        return "dev"
    key = (authorization or "").removeprefix("Bearer ").strip()
    digest = hashlib.sha256(key.encode()).hexdigest()
    if not key or digest not in settings.api_key_hashes:
        raise ApiError(401, "unauthorized", "Send a valid API key: Authorization: Bearer <key>")
    cid = digest[:12]
    now = time.monotonic()
    q = request.app.state.hits[cid]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= settings.rate_limit_per_minute:
        raise ApiError(429, "rate_limited", "Too many requests; try again in a minute")
    q.append(now)
    return cid


Client = Annotated[str, Depends(client)]


# ---------- app ----------


def create_app(
    settings: Settings | None = None,
    extractor: Extractor | None = None,
    transcriber: Transcriber | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.validate()
    if extractor is None:
        extractor = (
            LlamaCppExtractor(
                settings.llamacpp_url,
                settings.llamacpp_model,
                timeout=settings.llamacpp_timeout,
                mode=settings.prompt_mode,
            )
            if settings.extractor == "llamacpp"
            else KeywordExtractor()
        )
    if transcriber is None and settings.asr == "hf":
        transcriber = HfWhisperTranscriber({**ASR_MODELS, **settings.asr_model_overrides()})
    store = RecordStore(settings.db_path)

    app = FastAPI(
        title="PHC Scribe API",
        version="1.0.0",
        description=(
            "Structured antenatal-visit documentation for Nigerian primary health care, built"
            " on a fine-tuned N-ATLaS. A documentation aid: it drafts, a health worker"
            " confirms. It never gives advice or a diagnosis."
        ),
        responses=ERRORS,
    )
    app.state.settings = settings
    app.state.hits = defaultdict(deque)

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = rid[:64]
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        log.info(
            "request",
            extra={
                "request_id": request.state.request_id,
                "route": request.url.path,
                "status": response.status_code,
                "ms": round((time.perf_counter() - t0) * 1000, 1),
            },
        )
        return response

    def envelope(request: Request, status: int, code: str, message: str) -> JSONResponse:
        rid = getattr(request.state, "request_id", "")
        body = {"error": {"code": code, "message": message, "request_id": rid}}
        return JSONResponse(body, status_code=status, headers={"X-Request-ID": rid})

    @app.exception_handler(ApiError)
    async def api_error(request: Request, e: ApiError):
        return envelope(request, e.status, e.code, e.message)

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, e: RequestValidationError):
        first = e.errors()[0] if e.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ()))
        return envelope(request, 422, "invalid_request", f"{where}: {first.get('msg', 'invalid')}")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, e: StarletteHTTPException):
        return envelope(request, e.status_code, "http_error", str(e.detail))

    def versions() -> Versions:
        return Versions(
            vocabulary=load_vocabulary().version, rules=load_rules().version, model=extractor.name
        )

    def flags_of(record: Encounter) -> list[FlagOut]:
        return [FlagOut.of(f) for f in check(record)]

    def load(rid: str, cid: str) -> dict[str, Any]:
        rec = store.get(rid, cid)
        if rec is None:
            raise ApiError(404, "not_found", "No such record")
        return rec

    def record_out(rec: dict[str, Any]) -> RecordOut:
        record = Encounter.model_validate(rec["record"])
        events = [EventOut(**{k: e[k] for k in EventOut.model_fields}) for e in rec["events"]]
        return RecordOut(
            id=rec["id"],
            created_at=rec["created_at"],
            status=rec["status"],
            record=record,
            flags=flags_of(record),
            events=events,
        )

    @app.get("/v1/health", tags=["service"], summary="Liveness (no key needed)")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/version", tags=["service"], summary="Versions of the schema, rules and model")
    def version(_: Client) -> Versions:
        return versions()

    @app.post(
        "/v1/extract",
        tags=["documentation"],
        summary="Draft a structured record from visit text, with danger-sign flags",
    )
    def extract(body: ExtractIn, _: Client) -> ExtractOut:
        if len(body.text) > settings.max_text_chars:
            raise ApiError(413, "too_large", f"text is longer than {settings.max_text_chars}")
        t0 = time.perf_counter()
        try:
            draft = extractor.extract(body.text)
        except ExtractorError as e:
            raise ApiError(502, "model_unavailable", f"The model backend failed ({e})") from e
        g = ground(draft.record, body.text)
        dropped = [
            DroppedOut(path=r.path, reason="schema_repair", detail=r.detail) for r in draft.repairs
        ] + [DroppedOut(path=d.path, reason=d.reason, detail=d.detail) for d in g.dropped]
        checks = [
            ReviewCheck(path=c.path, reason="polarity", detail=c.detail)
            for c in polarity_check(g.record)
        ]
        return ExtractOut(
            record=g.record,
            flags=flags_of(g.record),
            grounding=Grounding(
                needs_review=bool(dropped or checks),
                fields_total=g.fields_total,
                dropped=dropped,
                checks=checks,
            ),
            versions=versions(),
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        )

    @app.post(
        "/v1/transcribe",
        tags=["documentation"],
        summary="Speech to text with the N-ATLaS ASR models",
        description="Send the recording as the raw request body (Content-Type: audio/wav,"
        " 16- or 32-bit PCM, any sample rate, up to about 5 minutes). Yoruba, Hausa and Igbo use"
        " their own NCAIR1 models; English and Pidgin use the Nigerian-accented English model.",
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {"audio/wav": {"schema": {"type": "string", "format": "binary"}}},
            }
        },
    )
    async def transcribe(
        request: Request,
        _: Client,
        language: Literal["en", "yo", "pcm", "ha", "ig"],
    ) -> TranscribeOut:
        if transcriber is None:
            raise ApiError(501, "asr_not_enabled", "Speech recognition is off on this server")
        data = await request.body()
        if len(data) > settings.max_audio_bytes:
            raise ApiError(413, "too_large", "audio is longer than about 5 minutes")
        try:
            samples, duration = read_wav(data)
        except AudioError as e:
            raise ApiError(415, "unsupported_audio", str(e)) from e
        t0 = time.perf_counter()
        try:
            text = transcriber.transcribe(samples, language)
        except Exception as e:  # model download or inference failure
            raise ApiError(502, "model_unavailable", f"ASR failed ({type(e).__name__})") from e
        return TranscribeOut(
            text=text,
            language=language,
            model=transcriber.model_for(language),
            duration_s=round(duration, 2),
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        )

    @app.post("/v1/check", tags=["documentation"], summary="Danger-sign flags for a record")
    def check_record(body: CheckIn, _: Client) -> CheckOut:
        return CheckOut(flags=flags_of(body.record), rules_version=load_rules().version)

    @app.post(
        "/v1/records",
        status_code=201,
        tags=["records"],
        summary="Save a draft record (idempotent)",
        description="Send a unique Idempotency-Key per record. Retrying with the same key and"
        " body returns the original record (200); the same key with another body is a 409.",
    )
    def create_record(
        body: RecordIn,
        cid: Client,
        idempotency_key: Annotated[str, Header(min_length=8, max_length=100)],
    ) -> JSONResponse:
        payload = body.model_dump(mode="json")
        try:
            rid, created = store.create(cid, idempotency_key, payload, body.actor)
        except IdempotencyConflict as e:
            raise ApiError(409, "idempotency_conflict", "Key reused with a different body") from e
        out = record_out(load(rid, cid)).model_dump(mode="json")
        return JSONResponse(out, status_code=201 if created else 200)

    @app.get("/v1/records/{record_id}", tags=["records"], summary="A record and its history")
    def get_record(record_id: str, cid: Client) -> RecordOut:
        return record_out(load(record_id, cid))

    @app.post(
        "/v1/records/{record_id}/confirm",
        tags=["records"],
        summary="A health worker confirms the record",
    )
    def confirm(record_id: str, body: ConfirmIn, cid: Client) -> RecordOut:
        rec = load(record_id, cid)
        if rec["status"] == "confirmed":
            return record_out(rec)
        store.append(record_id, "confirmed", {}, body.actor, None)
        return record_out(load(record_id, cid))

    @app.post(
        "/v1/records/{record_id}/amend",
        tags=["records"],
        summary="Correct a record (kept as a new version; needs confirming again)",
    )
    def amend(record_id: str, body: AmendIn, cid: Client) -> RecordOut:
        load(record_id, cid)
        store.append(
            record_id,
            "amended",
            {"record": body.record.model_dump(mode="json")},
            body.actor,
            body.reason,
        )
        return record_out(load(record_id, cid))

    return app


def _default_app() -> FastAPI:
    return create_app()


def __getattr__(name: str) -> Any:  # `uvicorn phc_scribe.api.app:app` builds it lazily
    if name == "app":
        return _default_app()
    raise AttributeError(name)
