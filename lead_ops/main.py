import hashlib
import hmac
import os
from html import escape

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .gemini import GeminiLeadAnalyzer
from .llm import OpenAILeadAnalyzer
from .models import BusinessRules, IncomingMessage
from .service import LeadStore, process_message_with_analyzer
from .postgres import PostgresLeadStore

APP_PASSWORD = os.getenv("APP_PASSWORD")
SESSION_SECRET = os.getenv("SESSION_SECRET") or APP_PASSWORD
WEBHOOK_KEY = os.getenv("WEBHOOK_KEY")
PROVIDER = os.getenv("LEAD_OPS_PROVIDER", "gemini").lower()
DB_PATH = os.getenv("LEAD_OPS_DB_PATH", "lead_ops.sqlite")

if os.getenv("DATABASE_URL"):
    store = PostgresLeadStore()
else:
    store = LeadStore(db_path=DB_PATH)

analyzer = None

def _get_analyzer():
    global analyzer
    if analyzer is not None:
        return analyzer
    if PROVIDER == "gemini":
        analyzer = GeminiLeadAnalyzer()
    elif PROVIDER == "openai":
        analyzer = OpenAILeadAnalyzer()
    else:
        raise RuntimeError("LEAD_OPS_PROVIDER must be 'gemini' or 'openai'")
    return analyzer

rules = BusinessRules(
    minimum_value=float(os.getenv("LEAD_MINIMUM_VALUE", "0")),
    require_company=os.getenv("LEAD_REQUIRE_COMPANY", "false").lower() == "true",
    auto_create_lead=True,
)

app = FastAPI(title="Lead Ops", version="0.2.0")


def _session_token() -> str:
    if not APP_PASSWORD or not SESSION_SECRET:
        return ""
    return hmac.new(
        SESSION_SECRET.encode(),
        b"lead-ops-session",
        hashlib.sha256,
    ).hexdigest()


def _authorized(request: Request) -> bool:
    if not APP_PASSWORD:
        return True
    return hmac.compare_digest(request.cookies.get("lead_ops_session", ""), _session_token())


def _require_auth(request: Request) -> None:
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="authentication_required")


def _dashboard() -> str:
    return """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lead Ops</title>
<style>
body{font-family:system-ui,-apple-system,sans-serif;max-width:1100px;margin:40px auto;padding:0 20px;color:#17202a;background:#f6f7f9}
.card{background:white;border:1px solid #ddd;border-radius:12px;padding:20px;margin:16px 0}
textarea,input{width:100%;box-sizing:border-box;padding:10px;margin:6px 0 14px;border:1px solid #ccc;border-radius:8px}
button{padding:10px 16px;border:0;border-radius:8px;cursor:pointer}
pre{white-space:pre-wrap;overflow:auto}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.badge{display:inline-block;padding:4px 8px;border-radius:999px;background:#eee}
@media(max-width:800px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<h1>Lead Ops</h1>
<p>Incoming message → AI analysis → business rules → action → evidence.</p>
<div class="grid">
<div class="card">
<h2>Process message</h2>
<form id="run">
<label>Sender</label><input id="sender" value="buyer@example.com" required>
<label>Subject</label><input id="subject" value="Request for pricing">
<label>Message</label><textarea id="body" rows="7" required>Please send pricing for 25 seats.</textarea>
<button>Process</button>
</form>
</div>
<div class="card">
<h2>Latest result</h2>
<pre id="result">No run yet.</pre>
</div>
</div>
<div class="card"><h2>Leads</h2><pre id="leads">Loading…</pre></div>
<div class="card"><h2>Recent runs</h2><pre id="runs">Loading…</pre></div>
<script>
async function load(){
 const [l,r]=await Promise.all([fetch('/api/leads'),fetch('/api/runs')]);
 document.getElementById('leads').textContent=JSON.stringify(await l.json(),null,2);
 document.getElementById('runs').textContent=JSON.stringify(await r.json(),null,2);
}
document.getElementById('run').addEventListener('submit',async e=>{
 e.preventDefault();
 const payload={source_id:'web-'+Date.now(),sender:sender.value,subject:subject.value,body:body.value};
 const r=await fetch('/api/runs',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});
 const data=await r.json();
 document.getElementById('result').textContent=JSON.stringify(data,null,2);
 await load();
});
load();
</script>
</body>
</html>"""


def _login_page(error: str = "") -> str:
    message = f"<p>{escape(error)}</p>" if error else ""
    return f"""<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lead Ops Login</title>
<style>body{{font-family:system-ui;max-width:420px;margin:80px auto;padding:20px}}input,button{{width:100%;padding:12px;margin:8px 0;box-sizing:border-box}}</style>
<h1>Lead Ops</h1><p>Sign in to your workspace.</p>{message}
<form id="login"><input id="password" type="password" placeholder="Password" required><button>Sign in</button></form>
<pre id="error"></pre>
<script>
document.getElementById('login').addEventListener('submit',async e=>{{
 e.preventDefault();
 const r=await fetch('/login',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{password:password.value}})}});
 if(r.ok) location.href='/'; else document.getElementById('error').textContent=await r.text();
}});
</script>"""


@app.get("/health")
def health():
    return {"status": "ok", "provider": PROVIDER, "database": "postgres" if os.getenv("DATABASE_URL") else "sqlite"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if not _authorized(request):
        return HTMLResponse(_login_page(), status_code=401)
    return HTMLResponse(_dashboard())


@app.post("/login")
async def login(request: Request):
    if not APP_PASSWORD:
        return {"authenticated": True, "auth_required": False}
    payload = await request.json()
    if not hmac.compare_digest(str(payload.get("password", "")), APP_PASSWORD):
        return JSONResponse({"error": "invalid_credentials"}, status_code=401)
    response = JSONResponse({"authenticated": True})
    response.set_cookie("lead_ops_session", _session_token(), httponly=True, samesite="lax", secure=False)
    return response


@app.post("/api/runs")
async def create_run(message: IncomingMessage, request: Request):
    _require_auth(request)
    result = await process_message_with_analyzer(message, rules, store, _get_analyzer())
    return result.model_dump()


@app.get("/api/runs")
def list_runs(request: Request):
    _require_auth(request)
    return [run.model_dump() for run in store.list_runs()]


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, request: Request):
    _require_auth(request)
    try:
        return store.get_run(run_id).model_dump()
    except KeyError:
        raise HTTPException(404, "run_not_found")


@app.get("/api/leads")
def list_leads(request: Request):
    _require_auth(request)
    return store.leads


@app.post("/webhooks/incoming")
async def incoming_webhook(
    message: IncomingMessage,
    x_webhook_key: str | None = Header(default=None),
):
    if not WEBHOOK_KEY or not x_webhook_key or not hmac.compare_digest(x_webhook_key, WEBHOOK_KEY):
        raise HTTPException(status_code=401, detail="invalid_webhook_key")
    result = await process_message_with_analyzer(message, rules, store, analyzer)
    return result.model_dump()
