from pathlib import Path

from starlette.testclient import TestClient

from personal_kb_mcp.config import Settings
from personal_kb_mcp.transport.fastapi_app import create_fastapi_app


def test_fastapi_app_exposes_health_and_mounts_mcp(tmp_path: Path) -> None:
    app = create_fastapi_app(Settings(vault_path=tmp_path / "vault"))

    with TestClient(app, base_url="http://127.0.0.1:9999") as client:
        health_response = client.get("/healthz")
        mcp_response = client.get("/mcp")

    assert health_response.status_code == 200
    assert health_response.json() == {
        "status": "ok",
        "mcp_path": "/mcp",
    }
    assert mcp_response.status_code == 406
    assert "Client must accept text/event-stream" in mcp_response.text
