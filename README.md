# Controlled AI Request → Action Router

A small reference implementation of a controlled AI workflow:

REQUEST → UNDERSTAND → VALIDATE → DECIDE → ACTION / HUMAN REVIEW → VERIFY → EVIDENCE

The MVP demonstrates a customer refund workflow without granting the model unrestricted authority over the external effect.

## Scope

- Python 3.12
- OpenAI Agents SDK
- Pydantic
- SQLite
- FastAPI
- HTML approval surface
- Mock payment provider

The first version intentionally avoids n8n, Redis, Kafka, Temporal, Postgres, Kubernetes, multi-agent orchestration, billing, and a custom agent runtime.

## Safety model

The model interprets the request and can retrieve information. Deterministic Python code owns policy decisions. Refund execution is an external effect and is gated by policy. High-value refunds require human approval. Every operation records evidence.

The mock provider can simulate a timeout after an effect has occurred so the workflow can exercise UNKNOWN → RECONCILIATING rather than incorrectly treating the operation as simply failed.

## Run

    uv sync
    uv run uvicorn app.main:app --reload

Open http://127.0.0.1:8000.

Set OPENAI_API_KEY to enable the real agent path. Without a key, the demo API still exposes the deterministic workflow and mock-provider tests.

## Tests

    uv run pytest

## Demo scenarios

1. $45 eligible refund → automatic execution.
2. $800 refund → human approval.
3. $800 refund rejected → no external effect.
4. Provider timeout after effect → UNKNOWN → reconciliation → COMPLETED.

See docs/MVP.md for the component and state model.
