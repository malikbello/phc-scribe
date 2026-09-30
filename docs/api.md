# PHC Scribe API v1

The API drafts a structured antenatal-care (ANC) record from what was said or written at a visit, flags danger signs, and keeps each record with its full history. It is a **documentation aid**: it drafts, and a health worker confirms. It never gives advice or a diagnosis.

- **Contract:** [`openapi.v1.json`](openapi.v1.json) is the source of truth. It is generated from the code, and CI fails if it is out of date. A running server also serves interactive docs at `/docs`.
- **Record schema:** [`schema/encounter.v0.1.json`](../schema/encounter.v0.1.json) (semver; every response states the schema, vocabulary, rules and model versions).
- **Model:** a fine-tuned N-ATLaS behind a llama.cpp server (`PHC_EXTRACTOR=llamacpp`). The same schema constrains decoding as in the benchmark. The keyword baseline (`PHC_EXTRACTOR=keyword`) needs no model and is the default for local testing.

## Endpoints

| Method and path | What it does |
|---|---|
| `GET /v1/health` | Liveness. No key needed. |
| `GET /v1/version` | API, service, schema, vocabulary, rules and model versions |
| `POST /v1/extract` | Visit text → draft record, danger-sign flags, grounding report |
| `POST /v1/check` | A record → danger-sign flags (the rules engine alone) |
| `POST /v1/records` | Save a draft record. Needs an `Idempotency-Key` header |
| `GET /v1/records/{id}` | The current record, its status and full event history |
| `POST /v1/records/{id}/confirm` | A health worker confirms the record |
| `POST /v1/records/{id}/amend` | Correct a record; the old version is kept, and the record needs confirming again |

Speech input (`/v1/transcribe`, N-ATLaS ASR) and the monthly NHMIS summary are the next endpoints.

## Example

```bash
curl -s https://<host>/v1/extract \
  -H "Authorization: Bearer $PHC_API_KEY" -H "Content-Type: application/json" \
  -d '{"text": "Oyun osu meje. Ori n fo mi gan, eje n jade. BP 150/100.", "language": "yo"}'
```

The response (shortened):

```json
{
  "record": {
    "findings": [
      {"concept": "severe_headache", "assertion": "present", "evidence": {"text": "Ori n fo mi gan", "start": 15, "end": 30}},
      {"concept": "vaginal_bleeding", "assertion": "present", "evidence": {"text": "eje n jade", "start": 32, "end": 42}}
    ],
    "vitals": {"blood_pressure": {"systolic": 150, "diastolic": 100, "evidence": {"text": "150/100"}}}
  },
  "flags": [{"rule_id": "DS-001", "severity": "urgent_referral", "message_en": "..."}, {"rule_id": "DS-003", "...": "..."}, {"rule_id": "CB-001", "...": "..."}],
  "grounding": {"needs_review": false, "fields_total": 3, "dropped": []},
  "versions": {"api": "v1", "schema_version": "0.1.0", "rules": "0.1.0", "model": "..."}
}
```

## Guarantees
- **Every value is grounded.** Each finding and number carries a quote copied exactly from the input, with character offsets. Values the model cannot support with a quote are dropped and listed in `grounding.dropped`, and `needs_review` becomes true.
- **Records are append-only.** Confirming and amending add events; nothing is overwritten. Each event records who (a worker id, not a name) and when.
- **Idempotent writes.** Retrying `POST /v1/records` with the same `Idempotency-Key` and body returns the original record (200, not a duplicate). The same key with a different body is refused (409).
- **Private per client.** A client sees only the records it created.

## Errors
Every error has the same shape, and every response carries an `X-Request-ID` header (send your own to trace a request end to end):

```json
{"error": {"code": "unauthorized", "message": "Send a valid API key: Authorization: Bearer <key>", "request_id": "…"}}
```

| Status | `code` | Meaning |
|---|---|---|
| 401 | `unauthorized` | Missing or wrong API key |
| 404 | `not_found` | No such record for this client |
| 409 | `idempotency_conflict` | Idempotency key reused with a different body |
| 413 | `too_large` | Text longer than 8,000 characters |
| 422 | `invalid_request` | The body does not match the contract |
| 429 | `rate_limited` | More than the per-key limit per minute (default 60) |
| 502 | `model_unavailable` | The model backend failed; nothing was saved |

## Security and privacy
- API keys are compared as SHA-256 hashes (`PHC_API_KEY_HASHES`); the service never stores a key. Create one with `python scripts/make_api_key.py` on your own computer.
- The service refuses to start without keys unless `PHC_ENV=dev`.
- Logs hold the request id, route, status and latency only. **Clinical text is never logged.**
- Responses are `Cache-Control: no-store`.

## Running it

```bash
pip install -e ".[api]"
PHC_ENV=dev uvicorn phc_scribe.api.app:app --port 8000               # keyword baseline, no key
PHC_API_KEY_HASHES=<hash> PHC_EXTRACTOR=llamacpp \
  PHC_LLAMACPP_URL=http://127.0.0.1:8080 uvicorn phc_scribe.api.app:app  # fine-tuned model
```

| Variable | Default | Meaning |
|---|---|---|
| `PHC_API_KEY_HASHES` | (required) | Comma-separated SHA-256 hashes of accepted keys |
| `PHC_ENV` | `production` | `dev` allows running without keys |
| `PHC_EXTRACTOR` | `keyword` | `keyword` or `llamacpp` |
| `PHC_LLAMACPP_URL` | `http://127.0.0.1:8080` | llama.cpp server with the GGUF model |
| `PHC_DB` | `phc_scribe.sqlite3` | SQLite file for records |
| `PHC_RATE_LIMIT_PER_MINUTE` | `60` | Requests per key per minute |
