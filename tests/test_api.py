from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_home_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "Controlled AI Request" in response.text
    assert "SUBMIT REQUEST" in response.text


def test_http_small_refund_completes():
    response = client.post(
        "/requests",
        json={"request_id": "http-1", "raw_text": "I want to refund order #1001."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    operation_id = data["operation_id"]

    evidence = client.get(f"/operations/{operation_id}/evidence")
    assert evidence.status_code == 200
    types = [item["type"] for item in evidence.json()]
    assert "REQUEST" in types
    assert "ANALYSIS" in types
    assert "POLICY_DECISION" in types
    assert "EXTERNAL_RESULT" in types
    assert "VERIFICATION" in types


def test_http_large_refund_approval_and_rejection():
    response = client.post(
        "/requests",
        json={"request_id": "http-2", "raw_text": "Please refund order #1002 for $800."},
    )
    assert response.status_code == 200
    operation_id = response.json()["operation_id"]

    approval_page = client.get(f"/operations/{operation_id}/approval")
    assert approval_page.status_code == 200
    assert "ACTION REQUIRES APPROVAL" in approval_page.text

    rejected = client.post(
        f"/operations/{operation_id}/approval",
        json={"approve": False},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"

    evidence = client.get(f"/operations/{operation_id}/evidence")
    assert evidence.status_code == 200
    assert any(item["type"] == "APPROVAL" for item in evidence.json())


def test_http_large_refund_approval_and_approval_executes():
    response = client.post(
        "/requests",
        json={"request_id": "http-3", "raw_text": "Please refund order #1002 for $800."},
    )
    assert response.status_code == 200
    operation_id = response.json()["operation_id"]
    approval_page = client.get(f"/operations/{operation_id}/approval")
    assert approval_page.status_code == 200
    assert "APPROVE" in approval_page.text

    approved = client.post(
        f"/operations/{operation_id}/approval",
        json={"approve": True},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "COMPLETED"

    evidence = client.get(f"/operations/{operation_id}/evidence")
    assert evidence.status_code == 200
    types = [item["type"] for item in evidence.json()]
    assert "APPROVAL" in types
    assert "VERIFICATION" in types


def test_http_missing_operation_returns_404():
    response = client.get("/operations/op_does_not_exist/evidence")
    assert response.status_code == 404
