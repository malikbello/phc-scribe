# ADR-0007: No purchased hardware and a $0 cash budget for NAIC

- **Status:** Accepted
- **Date:** 2026-09-29

## Context
No edge hardware is available. The budget is $0.

## Decision
Train on Kaggle's free GPUs. Serve the online API on Modal's free credits. Run the offline node on Malik's laptop (i7-8665U, 16 GB). Edge boxes are funded by the buyer at pilot scale.

## Consequences
Laptop latency is minutes per record (asynchronous by design). Free quotas limit training runs to about 3 plus 1 ablation.
