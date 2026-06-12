import asyncio
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from vault.component.write_queue import VaultWriteQueue
from vault.entity.vault_note import compute_sha256
from vault.entity.vault_path import VaultPaths
from vault.error.write_error import WriteConflictError
from vault.service.command.write_note_command import WriteNoteCommand
from vault.service.vault_write_service import VaultWriteService


def _write_command(
    *,
    note_path: str = "concepts/today.md",
    title: str = "Today",
    body: str = "## Summary\nBody text",
    if_hash: str | None = None,
) -> WriteNoteCommand:
    return WriteNoteCommand(
        note_path=note_path,
        title=title,
        type="concept",
        tags=("agent-memory",),
        sources=("raw/articles/source.md",),
        body=body,
        created=date(2026, 6, 12),
        updated=date(2026, 6, 12),
        confidence="medium",
        contested=False,
        if_hash=if_hash,
    )


def test_note_작성은_hash와_provenance를_함께_반환한다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: provenance actor가 지정된 vault writer가 있다.
        writer = VaultWriteService(
            paths=VaultPaths(root=tmp_path / "vault"), queue=VaultWriteQueue(), actor="tester"
        )

        # When: structured field 기반 command로 새 markdown note를 작성한다.
        result = await writer.write_note(_write_command())
        written_content = result.path.read_text(encoding="utf-8")
        source_content = written_content.split("<!-- kb-provenance:", maxsplit=1)[0]

        # Then: 렌더링된 note와 provenance hash가 함께 남는다.
        assert source_content.startswith("---\ntitle: Today\n")
        assert "\n# Today\n\n## Summary\nBody text\n" in source_content
        assert result.source_hash == compute_sha256(source_content)
        assert result.content_hash == compute_sha256(written_content)
        assert result.commit_hash is None
        assert f"source_hash={result.source_hash}" in written_content
        assert "actor=tester" in written_content

    asyncio.run(exercise_writer())


def test_existing_note_수정은_현재_content_hash가_맞을_때만_허용된다(tmp_path: Path) -> None:
    async def exercise_writer() -> None:
        # Given: 이미 작성된 note와 그 note의 현재 content hash가 있다.
        writer = VaultWriteService(
            paths=VaultPaths(root=tmp_path / "vault"), queue=VaultWriteQueue(), actor="tester"
        )
        first_result = await writer.write_note(_write_command(body="## Summary\nInitial body"))

        # When / Then: if_hash가 없거나 오래된 값이면 수정이 거부된다.
        with pytest.raises(WriteConflictError, match="if_hash is required"):
            await writer.write_note(_write_command(body="## Summary\nUpdate without hash"))

        with pytest.raises(WriteConflictError, match="stale if_hash"):
            await writer.write_note(_write_command(body="## Summary\nStale update", if_hash="bad"))

        # When: 현재 content hash로 note를 수정한다.
        updated_result = await writer.write_note(
            _write_command(body="## Summary\nFresh update", if_hash=first_result.content_hash)
        )

        # Then: stale overwrite 없이 새 본문과 hash가 기록된다.
        assert updated_result.source_hash
        assert "Fresh update" in updated_result.path.read_text(encoding="utf-8")

    asyncio.run(exercise_writer())


def test_write_command는_path와_type_불일치와_full_markdown_body를_거부한다() -> None:
    # When / Then: 폴더와 type이 맞지 않거나 body가 full markdown이면 command 검증에서 거부된다.
    with pytest.raises(ValidationError, match="type 'entity' is not allowed"):
        WriteNoteCommand(
            note_path="concepts/bad.md",
            title="Bad",
            type="entity",
            tags=("agent-memory",),
            sources=("raw/articles/source.md",),
            body="## Summary\nBody",
            created=date(2026, 6, 12),
            updated=date(2026, 6, 12),
        )

    with pytest.raises(ValidationError, match="YAML frontmatter"):
        _write_command(body="---\ntitle: Bad\n---\n# Bad")
