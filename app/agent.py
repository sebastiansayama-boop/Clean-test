import os,re
from agents import Agent,Runner
from .models import RequestAnalysis

def build_agent():
    return Agent(name="Controlled Request Analyst",
        instructions="Analyze a customer request for a controlled refund workflow. Extract facts, order ID and amount. Never execute a refund. Return a concise operator-facing reasoning_summary, not hidden chain-of-thought.",
        output_type=RequestAnalysis)

async def analyze_request(text):
    if not os.getenv("OPENAI_API_KEY"): return fallback_analysis(text)
    return (await Runner.run(build_agent(),text)).final_output

def fallback_analysis(text):
    lower=text.lower()
    order=re.search(r"(?:order|заказ)\s*#?([A-Za-z0-9_-]+)",text,re.I)
    amount=re.search(r"\$(\d+(?:\.\d+)?)",text)
    refund=any(x in lower for x in ("refund","возврат","вернуть"))
    return RequestAnalysis(intent="refund_request" if refund else "unknown",
      confidence=.85 if refund else .2,order_id=order.group(1) if order else None,
      requested_amount=float(amount.group(1)) if amount else None,
      requested_action="refund" if refund else "unknown",
      missing_information=[] if order else ["order_id"],
      reasoning_summary="Deterministic demo parser used because OPENAI_API_KEY is not configured.")
