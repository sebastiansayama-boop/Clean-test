from types import SimpleNamespace

import pytest

from app.adapters.stripe_payment import StripePaymentProvider


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

    def retrieve_payment_intent(self, payment_intent_id):
        assert payment_intent_id == "pi_test_123"
        return self.payment_intent

    def list_refunds(self, *, payment_intent, limit):
        assert payment_intent == "pi_test_123"
        assert limit == 100
        return SimpleNamespace(data=list(self.refund_objects))

    def create_refund(self, *, payment_intent, amount, reason, metadata, idempotency_key):
        assert payment_intent == "pi_test_123"
        assert amount == 80000
        assert reason == "requested_by_customer"
        assert metadata == {"router_operation_id": "op_test_123"}
        assert idempotency_key == "op_test_123"
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


def make(monkeypatch):
    fake = FakeStripe()
    monkeypatch.setattr("app.adapters.stripe_payment.stripe", fake)
    return fake, StripePaymentProvider({"1002": "pi_test_123"}, api_key="sk_test_fake")


def test_get_payment_normalizes_stripe_payment_intent(monkeypatch):
    fake, provider = make(monkeypatch)

    payment = provider.get_payment("1002")

    assert payment.payment_id == "pi_test_123"
    assert payment.amount == 800.0
    assert payment.currency == "USD"
    assert payment.status == "paid"
    assert payment.refundable is True


def test_refund_uses_operation_id_as_stripe_idempotency_key(monkeypatch):
    fake, provider = make(monkeypatch)

    result = provider.refund("pi_test_123", 800.0, "Customer request", "op_test_123")

    assert result["refund_id"] == "re_test_123"
    assert result["amount"] == 800.0
    assert len(fake.refund_objects) == 1


def test_get_refund_verifies_existing_stripe_refund(monkeypatch):
    fake, provider = make(monkeypatch)
    provider.refund("pi_test_123", 800.0, "Customer request", "op_test_123")

    result = provider.get_refund("pi_test_123", 800.0)

    assert result["refund_id"] == "re_test_123"
    assert result["status"] == "succeeded"


def test_connection_error_becomes_unknown_provider_outcome(monkeypatch):
    fake, provider = make(monkeypatch)

    def fail(**kwargs):
        raise FakeStripe.APIConnectionError("network failure")

    fake.Refund.create = fail

    with pytest.raises(Exception) as exc:
        provider.refund("pi_test_123", 800.0, "Customer request", "op_test_123")

    assert exc.value.__class__.__name__ == "ProviderTimeoutAfterEffect"
