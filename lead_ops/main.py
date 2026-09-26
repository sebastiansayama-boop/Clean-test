from fastapi import FastAPI, HTTPException
from .models import BusinessRules, IncomingMessage
from .service import LeadStore, process_message

app = FastAPI(title="Lead Operations MVP")
store = LeadStore()
rules = BusinessRules()

@app.get("/")
def home():
    return {"product": "Lead Operations MVP", "workflow": "input -> analyze -> rules -> action -> evidence", "status": "development"}

@app.post("/runs")
def create_run(message: IncomingMessage):
    return process_message(message, rules, store).model_dump()

@app.get("/runs/{run_id}")
def get_run(run_id: str):
    result = store.runs.get(run_id)
    if not result:
        raise HTTPException(404, "run_not_found")
    return result.model_dump()

@app.get("/leads")
def list_leads():
    return store.leads
