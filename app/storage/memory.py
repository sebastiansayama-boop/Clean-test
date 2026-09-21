from ..models import Evidence, Operation


class InMemoryStore:
    def __init__(self):
        self.operations = {}
        self.evidence = {}

    def save_operation(self, op: Operation):
        self.operations[op.operation_id] = op.model_copy(deep=True)

    def get_operation(self, oid: str):
        op = self.operations.get(oid)
        return op.model_copy(deep=True) if op else None

    def add_evidence(self, evidence: Evidence):
        self.evidence.setdefault(evidence.operation_id, []).append(evidence.model_copy(deep=True))

    def list_evidence(self, oid: str):
        return [e.model_copy(deep=True) for e in self.evidence.get(oid, [])]
