from fastapi.testclient import TestClient
from incidentpilot import api, store


def test_investigation_requires_approval_and_rejects_replay(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATABASE_PATH", tmp_path / "journey.sqlite3")
    with TestClient(api.app) as client:
        result = client.post(
            "/api/incidents", json={"scenario": "payment-connection-pool"}
        )
        assert result.status_code == 200
        data = result.json()
        assert data["status"] == "awaiting_approval"
        assert data["state"]["approval"] is None
        assert data["state"]["reasoning"]["diagnostician"] == "classifier"
        assert not data["state"]["proposal"]["abstained"]
        decision = {"actor": "Test reviewer", "approved": False}
        assert (
            client.post(
                f"/api/incidents/{data['id']}/approval", json=decision
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/incidents/{data['id']}/approval", json=decision
            ).status_code
            == 409
        )
        assert len(client.get(f"/api/incidents/{data['id']}/trace").json()) >= 5
