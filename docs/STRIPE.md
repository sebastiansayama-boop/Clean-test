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


## Real Test Mode smoke test

Create or use a successful Stripe sandbox PaymentIntent. Stripe documents sandbox testing and the test PaymentMethod `pm_card_visa`; sandbox transactions do not move real funds. The smoke test is opt-in and is never enabled by CI.

Set these variables locally:

    $env:RUN_STRIPE_TESTMODE="1"
    $env:STRIPE_API_KEY="sk_test_..."
    $env:STRIPE_TEST_ORDER_ID="1002"
    $env:STRIPE_TEST_PAYMENT_INTENT="pi_..."
    $env:STRIPE_TEST_IDEMPOTENCY_KEY="stripe-smoke-1002-refund-1"
    $env:STRIPE_TEST_REFUND_AMOUNT="1.00"

Then run:

    uv run pytest -q tests/test_stripe_testmode.py

The idempotency key should be reused if the smoke test is repeated for the same intended refund. Do not put the secret key in Git, `.env` files committed to the repository, or CI configuration.
