from personal_kb_mcp.config import Settings
from personal_kb_mcp.transport.mcp_server import create_mcp_server


def run_server(settings: Settings | None = None) -> None:
    resolved_settings = settings or Settings()
    server = create_mcp_server(resolved_settings)
    server.run(transport="streamable-http")


if __name__ == "__main__":
    run_server()
