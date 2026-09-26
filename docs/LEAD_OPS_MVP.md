# Lead Operations MVP

## Product slice

Incoming business message -> interpretation -> business rules -> lead action -> evidence.

The first engineering slice intentionally uses a deterministic local classifier. This makes the product workflow testable without an external model or integration account. The LLM adapter will be added after the deterministic contract is stable.

## Current behavior

- POST /runs accepts an incoming message.
- The classifier returns lead, spam, or unclear.
- Business rules can move a lead to human review.
- Qualified leads are stored as records.
- Every run returns action and evidence records.
- GET /runs/{run_id} exposes the result.
- GET /leads exposes created leads.

## Next implementation slices

1. Add a structured LLM adapter.
2. Persist runs and leads in SQLite.
3. Add Google Sheets as the first external write target.
4. Add an explicit review endpoint for PENDING_REVIEW.
5. Add Gmail/webhook ingestion.
6. Add Telegram/email summary delivery.
7. Add a minimal dashboard.

## Non-goals for this branch

No universal agent framework, custom runtime, multi-agent orchestration, billing system, or broad integration layer.
