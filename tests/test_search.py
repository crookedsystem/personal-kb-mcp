from pathlib import Path

import pytest

from personal_kb_mcp.vault.paths import VaultPathError
from personal_kb_mcp.vault.search import search_notes


def test_search_notes는_llm_wiki_구조를_반영해_synthesized_page를_우선한다(
    tmp_path: Path,
) -> None:
    # Given: index, synthesized concept page, raw source가 있는 Markdown LLM Wiki vault가 있다.
    vault_root = tmp_path / "vault"
    (vault_root / "concepts").mkdir(parents=True)
    (vault_root / "raw" / "articles").mkdir(parents=True)
    (vault_root / "index.md").write_text(
        "# Wiki Index\n\n- [[agent-memory]] — agent memory overview\n",
        encoding="utf-8",
    )
    (vault_root / "concepts" / "agent-memory.md").write_text(
        "---\n"
        "title: Agent Memory\n"
        "type: concept\n"
        "tags: [agent, memory, llm-wiki]\n"
        "sources: [raw/articles/agent-memory.md]\n"
        "---\n\n"
        "# Agent Memory\n\n"
        "LLM Wiki pages compound agent memory through linked Markdown notes.\n"
        "Related: [[retrieval]]\n",
        encoding="utf-8",
    )
    (vault_root / "raw" / "articles" / "agent-memory.md").write_text(
        "# Source\n\nagent memory raw transcript\n",
        encoding="utf-8",
    )

    # When: agent memory를 검색한다.
    results = search_notes(vault_root, "agent memory", limit=5)

    # Then: raw보다 synthesized concept page가 먼저 나오고 update용 hash/snippet도 제공된다.
    assert [result.path for result in results][:3] == [
        "concepts/agent-memory.md",
        "index.md",
        "raw/articles/agent-memory.md",
    ]
    concept = results[0]
    assert concept.title == "Agent Memory"
    assert concept.page_type == "concept"
    assert concept.tags == ["agent", "memory", "llm-wiki"]
    assert len(concept.content_hash) == 64
    assert concept.matches[0].line == 2
    assert "title: Agent Memory" in concept.matches[0].snippet


def test_search_notes는_path_prefix와_거부된_디렉터리를_적용한다(tmp_path: Path) -> None:
    # Given: 검색 가능한 concepts note와 거부된 .obsidian note가 있다.
    vault_root = tmp_path / "vault"
    (vault_root / "concepts").mkdir(parents=True)
    (vault_root / ".obsidian").mkdir(parents=True)
    (vault_root / "concepts" / "retrieval.md").write_text(
        "# Retrieval\n\nSearch compiled wiki pages.\n",
        encoding="utf-8",
    )
    (vault_root / ".obsidian" / "hidden.md").write_text(
        "# Retrieval private config\n",
        encoding="utf-8",
    )

    # When: concepts prefix로 검색한다.
    results = search_notes(vault_root, "retrieval", path_prefix="concepts")

    # Then: prefix 안의 markdown만 반환되고 denied directory는 노출되지 않는다.
    assert [result.path for result in results] == ["concepts/retrieval.md"]


@pytest.mark.parametrize("limit", [0, 51])
def test_search_notes는_limit_범위를_검증한다(tmp_path: Path, limit: int) -> None:
    # Given: 빈 vault가 있다.
    vault_root = tmp_path / "vault"

    # When / Then: 범위를 벗어난 limit은 명확한 오류를 낸다.
    with pytest.raises(ValueError, match="limit must be between"):
        search_notes(vault_root, "query", limit=limit)


def test_search_notes는_vault_밖_prefix를_거부한다(tmp_path: Path) -> None:
    # Given: vault root가 있다.
    vault_root = tmp_path / "vault"

    # When / Then: path_prefix는 vault 밖으로 escape할 수 없다.
    with pytest.raises(VaultPathError, match="escapes outside vault"):
        search_notes(vault_root, "query", path_prefix="../outside")
