from pathlib import Path

from vault.infrastructure.repository.vault_note_repository import VaultNoteRepository
from vault.service.vault_schema_service import VaultSchemaService

SCHEMA = """# Wiki Schema

## Frontmatter
Required fields: `title`, `created`, `updated`, `type`, `tags`, `sources`,
`confidence`, `contested`.
Allowed `type` values: `entity`, `concept`, `comparison`, `query`, `summary`.

## Tag taxonomy
- Knowledge: knowledge-base, agent-memory, mcp
- Engineering: verification
"""


def _write_schema(vault_root: Path, schema: str = SCHEMA) -> None:
    vault_root.mkdir(parents=True, exist_ok=True)
    (vault_root / "SCHEMA.md").write_text(schema, encoding="utf-8")


def test_validate_write_rejects_invalid_synthesized_frontmatter(tmp_path: Path) -> None:
    # Given: tag taxonomy가 있는 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: synthesized page frontmatter가 없거나 taxonomy 밖 tag를 쓰면 검증한다.
    missing_frontmatter = schema_service.validate_write(
        "concepts/agent-memory.md",
        "# Agent Memory\n",
    )
    unknown_tag = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: Agent Memory
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: [unknown-tag]
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Memory
""",
    )

    # Then: write boundary에서 바로 고칠 수 있는 issue code가 반환된다.
    assert [issue.code for issue in missing_frontmatter.issues] == ["missing_frontmatter"]
    assert [issue.code for issue in unknown_tag.issues] == ["unknown_tag"]
    assert unknown_tag.issues[0].value == "unknown-tag"


def test_validate_write_requires_raw_frontmatter_and_body_sha256(tmp_path: Path) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: raw note에 source metadata나 body-only sha256이 빠져 있다.
    missing_raw_metadata = schema_service.validate_write(
        "raw/hermes/session.md",
        "# Raw Session\n",
    )
    wrong_hash = schema_service.validate_write(
        "raw/hermes/session.md",
        """---
source_url: hermes-session:abc
ingested: 2026-06-10
sha256: bad
---

# Raw Session
""",
    )

    # Then: raw metadata와 sha256 mismatch를 hard error로 보고한다.
    assert [issue.code for issue in missing_raw_metadata.issues] == ["missing_frontmatter"]
    assert [issue.code for issue in wrong_hash.issues] == ["raw_sha256_mismatch"]


def test_validate_vault_reports_schema_hygiene_summary(tmp_path: Path) -> None:
    # Given: valid schema, invalid synthesized page, invalid raw note가 함께 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    (vault_root / "concepts").mkdir()
    (vault_root / "concepts" / "bad.md").write_text(
        """---
title: Bad
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: [not-in-schema]
sources: []
confidence: high
contested: false
---

# Bad
""",
        encoding="utf-8",
    )
    (vault_root / "raw" / "hermes").mkdir(parents=True)
    (vault_root / "raw" / "hermes" / "bad.md").write_text(
        """---
source_url: hermes-session:bad
ingested: 2026-06-10
sha256: bad
---

raw body
""",
        encoding="utf-8",
    )

    # When: vault 전체 schema hygiene를 검증한다.
    result = VaultSchemaService(
        note_repository=VaultNoteRepository(root=vault_root)
    ).validate_vault()

    # Then: content migration 없이 deterministic schema issue만 집계된다.
    assert result.summary.unknown_tags == 1
    assert result.summary.empty_sources == 1
    assert result.summary.raw_sha256_mismatch == 1
    assert {issue.path for issue in result.issues} == {
        "concepts/bad.md",
        "raw/hermes/bad.md",
    }


def test_wiki_context_returns_schema_index_recent_log_and_health(tmp_path: Path) -> None:
    # Given: SCHEMA, index, log가 있는 vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    (vault_root / "index.md").write_text("# Wiki Index\n\n## Concepts\n", encoding="utf-8")
    (vault_root / "log.md").write_text(
        "# Wiki Log\n\n## [2026-06-08] create | old\n## [2026-06-10] lint | recent\n",
        encoding="utf-8",
    )

    # When: MCP context-first workflow용 context를 만든다.
    context = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root)).wiki_context(
        recent_log_lines=1
    )

    # Then: LLM은 별도 파일 읽기 없이 schema/index/log/health를 확인할 수 있다.
    assert "## Tag taxonomy" in context.schema_text
    assert "# Wiki Index" in context.index
    assert context.recent_log == "## [2026-06-10] lint | recent"
    assert context.parsed_schema.allowed_tags == [
        "agent-memory",
        "knowledge-base",
        "mcp",
        "verification",
    ]
    assert context.health.schema_parse_ok is True
    assert context.health.unknown_tag_count == 0


def test_reconcile_taxonomy_supports_dry_run_then_schema_apply(tmp_path: Path) -> None:
    # Given: page가 SCHEMA.md에 없는 tag를 사용 중이다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    (vault_root / "concepts").mkdir()
    page_path = vault_root / "concepts" / "agent-harness.md"
    page_path.write_text(
        """---
title: Agent Harness
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: [agent-harness]
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Harness

Body that must not change.
""",
        encoding="utf-8",
    )
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))
    before_page = page_path.read_text(encoding="utf-8")

    # When: dry-run 후 add decision을 apply한다.
    dry_run = schema_service.reconcile_taxonomy(apply=False)
    applied = schema_service.reconcile_taxonomy(
        apply=True,
        decisions={"add": ["agent-harness"]},
    )

    # Then: dry-run은 변경하지 않고, apply는 SCHEMA.md만 보정해 unknown tag를 제거한다.
    assert dry_run.dry_run is True
    assert dry_run.unknown_tags == ["agent-harness"]
    assert page_path.read_text(encoding="utf-8") == before_page
    assert applied.changed_files == ["SCHEMA.md"]
    assert "agent-harness" in (vault_root / "SCHEMA.md").read_text(encoding="utf-8")
    assert schema_service.validate_vault().summary.unknown_tags == 0
