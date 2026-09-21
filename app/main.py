from fastapi import FastAPI,HTTPException
from fastapi.responses import HTMLResponse
from .models import ApprovalDecision,Request,RequestSubmission
from .workflow import ControlledRouter

app=FastAPI(title="Controlled AI Request → Action Router")
router=ControlledRouter()

@app.get("/",response_class=HTMLResponse)
def home():
    return """<!doctype html><title>Controlled AI Router</title><h1>Controlled AI Request → Action Router</h1>
<p>Submit requests through <code>POST /requests</code>. High-value refunds return <code>PENDING_APPROVAL</code>.</p>
<p>For a pending operation open <code>/operations/{operation_id}/approval</code>.</p>"""

@app.post("/requests")
async def submit_request(payload:RequestSubmission):
    return (await router.submit(Request(**payload.model_dump()))).model_dump()

@app.get("/operations/{operation_id}/approval",response_class=HTMLResponse)
def approval_page(operation_id:str):
    op=router.store.get_operation(operation_id)
    if not op: raise HTTPException(404,"Operation not found")
    if op.status.value!="PENDING_APPROVAL":
        return HTMLResponse(f"<h1>Operation \{operation_id\}</h1><p>Status: \{op.status.value\}</p>")
    amount=op.arguments.get("amount","unknown")
    return f"""<!doctype html><title>Approval</title><h1>ACTION REQUIRES APPROVAL</h1>
<p><b>Operation:</b> \{operation_id\}</p><p><b>Resource:</b> \{op.resource\}</p>
<p><b>Action:</b> Refund</p><p><b>Amount:</b> $\{amount\}</p><p><b>Reason:</b> Customer request</p>
<button onclick="decide(true)">APPROVE</button> <button onclick="decide(false)">REJECT</button>
<pre id="result"></pre>
<script>
async function decide(approve) {{
 const r=await fetch("/operations/\{operation_id\}/approval",{{method:"POST",headers:{{"content-type":"application/json"}},body:JSON.stringify({{approve}})}});
 document.getElementById("result").textContent=await r.text();
}}
</script>"""

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
