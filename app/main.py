from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from .models import ApprovalDecision, Request, RequestSubmission
from .workflow import ControlledRouter

app = FastAPI(title="Controlled AI Request → Action Router")
router = ControlledRouter()


@app.get("/", response_class=HTMLResponse)
def home():
    return """<!doctype html>
<title>Controlled AI Router</title>
<h1>Controlled AI Request → Action Router</h1>
<p>Submit a customer request. The router will analyze it, apply policy, execute safe actions, or pause for human approval.</p>
<form id="request-form">
  <label>Request<br><textarea id="raw_text" rows="4" cols="60" required>I want to cancel order #1002 and get a refund of $800.</textarea></label><br><br>
  <label>Request ID <input id="request_id" required></label>
  <button type="submit">SUBMIT REQUEST</button>
</form>
<pre id="result"></pre>
<script>
document.getElementById("request_id").value = "browser-" + Date.now();
document.getElementById('request-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const result = document.getElementById('result');
  const response = await fetch('/requests', {
    method: 'POST',
    headers: {'content-type': 'application/json'},
    body: JSON.stringify({
      request_id: document.getElementById('request_id').value,
      raw_text: document.getElementById('raw_text').value
    })
  });
  const data = await response.json();
  result.textContent = JSON.stringify(data, null, 2);
  if (data.status === 'PENDING_APPROVAL') {
    result.innerHTML += '\n\nApproval: ';
    const link = document.createElement('a');
    link.href = '/operations/' + data.operation_id + '/approval';
    link.textContent = 'OPEN APPROVAL';
    result.appendChild(link);
  }
});
</script>"""


@app.post("/requests")
async def submit_request(payload: RequestSubmission):
    return (await router.submit(Request(**payload.model_dump()))).model_dump()


@app.get("/operations/{operation_id}/approval", response_class=HTMLResponse)
def approval_page(operation_id: str):
    op = router.store.get_operation(operation_id)
    if not op:
        raise HTTPException(404, "Operation not found")
    if op.status.value != "PENDING_APPROVAL":
        return HTMLResponse(
            "<h1>Operation " + operation_id + "</h1><p>Status: " + op.status.value + "</p>"
        )
    amount = op.arguments.get("amount", "unknown")
    return HTMLResponse(
        "<!doctype html><title>Approval</title><h1>ACTION REQUIRES APPROVAL</h1>"
        "<p><b>Operation:</b> " + operation_id + "</p>"
        "<p><b>Resource:</b> " + op.resource + "</p>"
        "<p><b>Action:</b> Refund</p><p><b>Amount:</b> $" + str(amount) + "</p>"
        "<p><b>Reason:</b> Customer request</p>"
        "<button onclick=\"decide(true)\">APPROVE</button> "
        "<button onclick=\"decide(false)\">REJECT</button><pre id=\"result\"></pre>"
        "<script>async function decide(approve){const r=await fetch('/operations/" + operation_id + "/approval',"
        "{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({approve:approve})});"
        "document.getElementById('result').textContent=await r.text();}</script>"
    )


@app.post("/operations/{operation_id}/approval")
def approve_operation(operation_id: str, decision: ApprovalDecision):
    try:
        return router.approve(operation_id, decision.approve).model_dump()
    except KeyError:
        raise HTTPException(404, "Operation not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.post("/operations/{operation_id}/reconcile")
def reconcile(operation_id: str):
    try:
        return router.reconcile(operation_id).model_dump()
    except KeyError:
        raise HTTPException(404, "Operation not found")


@app.get("/operations/{operation_id}/evidence")
def evidence(operation_id: str):
    if not router.store.get_operation(operation_id):
        raise HTTPException(404, "Operation not found")
    return [x.model_dump() for x in router.store.list_evidence(operation_id)]
