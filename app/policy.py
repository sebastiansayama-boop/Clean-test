from .models import PolicyDecision

AUTO_REFUND_LIMIT = 100.0


def check_refund_policy(
    *, amount: float, payment_amount: float, payment_status: str, refundable: bool
) -> PolicyDecision:
    if amount <= 0:
        return PolicyDecision(allowed=False, requires_approval=False, reason="Refund amount must be positive.")
    if amount > payment_amount:
        return PolicyDecision(allowed=False, requires_approval=False, reason="Refund amount exceeds the payment amount.")
    if payment_status != "paid":
        return PolicyDecision(allowed=False, requires_approval=False, reason="Payment is not in a refundable paid state.")
    if not refundable:
        return PolicyDecision(allowed=False, requires_approval=False, reason="Payment is not refundable.")
    if amount > AUTO_REFUND_LIMIT:
        return PolicyDecision(allowed=True, requires_approval=True, reason="Amount exceeds automatic approval limit.")
    return PolicyDecision(allowed=True, requires_approval=False, reason="Refund is within automatic approval limit.")
