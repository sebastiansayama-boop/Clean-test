from app.policy import check_refund_policy
def test_small_refund_auto():
    d=check_refund_policy(amount=45,payment_amount=45,payment_status="paid",refundable=True)
    assert d.allowed and not d.requires_approval
def test_large_refund_requires_approval():
    d=check_refund_policy(amount=800,payment_amount=800,payment_status="paid",refundable=True)
    assert d.allowed and d.requires_approval
def test_unpaid_denied():
    assert not check_refund_policy(amount=45,payment_amount=45,payment_status="pending",refundable=True).allowed
