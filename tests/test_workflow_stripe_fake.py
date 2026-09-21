from types import SimpleNamespace

import pytest

from app.adapters.stripe_payment import StripePaymentProvider
from app.models import OperationStatus, Request
from app.storage.memory import InMemoryStore
from app.workflow import ControlledRouter


class FakeStripe:
    class APIConnectionError(Exception):
        pass

    def __init__(self):
        self.api_key = None
        self.PaymentIntent = SimpleNamespace(retrieve=self.retrieve_payment_intent)
        self.Refund = SimpleNamespace(
            list=self.list_refunds,
            create=self.create_refund,
        )
        self.payment_intent = SimpleNamespace(
            id="pi_test_123",
            status="succeeded",
            currency="usd",
            amount_received=80000,
        )
        self.refund_objects = []
        self.refund_create_calls = 0

    def retrieve_payment_intent(self, payment_intent_id):
        assert payment_intent_id == "pi_test_123"
        return self.payment_intent

    def list_refunds(self, *, payment_intent, limit):
        assert payment_intent == "pi_test_123"
        assert limit == 100
        return SimpleNamespace(data=list(self.refund_objects))

    def create_refund(
        self,
        *,
        payment_intent,
        amount,
        reason,
        metadata,
        idempotency_key,
    ):
        assert payment_intent == "pi_test_123"
        assert amount == 80000
        assert reason == "requested_by_customer"
        assert metadata == {"router_operation_id": idempotency_key}
        assert idempotency_key.startswith("op_")
        self.refund_create_calls += 1
        refund = SimpleNamespace(
            id="re_test_123",
            payment_intent=payment_intent,
            amount=amount,
            currency="usd",
            status="succeeded",
            reason=reason,
        )
        self.refund_objects.append(refund)
        return refund


@pytest.mark.asyncio
async def test_full_approval_workflow_uses_stripe_adapter_without_credentials(monkeypatch):
    fake = FakeStripe()
    monkeypatch.setattr("app.adapters.stripe_payment.stripe", fake)

    provider = StripePaymentProvider(
        {"1002": "pi_test_123"},
        api_key="sk_test_fake",
    )
    router = ControlledRouter(InMemoryStore(), provider)

    op = await router.submit(
        Request(
            request_id="stripe-fake-approval",
            raw_text="Please refund order #1002 for $800.",
        )
    )

    assert op.status == OperationStatus.PENDING_APPROVAL
    assert fake.refund_create_calls == 0

    op = router.approve(op.operation_id, True)

    assert op.status == OperationStatus.COMPLETED
    assert op.external_reference == "re_test_123"
    assert op.result["status"] == "succeeded"
    assert fake.refund_create_calls == 1

    evidence = router.store.list_evidence(op.operation_id)
    kinds = [item.type for item in evidence]
    assert "REQUEST" in kinds
    assert "ANALYSIS" in kinds
    assert "POLICY_DECISION" in kinds
    assert "APPROVAL" in kinds
    assert "EXTERNAL_RESULT" in kinds
    assert "VERIFICATION" in kinds
