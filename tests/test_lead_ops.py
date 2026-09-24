from lead_ops.models import BusinessRules, IncomingMessage, LeadClass
from lead_ops.service import LeadStore, process_message

def test_qualified_lead_is_created():
    store = LeadStore()
    result = process_message(IncomingMessage(source_id="1", sender="a@example.com", subject="Demo", body="We need pricing for a $4,000 service."), BusinessRules(), store)
    assert result.status == "COMPLETED"
    assert result.analysis.classification is LeadClass.LEAD
    assert result.actions[0]["type"] == "CREATE_LEAD"
    assert len(store.leads) == 1

def test_unclear_requires_review():
    result = process_message(IncomingMessage(source_id="2", sender="a@example.com", subject="Hello", body="Can you tell me more?"), BusinessRules(), LeadStore())
    assert result.status == "PENDING_REVIEW"
    assert result.actions[0]["type"] == "HUMAN_REVIEW"

def test_spam_creates_no_lead():
    store = LeadStore()
    result = process_message(IncomingMessage(source_id="3", sender="spam@example.com", subject="SEO backlinks", body="Casino backlinks offer"), BusinessRules(), store)
    assert result.analysis.classification is LeadClass.SPAM
    assert len(store.leads) == 0
