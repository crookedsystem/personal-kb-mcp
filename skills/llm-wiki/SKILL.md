---
name: llm-wiki
description: "Use llm-wiki from Hermes/Hermess, Claude Code, or Codex to search, model, and maintain an Obsidian/Markdown LLM Wiki knowledge base. Trigger for vault, KB, wiki, Obsidian, research memory, persistent note-writing, MCP context-loading hooks, and end-of-task wiki update workflows."
---

# LLM Wiki

Use the running `llm-wiki` server as the write/search bridge to a Git-backed Obsidian or Markdown vault, then maintain that vault with the LLM Wiki pattern: raw sources stay immutable, synthesized pages stay interlinked, and every durable change updates navigation and log files.

This is the single canonical skill for Hermes/Hermess, Claude Code, and Codex. The setup scripts copy this same skill into each agent's expected skill directory; only MCP config format, install path, and tool-name prefix differ by agent.

## When to use this skill

Use it when the user asks to use an Obsidian vault, Markdown KB, personal wiki, LLM Wiki, research memory, or `llm-wiki` as persistent knowledge for an agent.

Do not use it for one-off answers that should not be saved, or when the MCP server is unavailable and the user only wants a normal chat answer.

## MCP tools exposed by this server

The underlying server exposes these tool names:

- `kb_write_note(note_path, content, if_hash?)` — write a complete note inside the configured vault. It enforces the vault schema before writing. Existing notes require optimistic concurrency.
- `kb_search_notes(query, limit?, path_prefix?)` — search the Markdown LLM Wiki vault and return ranked paths, titles, page types, tags, content hashes, and line snippets.
- `kb_wiki_context(recent_log_lines?, include_schema_rules?, include_index?)` — return the schema-first orientation bundle: `SCHEMA.md`, `index.md`, recent `log.md`, parsed allowed types/tags/frontmatter rules, and current schema health.
- `kb_validate_vault(include_raw?)` — validate deterministic schema hygiene across the vault: frontmatter, required fields, path/type consistency, tag taxonomy, raw metadata, and raw body hashes.
- `kb_reconcile_taxonomy(apply?, decisions?)` — dry-run or apply deterministic tag taxonomy repair. Use it for tag add/rename/remove decisions, not for content migration.

Vault and graph counters are exposed as a REST API endpoint at `GET /metrics`, not as MCP tools.
Agent UIs may prefix MCP tool names. If you see prefixed names, map them back to the raw tool names above.

## Vault operating model

Keep these folders conceptually separate:

- `llm-wiki` repository — server/application code such as `src/`, `tests/`, `scripts/`.
- `KB_VAULT_PATH` — the Markdown vault opened by Obsidian and read/written by MCP tools.

Inside `KB_VAULT_PATH`, use this structure:

```text
SCHEMA.md        # conventions, page thresholds, tag taxonomy
index.md         # navigational catalog of synthesized pages
log.md           # append-only audit trail
raw/             # immutable source material and assets
entities/        # people, orgs, products, models, projects, standards
concepts/        # ideas, techniques, mechanisms, topics, principles
comparisons/     # side-by-side analyses and decision records
queries/         # valuable answered questions worth preserving
```

`raw/` is source material. `entities/`, `concepts/`, `comparisons/`, and `queries/` are synthesized wiki pages owned by the agent.

## First actions in a session

1. Confirm the MCP server is connected by listing tools or calling `kb_wiki_context`.
2. Start every wiki task with `kb_wiki_context` when it is available. Treat the returned `parsed_schema` as the write contract, not as background documentation.
3. Use `parsed_schema.required_synthesized_frontmatter`, `parsed_schema.allowed_types`, and `parsed_schema.tag_taxonomy` before creating or updating pages. Do not invent page types or tags.
4. Check `index` and recent `log` from `kb_wiki_context` before creating a page. Update existing pages instead of duplicating them, and avoid repeating recent work.
5. If `health` reports schema errors, fix deterministic hygiene with `kb_validate_vault`/`kb_reconcile_taxonomy` before creating new synthesized content.
6. Search for existing topic pages with `kb_search_notes` before creating new ones. Avoid duplicate entity or concept pages.
7. Decide the access mode:
   - **File-readable mode:** safe to update existing notes because you can read the complete current file, reconstruct it, and pass the exact current `content_hash` as `if_hash`.
   - **MCP-only mode:** `kb_search_notes` returns snippets, not full note bodies. Do not overwrite an existing note from snippets alone. Create new notes only, or ask the user for the full current note content before updating.

