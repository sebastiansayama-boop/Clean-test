from uuid import uuid4
from .agent import analyze_request
from .models import Evidence,Operation,OperationStatus,Request,now_iso
from .policy import check_refund_policy
from .adapters.mock_payment import MockPaymentProvider,ProviderTimeoutAfterEffect
from .storage.sqlite import SQLiteStore

class ControlledRouter:
    def __init__(self,store=None,provider=None):
        self.store=store or SQLiteStore(); self.provider=provider or MockPaymentProvider()

    async def submit(self,request:Request):
        analysis=await analyze_request(request.raw_text)
        op=Operation(operation_id="op_"+uuid4().hex[:12],request_id=request.request_id,
          action=analysis.requested_action,resource="order:"+(analysis.order_id or "unknown"),
          status=OperationStatus.ANALYZING)
        self._evidence(op,"REQUEST","request",request.model_dump()); self._evidence(op,"ANALYSIS","agent",analysis.model_dump())
        if analysis.requested_action!="refund" or not analysis.order_id:
            return self._finish(op,OperationStatus.FAILED,"Unsupported or incomplete request.")
        payment=self.provider.get_payment(analysis.order_id)
        op.status=OperationStatus.VALIDATING; self._save(op)
        if not payment: return self._finish(op,OperationStatus.FAILED,"Order/payment not found.")
        amount=analysis.requested_amount or payment.amount
        decision=check_refund_policy(amount=amount,payment_amount=payment.amount,payment_status=payment.status,refundable=payment.refundable)
        op.authorization="allowed" if decision.allowed else "denied"; op.arguments={"amount":amount,"payment_id":payment.payment_id,"reason":"Customer request"}
        self._evidence(op,"POLICY_DECISION","policy",decision.model_dump()); self._save(op)
        if not decision.allowed: return self._finish(op,OperationStatus.FAILED,decision.reason)
        if decision.requires_approval:
            op.status=OperationStatus.PENDING_APPROVAL; self._save(op); return op
        return self._execute(op,payment.payment_id,amount)

    def approve(self,oid,approve):
        op=self.store.get_operation(oid)
        if not op: raise KeyError(oid)
        if op.status!=OperationStatus.PENDING_APPROVAL: raise ValueError("Operation is not pending approval.")
        op.approval="approved" if approve else "rejected"; self._evidence(op,"APPROVAL","human",{"approve":approve})
        if not approve: return self._finish(op,OperationStatus.REJECTED,"Human approval rejected the external effect.")
        op.status=OperationStatus.APPROVED; self._save(op)
        return self._execute(op,op.arguments["payment_id"],op.arguments["amount"])

    def reconcile(self,oid):
        op=self.store.get_operation(oid)
        if not op: raise KeyError(oid)
        if op.status!=OperationStatus.UNKNOWN: return op
        op.status=OperationStatus.RECONCILING; self._save(op)
        refund=self.provider.get_refund(op.arguments["payment_id"],op.arguments["amount"])
        self._evidence(op,"RECONCILIATION","provider",{"found":bool(refund),"refund":refund})
        if refund:
            op.external_reference=refund["refund_id"]; op.result=refund
            return self._finish(op,OperationStatus.COMPLETED,"Reconciliation confirmed the external effect.")
        return self._finish(op,OperationStatus.UNKNOWN,"External outcome remains unresolved.")

    def _execute(self,op,payment_id,amount):
        op.status=OperationStatus.EXECUTING; self._save(op)
        try: result=self.provider.refund(payment_id,amount,"Customer request")
        except ProviderTimeoutAfterEffect as exc:
            op.status=OperationStatus.UNKNOWN; op.result={"error":str(exc)}
            self._evidence(op,"EXTERNAL_RESULT","provider",{"status":"unknown_after_timeout"}); self._save(op); return op
        op.status=OperationStatus.VERIFYING; op.external_reference=result["refund_id"]; op.result=result
        self._evidence(op,"EXTERNAL_RESULT","provider",result)
        verified=self.provider.get_refund(payment_id,amount)
        self._evidence(op,"VERIFICATION","provider",{"verified":bool(verified),"refund":verified})
        if not verified: return self._finish(op,OperationStatus.UNKNOWN,"Verification did not confirm the effect.")
        return self._finish(op,OperationStatus.COMPLETED,"Refund verified.")

    def _save(self,op):
        op.updated_at=now_iso(); self.store.save_operation(op)
    def _evidence(self,op,kind,source,data):
        self.store.add_evidence(Evidence(evidence_id="ev_"+uuid4().hex[:12],operation_id=op.operation_id,type=kind,source=source,data=data))
    def _finish(self,op,status,message):
        op.status=status; op.result={**(op.result or {}),"message":message}; self._save(op); return op
