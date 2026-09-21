from pathlib import Path

from app.models import Evidence, Operation, OperationStatus
from app.storage.sqlite import SQLiteStore


def test_sqlite_store_persists_operation_and_evidence():
    db_path = Path(__file__).parent / f".sqlite-test-{__import__('os').getpid()}.db"
    try:
        store = SQLiteStore(str(db_path))
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
    finally:
        db_path.unlink(missing_ok=True)


def test_pending_approval_survives_router_restart():
    db_path = Path(__file__).parent / f".sqlite-durable-approval-{__import__('os').getpid()}.db"
    try:
        import asyncio
        from app.adapters.mock_payment import MockPaymentProvider
        from app.models import Request, OperationStatus
        from app.workflow import ControlledRouter

        first = ControlledRouter(SQLiteStore(str(db_path)), MockPaymentProvider())
        op = asyncio.run(first.submit(Request(
            request_id="req_restart",
            raw_text="Please refund order #1002 for $800.",
        )))
        assert op.status == OperationStatus.PENDING_APPROVAL

        second_provider = MockPaymentProvider()
        second = ControlledRouter(SQLiteStore(str(db_path)), second_provider)
        restored = second.store.get_operation(op.operation_id)
        assert restored is not None
        assert restored.status == OperationStatus.PENDING_APPROVAL

        completed = second.approve(restored.operation_id, True)
        assert completed.status == OperationStatus.COMPLETED
        assert second_provider.refund_calls == 1
    finally:
        db_path.unlink(missing_ok=True)
