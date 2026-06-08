from dataclasses import asdict
from typing import Any, Literal, cast

from mcp.server.fastmcp import FastMCP

from personal_kb_mcp.config import Settings
from personal_kb_mcp.runtime import create_runtime
from personal_kb_mcp.vault.search import search_notes
from personal_kb_mcp.writes.writer import VaultWriter

McpLogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def create_mcp_server(settings: Settings, writer: VaultWriter | None = None) -> FastMCP[Any]:
    resolved_writer = writer or create_runtime(settings).writer
    server = FastMCP(
        "personal-kb-mcp",
        host=settings.host,
        port=settings.port,
        streamable_http_path=settings.mcp_path,
        log_level=cast(McpLogLevel, settings.log_level.upper()),
    )

    @server.tool(
        description=(
            "Write a complete Markdown note inside the configured vault. "
            "Existing notes require the current content_hash as if_hash so agents do not "
            "overwrite a newer wiki revision by accident."
        )
    )
    async def kb_write_note(
        note_path: str,
        content: str,
        if_hash: str | None = None,
    ) -> dict[str, str | None]:
        result = await resolved_writer.write_note(note_path, content, if_hash=if_hash)
        return {
            "path": result.path.as_posix(),
            "source_hash": result.source_hash,
            "content_hash": result.content_hash,
            "commit_hash": result.commit_hash,
        }

    @server.tool(
        description=(
            "Search Markdown notes in the configured LLM Wiki vault. Returns ranked note "
            "paths, titles, page types, tags, content_hash values for safe follow-up writes, "
            "and line snippets from matching wiki pages."
        )
    )
    def kb_search_notes(
        query: str,
        limit: int = 10,
        path_prefix: str | None = None,
    ) -> dict[str, Any]:
        results = search_notes(
            settings.vault_path,
            query,
            limit=limit,
            path_prefix=path_prefix,
        )
        return {
            "query": query,
            "count": len(results),
            "results": [asdict(result) for result in results],
        }

    return server
