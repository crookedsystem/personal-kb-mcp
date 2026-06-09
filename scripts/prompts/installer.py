"""Content templates rendered by the hook installer.

`HOOK_SCRIPT_TEMPLATE` is the generated bash wrapper; `HOOKS_README_TEMPLATE` is
the operator-facing README. Both use `.format` placeholders for runtime values.
Literal shell braces are escaped as `{{` / `}}`.
"""

from __future__ import annotations

from typing import Final

HOOK_SCRIPT_TEMPLATE: Final = """#!/usr/bin/env bash
set -euo pipefail

if [ -z "${{LLM_WIKI_MCP_SERVER_NAME:-}}" ]; then
  LLM_WIKI_MCP_SERVER_NAME={server_name}
fi
if [ -z "${{LLM_WIKI_MCP_URL:-}}" ]; then
  LLM_WIKI_MCP_URL={server_url}
fi
export LLM_WIKI_MCP_SERVER_NAME LLM_WIKI_MCP_URL

exec uv --project {repo_root} run python {helper} {mode} \\
  --server-name "$LLM_WIKI_MCP_SERVER_NAME" \\
  --server-url "$LLM_WIKI_MCP_URL"{extra} "$@"
"""

HOOKS_README_TEMPLATE: Final = """# LLM Wiki agent hooks

Installed by `uv run python scripts/main.py --agent {agent}` from:

`{repo_root}`

## Commands

- User input context loader: `{context_hook}`
- Stop/update enforcer: `{stop_hook}`

The context hook queries `{server_name}` at `{server_url}` with `kb_search_notes`
and prints a compact orientation block.

The stop hook asks the agent to run a final LLM Wiki update pass through MCP before it finishes.
It should write only durable facts/decisions/procedures, update `index.md`/`log.md` when
content changes, and use `content_hash` as `if_hash` for safe updates.

Claude Code user-level setup is merged into `{claude_settings_path}` when `--agent claude`
is used. Hermes/Hermess and Codex do not share Claude's JSON hook schema; wire these scripts into
the client's native hook/plugin/wrapper mechanism when available.
"""
