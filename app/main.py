from fastapi import FastAPI,HTTPException
from fastapi.responses import HTMLResponse
from .models import ApprovalDecision,Request,RequestSubmission
from .workflow import ControlledRouter

app=FastAPI(title="Controlled AI Request → Action Router")
router=ControlledRouter()

@app.get("/",response_class=HTMLResponse)
def home():
    return """<!doctype html><title>Controlled AI Router</title><h1>Controlled AI Request → Action Router</h1><p>POST a request to /requests. High-value refunds return PENDING_APPROVAL.</p>"""

@app.post("/requests")
async def submit_request(payload:RequestSubmission):
    return (await router.submit(Request(**payload.model_dump()))).model_dump()

@app.post("/operations/{operation_id}/approval")
def approve_operation(operation_id:str,decision:ApprovalDecision):
    try:return router.approve(operation_id,decision.approve).model_dump()
    except KeyError:raise HTTPException(404,"Operation not found")
    except ValueError as exc:raise HTTPException(409,str(exc))

@app.post("/operations/{operation_id}/reconcile")
def reconcile(operation_id:str):
    try:return router.reconcile(operation_id).model_dump()
    except KeyError:raise HTTPException(404,"Operation not found")

@app.get("/operations/{operation_id}/evidence")
def evidence(operation_id:str):
    if not router.store.get_operation(operation_id): raise HTTPException(404,"Operation not found")
    return [x.model_dump() for x in router.store.list_evidence(operation_id)]
