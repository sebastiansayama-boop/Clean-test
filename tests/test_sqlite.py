from app.models import Evidence, Operation, OperationStatus
from app.storage.sqlite import SQLiteStore


def test_sqlite_store_persists_operation_and_evidence(tmp_path):
    store = SQLiteStore(str(tmp_path / "router.db"))
    op = Operation(
        operation_id="op_test",
        request_id="req_test",
        action="refund",
        resource="order:1001",
        status=OperationStatus.RECEIVED,
    )
    store.save_operation(op)
    store.add_evidence(
        Evidence(
            evidence_id="ev_test",
            operation_id=op.operation_id,
            type="TEST",
            source="pytest",
            data={"ok": True},
        )
    )

    restored = store.get_operation(op.operation_id)
    evidence = store.list_evidence(op.operation_id)
    assert restored is not None
    assert restored.operation_id == op.operation_id
    assert evidence[0].data == {"ok": True}
