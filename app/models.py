from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class OperationStatus(StrEnum):
    RECEIVED="RECEIVED"; ANALYZING="ANALYZING"; VALIDATING="VALIDATING"; DECIDING="DECIDING"
    PENDING_APPROVAL="PENDING_APPROVAL"; APPROVED="APPROVED"; REJECTED="REJECTED"
    EXECUTING="EXECUTING"; VERIFYING="VERIFYING"; COMPLETED="COMPLETED"; FAILED="FAILED"
    UNKNOWN="UNKNOWN"; RECONCILING="RECONCILING"

class Request(BaseModel):
    request_id: str
    source: str="demo"
    received_at: str=Field(default_factory=now_iso)
    customer_id: str|None=None
    raw_text: str
    metadata: dict[str,Any]=Field(default_factory=dict)

class RequestAnalysis(BaseModel):
    intent: str
    confidence: float=Field(ge=0,le=1)
    order_id: str|None=None
    requested_amount: float|None=None
    requested_action: str
    missing_information: list[str]=Field(default_factory=list)
    reasoning_summary: str

class PolicyDecision(BaseModel):
    allowed: bool
    requires_approval: bool
    reason: str

class Operation(BaseModel):
    operation_id: str
    request_id: str
    action: str
    resource: str
    arguments: dict[str,Any]=Field(default_factory=dict)
    status: OperationStatus
    authorization: str="unknown"
    approval: str|None=None
    external_reference: str|None=None
    result: dict[str,Any]|None=None
    created_at: str=Field(default_factory=now_iso)
    updated_at: str=Field(default_factory=now_iso)

class Evidence(BaseModel):
    evidence_id: str
    operation_id: str
    type: str
    source: str
    data: dict[str,Any]
    timestamp: str=Field(default_factory=now_iso)

class RequestSubmission(BaseModel):
    request_id: str
    source: str="demo"
    customer_id: str|None=None
    raw_text: str
    metadata: dict[str,Any]=Field(default_factory=dict)

class ApprovalDecision(BaseModel):
    approve: bool
