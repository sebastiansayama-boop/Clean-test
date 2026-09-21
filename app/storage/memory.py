from threading import Lock

from ..models import Evidence, Operation, OperationStatus


class InMemoryStore:
    def __init__(self):
        self.operations = {}
        self.evidence = {}
        self._lock = Lock()

    def save_operation(self, op: Operation):
        with self._lock:
            self.operations[op.operation_id] = op.model_copy(deep=True)

    def get_operation(self, oid: str):
        with self._lock:
            op = self.operations.get(oid)
            return op.model_copy(deep=True) if op else None

    def claim_approval(self, oid: str, approve: bool):
        with self._lock:
            op = self.operations.get(oid)
            if op is None:
                return None
            if op.status != OperationStatus.PENDING_APPROVAL:
                return False
            op = op.model_copy(deep=True)
            op.approval = "approved" if approve else "rejected"
            op.status = OperationStatus.APPROVED if approve else OperationStatus.REJECTED
            self.operations[oid] = op
            return op.model_copy(deep=True)

    def add_evidence(self, evidence: Evidence):
        with self._lock:
            self.evidence.setdefault(evidence.operation_id, []).append(evidence.model_copy(deep=True))

    def list_evidence(self, oid: str):
        with self._lock:
            return [e.model_copy(deep=True) for e in self.evidence.get(oid, [])]
