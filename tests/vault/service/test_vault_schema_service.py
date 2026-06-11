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


def test_validate_write_accepts_crlf_synthesized_frontmatter(tmp_path: Path) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: Windows/Obsidian 스타일 CRLF frontmatter로 synthesized page를 검증한다.
    result = schema_service.validate_write(
        "concepts/agent-memory.md",
        "---\r\n"
        "title: Agent Memory\r\n"
        "created: 2026-06-10\r\n"
        "updated: 2026-06-10\r\n"
        "type: concept\r\n"
        "tags: [agent-memory]\r\n"
        "sources: [raw/hermes/source.md]\r\n"
        "confidence: medium\r\n"
        "contested: false\r\n"
        "---\r\n"
        "# Agent Memory\r\n",
    )

    # Then: 유효한 YAML frontmatter로 인식되어 missing_frontmatter가 발생하지 않는다.
    assert result.issues == []


def test_validate_write_rejects_blank_synthesized_sources(tmp_path: Path) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: sources가 list 형식이지만 실제 source 값은 비어 있다.
    result = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: Agent Memory
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: [agent-memory]
sources: ["   "]
confidence: medium
contested: false
---

# Agent Memory
""",
    )

    # Then: 빈 list와 동일하게 사용할 수 없는 source로 검증 실패한다.
    assert [issue.code for issue in result.issues] == ["empty_sources"]


def test_validate_write_rejects_synthesized_page_when_schema_is_missing(
    tmp_path: Path,
) -> None:
    # Given: SCHEMA.md가 아직 없는 vault가 있다.
    vault_root = tmp_path / "vault"
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: required frontmatter를 갖춘 synthesized page를 먼저 쓰려고 한다.
    result = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: Agent Memory
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: []
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Memory
""",
    )

    # Then: 기본 type fallback으로 통과시키지 않고 schema 생성부터 요구한다.
    assert [issue.code for issue in result.issues] == ["schema_missing"]


def test_validate_write_rejects_non_string_synthesized_type(tmp_path: Path) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: synthesized page type이 문자열이 아니다.
    result = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: Agent Memory
created: 2026-06-10
updated: 2026-06-10
type: [concept]
tags: []
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Memory
""",
    )

    # Then: required field 존재만으로 통과시키지 않고 타입 오류를 보고한다.
    assert [(issue.code, issue.field) for issue in result.issues] == [
        ("invalid_field_type", "type")
    ]


def test_validate_write_treats_scalar_synthesized_title_as_string(
    tmp_path: Path,
) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: title이 문자열은 아니지만 YAML scalar다.
    result = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: 123
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: []
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Memory
""",
    )

    # Then: scalar title은 문자열 title로 취급한다.
    assert result.issues == []


def test_validate_write_rejects_non_scalar_or_blank_synthesized_title(
    tmp_path: Path,
) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: title이 list이거나 빈 문자열이다.
    non_scalar = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: [Agent Memory]
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: []
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Memory
""",
    )
    blank = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: "   "
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: []
sources: [raw/hermes/source.md]
confidence: medium
contested: false
---

# Agent Memory
""",
    )

    # Then: wiki map에서 사용할 수 없는 title은 거부한다.
    assert [(issue.code, issue.field) for issue in non_scalar.issues] == [
        ("invalid_field_type", "title")
    ]
    assert [(issue.code, issue.field) for issue in blank.issues] == [("invalid_title", "title")]


def test_validate_write_rejects_non_string_synthesized_confidence(
    tmp_path: Path,
) -> None:
    # Given: schema가 준비된 LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    _write_schema(vault_root)
    schema_service = VaultSchemaService(note_repository=VaultNoteRepository(root=vault_root))

    # When: synthesized page confidence가 문자열이 아니다.
    result = schema_service.validate_write(
        "concepts/agent-memory.md",
        """---
title: Agent Memory
created: 2026-06-10
updated: 2026-06-10
type: concept
tags: []
sources: [raw/hermes/source.md]
confidence: [medium]
contested: false
---

# Agent Memory
""",
    )

    # Then: required field 존재만으로 통과시키지 않고 타입 오류를 보고한다.
    assert [(issue.code, issue.field) for issue in result.issues] == [
        ("invalid_field_type", "confidence")
    ]
