import json
import os
from dataclasses import dataclass
from typing import Any

import stripe

from .mock_payment import Payment, ProviderTimeoutAfterEffect


@dataclass
class StripePaymentProvider:
    """Stripe-backed payment adapter for the MVP.

    The application addresses orders; this adapter maps each order_id to a
    Stripe PaymentIntent ID. The MVP currently normalizes amounts to USD.
    """

    order_to_payment_intent: dict[str, str]
    api_key: str | None = None

    def __post_init__(self):
        key = self.api_key or os.getenv("STRIPE_API_KEY")
        if not key:
            raise ValueError("STRIPE_API_KEY is required for the Stripe provider.")
        stripe.api_key = key

    @classmethod
    def from_environment(cls):
        raw = os.getenv("STRIPE_PAYMENT_INTENTS_JSON", "{}")
        try:
            mapping = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("STRIPE_PAYMENT_INTENTS_JSON must be valid JSON.") from exc
        if not isinstance(mapping, dict):
            raise ValueError("STRIPE_PAYMENT_INTENTS_JSON must be a JSON object.")
        return cls({str(order): str(payment_intent) for order, payment_intent in mapping.items()})

    def get_payment(self, order_id: str):
        payment_intent_id = self.order_to_payment_intent.get(order_id)
        if not payment_intent_id:
            return None

        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        currency = str(payment_intent.currency).lower()
        if currency != "usd":
            raise ValueError("The MVP Stripe adapter currently supports USD payments only.")

        amount_received = int(payment_intent.amount_received or 0)
        refunds = stripe.Refund.list(payment_intent=payment_intent_id, limit=100)
        refunded_amount = sum(int(refund.amount or 0) for refund in refunds.data)
        refundable_cents = max(amount_received - refunded_amount, 0)

        status = "paid" if payment_intent.status == "succeeded" else str(payment_intent.status)
        return Payment(
            payment_id=payment_intent_id,
            order_id=order_id,
            amount=refundable_cents / 100,
            currency=currency.upper(),
            status=status,
            refundable=refundable_cents > 0,
        )

    def refund(self, payment_id: str, amount: float, reason: str, idempotency_key: str):
        try:
            refund = stripe.Refund.create(
                payment_intent=payment_id,
                amount=self._usd_to_cents(amount),
                reason="requested_by_customer",
                metadata={"router_operation_id": idempotency_key},
                idempotency_key=idempotency_key,
            )
        except stripe.APIConnectionError as exc:
            raise ProviderTimeoutAfterEffect(
                "Stripe connection failed; external refund outcome is unknown."
            ) from exc
        return self._refund_dict(refund)

    def get_refund(self, payment_id: str, amount: float):
        refunds = stripe.Refund.list(payment_intent=payment_id, limit=100)
        expected_cents = self._usd_to_cents(amount)
        for refund in refunds.data:
            if int(refund.amount or 0) == expected_cents:
                return self._refund_dict(refund)
        return None

    @staticmethod
    def _usd_to_cents(amount: float) -> int:
        cents = round(amount * 100)
        if cents <= 0:
            raise ValueError("Refund amount must be positive.")
        return cents

    @staticmethod
    def _refund_dict(refund: Any) -> dict[str, Any]:
        return {
            "refund_id": refund.id,
            "payment_id": refund.payment_intent,
            "amount": int(refund.amount) / 100,
            "currency": str(refund.currency).upper(),
            "status": refund.status,
            "reason": refund.reason,
        }