## Content model and page types

Use the `type` frontmatter value to decide where a page belongs and how readers will browse it.

| Type | Directory | Use for | Do not use for |
| --- | --- | --- | --- |
| `entity` | `entities/` | People, companies, products, models, projects, protocols, datasets, standards, APIs | Broad ideas or techniques |
| `concept` | `concepts/` | Techniques, principles, mechanisms, topics, terms, recurring patterns | Named organizations/products unless the page is about the abstract idea |
| `comparison` | `comparisons/` | Tradeoff analysis, A-vs-B decisions, rankings, matrices, migration choices | Simple summaries of one thing |
| `query` | `queries/` | A substantial answered question, investigation, synthesis, or research result worth reusing | Trivial lookups or temporary chat answers |
| `summary` | Usually `concepts/` or `queries/` | Cross-cutting overview pages and topic maps | Pages that can be classified more specifically |

### Page creation thresholds

Create or update pages only when the content improves future retrieval:

- Create a new page when the entity/concept appears in 2+ sources, or is central to one important source.
- Update an existing page when new material changes, confirms, dates, or clarifies something already covered.
- Create a `comparison` page when the user is choosing between alternatives or the source compares alternatives on multiple dimensions.
- Create a `query` page when the answer is non-trivial enough that re-deriving it would waste time later.
- Do not create pages for passing mentions, minor side details, or out-of-domain material.
- Split pages that exceed about 200 lines into focused sub-pages and cross-link them.

### Required frontmatter

Every synthesized wiki page starts with YAML frontmatter:

```yaml
---
title: Page Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: entity | concept | comparison | query | summary
tags: [tag-from-schema]
sources: [raw/articles/source-file.md]
confidence: high | medium | low
contested: false
---
```

All listed fields are required for synthesized pages. `confidence` and `contested` are not optional: use `confidence: low` for single-source, speculative, or fast-moving claims, and use `contested: true` when sources conflict and explain the conflict in the body. `tags` must come from the current `SCHEMA.md` tag taxonomy. If a needed tag is missing, update `SCHEMA.md` first or ask the user.

### Page body pattern

Keep pages scannable. Prefer this shape unless the vault `SCHEMA.md` says otherwise:

```markdown
# Page Title

## Summary
One short paragraph explaining why this page matters.

## Key facts
- Dated, source-backed facts.
- Link important related pages with [[wikilinks]].

## Relationships
- [[related-page]] — why it matters.

## Open questions
- What remains uncertain or contested?

## Sources
- raw/articles/source-file.md
```

Every new synthesized page should have at least two useful outbound `[[wikilinks]]` when possible. If two links are impossible because the vault is new, create the most important link now and add a log note that back-links should be filled after more pages exist.

## SCHEMA.md bootstrap

If `SCHEMA.md` is missing or the user is creating a new vault, create it before writing topic pages. Do not rely on an external schema that does not exist. Use this minimal schema and customize the domain/tags:

```markdown
# Wiki Schema

## Domain
[Define what this vault covers and what is out of scope.]

## Folder model
- `raw/`: immutable source material. Agents read it but do not edit it after ingest.
- `entities/`: people, organizations, products, models, projects, standards, APIs.
- `concepts/`: ideas, techniques, mechanisms, topics, recurring patterns.
- `comparisons/`: side-by-side analyses and decision records.
- `queries/`: durable answers to substantial questions.

## Naming
- Use lowercase kebab-case paths, for example `concepts/llm-wiki.md`.
- Use `[[wikilinks]]` for internal links.
- Add every synthesized page to `index.md`.
- Append every durable action to `log.md`.

## Frontmatter
Required fields: `title`, `created`, `updated`, `type`, `tags`, `sources`, `confidence`, `contested`.
Allowed `type` values: `entity`, `concept`, `comparison`, `query`, `summary`.
Tags must be declared in this file before a page can use them.

## Tag taxonomy
[List 10-20 allowed tags for this domain before using them.]

## Page thresholds
- Create a page when an entity/concept appears in 2+ sources or is central to one important source.
- Do not create pages for passing mentions.
- Split pages over about 200 lines.
- Mark contradictions with `contested: true` and explain both claims with dates and sources.
```

