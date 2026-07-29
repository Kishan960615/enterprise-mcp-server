from fastapi.testclient import TestClient

from enterprise_mcp.app import create_app
from enterprise_mcp.settings import Settings


def test_health_capabilities_and_audit(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/live").json() == {"status": "alive"}
        assert client.get("/health/ready").status_code == 200
        capabilities = client.get("/api/v1/capabilities")
        assert capabilities.status_code == 200
        assert any(
            item["name"] == "knowledge.search" for item in capabilities.json()["capabilities"]
        )
        audit = client.get("/api/v1/audit/events")
        assert audit.status_code == 200


def test_mcp_endpoint_accepts_protocol_request(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/mcp/",
            headers={"accept": "application/json, text/event-stream"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0"},
                },
            },
        )
        assert response.status_code == 200
        assert "enterprise" in response.text.lower()
