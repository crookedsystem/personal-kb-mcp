from pathlib import Path

from pytest import MonkeyPatch

from personal_kb_mcp import main as main_module
from personal_kb_mcp.config import Settings


class FakeServer:
    def __init__(self) -> None:
        self.transport: str | None = None

    def run(self, transport: str) -> None:
        self.transport = transport


def test_run_server_starts_streamable_http_transport(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_server = FakeServer()

    def fake_create_mcp_server(settings: Settings) -> FakeServer:
        assert settings.port == 9999
        return fake_server

    monkeypatch.setattr(main_module, "create_mcp_server", fake_create_mcp_server)

    main_module.run_server(Settings(vault_path=tmp_path / "vault"))

    assert fake_server.transport == "streamable-http"
