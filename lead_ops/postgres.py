import json
import os
from typing import Any

import psycopg

from .models import LeadAnalysis, RunResult


class PostgresLeadStore:
    """Postgres-backed store for the deployed SaaS runtime."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is required")
        self._initialize_db()

    def _connect(self):
        return psycopg.connect(self.database_url)

    def _initialize_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    id TEXT PRIMARY KEY,
                    data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

    @property
    def leads(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT data FROM leads ORDER BY created_at, id"
            ).fetchall()
        return [row[0] for row in rows]

    def add_lead(self, analysis: LeadAnalysis) -> dict[str, Any]:
        record = {
            "id": f"lead-{os.urandom(8).hex()}",
            "email": analysis.email,
            "name": analysis.name,
            "company": analysis.company,
            "request": analysis.request,
            "estimated_value": analysis.estimated_value,
        }
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO leads (id, data) VALUES (%s, %s::jsonb)",
                (record["id"], json.dumps(record)),
            )
        return record

    def save_run(self, result: RunResult) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs (run_id, data) VALUES (%s, %s::jsonb)
                ON CONFLICT (run_id) DO UPDATE SET data = EXCLUDED.data
                """,
                (result.run_id, result.model_dump_json()),
            )

    def get_run(self, run_id: str) -> RunResult:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT data FROM runs WHERE run_id = %s",
                (run_id,),
            ).fetchone()
        if not row:
            raise KeyError(run_id)
        return RunResult.model_validate(row[0])

    def list_runs(self, limit: int = 50) -> list[RunResult]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT data FROM runs ORDER BY created_at DESC, run_id DESC LIMIT %s",
                (limit,),
            ).fetchall()
        return [RunResult.model_validate(row[0]) for row in rows]
