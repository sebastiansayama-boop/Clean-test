import pytest
from app.workflow import ControlledRouter
from app.storage.memory import InMemoryStore
from app.adapters.mock_payment import MockPaymentProvider
from app.models import Request, OperationStatus


def make():
    return ControlledRouter(InMemoryStore(), MockPaymentProvider())


@pytest.mark.asyncio
async def test_small_refund_completes():
    r = make()
    op = await r.submit(Request(request_id="r1", raw_text="I want to refund order #1001."))
    assert op.status == OperationStatus.COMPLETED
    assert r.provider.refund_calls == 1


@pytest.mark.asyncio
async def test_large_refund_waits_for_approval():
    r = make()
    op = await r.submit(Request(request_id="r2", raw_text="Please refund order #1002 for $800."))
    assert op.status == OperationStatus.PENDING_APPROVAL
    assert r.provider.refund_calls == 0


@pytest.mark.asyncio
async def test_rejection_has_no_external_effect():
    r = make()
    op = await r.submit(Request(request_id="r3", raw_text="Please refund order #1002 for $800."))
    op = r.approve(op.operation_id, False)
    assert op.status == OperationStatus.REJECTED
    assert r.provider.refund_calls == 0


@pytest.mark.asyncio
async def test_timeout_becomes_unknown_and_reconciles():
    r = make()
    r.provider.timeout_after_effect = True
    op = await r.submit(Request(request_id="r4", raw_text="I want to refund order #1001."))
    assert op.status == OperationStatus.UNKNOWN
    op = r.reconcile(op.operation_id)
    assert op.status == OperationStatus.COMPLETED
