import re
import uuid
from dataclasses import dataclass, field
from typing import Any
from .models import BusinessRules, IncomingMessage, LeadAnalysis, LeadClass, RunResult

@dataclass
class LeadStore:
    leads: list[dict[str, Any]] = field(default_factory=list)
    runs: dict[str, RunResult] = field(default_factory=dict)
    def add_lead(self, analysis: LeadAnalysis) -> dict[str, Any]:
        record = {"id": f"lead-{len(self.leads) + 1}", "email": analysis.email, "name": analysis.name, "company": analysis.company, "request": analysis.request, "estimated_value": analysis.estimated_value}
        self.leads.append(record)
        return record

def analyze_message(message: IncomingMessage) -> LeadAnalysis:
    text = f"{message.subject}\n{message.body}".strip()
    lowered = text.lower()
    if any(word in lowered for word in ("unsubscribe", "casino", "viagra", "seo backlinks")):
        return LeadAnalysis(classification=LeadClass.SPAM, email=message.sender, confidence=0.98, reason="Matched spam indicators")
    value_match = re.search(r"(?:\\$|usd\\s*)([0-9][0-9,]*(?:\\.[0-9]+)?)", text, re.I)
    value = float(value_match.group(1).replace(",", "")) if value_match else None
    company_match = re.search(r"(?:company|from|at)\\s*[:\\-]?\\s*([A-Z][A-Za-z0-9 .&-]{1,60})", text)
    company = company_match.group(1).strip() if company_match else None
    sales_words = ("demo", "quote", "pricing", "price", "proposal", "service", "buy", "purchase", "enterprise")
    if any(word in lowered for word in sales_words):
        return LeadAnalysis(classification=LeadClass.LEAD, company=company, email=message.sender, request=message.body[:500], estimated_value=value, confidence=0.82, reason="Matched commercial-intent indicators")
    return LeadAnalysis(classification=LeadClass.UNCLEAR, company=company, email=message.sender, request=message.body[:500], estimated_value=value, confidence=0.55, reason="No deterministic classification signal was sufficient")

def process_message(message: IncomingMessage, rules: BusinessRules, store: LeadStore) -> RunResult:
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    analysis = analyze_message(message)
    actions: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = [{"type": "INPUT", "source_id": message.source_id}]
    if analysis.classification is LeadClass.LEAD:
        if rules.require_company and not analysis.company:
            analysis = analysis.model_copy(update={"classification": LeadClass.UNCLEAR, "reason": "Business rule requires company"})
        elif analysis.estimated_value is not None and analysis.estimated_value < rules.minimum_value:
            analysis = analysis.model_copy(update={"classification": LeadClass.UNCLEAR, "reason": "Below configured minimum value"})
    if analysis.classification is LeadClass.LEAD and rules.auto_create_lead:
        record = store.add_lead(analysis)
        actions.append({"type": "CREATE_LEAD", "status": "completed", "record_id": record["id"]})
        evidence.append({"type": "EXTERNAL_RESULT", "record_id": record["id"]})
        status = "COMPLETED"
    elif analysis.classification is LeadClass.UNCLEAR:
        actions.append({"type": "HUMAN_REVIEW", "status": "required"})
        status = "PENDING_REVIEW"
    else:
        actions.append({"type": "NO_ACTION", "status": "completed"})
        status = "COMPLETED"
    evidence.append({"type": "ANALYSIS", "classification": analysis.classification.value, "confidence": analysis.confidence})
    result = RunResult(run_id=run_id, status=status, analysis=analysis, actions=actions, evidence=evidence)
    store.runs[run_id] = result
    return result
