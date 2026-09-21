from dataclasses import dataclass

class ProviderTimeoutAfterEffect(Exception): pass

@dataclass
class Payment:
    payment_id:str; order_id:str; amount:float; currency:str; status:str="paid"; refundable:bool=True

class MockPaymentProvider:
    def __init__(self):
        self.payments={"1001":Payment("pay_1001","1001",45.0,"USD"),"1002":Payment("pay_1002","1002",800.0,"USD")}
        self.refunds={}; self.refund_calls=0; self.timeout_after_effect=False

    def get_payment(self,order_id):
        return self.payments.get(order_id)

    def refund(self,payment_id,amount,reason):
        self.refund_calls+=1
        for r in self.refunds.values():
            if r["payment_id"]==payment_id and r["amount"]==amount: return r
        r={"refund_id":f"re_{len(self.refunds)+1:04d}","payment_id":payment_id,"amount":amount,"currency":"USD","status":"succeeded","reason":reason}
        self.refunds[r["refund_id"]]=r
        if self.timeout_after_effect:
            self.timeout_after_effect=False
            raise ProviderTimeoutAfterEffect("Provider timed out after applying refund.")
        return r

    def get_refund(self,payment_id,amount):
        return next((r for r in self.refunds.values() if r["payment_id"]==payment_id and r["amount"]==amount),None)
