import pytest

from agents import Agent
from agents.testing import ScriptedModel, assistant_message

from lead_ops.llm import OpenAILeadAnalyzer
from lead_ops.models import BusinessRules, IncomingMessage, LeadAnalysis, LeadClass
from lead_ops.service import LeadStore, process_message, process_message_with_analyzer


def test_qualified_lead_is_created():
    store = LeadStore()
    result = process_message(
        IncomingMessage(
            source_id="1",
            sender="a@example.com",
            subject="Demo",
            body="We need pricing for a $4,000 service.",
        ),
        BusinessRules(),
        store,
    )
    assert result.status == "COMPLETED"
    assert result.analysis.classification is LeadClass.LEAD
    assert result.actions[0]["type"] == "CREATE_LEAD"
    assert len(store.leads) == 1


def test_unclear_requires_review():
    result = process_message(
        IncomingMessage(
            source_id="2",
            sender="a@example.com",
            subject="Hello",
            body="Can you tell me more?",
        ),
        BusinessRules(),
        LeadStore(),
    )
    assert result.status == "PENDING_REVIEW"
    assert result.actions[0]["type"] == "HUMAN_REVIEW"


def test_spam_creates_no_lead():
    store = LeadStore()
    result = process_message(
        IncomingMessage(
            source_id="3",
            sender="spam@example.com",
            subject="SEO backlinks",
            body="Casino backlinks offer",
        ),
        BusinessRules(),
        store,
    )
    assert result.analysis.classification is LeadClass.SPAM
    assert len(store.leads) == 0


class FakeAnalyzer:
    async def analyze(self, message: IncomingMessage) -> LeadAnalysis:
        return LeadAnalysis(
            classification=LeadClass.LEAD,
            email=message.sender,
            company="Acme",
            request="pricing",
            estimated_value=4000,
            confidence=0.91,
            reason="Structured model classification",
        )


@pytest.mark.asyncio
async def test_llm_result_is_passed_to_deterministic_business_rules():
    store = LeadStore()
    result = await process_message_with_analyzer(
        IncomingMessage(
            source_id="4",
            sender="buyer@example.com",
            subject="Pricing",
            body="Please send pricing.",
        ),
        BusinessRules(minimum_value=5000),
        store,
        FakeAnalyzer(),
    )

    assert result.status == "PENDING_REVIEW"
    assert result.analysis.classification is LeadClass.UNCLEAR
    assert result.analysis.reason == "Below configured minimum value"
    assert len(store.leads) == 0


@pytest.mark.asyncio
async def test_openai_adapter_uses_structured_output_without_network():
    scripted = ScriptedModel(
        [[
            assistant_message(
                LeadAnalysis(
                    classification=LeadClass.LEAD,
                    email="buyer@example.com",
                    company="Acme",
                    request="pricing",
                    estimated_value=4000,
                    confidence=0.93,
                    reason="Customer requested pricing.",
                ).model_dump_json()
            )
        ]]
    )
    analyzer = OpenAILeadAnalyzer(model="test-model")
    analyzer.agent = Agent(
        name="Lead Analyzer",
        instructions="Return the supplied structured lead analysis.",
        model=scripted,
        output_type=LeadAnalysis,
    )

    result = await analyzer.analyze(
        IncomingMessage(
            source_id="5",
            sender="buyer@example.com",
            subject="Pricing",
            body="Please send pricing.",
        )
    )

    assert result.classification is LeadClass.LEAD
    assert result.email == "buyer@example.com"
    assert result.estimated_value == 4000
    scripted.assert_complete()
