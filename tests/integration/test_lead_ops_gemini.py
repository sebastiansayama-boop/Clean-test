import asyncio
import os
import time

import pytest

from lead_ops.gemini import GeminiLeadAnalyzer
from lead_ops.models import IncomingMessage, LeadClass


pytestmark = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY is required for the real-provider integration test",
)


CONTROL_MESSAGES = [
    (
        "lead",
        IncomingMessage(
            source_id="control-lead-001",
            sender="anna@acme.example",
            subject="Request for a quote",
            body="Hi, we need a quote for 25 seats of your service for our team. Can you send pricing?",
        ),
    ),
    (
        "spam",
        IncomingMessage(
            source_id="control-spam-001",
            sender="promo@bulk.example",
            subject="BUY NOW!!!",
            body="Huge discount on unrelated products. Click this link and buy today. This message was sent in bulk.",
        ),
    ),
    (
        "unclear",
        IncomingMessage(
            source_id="control-unclear-001",
            sender="mike@example.com",
            subject="Question",
            body="Someone recommended your company to me. I wanted to ask a little more about what you do.",
        ),
    ),
]


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("expected_label,message", CONTROL_MESSAGES)
async def test_real_gemini_control_message(
    expected_label: str, message: IncomingMessage
) -> None:
    analyzer = GeminiLeadAnalyzer()
    started = time.perf_counter()
    analysis = await analyzer.analyze(message)
    latency_ms = (time.perf_counter() - started) * 1000

    print(
        f"RESULT source_id={message.source_id} "
        f"classification={analysis.classification.value} "
        f"confidence={analysis.confidence:.3f} "
        f"sender_email={analysis.sender_email!r} "
        f"company={analysis.company!r} "
        f"request={analysis.request!r} "
        f"estimated_value={analysis.estimated_value!r} "
        f"latency_ms={latency_ms:.0f} "
        f"reason={analysis.reason!r}"
    )

    assert analysis.classification in set(LeadClass)
    assert 0 <= analysis.confidence <= 1
    assert analysis.sender_email == message.sender
    assert analysis.reason

    expected = LeadClass(expected_label)
    assert analysis.classification == expected, (
        f"Expected {expected.value}, got {analysis.classification.value}. "
        f"Reason: {analysis.reason}"
    )


if __name__ == "__main__":
    asyncio.run(
        test_real_gemini_control_message("lead", CONTROL_MESSAGES[0][1])
    )