## index.md structure

`index.md` is the map readers use before search. Keep it sectioned by page type and alphabetized within each section.

```markdown
# Wiki Index

> Content catalog for synthesized wiki pages.
> Last updated: YYYY-MM-DD | Total pages: N

## Entities
- [[entities/example-company]] — One-line reason this page exists.

## Concepts
- [[concepts/llm-wiki]] — Agent-maintained Markdown knowledge base pattern.

## Comparisons
- [[comparisons/rag-vs-llm-wiki]] — Tradeoffs between retrieval and compiled wiki context.

## Queries
- [[queries/how-to-connect-obsidian]] — Answer on sharing KB_VAULT_PATH with Obsidian.
```

When any section grows past roughly 50 entries, split it by first letter or subdomain. When the index grows past roughly 200 entries, add `_meta/topic-map.md` for thematic browsing.

## log.md structure

`log.md` is append-only. Keep entries compact and consistent:

```markdown
# Wiki Log

> Format: `## [YYYY-MM-DD] action | subject`
> Actions: ingest, create, update, query, lint, archive, hook-sync

## [YYYY-MM-DD] create | concepts/llm-wiki
- Wrote: concepts/llm-wiki.md
- Updated: index.md
- Source: raw/articles/karpathy-llm-wiki.md
```

Rotate to `log-YYYY.md` if `log.md` becomes too large, then start a fresh `log.md` with a pointer to the rotated file.

## Provenance and hash rules

`kb_write_note` appends a provenance trailer automatically after synthesized and meta note content you provide:

```markdown
<!-- kb-provenance: source_hash=<sha256-of-content-before-trailer>; operation=write_note; actor=llm-wiki -->
```

Do not hand-author that trailer in the `content` argument unless you are intentionally doing a direct-file fallback outside MCP. Hashes have different meanings:

- `source_hash` is SHA-256 of the content before the server-added trailer.
- `content_hash` is SHA-256 of the final stored file, including the provenance trailer.
- For the next update, pass `content_hash` as `if_hash`, not `source_hash`.
- When updating from direct filesystem reads, compute SHA-256 over the exact current file text, including the provenance trailer and final newline.
- Raw notes under `raw/` are the exception: `kb_write_note` does not append the provenance trailer to raw notes because the raw frontmatter `sha256` must keep matching the body-only source archive bytes.

## Raw write contract

Use the existing `kb_write_note` tool for raw notes; do not invent a separate ingest flow unless the user explicitly asks for one. Every `raw/**.md` note must include frontmatter before the body:

```yaml
---
source_url: "https://example.com/source-or-hermes-session-id"
ingested: YYYY-MM-DD
sha256: "<sha256 of body only, excluding frontmatter>"
---
```

For Hermes sources, add enough optional metadata to identify the source without copying secrets:

```yaml
---
source_url: "hermes-session:20260609_074425_ae8639a9"
ingested: 2026-06-10
sha256: "<sha256 of body only>"
type: raw-session
source_system: hermes
profile: default
sessions:
  - 20260609_074425_ae8639a9
---
```

Raw files are source archives. Do not edit a raw body after creation. If the source changes, write a new raw note or explicitly record drift. Only repair raw frontmatter when metadata is missing, and preserve body bytes exactly.

## Write policy

- `kb_write_note` writes the full note body and validates it against the schema first. Treat schema validation errors as repair instructions: fix the content and retry; do not bypass validation.
- For updates, reconstruct the full target file and pass the current full-file hash as `if_hash`.
- Keep raw sources under `raw/` immutable. Corrections and synthesis belong in wiki pages such as `entities/`, `concepts/`, `comparisons/`, or `queries/`.
- Every meaningful write should update `index.md` and append a concise entry to `log.md` unless the user explicitly requests a draft-only note.
- Use lowercase kebab-case note paths such as `concepts/llm-wiki.md` and `entities/anthropic.md`.
- Prefer `[[wikilinks]]` between wiki pages. New synthesized pages should have at least two useful outbound links when possible.
- Preserve YAML frontmatter on wiki pages: `title`, `created`, `updated`, `type`, `tags`, `sources`, `confidence`, and `contested`.
- Do not create entity/comparison/concept batches unless the user explicitly asks for content migration. Schema repair and content synthesis are different operations.

## MCP context-first workflow

When LLM Wiki MCP tools are available, start every wiki task with `kb_wiki_context` and use the returned context as the source of truth:

1. Read `parsed_schema.required_synthesized_frontmatter` before creating or updating synthesized pages.
2. Choose `type` from `parsed_schema.allowed_types`; do not invent page types.
3. Choose tags only from `parsed_schema.tag_taxonomy` / `parsed_schema.allowed_tags`.
4. If a needed tag is missing, update `SCHEMA.md` first, run/dry-run `kb_reconcile_taxonomy`, or ask the user.
5. Check `index` before creating a page; update existing pages instead of duplicating them.
6. Check `recent_log` to avoid repeating work.
7. If `health` reports schema errors, fix deterministic hygiene before creating new content.
8. When writing raw notes, compute body-only `sha256` and use `kb_write_note`; do not invent a separate raw ingest flow.
9. If `kb_write_note` returns schema errors, fix the content and retry. Do not bypass validation.

`SCHEMA.md` is not documentation; it is the write contract that MCP enforces.

## LLM Wiki page flow

1. Capture or identify the source material.
2. Decide whether it belongs in `raw/` as immutable source, a synthesized page, or both.
3. Check existing pages from `index.md` and direct search when available.
4. Create or update only the pages that meet the page thresholds above or the vault `SCHEMA.md` thresholds.
5. Update navigation (`index.md`) and audit trail (`log.md`).
6. Report the exact note paths written and the returned hashes.

## Exploration flow

Use the wiki as a graph, not just a text search index:

1. Start with `index.md` and recent `log.md` to understand the current map and recent changes.
2. Search with multiple terms: the user's wording, likely synonyms, entity names, and tag names.
3. Use `path_prefix` to narrow searches: `entities`, `concepts`, `comparisons`, `queries`, or `raw`.
4. Follow `[[wikilinks]]` from relevant pages. Read linked pages before answering if they may change the synthesis.
5. Prefer pages with higher confidence, newer dates, and multiple sources. Surface low-confidence or contested pages explicitly.
6. If the answer becomes a reusable synthesis, file it as a `queries/` or `comparisons/` page and update `index.md` and `log.md`.

Example search plan:

```text
kb_search_notes(query="llm wiki obsidian vault", limit=5)
kb_search_notes(query="KB_VAULT_PATH", limit=5)
kb_search_notes(query="context hook", limit=5, path_prefix="concepts")
```

## Concrete examples

### Complete synthesized note content

This is the `content` you pass to `kb_write_note`; the server appends the provenance trailer after the final line.

```markdown
---
title: LLM Wiki
created: 2026-06-09
updated: 2026-06-09
type: concept
tags: [knowledge-base, agent-memory]
sources: [raw/articles/karpathy-llm-wiki.md]
confidence: medium
contested: false
---

# LLM Wiki

## Summary
An LLM Wiki is an agent-maintained Markdown knowledge base where raw sources stay immutable and synthesized pages accumulate durable context for future work.

## Key facts
- It differs from one-shot RAG because synthesis is saved once and reused later.
- A useful vault separates `raw/` source material from synthesized pages such as [[concepts/agent-memory]] and [[comparisons/rag-vs-llm-wiki]].

## Relationships
- [[concepts/agent-memory]] — persistent context strategy for agents.
- [[comparisons/rag-vs-llm-wiki]] — tradeoffs between retrieval and compiled wiki context.

## Open questions
- Which updates should be automatic at task stop time versus manually reviewed?

## Sources
- raw/articles/karpathy-llm-wiki.md
```

### Matching index entry

```markdown
- [[concepts/llm-wiki]] — Agent-maintained Markdown knowledge base pattern for durable context.
```

### Matching log entry

```markdown
## [2026-06-09] create | concepts/llm-wiki
- Wrote: concepts/llm-wiki.md
- Updated: index.md
- Source: raw/articles/karpathy-llm-wiki.md
```

## Hook-driven always-on usage

Use hooks or wrappers to make LLM Wiki context part of every agent turn. The repository setup script installs reusable hook commands by default (`uv run python scripts/main.py`, or per-agent with `--agent`). Pass `--no-hooks` or set `LLM_WIKI_INSTALL_HOOKS=false` only when you want to wire hooks manually.

The generated scripts call `scripts/agent_hooks/llm_wiki_agent_hook.py` in two modes:

- **User-input hook:** search the wiki through `kb_search_notes` at prompt time and inject a compact `<llm-wiki-context>` block before the model starts working.
- **Stop hook:** after the model finishes, force one final wiki update pass that records durable discoveries, decisions, and changed context through MCP.

The hook should run every time, but it should not create noisy pages every time. If the task produced no durable knowledge, either write no content page or append only a compact `hook-sync` log entry if the operator wants a full audit trail.

### Claude Code hook shape

Claude Code supports project/user hook events such as `UserPromptSubmit` and `Stop`. Setup installs `llm-wiki-context-hook.sh` and `llm-wiki-stop-hook.sh` under `${CLAUDE_HOOKS_DIR:-~/.claude/hooks/llm-wiki}/` and merges equivalent entries into `${CLAUDE_SETTINGS_PATH:-~/.claude/settings.json}`. A project-local `.claude/settings.json` can use the same shape if you prefer project hooks:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/llm-wiki-context-hook.sh",
            "timeout": 5
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/llm-wiki-stop-hook.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

`llm-wiki-context-hook.sh` should read the incoming prompt metadata from stdin when the agent provides it, query `kb_search_notes` or a local helper for `SCHEMA.md`, `index.md`, recent `log.md`, and topic matches, then print a compact context block to stdout. Keep it short enough that it helps rather than flooding the prompt.

`llm-wiki-stop-hook.sh` should read the session/transcript metadata available to the hook, decide what durable knowledge changed, then use `kb_search_notes` plus `kb_write_note` to update pages, `index.md`, and `log.md` with optimistic concurrency. The installed Claude/Codex stop hook emits a one-time `decision=block` response so the agent performs that update pass before its final stop; it must not block again when `stop_hook_active=true`.

The two architectures for stop-time updates — **in-loop** (re-prompt the same session via `decision=block`) versus **out-of-loop** (a stop hook spawns a separate headless writer such as `claude -p` / `codex exec`) — and their trade-offs are compared in the vault concept page `[[concepts/agent-stop-hook-self-update]]`. This skill installs the in-loop variant for Claude Code and Codex; see the headless fallback note below for unattended setups.

### Codex enforcement pattern (native hooks)

Codex (2026+) shares Claude Code's hook JSON schema: the same `hooks` object, the same `UserPromptSubmit`/`Stop` event names, the same `{type, command, timeout}` shape, the same stdin payload (`transcript_path`, `stop_hook_active`, `last_assistant_message`), and the same `decision=block` + `reason` Stop semantics. So the Claude hook JSON ports directly — only the destination file differs.

Setup installs this skill under `$CODEX_HOME/skills/llm-wiki/`, configures `[mcp_servers.llm_wiki]`, writes the context/stop scripts under `${CODEX_LLM_WIKI_HOOKS_DIR:-${CODEX_HOME:-~/.codex}/hooks/llm-wiki}/`, and merges `UserPromptSubmit`/`Stop` entries into `${CODEX_HOOKS_JSON_PATH:-~/.codex/hooks.json}`. Codex also accepts an inline `[hooks]` table in `config.toml`. Equivalent `hooks.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "~/.codex/hooks/llm-wiki/llm-wiki-context-hook.sh", "timeout": 5 } ] }
    ],
    "Stop": [
      { "hooks": [ { "type": "command", "command": "~/.codex/hooks/llm-wiki/llm-wiki-stop-hook.sh", "timeout": 10 } ] }
    ]
  }
}
```

### Hermes/Hermess enforcement pattern (out-of-loop)

Hermes exposes only finalize-style session hooks (`on_session_start`/`on_session_end`/`on_session_finalize`/`subagent_stop`, plus `pre/post_tool_call`) declared in `cli-config.yaml`; it pipes a JSON payload to the hook on stdin and reads stdout JSON back. These finalize hooks do **not** support Claude-style `decision=block` re-prompting, so the in-loop pattern does not apply — use the **out-of-loop** model: a finalize hook triggers a separate update pass rather than re-running the same session.

Setup installs this skill, configures the `llm_wiki` MCP server, and writes reusable hook commands under `${HERMES_LLM_WIKI_HOOKS_DIR:-${HERMES_HOME:-~/.hermes}/hooks/llm-wiki}/`. The minimum reliable setup is to start sessions with the skill loaded or call `/skill llm-wiki`; for automation, wire the generated context/stop scripts into a Hermes plugin, wrapper command, or finalize hook. Non-interactive runs (gateway, cron) must allow hooks with `--accept-hooks`, `HERMES_ACCEPT_HOOKS=1`, or the `hooks_auto_accept` config key.

### Headless fallback (any client, unattended)

When you must guarantee the update runs unattended, a stop/finalize hook can spawn a separate headless writer (`claude -p` or `codex exec`) instead of re-prompting in-loop. Three things are mandatory, or it silently no-ops: (1) the headless agent has no memory of the turn, so feed it the hook payload's `transcript_path`; (2) `claude -p --bare` skips the project MCP config and OAuth, so pass `--mcp-config` for `llm-wiki` plus a credential (`ANTHROPIC_API_KEY`/`apiKeyHelper`) or it will not have `kb_write_note`; (3) fully detach the process (`setsid`/`nohup`), since background tasks started during a `-p` run are killed shortly after it returns. See `[[concepts/agent-stop-hook-self-update]]` for the full comparison.

## Safety rules

- Do not invent existing vault contents. If you cannot read a page, say so and ask for it or create a clearly named draft note instead of overwriting.
- Do not hard-delete notes through this workflow.
- Do not overwrite existing notes in MCP-only mode from snippets alone.
- Treat the MCP endpoint as local by default: `http://127.0.0.1:9999/mcp`.
- If the server later enables bearer auth, add the authorization header in the agent MCP config before using write tools.
- Do not write raw, private transcripts wholesale into the wiki. Summarize durable decisions, facts, and relationships.

## Agent-specific MCP names

### Hermes/Hermess

Hermes prefixes native MCP tools as `mcp_<server>_<tool>`. With the default `llm_wiki` server name, look for:

- `mcp_llm_wiki_kb_write_note`
- `mcp_llm_wiki_kb_search_notes`
- `mcp_llm_wiki_kb_wiki_context`
- `mcp_llm_wiki_kb_validate_vault`
- `mcp_llm_wiki_kb_reconcile_taxonomy`

If these tools do not appear, run `hermes mcp list`, `hermes mcp test llm_wiki`, then restart the Hermes session or gateway. In an existing session, use `/reload-mcp` if available.

### Claude Code

Claude Code usually displays MCP tools with a server namespace such as `mcp__llm-wiki__kb_write_note`. With the default setup, look for the `llm-wiki` MCP server in `/mcp` or `claude mcp list`.

If project-scoped `.mcp.json` is used, Claude may ask you to approve the server the first time it sees the project. Approve only after confirming the endpoint is the expected local URL.

### Codex

Codex reads installed skills from `$CODEX_HOME/skills` (default `$HOME/.codex/skills`). The default MCP server id is `llm_wiki`; check Codex MCP startup/status output if the tools are not visible.

Install this skill under `$CODEX_HOME/skills/llm-wiki/`, or set `CODEX_SKILLS_DIR` only when your Codex installation explicitly loads another skill directory.
