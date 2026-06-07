---
name: personal-kb-llm-wiki
description: Use personal-kb-mcp from Hermes/Hermess, Claude Code, or Codex to maintain an Obsidian or Markdown LLM Wiki knowledge base. Trigger for vault, KB, wiki, Obsidian, research memory, and persistent note-writing tasks that should call the personal_kb or personal-kb MCP tools.
---

# Personal KB LLM Wiki

Use the running `personal-kb-mcp` server as the write/status bridge to a Git-backed Obsidian or Markdown vault, then maintain that vault with the LLM Wiki pattern: raw sources stay immutable, synthesized pages stay interlinked, and every durable change updates navigation and log files.

This is the single canonical skill for Hermes/Hermess, Claude Code, and Codex. The setup scripts copy this same skill into each agent's expected skill directory; only MCP config format, install path, and tool-name prefix differ by agent.

## When to use this skill

Use it when the user asks to use an Obsidian vault, Markdown KB, personal wiki, LLM Wiki, research memory, or `personal-kb-mcp` as persistent knowledge for an agent.

Do not use it for one-off answers that should not be saved, or when the MCP server is unavailable and the user only wants a normal chat answer.

## MCP tools exposed by this server

The underlying server exposes these tool names:

- `kb_write_note(note_path, content, if_hash?)` — write a complete note inside the configured vault. Existing notes require optimistic concurrency.
- `kb_vault_status()` — note count, vault existence, and basic vault status.
- `kb_graph_health()` — broken-link/orphan-style graph health snapshot.
- `kb_metrics()` — note/link/size metrics snapshot.

Agent UIs may prefix MCP tool names. If you see prefixed names, map them back to the raw tool names above.

## First actions in a session

1. Confirm the MCP server is connected by calling the status or metrics tool.
2. Orient before writing. If the vault is directly readable through file tools, read `SCHEMA.md`, `index.md`, and the recent tail of `log.md`. If the vault is not directly readable, use the status/health tools and ask the user for the relevant existing page content before updating existing notes.
3. Search for existing pages before creating new ones whenever the agent has file/search access to the vault. Avoid duplicate entity or concept pages.

## Write policy

- `kb_write_note` writes the full note body. For updates, reconstruct the full target file and pass the current full-file hash as `if_hash`.
- When updating from a previous MCP write result, use `content_hash` as the next `if_hash`, not `source_hash`.
- When updating from direct filesystem reads, compute SHA-256 over the exact current file text, including the provenance trailer.
- Keep raw sources under `raw/` immutable. Corrections and synthesis belong in wiki pages such as `entities/`, `concepts/`, `comparisons/`, or `queries/`.
- Every meaningful write should update `index.md` and append a concise entry to `log.md` unless the user explicitly requests a draft-only note.
- Use lowercase kebab-case note paths such as `concepts/llm-wiki.md` and `entities/anthropic.md`.
- Prefer `[[wikilinks]]` between wiki pages. New synthesized pages should have at least two useful outbound links when possible.
- Preserve YAML frontmatter on wiki pages: `title`, `created`, `updated`, `type`, `tags`, and `sources`.

## LLM Wiki page flow

1. Capture or identify the source material.
2. Decide whether it belongs in `raw/` as immutable source, a synthesized page, or both.
3. Check existing pages from `index.md` and direct search when available.
4. Create or update only the pages that meet the wiki schema thresholds.
5. Update navigation (`index.md`) and audit trail (`log.md`).
6. Report the exact note paths written and the returned hashes.

## Safety rules

- Do not invent existing vault contents. If you cannot read a page, say so and ask for it or create a clearly named draft note instead of overwriting.
- Do not hard-delete notes through this workflow.
- Treat the MCP endpoint as local by default: `http://127.0.0.1:9999/mcp`.
- If the server later enables bearer auth, add the authorization header in the agent MCP config before using write tools.

## Agent-specific MCP names

### Hermes/Hermess

Hermes prefixes native MCP tools as `mcp_<server>_<tool>`. With the default `personal_kb` server name, look for:

- `mcp_personal_kb_kb_write_note`
- `mcp_personal_kb_kb_vault_status`
- `mcp_personal_kb_kb_graph_health`
- `mcp_personal_kb_kb_metrics`

If these tools do not appear, run `hermes mcp list`, `hermes mcp test personal_kb`, then restart the Hermes session or gateway. In an existing session, use `/reload-mcp` if available.

### Claude Code

Claude Code usually displays MCP tools with a server namespace such as `mcp__personal-kb__kb_write_note`. With the default setup, look for the `personal-kb` MCP server in `/mcp` or `claude mcp list`.

If project-scoped `.mcp.json` is used, Claude may ask you to approve the server the first time it sees the project. Approve only after confirming the endpoint is the expected local URL.

### Codex

Codex reads this skill from `.agents/skills` or `$HOME/.agents/skills`. The default MCP server id is `personal_kb`; check Codex MCP startup/status output if the tools are not visible.

When adding this as a repo skill, place it under `.agents/skills/personal-kb-llm-wiki/`. When adding it for one user across all repos, place it under `$HOME/.agents/skills/personal-kb-llm-wiki/`.
