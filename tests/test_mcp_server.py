import asyncio
from pathlib import Path
from typing import Any, cast

from personal_kb_mcp.config import Settings
from personal_kb_mcp.transport.mcp_server import create_mcp_server


def test_mcp_server는_기본_http_설정을_사용한다(tmp_path: Path) -> None:
    # Given: 기본 Settings로 MCP server를 생성한다.
    server = create_mcp_server(Settings(vault_path=tmp_path / "vault"))

    # When: FastMCP HTTP 설정을 조회한다.
    settings = server.settings

    # Then: local-only host, 기본 port, streamable HTTP path가 적용된다.
    assert settings.host == "127.0.0.1"
    assert settings.port == 9999
    assert settings.streamable_http_path == "/mcp"


def test_mcp_server는_핵심_tool을_등록하고_note를_작성한다(tmp_path: Path) -> None:
    async def exercise_server() -> None:
        # Given: 임시 vault를 바라보는 MCP server가 있다.
        server = create_mcp_server(Settings(vault_path=tmp_path / "vault"))

        # When: 등록된 tool 목록을 조회하고 write/status tool을 호출한다.
        tools = await server.list_tools()
        _, write_result = await server.call_tool(
            "kb_write_note",
            {"note_path": "daily/today.md", "content": "Body text"},
        )
        structured_write_result = cast(dict[str, Any], write_result)
        _, status_result = await server.call_tool("kb_vault_status", {})
        structured_status_result = cast(dict[str, Any], status_result)

        # Then: 핵심 tool이 노출되고 write 결과가 status에 반영된다.
        assert {tool.name for tool in tools} >= {
            "kb_write_note",
            "kb_vault_status",
            "kb_graph_health",
            "kb_metrics",
        }
        assert structured_write_result["source_hash"]
        assert structured_status_result["note_count"] == 1

    asyncio.run(exercise_server())
