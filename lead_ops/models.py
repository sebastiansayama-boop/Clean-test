from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class LeadClass(str, Enum):
    LEAD = "lead"
    SPAM = "spam"
    UNCLEAR = "unclear"

class IncomingMessage(BaseModel):
    source_id: str
    sender: str
    subject: str = ""
    body: str

class LeadAnalysis(BaseModel):
    classification: LeadClass
    name: str | None = None
    company: str | None = None
    email: str | None = None
    request: str | None = None
    estimated_value: float | None = None
    confidence: float = Field(ge=0, le=1)
    reason: str

class BusinessRules(BaseModel):
    minimum_value: float = 0
    require_company: bool = False
    auto_create_lead: bool = True

class RunResult(BaseModel):
    run_id: str
    status: str
    analysis: LeadAnalysis
    actions: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
