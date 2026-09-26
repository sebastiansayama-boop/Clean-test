import pytest
from fastapi.testclient import TestClient

import lead_ops.main as main
from lead_ops.models import LeadAnalysis, LeadClass
from lead_ops.service import LeadStore


class FakeAnalyzer:
    async def analyze(self, message):
        return LeadAnalysis(
            classification=LeadClass.LEAD,
            email=message.sender,
            company="Acme",
            request=message.body,
            estimated_value=4000,
            confidence=0.94,
            reason="Commercial request",
        )


@pytest.fixture
def client(tmp_path):
    main.store = LeadStore(db_path=str(tmp_path / "saas.sqlite"))
    main.analyzer = FakeAnalyzer()
    return TestClient(main.app)


def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_processes_message_and_persists_result(client):
    response = client.post(
        "/api/runs",
        json={
            "source_id": "web-1",
            "sender": "buyer@example.com",
            "subject": "Pricing",
            "body": "Please send pricing for 25 seats.",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["actions"][0]["type"] == "CREATE_LEAD"

    leads = client.get("/api/leads")
    assert leads.status_code == 200
    assert len(leads.json()) == 1

    runs = client.get("/api/runs")
    assert runs.status_code == 200
    assert runs.json()[0]["run_id"] == data["run_id"]


def test_webhook_requires_key(client, monkeypatch):
    monkeypatch.setattr(main, "WEBHOOK_KEY", "secret")
    payload = {
        "source_id": "webhook-1",
        "sender": "buyer@example.com",
        "subject": "Quote",
        "body": "Please send a quote.",
    }

    denied = client.post("/webhooks/incoming", json=payload)
    assert denied.status_code == 401

    allowed = client.post(
        "/webhooks/incoming",
        json=payload,
        headers={"x-webhook-key": "secret"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["actions"][0]["type"] == "CREATE_LEAD"
