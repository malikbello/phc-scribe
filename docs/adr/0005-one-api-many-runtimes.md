# ADR-0005: One API contract, many runtimes

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
Facilities range from connected to fully offline. We have no purchased hardware.

## Decision
A single versioned API (`/v1`, OpenAPI) with a model adapter over two runtimes: vLLM + LoRA on cloud GPU (Modal), and llama.cpp GGUF on CPU (laptop now, a buyer-funded edge box later).

## Consequences
The same client and integrations work everywhere. Two runtime backends must be kept in parity by contract tests.
