import os

import pytest

from app.adapters.stripe_payment import StripePaymentProvider


pytestmark = pytest.mark.integration


def test_real_stripe_testmode_refund():
    if os.getenv("RUN_STRIPE_TESTMODE") != "1":
        pytest.skip("Set RUN_STRIPE_TESTMODE=1 to run the real Stripe Test Mode smoke test.")

    api_key = os.getenv("STRIPE_API_KEY")
    order_id = os.getenv("STRIPE_TEST_ORDER_ID")
    payment_intent_id = os.getenv("STRIPE_TEST_PAYMENT_INTENT")
    idempotency_key = os.getenv("STRIPE_TEST_IDEMPOTENCY_KEY")
    amount = float(os.getenv("STRIPE_TEST_REFUND_AMOUNT", "1.00"))

    missing = [
        name
        for name, value in {
            "STRIPE_API_KEY": api_key,
            "STRIPE_TEST_ORDER_ID": order_id,
            "STRIPE_TEST_PAYMENT_INTENT": payment_intent_id,
            "STRIPE_TEST_IDEMPOTENCY_KEY": idempotency_key,
        }.items()
        if not value
    ]
    if missing:
        pytest.fail("Missing Stripe Test Mode variables: " + ", ".join(missing))

    provider = StripePaymentProvider(
        {order_id: payment_intent_id},
        api_key=api_key,
    )

    payment = provider.get_payment(order_id)
    assert payment.payment_id == payment_intent_id
    assert payment.currency == "USD"
    assert payment.status == "paid"
    assert payment.amount >= amount

    refund = provider.refund(
        payment_intent_id,
        amount,
        "Customer request",
        idempotency_key=idempotency_key,
    )

    assert refund["payment_id"] == payment_intent_id
    assert refund["amount"] == amount
    assert refund["status"] in {"pending", "succeeded"}

    observed = provider.get_refund(payment_intent_id, amount)
    assert observed is not None
    assert observed["amount"] == amount
