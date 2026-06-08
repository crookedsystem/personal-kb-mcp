from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from personal_kb_mcp.config import Settings
from personal_kb_mcp.runtime import create_runtime
from personal_kb_mcp.status.health import inspect_vault
from personal_kb_mcp.transport.errors import register_error_handlers
from personal_kb_mcp.transport.mcp_server import create_mcp_server


class ToolDocument(BaseModel):
    name: str
    description: str | None
    inputSchema: dict[str, Any]
    outputSchema: dict[str, Any] | None


class MetricsDocument(BaseModel):
    vault_notes_total: int
    vault_bytes_total: int
    graph_links_total: int
    graph_broken_links_total: int
    graph_orphans_total: int


def create_fastapi_app(settings: Settings) -> FastAPI:
    runtime = create_runtime(settings)
    mcp_server = create_mcp_server(settings, writer=runtime.writer)
    mcp_app = mcp_server.streamable_http_app()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _ = app
        async with mcp_server.session_manager.run():
            yield

    app = FastAPI(title="personal-kb-mcp", lifespan=lifespan)
    register_error_handlers(app)
    app.state.runtime = runtime

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mcp_path": settings.mcp_path}

    @app.get("/metrics", response_model=MetricsDocument)
    def metrics() -> MetricsDocument:
        return MetricsDocument(**asdict(inspect_vault(settings.vault_path).metrics))

    @app.get("/tools", response_model=list[ToolDocument])
    async def tools() -> list[ToolDocument]:
        mcp_tools = await mcp_server.list_tools()
        return [
            ToolDocument(
                name=tool.name,
                description=tool.description,
                inputSchema=tool.inputSchema,
                outputSchema=tool.outputSchema,
            )
            for tool in mcp_tools
        ]

    app.router.routes.extend(mcp_app.routes)
    return app
