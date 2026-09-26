import os

from google import genai
from google.genai import types

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


class GeminiLeadAnalyzer:
    """Production LLM adapter for Gemini structured-output analysis."""

    def __init__(self, model: str | None = None) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is required")

        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.client = genai.Client(api_key=api_key)

    async def analyze(self, message: IncomingMessage) -> LeadAnalysis:
        prompt = (
            f"Sender: {message.sender}\n"
            f"Subject: {message.subject}\n"
            f"Body:\n{message.body}"
        )
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=LEAD_ANALYSIS_INSTRUCTIONS,
                response_mime_type="application/json",
                response_schema=LeadAnalysis,
            ),
        )
        if not response.text:
            raise RuntimeError("Gemini returned an empty response")
        return LeadAnalysis.model_validate_json(response.text)
