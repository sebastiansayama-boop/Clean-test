# Stripe test provider

The MVP keeps MockPaymentProvider as the default CI provider and adds
StripePaymentProvider as a real external-effect adapter.

The adapter maps application order IDs to Stripe PaymentIntent IDs through
STRIPE_PAYMENT_INTENTS_JSON:

    {"1002": "pi_test_..."}

Required environment variables:

    STRIPE_API_KEY=sk_test_...
    STRIPE_PAYMENT_INTENTS_JSON={"1002":"pi_..."}

The adapter currently supports USD only because the MVP policy and request
model use dollar amounts. Stripe amounts are converted to cents at the adapter
boundary.

The external refund uses the durable application operation_id as the Stripe
idempotency key. A Stripe connection error is treated as an unknown external
outcome so the workflow can reconcile instead of declaring a false failure.

This integration is intentionally test-mode oriented. No Stripe credentials
belong in the repository or CI configuration.
