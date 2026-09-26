import json
import re
import sqlite3
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from .models import BusinessRules, IncomingMessage, LeadAnalysis, LeadClass, RunResult


class LeadAnalyzer(Protocol):
    async def analyze(self, message: IncomingMessage) -> LeadAnalysis:
        ...


@dataclass
class LeadStore:
    """Small persistence boundary for leads and run evidence."""

    db_path: str | None = None
    leads: list[dict[str, Any]] = field(default_factory=list)
    runs: dict[str, RunResult] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.db_path is not None:
            self._initialize_db()
            self._load()

    def _connect(self) -> sqlite3.Connection:
        if self.db_path is None:
            raise RuntimeError("Database persistence is not configured")
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                )
                """
            )

    def _load(self) -> None:
        with self._connect() as connection:
            self.leads = [
                json.loads(row["data"])
                for row in connection.execute("SELECT data FROM leads ORDER BY rowid")
            ]
            self.runs = {
                row["run_id"]: RunResult.model_validate_json(row["data"])
                for row in connection.execute("SELECT run_id, data FROM runs ORDER BY rowid")
            }

    def add_lead(self, analysis: LeadAnalysis) -> dict[str, Any]:
        record = {
            "id": f"lead-{len(self.leads) + 1}",
            "email": analysis.email,
            "name": analysis.name,
            "company": analysis.company,
            "request": analysis.request,
            "estimated_value": analysis.estimated_value,
        }
        self.leads.append(record)
        if self.db_path is not None:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO leads (id, data) VALUES (?, ?)",
                    (record["id"], json.dumps(record)),
                )
        return record

    def save_run(self, result: RunResult) -> None:
        self.runs[result.run_id] = result
        if self.db_path is not None:
            with self._connect() as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO runs (run_id, data) VALUES (?, ?)",
                    (result.run_id, result.model_dump_json()),
                )

    def get_run(self, run_id: str) -> RunResult:
        return self.runs[run_id]


def analyze_message(message: IncomingMessage) -> LeadAnalysis:
    """Deterministic fallback used for local logic tests and offline operation."""
    text = f"{message.subject}\n{message.body}".strip()
    lowered = text.lower()

    if any(word in lowered for word in ("unsubscribe", "casino", "viagra", "seo backlinks")):
        return LeadAnalysis(
            classification=LeadClass.SPAM,
            email=message.sender,
            confidence=0.98,
            reason="Matched spam indicators",
        )

    value_match = re.search(r"(?:\$|usd\s*)([0-9][0-9,]*(?:\.[0-9]+)?)", text, re.I)
    value = float(value_match.group(1).replace(",", "")) if value_match else None

    company_match = re.search(
        r"(?:company|from|at)\s*[:\-]?\s*([A-Z][A-Za-z0-9 .&-]{1,60})",
        text,
    )
    company = company_match.group(1).strip() if company_match else None

    sales_words = (
        "demo", "quote", "pricing", "price", "proposal",
        "service", "buy", "purchase", "enterprise",
    )
    if any(word in lowered for word in sales_words):
        return LeadAnalysis(
            classification=LeadClass.LEAD,
            company=company,
            email=message.sender,
            request=message.body[:500],
            estimated_value=value,
            confidence=0.82,
            reason="Matched commercial-intent indicators",
        )

    return LeadAnalysis(
        classification=LeadClass.UNCLEAR,
        company=company,
        email=message.sender,
        request=message.body[:500],
        estimated_value=value,
        confidence=0.55,
        reason="No deterministic classification signal was sufficient",
    )


def _apply_analysis(
    message: IncomingMessage,
    analysis: LeadAnalysis,
    rules: BusinessRules,
    store: LeadStore,
) -> RunResult:
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    actions: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = [
        {"type": "INPUT", "source_id": message.source_id},
        {"type": "ANALYSIS", "classification": analysis.classification.value, "confidence": analysis.confidence},
    ]

    original_classification = analysis.classification.value
    rule_decision = "PASSED"

    if analysis.classification is LeadClass.LEAD:
        if rules.require_company and not analysis.company:
            analysis = analysis.model_copy(update={
                "classification": LeadClass.UNCLEAR,
                "reason": "Business rule requires company",
            })
            rule_decision = "REQUIRE_COMPANY"
        elif analysis.estimated_value is not None and analysis.estimated_value < rules.minimum_value:
            analysis = analysis.model_copy(update={
                "classification": LeadClass.UNCLEAR,
                "reason": "Below configured minimum value",
            })
            rule_decision = "MINIMUM_VALUE"

    evidence.append({
        "type": "RULE_DECISION",
        "original_classification": original_classification,
        "final_classification": analysis.classification.value,
        "decision": rule_decision,
    })

    if analysis.classification is LeadClass.LEAD and rules.auto_create_lead:
        record = store.add_lead(analysis)
        action = {"type": "CREATE_LEAD", "status": "completed", "record_id": record["id"]}
        actions.append(action)
        evidence.append({"type": "PERSISTED_RESULT", "record_id": record["id"]})
        status = "COMPLETED"
    elif analysis.classification is LeadClass.UNCLEAR:
        action = {"type": "HUMAN_REVIEW", "status": "required"}
        actions.append(action)
        evidence.append({"type": "ACTION_RESULT", "action": "HUMAN_REVIEW", "status": "required"})
        status = "PENDING_REVIEW"
    else:
        action = {"type": "NO_ACTION", "status": "completed"}
        actions.append(action)
        evidence.append({"type": "ACTION_RESULT", "action": "NO_ACTION", "status": "completed"})
        status = "COMPLETED"

    result = RunResult(
        run_id=run_id,
        status=status,
        analysis=analysis,
        actions=actions,
        evidence=evidence,
    )
    store.save_run(result)
    return result


def process_message(message: IncomingMessage, rules: BusinessRules, store: LeadStore) -> RunResult:
    return _apply_analysis(message, analyze_message(message), rules, store)


async def process_message_with_analyzer(
    message: IncomingMessage,
    rules: BusinessRules,
    store: LeadStore,
    analyzer: LeadAnalyzer,
) -> RunResult:
    analysis = await analyzer.analyze(message)
    return _apply_analysis(message, analysis, rules, store)
