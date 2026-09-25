import os

from agents import Agent, Runner
from .models import IncomingMessage, LeadAnalysis


LEAD_ANALYSIS_INSTRUCTIONS = """
You classify incoming business messages for a small-business lead operations workflow.

Return only the structured LeadAnalysis object.

Rules:
- classification must be exactly one of: lead, spam, unclear.
- lead means there is credible commercial intent such as asking for pricing, a quote,
  demo, proposal, purchase, service, or enterprise offering.
- spam means the message is clearly unsolicited/promotional junk or unrelated bulk spam.
- unclear means there is not enough evidence to classify it as a lead or spam.
- Extract the sender email from the supplied sender field.
- Extract a company only when the message provides reasonable evidence for it.
- Extract the customer's concrete request when possible.
- Extract an estimated monetary value only when the message provides one; otherwise null.
- confidence must be between 0 and 1 and reflect the evidence in the message.
- reason must briefly explain the classification using evidence from the message.
- Do not invent names, companies, values, or requests.
"""


class OpenAILeadAnalyzer:
    """Production LLM adapter for lead analysis."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("LEAD_OPS_MODEL", "gpt-5.6-luna")
        self.agent = Agent(
            name="Lead Analyzer",
            instructions=LEAD_ANALYSIS_INSTRUCTIONS,
            model=self.model,
            output_type=LeadAnalysis,
        )

    async def analyze(self, message: IncomingMessage) -> LeadAnalysis:
        prompt = (
            f"Sender: {message.sender}\n"
            f"Subject: {message.subject}\n"
            f"Body:\n{message.body}"
        )
        result = await Runner.run(self.agent, prompt, max_turns=1)
        return result.final_output_as(LeadAnalysis, raise_if_incorrect_type=True)
