from .models import PolicyDecision
AUTO_REFUND_LIMIT=100.0

def check_refund_policy(*,amount:float,payment_status:str,refundable:bool)->PolicyDecision:
    if amount<=0: return PolicyDecision(False,False,"Refund amount must be positive.")
    if payment_status!="paid": return PolicyDecision(False,False,"Payment is not in a refundable paid state.")
    if not refundable: return PolicyDecision(False,False,"Payment is not refundable.")
    if amount>AUTO_REFUND_LIMIT:
        return PolicyDecision(True,True,"Amount exceeds automatic approval limit.")
    return PolicyDecision(True,False,"Refund is within automatic approval limit.")
